package main

import (
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

const svName = "WowFT.lua"

// FindSavedVariables sucht WowFT.lua für alle Accounts und Spielversionen
// unterhalb des WoW-Ordners, z. B. _forever_/WTF/Account/NAME/SavedVariables.
// Groß-/Kleinschreibung der Ordner wird ignoriert, weil Linux-Dateisysteme
// (Wine, Proton) sie unterscheiden, WoW aber nicht.
func FindSavedVariables(wowDir string) []string {
	if wowDir == "" {
		return nil
	}
	roots := []string{wowDir}
	if entries, err := os.ReadDir(wowDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				roots = append(roots, filepath.Join(wowDir, e.Name()))
			}
		}
	}
	var out []string
	for _, root := range roots {
		account := childFold(childFold(root, "WTF"), "Account")
		if account == "" {
			continue
		}
		entries, err := os.ReadDir(account)
		if err != nil {
			continue
		}
		for _, acc := range entries {
			if !acc.IsDir() {
				continue
			}
			sv := childFold(filepath.Join(account, acc.Name()), "SavedVariables")
			if f := childFold(sv, svName); f != "" {
				if st, err := os.Stat(f); err == nil && st.Mode().IsRegular() {
					out = append(out, f)
				}
			}
		}
	}
	sort.Strings(out)
	return out
}

// childFold findet einen Eintrag in dir ohne Rücksicht auf Groß-/Kleinschreibung.
func childFold(dir, name string) string {
	if dir == "" {
		return ""
	}
	exact := filepath.Join(dir, name)
	if _, err := os.Stat(exact); err == nil {
		return exact
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return ""
	}
	for _, e := range entries {
		if strings.EqualFold(e.Name(), name) {
			return filepath.Join(dir, e.Name())
		}
	}
	return ""
}

// linuxWowPatterns deckt die üblichen Wine-/Proton-Orte ab
// (Lutris, Bottles, Steam/Proton, Heroic, eigene Prefixe).
func linuxWowPatterns(home string) []string {
	prefixes := []string{
		filepath.Join(home, ".wine"),
		filepath.Join(home, "Games", "*"),
		filepath.Join(home, "Games", "Heroic", "Prefixes", "*"),
		filepath.Join(home, "Games", "Heroic", "Prefixes", "default", "*"),
		filepath.Join(home, ".local", "share", "wineprefixes", "*"),
		filepath.Join(home, ".local", "share", "lutris", "prefixes", "*"),
		filepath.Join(home, ".local", "share", "bottles", "bottles", "*"),
		filepath.Join(home, ".var", "app", "com.usebottles.bottles", "data", "bottles", "bottles", "*"),
		filepath.Join(home, ".steam", "steam", "steamapps", "compatdata", "*", "pfx"),
		filepath.Join(home, ".local", "share", "Steam", "steamapps", "compatdata", "*", "pfx"),
		filepath.Join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam",
			"steamapps", "compatdata", "*", "pfx"),
	}
	var out []string
	for _, p := range prefixes {
		for _, pf := range []string{"Program Files (x86)", "Program Files"} {
			out = append(out, filepath.Join(p, "drive_c", pf, "World of Warcraft"))
		}
	}
	return out
}

// GuessWowDirs liefert existierende Standard-Installationsorte.
func GuessWowDirs() []string {
	home, _ := os.UserHomeDir()
	var patterns []string
	switch runtime.GOOS {
	case "windows":
		for _, drive := range []string{"C:", "D:", "E:"} {
			patterns = append(patterns,
				drive+`\Program Files (x86)\World of Warcraft`,
				drive+`\Program Files\World of Warcraft`,
				drive+`\World of Warcraft`,
				drive+`\Games\World of Warcraft`,
			)
		}
	case "darwin":
		patterns = []string{"/Applications/World of Warcraft"}
	default:
		patterns = linuxWowPatterns(home)
	}
	return existingDirs(patterns)
}

func existingDirs(patterns []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, p := range patterns {
		matches, _ := filepath.Glob(p)
		for _, m := range matches {
			if st, err := os.Stat(m); err == nil && st.IsDir() && !seen[m] {
				seen[m] = true
				out = append(out, m)
			}
		}
	}
	// Ordner mit gefundener WowFT.lua zuerst vorschlagen.
	sort.SliceStable(out, func(i, j int) bool {
		return len(FindSavedVariables(out[i])) > 0 && len(FindSavedVariables(out[j])) == 0
	})
	return out
}
