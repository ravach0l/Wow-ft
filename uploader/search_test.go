package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func mkdirs(t *testing.T, paths ...string) {
	t.Helper()
	for _, p := range paths {
		if err := os.MkdirAll(p, 0o755); err != nil {
			t.Fatal(err)
		}
	}
}

func TestSearchWowDirs(t *testing.T) {
	root := t.TempDir()
	// 1) Battle.net-Installation mit unbekanntem Exe-Namen tief in einem Proton-Prefix
	inst := filepath.Join(root, ".local", "share", "Steam", "steamapps", "compatdata", "42", "pfx",
		"drive_c", "Program Files (x86)", "World of Warcraft")
	writeFile(t, filepath.Join(inst, ".build.info"), "")
	writeFile(t, filepath.Join(inst, "_forever_", "WowForever.exe"), "")
	// 2) Kopierte Installation ohne .exe-Treffer, aber mit WTF + Interface
	copyDir := filepath.Join(root, "Spiele", "WoW-Kopie")
	mkdirs(t, filepath.Join(copyDir, "WTF"), filepath.Join(copyDir, "Interface"))
	// 3) Nur ein Launcher: kein Spielordner
	writeFile(t, filepath.Join(root, "Downloads", "World of Warcraft Launcher.exe"), "")
	// 4) In node_modules wird nicht gesucht
	writeFile(t, filepath.Join(root, "proj", "node_modules", "x", "Wow.exe"), "")

	got := SearchWowDirs([]string{root}, 12, 5*time.Second)
	want := []string{inst, copyDir}
	if !reflect.DeepEqual(sortedCopy(got), sortedCopy(want)) {
		t.Fatalf("got %v\nwant %v", got, want)
	}

	// Tiefenlimit greift
	if got := SearchWowDirs([]string{root}, 3, 5*time.Second); len(got) != 1 || got[0] != copyDir {
		t.Fatalf("Tiefe 3: %v", got)
	}
}

func TestSearchFindsSavedVariablesThroughResult(t *testing.T) {
	root := t.TempDir()
	inst := filepath.Join(root, "Games", "World of Warcraft")
	writeFile(t, filepath.Join(inst, "World of Warcraft Launcher.exe"), "")
	writeFile(t, filepath.Join(inst, "_forever_", "Wow.exe"), "")
	sv := filepath.Join(inst, "_forever_", "WTF", "Account", "X", "SavedVariables", "WowFT.lua")
	writeFile(t, sv, "x")
	got := SearchWowDirs([]string{root}, 6, 5*time.Second)
	if len(got) != 1 || got[0] != inst {
		t.Fatalf("got %v", got)
	}
	if f := FindSavedVariables(got[0]); len(f) != 1 || f[0] != sv {
		t.Fatalf("SavedVariables: %v", f)
	}
}

func TestIsWowExe(t *testing.T) {
	for name, want := range map[string]bool{
		"Wow.exe": true, "WowClassic.exe": true, "WOWFOREVER.EXE": true, "World of Warcraft.app": true,
		"World of Warcraft Launcher.exe": false, "WowError.exe": false, "notwow.exe": false, "Wow.lua": false,
	} {
		if isWowExe(name) != want {
			t.Errorf("%s: want %v", name, want)
		}
	}
}

func sortedCopy(s []string) []string {
	c := append([]string{}, s...)
	for i := range c {
		for j := i + 1; j < len(c); j++ {
			if c[j] < c[i] {
				c[i], c[j] = c[j], c[i]
			}
		}
	}
	return c
}
