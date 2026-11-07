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
	"runtime/debug"
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
		find       = flag.Bool("find", false, "WoW-Installationen suchen und anzeigen")
		update     = flag.Bool("update", false, "jetzt nach einer neuen Uploader-Version suchen und sie installieren")
	)
	flag.Parse()

	CleanupOldExecutable()
	if *update {
		res, err := NewUpdater(func(f string, a ...any) { fmt.Printf(f+"\n", a...) }).Check()
		switch {
		case err != nil:
			fmt.Println(err)
			return 1
		case Version == "dev":
			fmt.Println("Selbst gebaute Version: keine automatischen Updates.")
		case res.Replaced:
			fmt.Printf("Aktualisiert auf %s. Beim nächsten Start läuft die neue Version.\n", res.Latest)
		default:
			fmt.Printf("Aktuell (%s).\n", Version)
		}
		return 0
	}
	if *version {
		fmt.Println("wowft-uploader", Version)
		if v := EmbeddedAddonVersion(); v != "" {
			fmt.Println("enthaltenes Addon: WowFT", v)
		} else {
			fmt.Println("enthaltenes Addon: keins (Build ohne go generate)")
		}
		return 0
	}
	if *find {
		fmt.Println("Suche WoW-Installationen …")
		dirs := append(knownWowDirs(), searchWowDirs()...)
		seen := map[string]bool{}
		for _, d := range dirs {
			if seen[d] {
				continue
			}
			seen[d] = true
			fmt.Println(d)
			for _, f := range FindSavedVariables(d) {
				fmt.Println("   ", f)
			}
		}
		if len(seen) == 0 {
			fmt.Println("Nichts gefunden.")
			return 1
		}
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
	// Erste Zeile immer ins Log: So zeigt eine Log-Datei auch dann etwas, wenn der
	// Uploader in der Einrichtung hängen bleibt oder abstürzt.
	logger.Printf("Start: wowft-uploader %s (%s/%s) %s", Version, runtime.GOOS, runtime.GOARCH, strings.Join(os.Args[1:], " "))
	defer func() {
		if r := recover(); r != nil {
			logger.Printf("Absturz: %v\n%s", r, debug.Stack())
			pause()
			os.Exit(2)
		}
	}()

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
		logger.Printf("Einrichtung gestartet (Konfiguration: %s)", *configPath)
		cfg, started, err = interactiveSetup(*configPath, cfg, logger.Writer())
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
		if cfg.AutoAddon() {
			EnsureAddon(cfg.WowDir, logger.Printf)
		}
		files := append(append([]string{}, cfg.Files...), FindSavedVariables(cfg.WowDir)...)
		if len(files) == 0 {
			logger.Printf("Noch keine %s unter %s: im Spiel einloggen, danach /reload oder ausloggen.", svName, cfg.WowDir)
			return 1
		}
		failed := false
		w := NewWatcher(cfg, client, statePath, logger)
		w.CfgPath = *configPath
		for _, f := range files {
			content, err := os.ReadFile(f)
			if err != nil {
				logger.Printf("%s: %v", f, err)
				failed = true
				continue
			}
			w.redeemGameCode(content)
			server, token := EffectiveCredentials(cfg, content)
			if token == "" {
				logger.Printf("%s: noch nicht gekoppelt (-setup, oder Code fürs Spiel im Spiel eintragen)", f)
				failed = true
				continue
			}
			client.SetCredentials(server, token)
			res, err := client.Upload(StripAddonSettings(content))
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
	if v := EmbeddedAddonVersion(); v != "" && cfg.AutoAddon() {
		logger.Printf("Enthaltenes Addon: WowFT %s (wird bei Bedarf installiert bzw. aktualisiert).", v)
	} else if v == "" {
		logger.Printf("Hinweis: In diesem Build ist kein Addon enthalten; es wird nicht automatisch installiert.")
	}
	if cfg.Token == "" {
		logger.Printf("Noch nicht gekoppelt: Ein Token oder Code fürs Spiel aus den Einstellungen im Spiel wird verwendet.")
	}
	w := NewWatcher(cfg, client, statePath, logger)
	w.CfgPath = *configPath
	stop := make(chan struct{})
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sig
		close(stop)
	}()
	if cfg.Updates() {
		go NewUpdater(logger.Printf).RunUpdates(stop)
	}
	w.Run(stop)
	logger.Printf("Beendet.")
	return 0
}

// interactiveSetup fragt alles ab; die Ausgaben gehen auch ins Log (out schreibt auf
// Konsole und Log-Datei), damit sich Probleme bei der Einrichtung später nachvollziehen lassen.
func interactiveSetup(path string, old *Config, out io.Writer) (*Config, bool, error) {
	cfg, err := RunSetup(os.Stdin, out, old)
	if err != nil {
		return nil, false, err
	}
	if err := SaveConfig(path, cfg); err != nil {
		return nil, false, err
	}
	fmt.Fprintf(out, "Gespeichert in %s\n", path)
	if runtime.GOOS != "windows" && runtime.GOOS != "linux" {
		return cfg, false, nil
	}
	fmt.Fprint(out, "Beim Anmelden automatisch im Hintergrund starten? [J/n]: ")
	line, _ := bufio.NewReader(os.Stdin).ReadString('\n')
	if a := strings.ToLower(strings.TrimSpace(line)); a != "" && a != "j" && a != "y" {
		fmt.Fprintln(out, "Kein Autostart.")
		return cfg, false, nil
	}
	started, err := SetAutostart(true, path)
	switch {
	case err != nil:
		fmt.Fprintln(out, "Autostart fehlgeschlagen:", err)
	case started:
		fmt.Fprintln(out, "Autostart eingerichtet. Der Uploader läuft jetzt als Dienst im Hintergrund.")
		fmt.Fprintln(out, "Status: systemctl --user status wowft-uploader · Log: journalctl --user -u wowft-uploader -f")
	default:
		fmt.Fprintln(out, "Autostart eingerichtet (ab der nächsten Anmeldung).")
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
