//go:build linux

package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const unitName = "wowft-uploader.service"

func systemdUnit(exe, configPath string) string {
	return fmt.Sprintf(`[Unit]
Description=WowFT-Uploader (WoW Forever Freundes-Tracker)
After=network-online.target

[Service]
ExecStart=%s -config %s
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
`, systemdQuote(exe), systemdQuote(configPath))
}

func desktopEntry(exe, configPath string) string {
	return fmt.Sprintf(`[Desktop Entry]
Type=Application
Name=WowFT-Uploader
Exec=%s -config %s
X-GNOME-Autostart-enabled=true
NoDisplay=true
`, desktopQuote(exe), desktopQuote(configPath))
}

func systemdQuote(s string) string {
	return `"` + strings.NewReplacer(`\`, `\\`, `"`, `\"`, "%", "%%").Replace(s) + `"`
}

func desktopQuote(s string) string {
	return `"` + strings.NewReplacer(`\`, `\\\\`, `"`, `\"`, "`", "\\`", "$", `\$`).Replace(s) + `"`
}

func hasSystemdUser() bool {
	return exec.Command("systemctl", "--user", "show-environment").Run() == nil
}

// SetAutostart richtet einen systemd-Benutzerdienst ein (startet ihn sofort)
// oder, ohne systemd, einen XDG-Autostart-Eintrag für die Desktop-Anmeldung.
// started ist true, wenn der Uploader jetzt bereits im Hintergrund läuft.
func SetAutostart(enable bool, configPath string) (started bool, err error) {
	cfgDir, err := os.UserConfigDir()
	if err != nil {
		return false, err
	}
	unitPath := filepath.Join(cfgDir, "systemd", "user", unitName)
	desktopPath := filepath.Join(cfgDir, "autostart", "wowft-uploader.desktop")

	if !enable {
		if hasSystemdUser() {
			_ = exec.Command("systemctl", "--user", "disable", "--now", unitName).Run()
		}
		_ = os.Remove(unitPath)
		_ = os.Remove(desktopPath)
		if hasSystemdUser() {
			_ = exec.Command("systemctl", "--user", "daemon-reload").Run()
		}
		return false, nil
	}

	exe, err := os.Executable()
	if err != nil {
		return false, err
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	if configPath, err = filepath.Abs(configPath); err != nil {
		return false, err
	}

	if hasSystemdUser() {
		if err := writeTextFile(unitPath, systemdUnit(exe, configPath)); err != nil {
			return false, err
		}
		for _, args := range [][]string{{"daemon-reload"}, {"enable", "--now", unitName}, {"restart", unitName}} {
			if out, err := exec.Command("systemctl", append([]string{"--user"}, args...)...).CombinedOutput(); err != nil {
				return false, fmt.Errorf("systemctl --user %s: %v: %s", strings.Join(args, " "), err, out)
			}
		}
		return true, nil
	}
	if err := writeTextFile(desktopPath, desktopEntry(exe, configPath)); err != nil {
		return false, errors.Join(errors.New("kein systemd gefunden, XDG-Autostart fehlgeschlagen"), err)
	}
	return false, nil
}

func writeTextFile(path, content string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0o644)
}
