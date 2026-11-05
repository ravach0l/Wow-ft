// WowFT-Uploader: beobachtet WowFT.lua und schickt sie an den Server.
package main

import (
	"bufio"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
)

func main() {
	os.Exit(run())
}

func run() int {
	var (
		configPath = flag.String("config", "", "Pfad zur config.json (Standard: Benutzer-Konfigurationsordner)")
		setup      = flag.Bool("setup", false, "Server, Token und WoW-Ordner neu eingeben")
		once       = flag.Bool("once", false, "einmal hochladen und beenden")
		autostart  = flag.String("autostart", "", "on oder off: beim Windows-Start ausführen")
		background = flag.Bool("background", false, "ohne sichtbares Fenster laufen (Windows)")
		version    = flag.Bool("version", false, "Version anzeigen")
	)
	flag.Parse()

	if *version {
		fmt.Println("wowft-uploader", Version)
		return 0
	}

	dir, err := DefaultConfigDir()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Konfigurationsordner nicht gefunden:", err)
		return 1
	}
	if *configPath == "" {
		*configPath = filepath.Join(dir, "config.json")
	}
	baseDir := filepath.Dir(*configPath)
	_ = os.MkdirAll(baseDir, 0o700)
	logger := newLogger(filepath.Join(baseDir, "uploader.log"), !*background)

	if *autostart != "" {
		on := *autostart == "on"
		started, err := SetAutostart(on, *configPath)
		if err != nil {
			logger.Printf("Autostart: %v", err)
			return 1
		}
		logger.Printf("Autostart %s.", map[bool]string{true: "eingeschaltet", false: "ausgeschaltet"}[on])
		if started {
			logger.Printf("Der Uploader läuft jetzt im Hintergrund (systemctl --user status %s).", "wowft-uploader")
		}
		return 0
	}

	cfg, err := LoadConfig(*configPath)
	if *setup || errors.Is(err, fs.ErrNotExist) {
		var started bool
		cfg, started, err = interactiveSetup(*configPath, cfg)
		if err != nil {
			logger.Printf("Einrichtung abgebrochen: %v", err)
			pause()
			return 1
		}
		if started {
			// Der Hintergrunddienst übernimmt; keine zweite Instanz starten.
			return 0
		}
	} else if err != nil {
		logger.Printf("Konfiguration %s fehlerhaft: %v (mit -setup neu einrichten)", *configPath, err)
		pause()
		return 1
	}

	if *background {
		hideConsole()
	}

	client := NewClient(cfg.Server, cfg.Token)
	statePath := filepath.Join(baseDir, "state.json")

	if *once {
		files := append(append([]string{}, cfg.Files...), FindSavedVariables(cfg.WowDir)...)
		if len(files) == 0 {
			logger.Printf("Keine %s gefunden unter %s", svName, cfg.WowDir)
			return 1
		}
		failed := false
		w := NewWatcher(cfg, client, statePath, logger)
		for _, f := range files {
			content, err := os.ReadFile(f)
			if err != nil {
				logger.Printf("%s: %v", f, err)
				failed = true
				continue
			}
			res, err := client.Upload(content)
			if err != nil {
				logger.Printf("%s: %v", f, err)
				failed = true
				continue
			}
			logger.Printf("%s: %d Charakter(e), %d neue Snapshots, %d neue Ereignisse",
				f, res.Characters, res.Snapshots, res.Events)
			w.uploadPhotos(f, res.PhotoRequests)
		}
		if failed {
			return 1
		}
		return 0
	}

	logger.Printf("WowFT-Uploader %s läuft. Server: %s. Beenden mit Strg+C.", Version, cfg.Server)
	w := NewWatcher(cfg, client, statePath, logger)
	stop := make(chan struct{})
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sig
		close(stop)
	}()
	w.Run(stop)
	logger.Printf("Beendet.")
	return 0
}

func interactiveSetup(path string, old *Config) (*Config, bool, error) {
	cfg, err := RunSetup(os.Stdin, os.Stdout, old)
	if err != nil {
		return nil, false, err
	}
	if err := SaveConfig(path, cfg); err != nil {
		return nil, false, err
	}
	fmt.Printf("Gespeichert in %s\n", path)
	if runtime.GOOS != "windows" && runtime.GOOS != "linux" {
		return cfg, false, nil
	}
	fmt.Print("Beim Anmelden automatisch im Hintergrund starten? [J/n]: ")
	line, _ := bufio.NewReader(os.Stdin).ReadString('\n')
	if a := strings.ToLower(strings.TrimSpace(line)); a != "" && a != "j" && a != "y" {
		return cfg, false, nil
	}
	started, err := SetAutostart(true, path)
	switch {
	case err != nil:
		fmt.Println("Autostart fehlgeschlagen:", err)
	case started:
		fmt.Println("Autostart eingerichtet. Der Uploader läuft jetzt als Dienst im Hintergrund.")
		fmt.Println("Status: systemctl --user status wowft-uploader · Log: journalctl --user -u wowft-uploader -f")
	default:
		fmt.Println("Autostart eingerichtet (ab der nächsten Anmeldung).")
	}
	return cfg, started, nil
}

func newLogger(path string, console bool) *log.Logger {
	// Log klein halten: über 1 MB wird neu begonnen.
	if st, err := os.Stat(path); err == nil && st.Size() > 1<<20 {
		_ = os.Rename(path, path+".old")
	}
	var w io.Writer = io.Discard
	if f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600); err == nil {
		w = f
	}
	if console {
		w = io.MultiWriter(os.Stdout, w)
	}
	return log.New(w, "", log.LstdFlags)
}

// pause hält das Fenster offen, wenn der Uploader per Doppelklick gestartet wurde.
func pause() {
	if runtime.GOOS == "windows" {
		fmt.Print("Enter zum Schließen …")
		_, _ = bufio.NewReader(os.Stdin).ReadString('\n')
	}
}
