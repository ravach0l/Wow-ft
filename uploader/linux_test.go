//go:build linux

package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestFindSavedVariablesIgnoresCase(t *testing.T) {
	wow := t.TempDir()
	// Wine legt Ordner manchmal anders geschrieben an.
	p := filepath.Join(wow, "_forever_", "wtf", "ACCOUNT", "Acc", "savedvariables", "WowFT.lua")
	writeFile(t, p, "x")
	got := FindSavedVariables(wow)
	if len(got) != 1 || got[0] != p {
		t.Fatalf("got %v", got)
	}
}

func TestGuessWowDirsLinuxPrefixes(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	lutris := filepath.Join(home, "Games", "battlenet", "drive_c", "Program Files (x86)", "World of Warcraft")
	bottles := filepath.Join(home, ".var", "app", "com.usebottles.bottles", "data", "bottles", "bottles",
		"WoW", "drive_c", "Program Files (x86)", "World of Warcraft")
	proton := filepath.Join(home, ".local", "share", "Steam", "steamapps", "compatdata", "123", "pfx",
		"drive_c", "Program Files (x86)", "World of Warcraft")
	for _, d := range []string{lutris, bottles, proton} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	// Ordner mit vorhandener WowFT.lua kommt zuerst.
	writeFile(t, filepath.Join(proton, "_forever_", "WTF", "Account", "A", "SavedVariables", "WowFT.lua"), "x")
	got := GuessWowDirs()
	if len(got) != 3 || got[0] != proton {
		t.Fatalf("got %v", got)
	}
}

func TestAutostartFiles(t *testing.T) {
	unit := systemdUnit("/home/a b/bin/wowft-uploader", "/home/a b/.config/wowft/config.json")
	if !strings.Contains(unit, `ExecStart="/home/a b/bin/wowft-uploader" -config "/home/a b/.config/wowft/config.json"`) {
		t.Fatal(unit)
	}
	if !strings.Contains(unit, "WantedBy=default.target") {
		t.Fatal(unit)
	}
	if !strings.Contains(systemdQuote("50%"), "50%%") {
		t.Fatal("Prozent nicht maskiert")
	}
	d := desktopEntry("/opt/w$x", "/c.json")
	if !strings.Contains(d, `Exec="/opt/w\$x" -config "/c.json"`) {
		t.Fatal(d)
	}
}
