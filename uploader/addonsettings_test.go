package main

import (
	"os"
	"strings"
	"testing"
	"time"
)

const savedWithToken = `WowFTDB = {
["schema"] = 1,
["upload"] = {
["server"] = "https://wow.example.org/",
["token"] = "wft_geheim123",
},
["characters"] = {
["Player-1-ABC"] = {
["name"] = "Testa",
},
},
}
`

func TestReadAddonSettings(t *testing.T) {
	got := ReadAddonSettings([]byte(savedWithToken))
	if got.Server != "https://wow.example.org" || got.Token != "wft_geheim123" {
		t.Fatalf("%+v", got)
	}
	if got := ReadAddonSettings([]byte("WowFTDB = {}\n")); got != (AddonSettings{}) {
		t.Fatalf("ohne Block: %+v", got)
	}
	// Ein Schlüssel "token" außerhalb des upload-Blocks zählt nicht.
	other := "WowFTDB = {\n[\"characters\"] = {\n[\"token\"] = \"wft_fremd\",\n},\n}\n"
	if got := ReadAddonSettings([]byte(other)); got.Token != "" {
		t.Fatalf("falscher Block gelesen: %+v", got)
	}
}

func TestStripAddonSettings(t *testing.T) {
	out := string(StripAddonSettings([]byte(savedWithToken)))
	if strings.Contains(out, "wft_geheim123") {
		t.Fatal("Token ist noch in den Daten")
	}
	if !strings.Contains(out, `["token"] = "",`) || !strings.Contains(out, `["server"] = "https://wow.example.org/"`) {
		t.Fatalf("Struktur verändert:\n%s", out)
	}
	// Alles außerhalb des Blocks bleibt byte-genau gleich.
	if !strings.HasSuffix(out, "[\"characters\"] = {\n[\"Player-1-ABC\"] = {\n[\"name\"] = \"Testa\",\n},\n},\n}\n") {
		t.Fatalf("Rest verändert:\n%s", out)
	}
	// Ohne Block unverändert.
	plain := []byte("WowFTDB = {}\n")
	if string(StripAddonSettings(plain)) != string(plain) {
		t.Fatal("Datei ohne Block verändert")
	}
}

func TestEffectiveCredentials(t *testing.T) {
	cfg := &Config{Server: "https://alt.example.org", Token: "wft_config", WowDir: "/w"}
	srv, tok := EffectiveCredentials(cfg, []byte(savedWithToken))
	if srv != "https://wow.example.org" || tok != "wft_geheim123" {
		t.Fatalf("Spiel soll Vorrang haben: %s %s", srv, tok)
	}
	srv, tok = EffectiveCredentials(cfg, []byte("WowFTDB = {}"))
	if srv != cfg.Server || tok != "wft_config" {
		t.Fatalf("ohne Spielwerte soll die Konfiguration gelten: %s %s", srv, tok)
	}
	bad := "WowFTDB = {\n[\"upload\"] = {\n[\"server\"] = \"http://boese.example.org\",\n[\"token\"] = \"kein-token\",\n},\n}\n"
	srv, tok = EffectiveCredentials(cfg, []byte(bad))
	if srv != cfg.Server || tok != "wft_config" {
		t.Fatalf("ungültige Spielwerte müssen ignoriert werden: %s %s", srv, tok)
	}
	empty := &Config{Server: DefaultServer}
	if _, tok := EffectiveCredentials(empty, []byte("WowFTDB = {}")); tok != "" {
		t.Fatalf("Token ohne Quelle: %q", tok)
	}
}

type credFake struct {
	fakeUploader
	server, token string
}

func (c *credFake) SetCredentials(server, token string) { c.server, c.token = server, token }

func TestWatcherUsesAddonTokenAndStripsIt(t *testing.T) {
	up := &credFake{}
	w, sv, _ := newTestWatcher(t, up)
	writeFile(t, sv, savedWithToken)
	now := time.Now()
	// Beim Start gilt eine vorhandene Datei als „gesetzt“ und wird sofort geprüft.
	if w.Poll(now) != 1 {
		t.Fatal("nicht hochgeladen")
	}
	if up.server != "https://wow.example.org" || up.token != "wft_geheim123" {
		t.Fatalf("Zugangsdaten: %s %s", up.server, up.token)
	}
	if len(up.calls) != 1 || strings.Contains(up.calls[0], "wft_geheim123") {
		t.Fatalf("Token wurde mit hochgeladen: %v", up.calls)
	}
}

func TestWatcherWithoutAnyTokenDoesNotUpload(t *testing.T) {
	up := &credFake{}
	w, sv, _ := newTestWatcher(t, up)
	w.cfg.Token = ""
	writeFile(t, sv, "WowFTDB = {}\n")
	now := time.Now()
	if w.Poll(now) != 0 || len(up.calls) != 0 {
		t.Fatal("ohne Token darf nichts gesendet werden")
	}
	// Gleiche Datei wird nicht jedes Mal erneut gemeldet.
	if w.Poll(now.Add(15*time.Second)) != 0 || len(up.calls) != 0 {
		t.Fatal("erneuter Versuch ohne Änderung")
	}
	// Sobald der Token im Spiel eingetragen wurde, geht es los.
	writeFile(t, sv, savedWithToken)
	future := time.Now().Add(time.Hour)
	_ = os.Chtimes(sv, future, future)
	w.Poll(now.Add(20 * time.Second))
	if w.Poll(now.Add(24*time.Second)) != 1 {
		t.Fatal("Upload nach Eintragen des Tokens fehlt")
	}
}
