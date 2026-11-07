package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Der Uploader aktualisiert sich selbst aus den GitHub-Releases:
//  1. neueste Version abfragen (einmal beim Start, dann täglich),
//  2. passende Datei und SHA256SUMS.txt laden, Prüfsumme vergleichen,
//  3. die laufende Datei austauschen und neu starten.
// Selbst gebaute Versionen ("dev") aktualisieren sich nie.

const (
	updateRepo      = "ravach0l/Wow-ft"
	updateEvery     = 24 * time.Hour
	maxUpdateBytes  = 64 << 20
	checksumsName   = "SHA256SUMS.txt"
	restartExitCode = 75 // systemd startet den Dienst damit neu (Restart=on-failure)
)

// Austauschbar für Tests.
var (
	updateAPI      = "https://api.github.com/repos/" + updateRepo + "/releases/latest"
	executablePath = func() (string, error) {
		p, err := os.Executable()
		if err != nil {
			return "", err
		}
		return filepath.EvalSymlinks(p)
	}
	restartSelf = restartProcess
)

type releaseInfo struct {
	TagName string `json:"tag_name"`
	Assets  []struct {
		Name string `json:"name"`
		URL  string `json:"browser_download_url"`
	} `json:"assets"`
}

// AssetName ist der Dateiname im Release für dieses System.
func AssetName(goos, goarch string) string {
	switch {
	case goos == "windows":
		return "wowft-uploader.exe"
	case goos == "linux":
		return "wowft-uploader-linux-" + goarch
	case goos == "darwin":
		return "wowft-uploader-macos-" + goarch
	}
	return ""
}

// UpdateResult beschreibt eine Prüfung.
type UpdateResult struct {
	Latest   string // neueste Version laut GitHub (ohne "v")
	Replaced bool   // Datei wurde ausgetauscht; Neustart nötig
	Path     string // Pfad der neuen Datei (vor dem Austausch ermittelt)
}

type Updater struct {
	HTTP *http.Client
	Log  func(string, ...any)
}

func NewUpdater(logf func(string, ...any)) *Updater {
	return &Updater{HTTP: &http.Client{Timeout: 60 * time.Second}, Log: logf}
}

func (u *Updater) get(url string, limit int64) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "wowft-uploader/"+Version)
	req.Header.Set("Accept", "application/vnd.github+json")
	resp, err := u.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d bei %s", resp.StatusCode, url)
	}
	data, err := io.ReadAll(io.LimitReader(resp.Body, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > limit {
		return nil, errors.New("Datei zu groß")
	}
	return data, nil
}

// parseChecksums liest Zeilen der Form "<sha256>  <dateiname>".
func parseChecksums(data []byte) map[string]string {
	out := map[string]string{}
	sc := bufio.NewScanner(bytes.NewReader(data))
	for sc.Scan() {
		fields := strings.Fields(sc.Text())
		if len(fields) == 2 && len(fields[0]) == 64 {
			out[strings.TrimPrefix(fields[1], "*")] = strings.ToLower(fields[0])
		}
	}
	return out
}

// Check prüft auf eine neue Version und tauscht die laufende Datei aus, falls es eine gibt.
func (u *Updater) Check() (UpdateResult, error) {
	var res UpdateResult
	if Version == "dev" || Version == "" {
		return res, nil
	}
	data, err := u.get(updateAPI, 1<<20)
	if err != nil {
		return res, fmt.Errorf("Update-Prüfung: %w", err)
	}
	var rel releaseInfo
	if err := json.Unmarshal(data, &rel); err != nil {
		return res, fmt.Errorf("Update-Prüfung: unerwartete Antwort")
	}
	res.Latest = strings.TrimPrefix(rel.TagName, "v")
	if res.Latest == "" || compareVersions(res.Latest, Version) <= 0 {
		return res, nil
	}

	name := AssetName(runtime.GOOS, runtime.GOARCH)
	var assetURL, sumsURL string
	for _, a := range rel.Assets {
		switch a.Name {
		case name:
			assetURL = a.URL
		case checksumsName:
			sumsURL = a.URL
		}
	}
	if assetURL == "" || sumsURL == "" {
		return res, fmt.Errorf("Version %s: %s oder %s fehlt im Release", res.Latest, name, checksumsName)
	}
	sums, err := u.get(sumsURL, 1<<20)
	if err != nil {
		return res, err
	}
	want := parseChecksums(sums)[name]
	if want == "" {
		return res, fmt.Errorf("keine Prüfsumme für %s", name)
	}
	bin, err := u.get(assetURL, maxUpdateBytes)
	if err != nil {
		return res, err
	}
	got := sha256.Sum256(bin)
	if hex.EncodeToString(got[:]) != want {
		return res, errors.New("Prüfsumme stimmt nicht, Update verworfen")
	}
	path, err := replaceExecutable(bin)
	if err != nil {
		return res, fmt.Errorf("Austausch fehlgeschlagen: %w", err)
	}
	res.Replaced, res.Path = true, path
	return res, nil
}

// replaceExecutable schreibt die neue Datei neben die laufende und tauscht sie aus.
// Windows erlaubt kein Überschreiben der laufenden .exe, wohl aber das Umbenennen;
// die alte Datei (*.old) wird beim nächsten Start entfernt.
// Gibt den Pfad zurück: Nach dem Austausch zeigt os.Executable auf die alte Datei.
func replaceExecutable(bin []byte) (string, error) {
	exe, err := executablePath()
	if err != nil {
		return "", err
	}
	tmp := exe + ".new"
	if err := os.WriteFile(tmp, bin, 0o755); err != nil {
		return "", err
	}
	old := exe + ".old"
	_ = os.Remove(old)
	if err := os.Rename(exe, old); err != nil {
		_ = os.Remove(tmp)
		return "", err
	}
	if err := os.Rename(tmp, exe); err != nil {
		_ = os.Rename(old, exe) // alten Stand zurückholen
		return "", err
	}
	if runtime.GOOS != "windows" {
		_ = os.Remove(old) // unter Linux/macOS läuft das Programm trotz gelöschter Datei weiter
	}
	return exe, nil
}

// CleanupOldExecutable entfernt die nach einem Update übrig gebliebene alte Datei.
func CleanupOldExecutable() {
	if exe, err := executablePath(); err == nil {
		_ = os.Remove(exe + ".old")
	}
}

// restartProcess startet die neue Version. Unter systemd übernimmt der Dienst den Neustart
// (Beenden mit Code 75); sonst wird das Programm mit denselben Argumenten neu gestartet.
func restartProcess(exe string) {
	if os.Getenv("INVOCATION_ID") != "" {
		os.Exit(restartExitCode)
	}
	cmd := exec.Command(exe, os.Args[1:]...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	err := cmd.Start()
	if err == nil {
		os.Exit(0)
	}
	fmt.Fprintln(os.Stderr, "Neustart fehlgeschlagen:", err)
	os.Exit(restartExitCode)
}

// RunUpdates prüft beim Start und danach täglich; nach einem Austausch folgt der Neustart.
func (u *Updater) RunUpdates(stop <-chan struct{}) {
	for {
		res, err := u.Check()
		switch {
		case err != nil:
			u.Log("%v", err)
		case res.Replaced:
			u.Log("Uploader auf Version %s aktualisiert, starte neu …", res.Latest)
			restartSelf(res.Path)
			return
		}
		select {
		case <-stop:
			return
		case <-time.After(updateEvery):
		}
	}
}
