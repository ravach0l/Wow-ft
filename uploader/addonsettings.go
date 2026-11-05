package main

import (
	"bytes"
	"regexp"
	"strings"
)

// Das Addon speichert Server und Upload-Token, die man im Spiel unter
// „Einstellungen“ einträgt, im Block WowFTDB.upload:
//
//	["upload"] = {
//	["server"] = "https://…",
//	["token"] = "wft_…",
//	},
//
// WoW schreibt SavedVariables ohne Einrückung; der Block enthält keine
// verschachtelten Tabellen und endet daher an der ersten Zeile "}".
var (
	uploadBlockStart = []byte(`["upload"] = {`)
	tokenValueRe     = regexp.MustCompile(`(\["token"\]\s*=\s*")[^"\\]*(")`)
	tokenReadRe      = regexp.MustCompile(`\["token"\]\s*=\s*"([^"\\]*)"`)
	serverReadRe     = regexp.MustCompile(`\["server"\]\s*=\s*"([^"\\]*)"`)
)

// AddonSettings sind die im Spiel eingetragenen Zugangsdaten (können leer sein).
type AddonSettings struct {
	Server string
	Token  string
}

// uploadBlock liefert Anfang und Ende (Ende ohne die schließende Klammer) des upload-Blocks.
func uploadBlock(content []byte) (start, end int, ok bool) {
	i := bytes.Index(content, uploadBlockStart)
	if i < 0 {
		return 0, 0, false
	}
	j := bytes.Index(content[i:], []byte("\n}"))
	if j < 0 {
		return 0, 0, false
	}
	return i, i + j, true
}

// ReadAddonSettings liest Server und Token aus dem upload-Block der Datei.
func ReadAddonSettings(content []byte) AddonSettings {
	start, end, ok := uploadBlock(content)
	if !ok {
		return AddonSettings{}
	}
	block := content[start:end]
	var s AddonSettings
	if m := serverReadRe.FindSubmatch(block); m != nil {
		s.Server = strings.TrimRight(strings.TrimSpace(string(m[1])), "/")
	}
	if m := tokenReadRe.FindSubmatch(block); m != nil {
		s.Token = strings.TrimSpace(string(m[1]))
	}
	return s
}

// StripAddonSettings leert den Token im upload-Block. Der Token soll den Rechner
// nie als Teil der hochgeladenen Daten verlassen; er geht nur im Authorization-Header mit.
func StripAddonSettings(content []byte) []byte {
	start, end, ok := uploadBlock(content)
	if !ok {
		return content
	}
	block := tokenValueRe.ReplaceAll(content[start:end], []byte(`${1}${2}`))
	out := make([]byte, 0, len(content))
	out = append(out, content[:start]...)
	out = append(out, block...)
	out = append(out, content[end:]...)
	return out
}

func validServer(s string) bool {
	return strings.HasPrefix(s, "https://") || strings.HasPrefix(s, "http://localhost") ||
		strings.HasPrefix(s, "http://127.0.0.1")
}

// EffectiveCredentials bestimmt Server und Token für einen Upload. Was im Spiel
// eingetragen wurde, hat Vorrang vor der Konfigurationsdatei (es ist das Neuere);
// ungültige Werte aus dem Spiel werden ignoriert. Ein leerer Token heißt: keiner vorhanden.
func EffectiveCredentials(cfg *Config, content []byte) (server, token string) {
	server, token = cfg.Server, cfg.Token
	a := ReadAddonSettings(content)
	if strings.HasPrefix(a.Token, "wft_") {
		token = a.Token
	}
	if a.Server != "" && validServer(a.Server) {
		server = a.Server
	}
	return server, token
}

// Credentialed ist für Uploader, deren Zugangsdaten sich pro Datei ändern können.
type Credentialed interface {
	SetCredentials(server, token string)
}
