package main

import (
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

// Durchsucht Laufwerke bzw. das Home-Verzeichnis nach einer WoW-Installation,
// wenn sie nicht an einem der bekannten Orte liegt. Der Name der Programmdatei
// von Forever ist unbekannt, deshalb zählen mehrere Merkmale:
//   - eine Datei Wow*.exe oder "World of Warcraft*.exe" (z. B. WowClassic.exe)
//   - eine App "World of Warcraft*.app" (macOS)
//   - die Unterordner WTF und Interface nebeneinander (Spielordner, egal wie die .exe heißt)
// Gefunden wird der Spielordner (z. B. _forever_); liegt darüber der
// Battle.net-Installationsordner (.build.info, Launcher), wird dieser genommen.

const (
	searchBudget  = 20 * time.Second
	searchMaxDirs = 400_000
)

var skipDirs = map[string]bool{
	"node_modules": true, ".git": true, ".cache": true, ".npm": true, ".cargo": true,
	".rustup": true, ".gradle": true, ".m2": true, ".nuget": true, "go": true,
	"windows": true, "$recycle.bin": true, "system volume information": true,
	"appdata": true, "programdata": true, "proc": true, "sys": true, "dev": true,
	"library": true, "snap": true, ".trash": true, "msocache": true, "recovery": true,
	"winsxs": true, "dosdevices": true, // Wine: Links auf Laufwerke, sonst Schleifen
}

func isWowExe(name string) bool {
	n := strings.ToLower(name)
	if strings.Contains(n, "launcher") || strings.Contains(n, "uninstall") || strings.Contains(n, "error") {
		return false
	}
	if strings.HasSuffix(n, ".exe") {
		return strings.HasPrefix(n, "wow") || strings.HasPrefix(n, "world of warcraft")
	}
	return strings.HasSuffix(n, ".app") && strings.HasPrefix(n, "world of warcraft")
}

// isGameDir erkennt einen Spielordner wie _classic_era_ oder _forever_.
func isGameDir(entries []os.DirEntry) bool {
	hasWTF, hasInterface := false, false
	for _, e := range entries {
		n := strings.ToLower(e.Name())
		if isWowExe(e.Name()) {
			return true
		}
		if e.IsDir() {
			hasWTF = hasWTF || n == "wtf"
			hasInterface = hasInterface || n == "interface"
		}
	}
	return hasWTF && hasInterface
}

func isInstallRoot(dir string) bool {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return false
	}
	for _, e := range entries {
		n := strings.ToLower(e.Name())
		if n == ".build.info" || strings.HasPrefix(n, "world of warcraft launcher") {
			return true
		}
	}
	return false
}

// SearchWowDirs durchsucht roots bis maxDepth Ebenen tief (Breitensuche, mit Zeitlimit).
func SearchWowDirs(roots []string, maxDepth int, budget time.Duration) []string {
	deadline := time.Now().Add(budget)
	type item struct {
		path  string
		depth int
	}
	queue := make([]item, 0, len(roots))
	for _, r := range roots {
		queue = append(queue, item{r, 0})
	}
	seen := map[string]bool{}
	var found []string
	visited := 0
	for len(queue) > 0 && visited < searchMaxDirs && time.Now().Before(deadline) {
		cur := queue[0]
		queue = queue[1:]
		visited++
		entries, err := os.ReadDir(cur.path)
		if err != nil {
			continue
		}
		if isGameDir(entries) {
			dir := cur.path
			if parent := filepath.Dir(dir); parent != dir && isInstallRoot(parent) {
				dir = parent
			}
			if !seen[dir] {
				seen[dir] = true
				found = append(found, dir)
			}
			continue // in einem Spielordner nicht weitersuchen
		}
		if cur.depth >= maxDepth {
			continue
		}
		for _, e := range entries {
			// Symlinks nicht folgen (Schleifen, doppelte Treffer).
			if !e.IsDir() || e.Type()&os.ModeSymlink != 0 || skipDirs[strings.ToLower(e.Name())] {
				continue
			}
			queue = append(queue, item{filepath.Join(cur.path, e.Name()), cur.depth + 1})
		}
	}
	sort.Strings(found)
	return found
}

func existing(paths ...string) []string {
	var out []string
	for _, p := range paths {
		if st, err := os.Stat(p); err == nil && st.IsDir() {
			out = append(out, p)
		}
	}
	return out
}

// searchWowDirs ist austauschbar, damit Tests nicht den echten Rechner durchsuchen.
var searchWowDirs = SearchWowDirsDefault

// SearchWowDirsDefault durchsucht die üblichen Orte des Systems.
func SearchWowDirsDefault() []string {
	home, _ := os.UserHomeDir()
	switch runtime.GOOS {
	case "windows":
		var drives []string
		for c := 'C'; c <= 'Z'; c++ {
			drives = append(drives, string(c)+`:\`)
		}
		return SearchWowDirs(existing(drives...), 5, searchBudget)
	case "darwin":
		return SearchWowDirs(existing("/Applications", filepath.Join(home, "Applications"), home), 5, searchBudget)
	default:
		// Wine-/Proton-Prefixe liegen tief: ~/.local/share/Steam/steamapps/compatdata/ID/pfx/drive_c/...
		roots := existing(home, "/mnt", "/media", "/run/media", "/opt", "/games")
		return SearchWowDirs(roots, 12, searchBudget)
	}
}
