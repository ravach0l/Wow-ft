package main

import (
	"bufio"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// RunSetup fragt Server, Token und WoW-Ordner ab. Vorhandene Werte sind Vorgaben.
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
	fmt.Fprintln(out, "Den Upload-Token erzeugst du auf der Webseite unter „Profil“.")
	fmt.Fprintln(out, "Du kannst ihn auch im Spiel unter Einstellungen (Minimap-Button) eintragen;")
	fmt.Fprintln(out, "dann hier einfach Enter drücken.")
	fmt.Fprintln(out)

	var err error
	if c.Server, err = ask("Server", c.Server); err != nil {
		return nil, err
	}
	tokenDefault := ""
	if c.Token != "" {
		tokenDefault = c.Token[:min(10, len(c.Token))] + "…"
	}
	tok, err := ask("Upload-Token", tokenDefault)
	if err != nil {
		return nil, err
	}
	if tok != tokenDefault {
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
