//go:build !windows

package main

import "errors"

// SetAutostart ist nur unter Windows umgesetzt. Unter Linux siehe
// deploy/wowft-uploader.service (systemd --user).
func SetAutostart(bool) error {
	return errors.New("Autostart gibt es nur unter Windows; unter Linux die systemd-Unit verwenden")
}
