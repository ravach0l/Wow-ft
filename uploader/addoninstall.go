package main

//go:generate go run ./cmd/syncaddon

import (
	"embed"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// Das Addon steckt in der .exe (go generate kopiert ../addon/WowFT nach addonfiles/WowFT).
// Der Uploader installiert es in den Spielordner und ersetzt ältere Versionen.

//go:embed all:addonfiles
var embeddedFiles embed.FS

const addonName = "WowFT"

var tocVersionRe = regexp.MustCompile(`(?m)^##\s*Version:\s*(\S+)`)

// EmbeddedAddon liefert die eingebetteten Addon-Dateien (nil, wenn beim Bauen nicht erzeugt).
func EmbeddedAddon() fs.FS {
	sub, err := fs.Sub(embeddedFiles, "addonfiles/"+addonName)
	if err != nil {
		return nil
	}
	if _, err := fs.Stat(sub, addonName+".toc"); err != nil {
		return nil
	}
	return sub
}

func tocVersion(toc []byte) string {
	if m := tocVersionRe.FindSubmatch(toc); m != nil {
		return string(m[1])
	}
	return ""
}

// compareVersions vergleicht "1.2.3"-Versionen zahlenweise (-1, 0, 1).
func compareVersions(a, b string) int {
	pa, pb := strings.Split(a, "."), strings.Split(b, ".")
	for i := 0; i < max(len(pa), len(pb)); i++ {
		var x, y int
		if i < len(pa) {
			x, _ = strconv.Atoi(pa[i])
		}
		if i < len(pb) {
			y, _ = strconv.Atoi(pb[i])
		}
		if x != y {
			if x < y {
				return -1
			}
			return 1
		}
	}
	return 0
}

// GameDirsForAddon bestimmt, in welche Spielordner das Addon gehört:
// alle Forever-Ordner (Name enthält "forever"); gibt es keinen, den einzigen Spielordner.
// Ist der WoW-Ordner selbst ein Spielordner, zählt er mit.
func GameDirsForAddon(wowDir string) []string {
	if wowDir == "" {
		return nil
	}
	var games []string
	if entries, err := os.ReadDir(wowDir); err == nil {
		if isGameDir(entries) {
			return []string{wowDir}
		}
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			p := filepath.Join(wowDir, e.Name())
			if sub, err := os.ReadDir(p); err == nil && isGameDir(sub) {
				games = append(games, p)
			}
		}
	}
	var forever []string
	for _, g := range games {
		if strings.Contains(strings.ToLower(filepath.Base(g)), "forever") {
			forever = append(forever, g)
		}
	}
	if len(forever) > 0 {
		return forever
	}
	if len(games) == 1 {
		return games
	}
	return nil
}

// AddonResult beschreibt, was beim Installieren passiert ist.
type AddonResult struct {
	Dir       string // Zielordner …/Interface/AddOns/WowFT
	Installed string // Version vorher ("" = nicht vorhanden)
	Version   string // eingebettete Version
	Changed   bool
}

// InstallAddon installiert oder aktualisiert das Addon in einem Spielordner.
// Eine neuere oder gleich alte installierte Version bleibt unangetastet.
func InstallAddon(gameDir string, addon fs.FS) (AddonResult, error) {
	toc, err := fs.ReadFile(addon, addonName+".toc")
	if err != nil {
		return AddonResult{}, err
	}
	res := AddonResult{Version: tocVersion(toc)}
	addons := filepath.Join(gameDir, "Interface", "AddOns")
	if dir := childFold(gameDir, "Interface"); dir != "" {
		if sub := childFold(dir, "AddOns"); sub != "" {
			addons = sub
		} else {
			addons = filepath.Join(dir, "AddOns")
		}
	}
	res.Dir = filepath.Join(addons, addonName)
	if existing := childFold(addons, addonName); existing != "" {
		res.Dir = existing
		if old, err := os.ReadFile(filepath.Join(existing, addonName+".toc")); err == nil {
			res.Installed = tocVersion(old)
			if res.Installed == "" {
				res.Installed = "?"
			}
		}
	}
	if res.Installed != "" && res.Installed != "?" && compareVersions(res.Installed, res.Version) >= 0 {
		return res, nil
	}

	// Erst vollständig in einen Nachbarordner schreiben, dann austauschen:
	// So bleibt nie ein halbes Addon zurück.
	if err := os.MkdirAll(addons, 0o755); err != nil {
		return res, err
	}
	tmp, err := os.MkdirTemp(addons, ".wowft-neu-")
	if err != nil {
		return res, err
	}
	defer os.RemoveAll(tmp)
	err = fs.WalkDir(addon, ".", func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		target := filepath.Join(tmp, filepath.FromSlash(p))
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		data, err := fs.ReadFile(addon, p)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, 0o644)
	})
	if err != nil {
		return res, err
	}
	old := ""
	if _, err := os.Stat(res.Dir); err == nil {
		old = filepath.Join(addons, fmt.Sprintf(".wowft-alt-%d", os.Getpid()))
		_ = os.RemoveAll(old)
		if err := os.Rename(res.Dir, old); err != nil {
			return res, err
		}
	}
	if err := os.Rename(tmp, res.Dir); err != nil {
		if old != "" {
			_ = os.Rename(old, res.Dir) // alten Stand zurückholen
		}
		return res, err
	}
	if old != "" {
		_ = os.RemoveAll(old)
	}
	res.Changed = true
	return res, nil
}

// EnsureAddon installiert das Addon in alle passenden Spielordner und beschreibt das Ergebnis.
func EnsureAddon(wowDir string, logf func(string, ...any)) {
	addon := EmbeddedAddon()
	if addon == nil {
		return // Entwicklungs-Build ohne go generate
	}
	games := GameDirsForAddon(wowDir)
	if len(games) == 0 {
		logf("Addon nicht installiert: kein eindeutiger Forever-Spielordner unter %s gefunden. "+
			"Bitte WowFT von Hand nach Interface/AddOns kopieren.", wowDir)
		return
	}
	for _, g := range games {
		res, err := InstallAddon(g, addon)
		switch {
		case err != nil && errors.Is(err, fs.ErrPermission):
			logf("Addon konnte nicht installiert werden: keine Schreibrechte für %s. "+
				"Bitte WowFT von Hand nach Interface/AddOns kopieren.", filepath.Join(g, "Interface", "AddOns"))
		case err != nil:
			logf("Addon konnte nicht installiert werden (%s): %v", g, err)
		case res.Changed && res.Installed == "":
			logf("Addon WowFT %s installiert in %s. Im Spiel neu einloggen.", res.Version, res.Dir)
		case res.Changed:
			logf("Addon WowFT aktualisiert (%s → %s). Wirksam nach /reload oder neuem Login.", res.Installed, res.Version)
		}
	}
}
