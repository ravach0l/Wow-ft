//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
)

const runKey = `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

// SetAutostart trägt den Uploader beim Windows-Start ein oder aus.
func SetAutostart(enable bool) error {
	if !enable {
		return exec.Command("reg", "delete", runKey, "/v", "WowFT", "/f").Run()
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	value := fmt.Sprintf(`"%s" -background`, exe)
	return exec.Command("reg", "add", runKey, "/v", "WowFT", "/t", "REG_SZ", "/d", value, "/f").Run()
}
