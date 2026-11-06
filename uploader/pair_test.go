package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// fakePairServer spielt die Kopplungs-Endpunkte des Servers nach.
func fakePairServer(t *testing.T, pendingPolls int) (*httptest.Server, *[]string) {
	t.Helper()
	var calls []string
	polls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		calls = append(calls, r.URL.Path+" "+string(body)+" auth="+r.Header.Get("Authorization"))
		switch r.URL.Path {
		case "/api/pair/start":
			w.Write([]byte(`{"userCode":"K7Q-4MX","deviceCode":"geheim","verifyUrl":"https://x/koppeln?code=K7Q-4MX","expiresIn":60,"interval":1}`))
		case "/api/pair/poll":
			polls++
			if polls <= pendingPolls {
				w.Write([]byte(`{"status":"pending"}`))
				return
			}
			w.Write([]byte(`{"status":"ok","token":"wft_neu","userName":"kathi"}`))
		case "/api/pair/redeem":
			var in map[string]string
			_ = json.Unmarshal(body, &in)
			if in["code"] != "WFTABCDEFGH" {
				w.WriteHeader(http.StatusNotFound)
				w.Write([]byte(`{"detail":"Code unbekannt"}`))
				return
			}
			w.Write([]byte(`{"status":"ok","token":"wft_auscode","userName":"kathi"}`))
		case "/api/ingest":
			w.Write([]byte(`{"characters":1,"snapshots":1,"events":0,"skipped":[],"photoRequests":[]}`))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(srv.Close)
	return srv, &calls
}

func TestIsGameCode(t *testing.T) {
	for code, want := range map[string]bool{
		"WFT-ABCD-EFGH": true, "wft abcd efgh": true, "WFTABCDEFGH": true,
		"WFT-ABCD-EFG": false, "WFT-ABCD-EFG0": false, "wft_abcdefgh": false, "": false,
	} {
		if IsGameCode(code) != want {
			t.Errorf("%q: want %v", code, want)
		}
	}
}

func TestPairDevice(t *testing.T) {
	srv, calls := fakePairServer(t, 2)
	var opened string
	pairSleep = func(time.Duration) {}
	openBrowser = func(u string) error { opened = u; return nil }
	t.Cleanup(func() { pairSleep = time.Sleep; openBrowser = openBrowserDefault })

	var out bytes.Buffer
	tok, err := PairDevice(NewClient(srv.URL, ""), &out)
	if err != nil || tok != "wft_neu" {
		t.Fatalf("tok=%q err=%v", tok, err)
	}
	if opened != "https://x/koppeln?code=K7Q-4MX" || !strings.Contains(out.String(), "K7Q-4MX") {
		t.Fatalf("opened=%q out=%s", opened, out.String())
	}
	if len(*calls) != 4 || !strings.Contains((*calls)[1], `"deviceCode":"geheim"`) {
		t.Fatalf("calls: %v", *calls)
	}
	// Ohne Token wird kein (leerer) Authorization-Header gesendet.
	if !strings.HasSuffix((*calls)[0], "auth=") {
		t.Fatalf("Header gesendet: %s", (*calls)[0])
	}
}

func TestWatcherRedeemsGameCode(t *testing.T) {
	srv, calls := fakePairServer(t, 0)
	wow := t.TempDir()
	sv := filepath.Join(wow, "_forever_", "WTF", "Account", "A", "SavedVariables", "WowFT.lua")
	content := "WowFTDB = {\n[\"upload\"] = {\n[\"token\"] = \"wft-abcd-efgh\",\n},\n}\n"
	writeFile(t, sv, content)
	cfgPath := filepath.Join(t.TempDir(), "config.json")
	cfg := &Config{Server: srv.URL, WowDir: wow}
	cfg.normalize()
	w := NewWatcher(cfg, NewClient(srv.URL, ""), filepath.Join(t.TempDir(), "state.json"), log.New(io.Discard, "", 0))
	w.CfgPath = cfgPath

	if w.Poll(time.Now()) != 1 {
		t.Fatalf("kein Upload: %v", *calls)
	}
	if cfg.Token != "wft_auscode" {
		t.Fatalf("Token nicht übernommen: %q", cfg.Token)
	}
	saved, err := LoadConfig(cfgPath)
	if err != nil || saved.Token != "wft_auscode" {
		t.Fatalf("nicht gespeichert: %+v %v", saved, err)
	}
	last := (*calls)[len(*calls)-1]
	if !strings.HasPrefix(last, "/api/ingest") || !strings.Contains(last, "auth=Bearer wft_auscode") {
		t.Fatalf("Upload ohne neuen Token: %s", last)
	}
	// Der Code bleibt in der Datei stehen; er wird nicht noch einmal eingelöst.
	writeFile(t, sv, content+"-- geändert\n")
	future := time.Now().Add(time.Hour)
	_ = os.Chtimes(sv, future, future)
	w.Poll(time.Now().Add(time.Minute))
	w.Poll(time.Now().Add(2 * time.Minute))
	redeems := 0
	for _, c := range *calls {
		if strings.HasPrefix(c, "/api/pair/redeem") {
			redeems++
		}
	}
	if redeems != 1 {
		t.Fatalf("Code %d-mal eingelöst", redeems)
	}
}

func TestWatcherInvalidGameCode(t *testing.T) {
	srv, calls := fakePairServer(t, 0)
	wow := t.TempDir()
	sv := filepath.Join(wow, "_forever_", "WTF", "Account", "A", "SavedVariables", "WowFT.lua")
	writeFile(t, sv, "WowFTDB = {\n[\"upload\"] = {\n[\"token\"] = \"WFT-ZZZZ-ZZZZ\",\n},\n}\n")
	cfg := &Config{Server: srv.URL, WowDir: wow}
	cfg.normalize()
	var logs bytes.Buffer
	w := NewWatcher(cfg, NewClient(srv.URL, ""), filepath.Join(t.TempDir(), "state.json"), log.New(&logs, "", 0))
	if w.Poll(time.Now()) != 0 || cfg.Token != "" {
		t.Fatal("ungültiger Code darf nicht koppeln")
	}
	if !strings.Contains(logs.String(), "neuen erzeugen") {
		t.Fatalf("Log: %s", logs.String())
	}
	if len(*calls) != 1 {
		t.Fatalf("calls: %v", *calls)
	}
}
