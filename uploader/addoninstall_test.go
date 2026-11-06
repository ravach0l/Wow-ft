package main

import (
	"bytes"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"
	"time"
)

func fakeAddon(version string) fs.FS {
	return fstest.MapFS{
		"WowFT.toc": {Data: []byte("## Interface: 16001\n## Version: " + version + "\n\nCore.lua\n")},
		"Core.lua":  {Data: []byte("-- " + version + "\n")},
	}
}

func readAddon(t *testing.T, dir string) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(dir, "Core.lua"))
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

func TestCompareVersions(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{{"0.3.0", "0.2.9", 1}, {"0.3", "0.3.0", 0}, {"0.10.0", "0.9.0", 1}, {"1.0.0", "1.0.1", -1}}
	for _, c := range cases {
		if got := compareVersions(c.a, c.b); got != c.want {
			t.Errorf("%s vs %s: %d", c.a, c.b, got)
		}
	}
}

func TestGameDirsForAddon(t *testing.T) {
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "_forever_", "WowForever.exe"), "")
	writeFile(t, filepath.Join(root, "_classic_era_", "WowClassic.exe"), "")
	mkdirs(t, filepath.Join(root, "Data"))
	if got := GameDirsForAddon(root); len(got) != 1 || filepath.Base(got[0]) != "_forever_" {
		t.Fatalf("got %v", got)
	}
	// Nur eine Spielversion, Name unbekannt: die nehmen.
	one := t.TempDir()
	mkdirs(t, filepath.Join(one, "_neu_", "WTF"), filepath.Join(one, "_neu_", "Interface"))
	if got := GameDirsForAddon(one); len(got) != 1 || filepath.Base(got[0]) != "_neu_" {
		t.Fatalf("got %v", got)
	}
	// Mehrere Versionen ohne Forever: nicht raten.
	two := t.TempDir()
	writeFile(t, filepath.Join(two, "_retail_", "Wow.exe"), "")
	writeFile(t, filepath.Join(two, "_classic_", "WowClassic.exe"), "")
	if got := GameDirsForAddon(two); got != nil {
		t.Fatalf("got %v", got)
	}
	// Spielordner direkt angegeben.
	if got := GameDirsForAddon(filepath.Join(root, "_forever_")); len(got) != 1 {
		t.Fatalf("got %v", got)
	}
}

func TestInstallAddonFreshUpdateAndKeepNewer(t *testing.T) {
	game := t.TempDir()
	writeFile(t, filepath.Join(game, "WowForever.exe"), "")

	res, err := InstallAddon(game, fakeAddon("0.3.0"))
	if err != nil || !res.Changed || res.Installed != "" {
		t.Fatalf("%+v %v", res, err)
	}
	dir := filepath.Join(game, "Interface", "AddOns", "WowFT")
	if res.Dir != dir || readAddon(t, dir) != "-- 0.3.0\n" {
		t.Fatalf("Dir=%s", res.Dir)
	}
	// Gleiche Version: nichts tun.
	if res, _ := InstallAddon(game, fakeAddon("0.3.0")); res.Changed {
		t.Fatal("gleiche Version neu installiert")
	}
	// Neuere eingebettete Version ersetzt; alte Zusatzdateien verschwinden.
	writeFile(t, filepath.Join(dir, "Alt.lua"), "x")
	res, err = InstallAddon(game, fakeAddon("0.4.0"))
	if err != nil || !res.Changed || res.Installed != "0.3.0" || readAddon(t, dir) != "-- 0.4.0\n" {
		t.Fatalf("%+v %v", res, err)
	}
	if _, err := os.Stat(filepath.Join(dir, "Alt.lua")); !os.IsNotExist(err) {
		t.Fatal("alte Datei übrig")
	}
	// Installierte Version ist neuer (z. B. selbst gebaut): nicht zurückstufen.
	if res, _ := InstallAddon(game, fakeAddon("0.3.9")); res.Changed || readAddon(t, dir) != "-- 0.4.0\n" {
		t.Fatal("neuere Version überschrieben")
	}
	// Keine Reste der Zwischenordner.
	entries, _ := os.ReadDir(filepath.Join(game, "Interface", "AddOns"))
	if len(entries) != 1 {
		t.Fatalf("Reste: %v", entries)
	}
}

func TestInstallAddonRespectsExistingCase(t *testing.T) {
	game := t.TempDir()
	// Unter Wine/Linux kann der Ordner anders geschrieben sein.
	writeFile(t, filepath.Join(game, "interface", "addons", "wowft", "WowFT.toc"), "## Version: 0.1.0\n")
	res, err := InstallAddon(game, fakeAddon("0.3.0"))
	if err != nil || !res.Changed || res.Installed != "0.1.0" {
		t.Fatalf("%+v %v", res, err)
	}
	if res.Dir != filepath.Join(game, "interface", "addons", "wowft") {
		t.Fatalf("Dir=%s", res.Dir)
	}
}

func TestInstallAddonWithoutPermission(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("als root greifen Dateirechte nicht")
	}
	game := t.TempDir()
	mkdirs(t, filepath.Join(game, "Interface", "AddOns"))
	_ = os.Chmod(filepath.Join(game, "Interface", "AddOns"), 0o555)
	t.Cleanup(func() { _ = os.Chmod(filepath.Join(game, "Interface", "AddOns"), 0o755) })
	if _, err := InstallAddon(game, fakeAddon("0.3.0")); err == nil {
		t.Fatal("Fehler erwartet")
	}
}

// Das eingebettete Addon muss dem aktuellen Stand in addon/WowFT entsprechen
// (sonst fehlt `go generate ./...` vor dem Bauen).
func TestEmbeddedAddonUpToDate(t *testing.T) {
	addon := EmbeddedAddon()
	if addon == nil {
		t.Skip("kein eingebettetes Addon: vorher `go generate ./...` ausführen")
	}
	src := filepath.Join("..", "addon", "WowFT")
	entries, err := os.ReadDir(src)
	if err != nil {
		t.Skip("Quellordner nicht vorhanden")
	}
	for _, e := range entries {
		want, _ := os.ReadFile(filepath.Join(src, e.Name()))
		got, err := fs.ReadFile(addon, e.Name())
		if err != nil || !bytes.Equal(got, want) {
			t.Errorf("%s ist veraltet: go generate ./... ausführen", e.Name())
		}
	}
}

func TestWatcherInstallsAddonOncePerHour(t *testing.T) {
	if EmbeddedAddon() == nil {
		t.Skip("kein eingebettetes Addon")
	}
	up := &fakeUploader{}
	w, sv, _ := newTestWatcher(t, up)
	game := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(sv)))))
	writeFile(t, filepath.Join(game, "WowForever.exe"), "")
	var logs bytes.Buffer
	w.log.SetOutput(&logs)

	now := time.Now()
	w.Poll(now)
	toc := filepath.Join(game, "Interface", "AddOns", "WowFT", "WowFT.toc")
	if _, err := os.Stat(toc); err != nil {
		t.Fatalf("Addon nicht installiert: %s", logs.String())
	}
	if !strings.Contains(logs.String(), "installiert") {
		t.Fatalf("Log: %s", logs.String())
	}
	_ = os.RemoveAll(filepath.Dir(toc))
	w.Poll(now.Add(10 * time.Minute))
	if _, err := os.Stat(toc); err == nil {
		t.Fatal("vor Ablauf einer Stunde erneut geprüft")
	}
	w.Poll(now.Add(61 * time.Minute))
	if _, err := os.Stat(toc); err != nil {
		t.Fatal("nach einer Stunde nicht wieder installiert")
	}

	// Abschaltbar.
	off := false
	w.cfg.AddonInstall = &off
	_ = os.RemoveAll(filepath.Dir(toc))
	w.Poll(now.Add(3 * time.Hour))
	if _, err := os.Stat(toc); err == nil {
		t.Fatal("trotz addonInstall=false installiert")
	}
}
