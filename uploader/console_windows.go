//go:build windows

package main

import (
	"os/exec"
	"syscall"
	"time"
)

// hideConsole versteckt das Konsolenfenster (für den Autostart).
func hideConsole() {
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	user32 := syscall.NewLazyDLL("user32.dll")
	hwnd, _, _ := kernel32.NewProc("GetConsoleWindow").Call()
	if hwnd != 0 {
		user32.NewProc("ShowWindow").Call(hwnd, 0) // SW_HIDE
	}
}

// startBackground startet den Uploader losgelöst von diesem Konsolenfenster im Hintergrund.
func startBackground(configPath string) error {
	exe, err := executablePath()
	if err != nil {
		return err
	}
	cmd := exec.Command(exe, "-background", "-config", configPath)
	// DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: kein Konsolenfenster, unabhängig vom Elternprozess.
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000008 | 0x00000200}
	if err := cmd.Start(); err != nil {
		return err
	}
	return cmd.Process.Release()
}

// closeDelay lässt die Abschlussmeldung kurz stehen, bevor sich das Fenster schließt.
func closeDelay() { time.Sleep(6 * time.Second) }
