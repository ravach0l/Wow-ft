package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

const (
	settleTime     = 3 * time.Second  // WoW schreibt die Datei in mehreren Schritten
	rediscoverTime = 60 * time.Second // neue Accounts/Ordner finden
	minBackoff     = 5 * time.Second
	maxBackoff     = 5 * time.Minute
)

type Uploader interface {
	Upload(content []byte) (*Result, error)
	UploadPhoto(characterID int, t int64, jpegData []byte) error
}

type fileState struct {
	modTime    time.Time
	size       int64
	changedAt  time.Time
	nextTry    time.Time
	backoff    time.Duration
	failedHash string // Inhalt, den der Server dauerhaft abgelehnt hat
}

// Watcher prüft die Dateien in festen Abständen. Poll ist ohne Schlafen
// testbar; Run ruft Poll in einer Schleife auf.
type Watcher struct {
	cfg       *Config
	up        Uploader
	statePath string
	log       *log.Logger

	files        []string
	lastDiscover time.Time
	state        map[string]*fileState
	uploaded     map[string]string // Pfad -> Hash des zuletzt hochgeladenen Inhalts; "photo:…" -> Datei
	photoMissing map[string]bool
	// LastSuccess ist der Zeitpunkt des letzten erfolgreichen Uploads.
	LastSuccess time.Time
}

func NewWatcher(cfg *Config, up Uploader, statePath string, logger *log.Logger) *Watcher {
	w := &Watcher{
		cfg: cfg, up: up, statePath: statePath, log: logger,
		state: map[string]*fileState{}, uploaded: map[string]string{}, photoMissing: map[string]bool{},
	}
	if data, err := os.ReadFile(statePath); err == nil {
		_ = json.Unmarshal(data, &w.uploaded)
	}
	return w
}

func (w *Watcher) discover(now time.Time) {
	if !w.lastDiscover.IsZero() && now.Sub(w.lastDiscover) < rediscoverTime {
		return
	}
	w.lastDiscover = now
	seen := map[string]bool{}
	var files []string
	for _, f := range append(append([]string{}, w.cfg.Files...), FindSavedVariables(w.cfg.WowDir)...) {
		if !seen[f] {
			seen[f] = true
			files = append(files, f)
		}
	}
	if len(files) != len(w.files) {
		if len(files) == 0 {
			w.log.Printf("Noch keine %s gefunden. Einmal im Spiel einloggen und /reload eingeben.", svName)
		}
		for _, f := range files {
			if w.state[f] == nil {
				w.log.Printf("Beobachte %s", f)
			}
		}
	}
	w.files = files
}

// Poll führt einen Prüfdurchlauf aus und gibt die Zahl erfolgreicher Uploads zurück.
func (w *Watcher) Poll(now time.Time) int {
	w.discover(now)
	done := 0
	for _, path := range w.files {
		if w.pollFile(path, now) {
			done++
		}
	}
	return done
}

func (w *Watcher) pollFile(path string, now time.Time) bool {
	st, err := os.Stat(path)
	if err != nil {
		return false
	}
	fs := w.state[path]
	if fs == nil {
		// Beim Start gilt eine vorhandene Datei als „gesetzt“.
		fs = &fileState{modTime: st.ModTime(), size: st.Size(), changedAt: now.Add(-settleTime)}
		w.state[path] = fs
	}
	if !st.ModTime().Equal(fs.modTime) || st.Size() != fs.size {
		fs.modTime, fs.size, fs.changedAt = st.ModTime(), st.Size(), now
		return false
	}
	if now.Sub(fs.changedAt) < settleTime || now.Before(fs.nextTry) {
		return false
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	sum := sha256.Sum256(content)
	hash := hex.EncodeToString(sum[:])
	if hash == w.uploaded[path] || hash == fs.failedHash {
		return false
	}

	res, err := w.up.Upload(content)
	if err != nil {
		var ue *UploadError
		if errors.As(err, &ue) && ue.Permanent {
			fs.failedHash = hash
			if ue.Status == 401 {
				w.log.Printf("Upload abgelehnt: Token ungültig oder widerrufen. Neuen Token auf der Webseite erzeugen und den Uploader mit -setup neu einrichten.")
			} else {
				w.log.Printf("Upload abgelehnt (%v). Neuer Versuch, sobald sich die Datei ändert.", err)
			}
			return false
		}
		if fs.backoff == 0 {
			fs.backoff = minBackoff
		} else if fs.backoff *= 2; fs.backoff > maxBackoff {
			fs.backoff = maxBackoff
		}
		fs.nextTry = now.Add(fs.backoff)
		w.log.Printf("Upload fehlgeschlagen (%v), neuer Versuch in %s", err, fs.backoff)
		return false
	}

	fs.backoff, fs.nextTry, fs.failedHash = 0, time.Time{}, ""
	w.uploaded[path] = hash
	w.LastSuccess = now
	w.saveState()
	msg := "Hochgeladen: %d Charakter(e), %d neue Snapshots, %d neue Ereignisse"
	w.log.Printf(msg, res.Characters, res.Snapshots, res.Events)
	if len(res.Skipped) > 0 {
		w.log.Printf("Übersprungen (gehören einem anderen Konto): %v", res.Skipped)
	}
	w.uploadPhotos(path, res.PhotoRequests)
	return true
}

// uploadPhotos sucht zu jedem /ft foto-Zeitpunkt den Screenshot und lädt ihn hoch.
func (w *Watcher) uploadPhotos(svPath string, reqs []PhotoRequest) {
	if len(reqs) == 0 {
		return
	}
	dir := ScreenshotDir(svPath)
	changed := false
	for _, r := range reqs {
		key := fmt.Sprintf("photo:%d:%d", r.CharacterID, r.T)
		if w.uploaded[key] != "" {
			continue
		}
		shot := FindScreenshot(dir, time.Unix(r.T, 0))
		if shot == "" {
			if !w.photoMissing[key] {
				w.photoMissing[key] = true
				w.log.Printf("Kein Screenshot zu /ft foto von %s gefunden (Ordner: %s). Nur JPG/PNG werden unterstützt.", r.Name, dir)
			}
			continue
		}
		data, err := MakePortrait(shot)
		if err != nil {
			w.log.Printf("Screenshot %s nicht lesbar: %v", shot, err)
			w.uploaded[key] = "unlesbar"
			changed = true
			continue
		}
		if err := w.up.UploadPhoto(r.CharacterID, r.T, data); err != nil {
			var ue *UploadError
			if errors.As(err, &ue) && ue.Permanent {
				w.uploaded[key] = "abgelehnt"
				changed = true
			}
			w.log.Printf("Foto von %s nicht hochgeladen: %v", r.Name, err)
			continue
		}
		w.uploaded[key] = filepath.Base(shot)
		changed = true
		w.log.Printf("Foto von %s hochgeladen (%s).", r.Name, filepath.Base(shot))
	}
	if changed {
		w.saveState()
	}
}

func (w *Watcher) saveState() {
	data, _ := json.MarshalIndent(w.uploaded, "", "  ")
	if err := os.WriteFile(w.statePath, data, 0o600); err != nil {
		w.log.Printf("Status konnte nicht gespeichert werden: %v", err)
	}
}

func (w *Watcher) Run(stop <-chan struct{}) {
	interval := time.Duration(w.cfg.PollSeconds) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	w.Poll(time.Now())
	for {
		select {
		case <-stop:
			return
		case now := <-ticker.C:
			w.Poll(now)
		}
	}
}
