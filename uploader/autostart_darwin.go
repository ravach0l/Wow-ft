//go:build darwin

package main

import "errors"

func SetAutostart(bool, string) (bool, error) {
	return false, errors.New("Autostart ist unter macOS noch nicht umgesetzt")
}
