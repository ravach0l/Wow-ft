// syncaddon kopiert das Addon (../addon/WowFT) nach addonfiles/WowFT, damit der
// Uploader es einbetten und selbst installieren kann. Aufruf: go generate ./...
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	src := filepath.Join("..", "addon", "WowFT")
	dst := filepath.Join("addonfiles", "WowFT")
	entries, err := os.ReadDir(src)
	if err != nil {
		fmt.Fprintln(os.Stderr, "syncaddon:", err)
		os.Exit(1)
	}
	if err := os.RemoveAll(dst); err != nil {
		fmt.Fprintln(os.Stderr, "syncaddon:", err)
		os.Exit(1)
	}
	if err := os.MkdirAll(dst, 0o755); err != nil {
		fmt.Fprintln(os.Stderr, "syncaddon:", err)
		os.Exit(1)
	}
	n := 0
	for _, e := range entries {
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if e.IsDir() || (ext != ".lua" && ext != ".toc" && ext != ".xml") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(src, e.Name()))
		if err != nil {
			fmt.Fprintln(os.Stderr, "syncaddon:", err)
			os.Exit(1)
		}
		if err := os.WriteFile(filepath.Join(dst, e.Name()), data, 0o644); err != nil {
			fmt.Fprintln(os.Stderr, "syncaddon:", err)
			os.Exit(1)
		}
		n++
	}
	fmt.Printf("syncaddon: %d Dateien nach %s kopiert\n", n, dst)
}
