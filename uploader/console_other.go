//go:build !windows

package main

import "errors"

func hideConsole() {}

// startBackground ist nur unter Windows nötig (unter Linux übernimmt systemd).
func startBackground(string) error {
	return errors.New("nur unter Windows")
}

func closeDelay() {}
