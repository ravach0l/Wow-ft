package main

import (
	"bytes"
	"compress/gzip"
	"errors"
	"fmt"
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

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestFindSavedVariables(t *testing.T) {
	wow := t.TempDir()
	a := filepath.Join(wow, "_forever_", "WTF", "Account", "ACC1", "SavedVariables", "WowFT.lua")
	b := filepath.Join(wow, "WTF", "Account", "ACC2", "SavedVariables", "WowFT.lua")
	other := filepath.Join(wow, "_forever_", "WTF", "Account", "ACC1", "SavedVariables", "Other.lua")
	for _, p := range []string{a, b, other} {
		writeFile(t, p, "x")
	}
	got := FindSavedVariables(wow)
	if len(got) != 2 || !strings.Contains(strings.Join(got, "|"), "ACC1") || !strings.Contains(strings.Join(got, "|"), "ACC2") {
		t.Fatalf("unerwartet: %v", got)
	}
	if FindSavedVariables("") != nil {
		t.Fatal("leerer Ordner sollte nil liefern")
	}
}

func TestConfigRoundtripAndValidation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "c", "config.json")
	c := &Config{Server: "https://example.org/", Token: "wft_abc", WowDir: "/wow"}
	if err := SaveConfig(path, c); err != nil {
		t.Fatal(err)
	}
	got, err := LoadConfig(path)
	if err != nil {
		t.Fatal(err)
	}
	if got.Server != "https://example.org" || got.PollSeconds != 5 {
		t.Fatalf("normalize: %+v", got)
	}
	if st, _ := os.Stat(path); st.Mode().Perm()&0o077 != 0 {
		t.Fatalf("config ist für andere lesbar: %v", st.Mode())
	}
	bad := []*Config{
		{Server: "https://x", Token: "falsch", WowDir: "/w"},
		{Server: "http://x", Token: "wft_a", WowDir: "/w"},
		{Server: "https://x", Token: "wft_a"},
		{Server: "https://x", WowDir: ""},
	}
	// Ohne Token ist gültig: Er kommt dann aus den Einstellungen im Spiel.
	noToken := &Config{Server: "https://x", WowDir: "/w"}
	noToken.normalize()
	if err := noToken.Validate(); err != nil {
		t.Errorf("Konfiguration ohne Token sollte gültig sein: %v", err)
	}
	for _, b := range bad {
		b.normalize()
		if b.Validate() == nil {
			t.Errorf("sollte ungültig sein: %+v", b)
		}
	}
}

func TestClientUpload(t *testing.T) {
	var gotBody, gotAuth, gotEnc string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotEnc = r.Header.Get("Content-Encoding")
		zr, err := gzip.NewReader(r.Body)
		if err != nil {
			t.Error(err)
			return
		}
		b, _ := io.ReadAll(zr)
		gotBody = string(b)
		w.Write([]byte(`{"characters":1,"snapshots":2,"events":0,"skipped":[]}`))
	}))
	defer srv.Close()
	res, err := NewClient(srv.URL, "wft_x").Upload([]byte("WowFTDB = {}"))
	if err != nil {
		t.Fatal(err)
	}
	if res.Snapshots != 2 || gotBody != "WowFTDB = {}" || gotAuth != "Bearer wft_x" || gotEnc != "gzip" {
		t.Fatalf("res=%+v body=%q auth=%q enc=%q", res, gotBody, gotAuth, gotEnc)
	}
}

func TestClientErrors(t *testing.T) {
	for status, permanent := range map[int]bool{401: true, 422: true, 429: false, 502: false} {
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(status)
			w.Write([]byte(`{"detail":"nein"}`))
		}))
		_, err := NewClient(srv.URL, "wft_x").Upload([]byte("x"))
		srv.Close()
		var ue *UploadError
		if !errors.As(err, &ue) || ue.Permanent != permanent || ue.Message != "nein" {
			t.Errorf("status %d: %v", status, err)
		}
	}
}

type fakeUploader struct {
	calls    []string
	errs     []error
	result   *Result
	photos   []string
	photoErr error
}

func (f *fakeUploader) UploadPhoto(characterID int, t int64, data []byte) error {
	f.photos = append(f.photos, fmt.Sprintf("%d:%d:%d", characterID, t, len(data)))
	return f.photoErr
}

func (f *fakeUploader) Upload(content []byte) (*Result, error) {
	f.calls = append(f.calls, string(content))
	if len(f.errs) > 0 {
		err := f.errs[0]
		f.errs = f.errs[1:]
		if err != nil {
			return nil, err
		}
	}
	if f.result != nil {
		return f.result, nil
	}
	return &Result{Characters: 1}, nil
}

func newTestWatcher(t *testing.T, up Uploader) (*Watcher, string, string) {
	wow := t.TempDir()
	sv := filepath.Join(wow, "_forever_", "WTF", "Account", "A", "SavedVariables", "WowFT.lua")
	writeFile(t, sv, "v1")
	state := filepath.Join(t.TempDir(), "state.json")
	cfg := &Config{Server: "https://x", Token: "wft_x", WowDir: wow}
	cfg.normalize()
	return NewWatcher(cfg, up, state, log.New(&bytes.Buffer{}, "", 0)), sv, state
}

func TestWatcherUploadsOnceAndAfterChange(t *testing.T) {
	up := &fakeUploader{}
	w, sv, state := newTestWatcher(t, up)
	now := time.Now()

	if n := w.Poll(now); n != 1 {
		t.Fatalf("erster Durchlauf: %d Uploads", n)
	}
	if n := w.Poll(now.Add(5 * time.Second)); n != 0 {
		t.Fatal("unveränderte Datei erneut hochgeladen")
	}

	writeFile(t, sv, "v2 länger")
	future := time.Now().Add(time.Hour)
	_ = os.Chtimes(sv, future, future)
	if n := w.Poll(now.Add(10 * time.Second)); n != 0 {
		t.Fatal("Upload vor Ablauf der Wartezeit")
	}
	if n := w.Poll(now.Add(14 * time.Second)); n != 1 {
		t.Fatal("geänderte Datei nicht hochgeladen")
	}
	if strings.Join(up.calls, ",") != "v1,v2 länger" {
		t.Fatalf("calls: %v", up.calls)
	}

	// Neuer Watcher mit gespeichertem Status lädt nicht erneut hoch.
	w2 := NewWatcher(w.cfg, up, state, w.log)
	if n := w2.Poll(now.Add(time.Minute)); n != 0 {
		t.Fatal("nach Neustart doppelt hochgeladen")
	}
}

func TestWatcherBackoffAndPermanentErrors(t *testing.T) {
	up := &fakeUploader{errs: []error{&UploadError{Message: "netz"}, nil}}
	w, sv, _ := newTestWatcher(t, up)
	now := time.Now()
	if w.Poll(now) != 0 {
		t.Fatal("Fehler als Erfolg gezählt")
	}
	if w.Poll(now.Add(2*time.Second)) != 0 || len(up.calls) != 1 {
		t.Fatal("Backoff nicht eingehalten")
	}
	if w.Poll(now.Add(6*time.Second)) != 1 {
		t.Fatal("kein neuer Versuch nach Backoff")
	}

	up.errs = []error{&UploadError{Status: 422, Message: "kaputt", Permanent: true}}
	writeFile(t, sv, "kaputt")
	future := time.Now().Add(2 * time.Hour)
	_ = os.Chtimes(sv, future, future)
	w.Poll(now.Add(20 * time.Second))
	w.Poll(now.Add(30 * time.Second))
	calls := len(up.calls)
	w.Poll(now.Add(10 * time.Minute))
	if len(up.calls) != calls {
		t.Fatal("dauerhaft abgelehnte Datei erneut gesendet")
	}
}

func TestRunSetup(t *testing.T) {
	var guesses []string
	searchWowDirs = func() []string { return guesses }
	paired, pairErr := 0, error(nil)
	pairDevice = func(server string, out io.Writer) (string, error) {
		paired++
		if pairErr != nil {
			return "", pairErr
		}
		return "wft_gekoppelt", nil
	}
	redeemCode = func(server, code string) (string, error) { return "wft_auscode", nil }
	t.Cleanup(func() {
		searchWowDirs = SearchWowDirsDefault
		pairDevice = func(server string, out io.Writer) (string, error) { return PairDevice(NewClient(server, ""), out) }
		redeemCode = func(server, code string) (string, error) {
			tok, _, err := NewClient(server, "").RedeemGameCode(code, DeviceName())
			return tok, err
		}
	})
	wow := t.TempDir()
	var out bytes.Buffer

	// Ein einziger gefundener Ordner: keine Frage. Koppeln kommt zuletzt, danach keine Eingabe mehr.
	guesses = []string{wow}
	c, err := RunSetup(strings.NewReader(""), &out, nil)
	if err != nil {
		t.Fatal(err)
	}
	if c.Server != DefaultServer || c.Token != "wft_gekoppelt" || c.WowDir != wow || paired != 1 {
		t.Fatalf("%+v paired=%d", c, paired)
	}
	if strings.Contains(out.String(), "Server [") {
		t.Fatal("nach dem Server wird nicht mehr gefragt")
	}
	// Mehrere Ordner: Auswahl per Nummer.
	other := t.TempDir()
	guesses = []string{other, wow}
	c, err = RunSetup(strings.NewReader("2\n"), &out, nil)
	if err != nil || c.WowDir != wow {
		t.Fatalf("%+v %v", c, err)
	}
	// Nichts gefunden: Pfad eingeben.
	guesses = nil
	c, err = RunSetup(strings.NewReader(wow+"\n"), &out, nil)
	if err != nil || c.WowDir != wow {
		t.Fatalf("%+v %v", c, err)
	}
	// Schon eingerichtet: Enter behält Ordner und Token, keine neue Kopplung.
	n := paired
	c2, err := RunSetup(strings.NewReader("\n\n"), &out, c)
	if err != nil || c2.Token != "wft_gekoppelt" || c2.WowDir != wow || paired != n {
		t.Fatalf("%+v %v paired=%d", c2, err, paired)
	}
	// Schon eingerichtet, aber neu koppeln.
	if _, err := RunSetup(strings.NewReader("\nj\n"), &out, c); err != nil || paired != n+1 {
		t.Fatalf("neu koppeln: %v paired=%d", err, paired)
	}
	// Koppeln klappt nicht: Token von Hand, Code fürs Spiel oder später.
	pairErr = errors.New("Server nicht erreichbar")
	guesses = []string{wow}
	c3, err := RunSetup(strings.NewReader("wft_hand\n"), &out, nil)
	if err != nil || c3.Token != "wft_hand" {
		t.Fatalf("%+v %v", c3, err)
	}
	c4, err := RunSetup(strings.NewReader("wft-abcd-efgh\n"), &out, nil)
	if err != nil || c4.Token != "wft_auscode" {
		t.Fatalf("%+v %v", c4, err)
	}
	c5, err := RunSetup(strings.NewReader("\n"), &out, nil)
	if err != nil || c5.Token != "" {
		t.Fatalf("später koppeln: %+v %v", c5, err)
	}
}
