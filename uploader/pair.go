package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
	"time"
)

// Koppeln statt Token abtippen (Gegenstück: server/wowft/api/pairing.py).
//
//  1. Gerätecode: Der Uploader zeigt einen kurzen Code und öffnet die Webseite;
//     dort bestätigt man mit einem Klick, der Uploader holt sich den Token ab.
//  2. Code fürs Spiel: Auf der Webseite erzeugt man WFT-XXXX-XXXX, trägt ihn im Spiel
//     ins Token-Feld ein und tippt /reload; der Uploader tauscht ihn gegen einen Token.

type PairStart struct {
	UserCode   string `json:"userCode"`
	DeviceCode string `json:"deviceCode"`
	VerifyURL  string `json:"verifyUrl"`
	ExpiresIn  int    `json:"expiresIn"`
	Interval   int    `json:"interval"`
}

type pairResult struct {
	Status   string `json:"status"`
	Token    string `json:"token"`
	UserName string `json:"userName"`
}

var gameCodeRe = regexp.MustCompile(`^WFT[A-HJ-NP-Z2-9]{8}$`)

// NormalizeCode entfernt Leerzeichen und Bindestriche und schreibt groß.
func NormalizeCode(s string) string {
	return strings.ToUpper(strings.NewReplacer(" ", "", "-", "", "\t", "").Replace(s))
}

// IsGameCode erkennt einen Code fürs Spiel (WFT-XXXX-XXXX, Schreibweise egal).
func IsGameCode(s string) bool {
	return gameCodeRe.MatchString(NormalizeCode(s))
}

// DeviceName ist der Name, unter dem der Token im Profil erscheint.
func DeviceName() string {
	if h, err := os.Hostname(); err == nil && h != "" {
		return h
	}
	return "Uploader"
}

func (c *Client) postJSON(path string, in, out any) error {
	body, err := json.Marshal(in)
	if err != nil {
		return err
	}
	data, err := c.post(path, "application/json", bytes.NewReader(body), false)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, out); err != nil {
		return &UploadError{Message: "unerwartete Antwort"}
	}
	return nil
}

func (c *Client) StartPairing(deviceName string) (*PairStart, error) {
	var s PairStart
	if err := c.postJSON("/api/pair/start", map[string]string{"deviceName": deviceName}, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// PollPairing gibt den Token zurück, sobald die Kopplung bestätigt ist ("" = noch offen).
func (c *Client) PollPairing(deviceCode string) (token, user string, err error) {
	var r pairResult
	if err := c.postJSON("/api/pair/poll", map[string]string{"deviceCode": deviceCode}, &r); err != nil {
		return "", "", err
	}
	if r.Status != "ok" {
		return "", "", nil
	}
	return r.Token, r.UserName, nil
}

// RedeemGameCode tauscht einen Code aus dem Spiel gegen einen Upload-Token.
func (c *Client) RedeemGameCode(code, deviceName string) (token, user string, err error) {
	var r pairResult
	in := map[string]string{"code": NormalizeCode(code), "deviceName": deviceName}
	if err := c.postJSON("/api/pair/redeem", in, &r); err != nil {
		return "", "", err
	}
	if r.Status != "ok" || !strings.HasPrefix(r.Token, "wft_") {
		return "", "", &UploadError{Message: "unerwartete Antwort"}
	}
	return r.Token, r.UserName, nil
}

// Austauschbar für Tests.
var (
	pairSleep   = time.Sleep
	openBrowser = openBrowserDefault
)

func openBrowserDefault(url string) error {
	switch runtime.GOOS {
	case "windows":
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	case "darwin":
		return exec.Command("open", url).Start()
	default:
		return exec.Command("xdg-open", url).Start()
	}
}

// PairDevice zeigt den Code, öffnet den Browser und wartet auf die Bestätigung.
func PairDevice(c *Client, out io.Writer) (token string, err error) {
	s, err := c.StartPairing(DeviceName())
	if err != nil {
		return "", fmt.Errorf("Server nicht erreichbar: %w", err)
	}
	fmt.Fprintln(out)
	fmt.Fprintln(out, "  Uploader mit deinem Konto koppeln")
	fmt.Fprintln(out)
	fmt.Fprintf(out, "      Code:  %s\n", s.UserCode)
	fmt.Fprintln(out)
	fmt.Fprintf(out, "  Öffne %s\n", s.VerifyURL)
	fmt.Fprintln(out, "  (passiert gleich von selbst), melde dich an und klicke auf „Koppeln“.")
	fmt.Fprintln(out, "  Warte auf die Bestätigung … (Abbrechen mit Strg+C)")
	_ = openBrowser(s.VerifyURL)

	interval := time.Duration(max(1, s.Interval)) * time.Second
	deadline := time.Now().Add(time.Duration(s.ExpiresIn) * time.Second)
	for time.Now().Before(deadline) {
		pairSleep(interval)
		tok, user, err := c.PollPairing(s.DeviceCode)
		if err != nil {
			var ue *UploadError
			if errors.As(err, &ue) && ue.Permanent {
				return "", fmt.Errorf("Kopplung abgebrochen: %w", err)
			}
			continue // Netz kurz weg: weiter warten
		}
		if tok != "" {
			fmt.Fprintf(out, "  Gekoppelt mit dem Konto „%s“.\n\n", user)
			return tok, nil
		}
	}
	return "", errors.New("Zeit abgelaufen. Bitte den Uploader neu starten oder -setup verwenden")
}
