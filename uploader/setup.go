package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// pairDevice ist austauschbar, damit Tests ohne Server und Browser auskommen.
var pairDevice = func(server string, out io.Writer) (string, error) {
	return PairDevice(NewClient(server, ""), out)
}

// redeemCode tauscht einen Code fürs Spiel direkt im Einrichtungsdialog ein.
var redeemCode = func(server, code string) (string, error) {
	tok, _, err := NewClient(server, "").RedeemGameCode(code, DeviceName())
	return tok, err
}

// RunSetup richtet den Uploader ein. Reihenfolge mit Absicht: erst der WoW-Ordner (nur bei
// mehreren Kandidaten eine Frage), dann das Addon, zum Schluss das Koppeln. Beim Koppeln
// öffnet sich der Browser und rückt in den Vordergrund; danach darf keine Frage mehr im
// Konsolenfenster warten, die niemand sieht.
func RunSetup(in io.Reader, out io.Writer, old *Config) (*Config, error) {
	r := bufio.NewReader(in)
	ask := func(prompt, def string) (string, error) {
		if def != "" {
			fmt.Fprintf(out, "%s [%s]: ", prompt, def)
		} else {
			fmt.Fprintf(out, "%s: ", prompt)
		}
		line, err := r.ReadString('\n')
		if err != nil && line == "" {
			return "", err
		}
		line = strings.TrimSpace(line)
		if line == "" {
			return def, nil
		}
		return line, nil
	}

	c := &Config{Server: DefaultServer}
	if old != nil {
		*c = *old
	}
	c.normalize()
	if !validServer(c.Server) {
		return nil, errors.New("Server-Adresse muss mit https:// beginnen")
	}
	fmt.Fprintln(out, "WowFT-Uploader einrichten")
	fmt.Fprintf(out, "Server: %s\n\n", c.Server)

	// 1. WoW-Ordner
	dir, err := chooseWowDir(ask, out, c.WowDir)
	if err != nil {
		return nil, err
	}
	c.WowDir = dir
	if c.WowDir == "" {
		return nil, errors.New("kein WoW-Ordner angegeben")
	}

	// 2. Addon
	if c.AutoAddon() {
		EnsureAddon(c.WowDir, func(format string, args ...any) { fmt.Fprintf(out, format+"\n", args...) })
	}
	files := FindSavedVariables(c.WowDir)
	for _, f := range files {
		fmt.Fprintf(out, "Gefunden: %s\n", f)
	}

	// 3. Koppeln – zuletzt, danach keine Fragen mehr.
	if c.Token != "" {
		answer, err := ask(fmt.Sprintf("Schon gekoppelt (%s…). Neu koppeln? [j/N]", c.Token[:min(10, len(c.Token))]), "")
		if err != nil {
			return nil, err
		}
		if a := strings.ToLower(answer); a == "j" || a == "y" {
			if c.Token, err = pairOrManual(ask, out, c.Server); err != nil {
				return nil, err
			}
		}
	} else if c.Token, err = pairOrManual(ask, out, c.Server); err != nil {
		return nil, err
	}

	c.normalize()
	if err := c.Validate(); err != nil {
		return nil, err
	}
	if len(files) == 0 {
		fmt.Fprintf(out, "Noch keine %s: Im Spiel einloggen; danach schickt der Uploader den Stand bei jedem Logout oder /reload.\n", svName)
	}
	return c, nil
}

// chooseWowDir fragt nur, wenn es nicht eindeutig ist: ein gefundener Ordner wird ohne Frage
// übernommen, mehrere werden zur Auswahl gestellt, keiner heißt: Pfad eingeben.
func chooseWowDir(ask func(string, string) (string, error), out io.Writer, current string) (string, error) {
	if current != "" {
		return ask("WoW-Ordner", current)
	}
	guesses := knownWowDirs()
	if len(guesses) == 0 {
		fmt.Fprintln(out, "Suche die WoW-Installation auf diesem Rechner (bis zu 20 Sekunden) …")
		guesses = sortByFound(searchWowDirs())
	}
	switch len(guesses) {
	case 0:
		fmt.Fprintln(out, "Nichts gefunden. Bitte den Ordner angeben, in dem die WoW-Programmdatei liegt.")
		return ask("WoW-Ordner", "")
	case 1:
		fmt.Fprintf(out, "WoW-Ordner: %s\n", guesses[0])
		return guesses[0], nil
	}
	fmt.Fprintln(out, "Gefundene WoW-Ordner:")
	for i, g := range guesses {
		fmt.Fprintf(out, "  %d) %s\n", i+1, g)
	}
	dir, err := ask("Welcher? Nummer oder Pfad", "1")
	if err != nil {
		return "", err
	}
	if n, convErr := strconv.Atoi(dir); convErr == nil && n >= 1 && n <= len(guesses) {
		return guesses[n-1], nil
	}
	return dir, nil
}

// pairOrManual koppelt über den Browser. Klappt das nicht (Server nicht erreichbar,
// abgelaufen), kann man einen Token oder Code fürs Spiel einfügen oder es später machen.
func pairOrManual(ask func(string, string) (string, error), out io.Writer, server string) (string, error) {
	tok, err := pairDevice(server, out)
	if err == nil {
		return tok, nil
	}
	fmt.Fprintf(out, "Koppeln hat nicht geklappt: %v\n", err)
	fmt.Fprintln(out, "Du kannst einen Token oder einen Code fürs Spiel (Webseite → Profil) einfügen,")
	fmt.Fprintln(out, "oder leer lassen und den Code später im Spiel eintragen.")
	tok, err = ask("Token oder Code", "")
	if err != nil || tok == "" {
		return "", nil
	}
	if IsGameCode(tok) {
		if tok, err = redeemCode(server, tok); err != nil {
			return "", fmt.Errorf("Code nicht eingelöst: %w", err)
		}
	}
	return tok, nil
}
