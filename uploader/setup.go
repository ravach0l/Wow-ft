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

// RunSetup fragt Server, Kopplung und WoW-Ordner ab. Vorhandene Werte sind Vorgaben.
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
	fmt.Fprintln(out, "WowFT-Uploader einrichten")
	fmt.Fprintln(out)

	var err error
	if c.Server, err = ask("Server", c.Server); err != nil {
		return nil, err
	}
	c.normalize()
	if !validServer(c.Server) {
		return nil, errors.New("Server-Adresse muss mit https:// beginnen")
	}

	// Koppeln: Der Uploader holt sich den Token selbst, man bestätigt nur im Browser.
	question := "Uploader jetzt mit deinem Konto koppeln? [J/n]"
	if c.Token != "" {
		question = fmt.Sprintf("Schon gekoppelt (%s…). Neu koppeln? [j/N]", c.Token[:min(10, len(c.Token))])
	}
	answer, err := ask(question, "")
	if err != nil {
		return nil, err
	}
	answer = strings.ToLower(answer)
	wantPair := answer == "j" || answer == "y" || (c.Token == "" && answer == "")
	switch {
	case wantPair:
		tok, err := pairDevice(c.Server, out)
		if err != nil {
			return nil, err
		}
		c.Token = tok
	case c.Token == "" && (answer == "n" || answer == "nein"):
		fmt.Fprintln(out, "Dann den Token hier einfügen, oder leer lassen und später auf der Webseite")
		fmt.Fprintln(out, "unter Profil einen Code fürs Spiel erzeugen und ihn im Spiel eintragen.")
		tok, err := ask("Upload-Token oder Code fürs Spiel", "")
		if err != nil {
			return nil, err
		}
		if IsGameCode(tok) {
			if tok, err = redeemCode(c.Server, tok); err != nil {
				return nil, fmt.Errorf("Code nicht eingelöst: %w", err)
			}
		}
		c.Token = tok
	}

	guesses := knownWowDirs()
	if len(guesses) == 0 {
		fmt.Fprintln(out, "Suche die WoW-Installation auf diesem Rechner (bis zu 20 Sekunden) …")
		guesses = sortByFound(searchWowDirs())
	}
	if len(guesses) == 0 {
		fmt.Fprintln(out, "Nichts gefunden. Bitte den Ordner angeben, in dem die WoW-Programmdatei liegt.")
	}
	def := c.WowDir
	if def == "" && len(guesses) > 0 {
		def = guesses[0]
	}
	if len(guesses) > 1 {
		fmt.Fprintln(out, "Gefundene WoW-Ordner:")
		for i, g := range guesses {
			fmt.Fprintf(out, "  %d) %s\n", i+1, g)
		}
	}
	dir, err := ask("WoW-Ordner (oder Nummer)", def)
	if err != nil {
		return nil, err
	}
	if n, convErr := strconv.Atoi(dir); convErr == nil && n >= 1 && n <= len(guesses) {
		dir = guesses[n-1]
	}
	c.WowDir = dir
	c.normalize()
	if err := c.Validate(); err != nil {
		return nil, err
	}
	files := FindSavedVariables(c.WowDir)
	if len(files) == 0 {
		fmt.Fprintf(out, "Hinweis: noch keine %s gefunden. Das Addon installieren, einloggen und /reload eingeben.\n", svName)
	} else {
		for _, f := range files {
			fmt.Fprintf(out, "Gefunden: %s\n", f)
		}
	}
	return c, nil
}
