package main

import (
	"os"
	"path/filepath"
	"runtime"
	"sort"
)

const svName = "WowFT.lua"

// FindSavedVariables sucht WowFT.lua für alle Accounts und Spielversionen
// unterhalb des WoW-Ordners, z. B. _forever_/WTF/Account/NAME/SavedVariables.
func FindSavedVariables(wowDir string) []string {
	if wowDir == "" {
		return nil
	}
	patterns := []string{
		filepath.Join(wowDir, "WTF", "Account", "*", "SavedVariables", svName),
		filepath.Join(wowDir, "*", "WTF", "Account", "*", "SavedVariables", svName),
	}
	seen := map[string]bool{}
	var out []string
	for _, p := range patterns {
		matches, _ := filepath.Glob(p)
		for _, m := range matches {
			if !seen[m] {
				seen[m] = true
				out = append(out, m)
			}
		}
	}
	sort.Strings(out)
	return out
}

// GuessWowDirs liefert existierende Standard-Installationsorte.
func GuessWowDirs() []string {
	home, _ := os.UserHomeDir()
	var candidates []string
	switch runtime.GOOS {
	case "windows":
		for _, drive := range []string{"C:", "D:", "E:"} {
			candidates = append(candidates,
				drive+`\Program Files (x86)\World of Warcraft`,
				drive+`\Program Files\World of Warcraft`,
				drive+`\World of Warcraft`,
				drive+`\Games\World of Warcraft`,
			)
		}
	case "darwin":
		candidates = []string{"/Applications/World of Warcraft"}
	default:
		pf := filepath.Join("drive_c", "Program Files (x86)", "World of Warcraft")
		candidates = []string{
			filepath.Join(home, "Games", "battlenet", pf),
			filepath.Join(home, "Games", "world-of-warcraft", pf),
			filepath.Join(home, ".wine", pf),
		}
	}
	var out []string
	for _, c := range candidates {
		if st, err := os.Stat(c); err == nil && st.IsDir() {
			out = append(out, c)
		}
	}
	return out
}
