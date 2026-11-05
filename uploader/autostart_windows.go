//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)

const runKey = `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

// SetAutostart trägt den Uploader beim Windows-Start ein oder aus.
// started ist immer false: der Eintrag wirkt erst beim nächsten Anmelden.
func SetAutostart(enable bool, configPath string) (started bool, err error) {
	if !enable {
		return false, exec.Command("reg", "delete", runKey, "/v", "WowFT", "/f").Run()
	}
	exe, err := os.Executable()
	if err != nil {
		return false, err
	}
	if configPath, err = filepath.Abs(configPath); err != nil {
		return false, err
	}
	value := fmt.Sprintf(`"%s" -background -config "%s"`, exe, configPath)
	return false, exec.Command("reg", "add", runKey, "/v", "WowFT", "/t", "REG_SZ", "/d", value, "/f").Run()
}
