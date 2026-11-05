package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

const DefaultServer = "https://wow.the-birds.xyz"

// Config wird als JSON im Benutzer-Konfigurationsordner gespeichert.
type Config struct {
	Server string `json:"server"`
	Token  string `json:"token"`
	// WowDir ist der WoW-Installationsordner; darunter wird WowFT.lua gesucht.
	WowDir string `json:"wowDir"`
	// Files sind zusätzliche, explizit angegebene SavedVariables-Dateien.
	Files []string `json:"files,omitempty"`
	// PollSeconds ist das Prüfintervall (Standard 5).
	PollSeconds int `json:"pollSeconds,omitempty"`
}

func DefaultConfigDir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "wowft"), nil
}

func LoadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var c Config
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, err
	}
	c.normalize()
	return &c, c.Validate()
}

func (c *Config) normalize() {
	c.Server = strings.TrimRight(strings.TrimSpace(c.Server), "/")
	if c.Server == "" {
		c.Server = DefaultServer
	}
	c.Token = strings.TrimSpace(c.Token)
	if c.PollSeconds <= 0 {
		c.PollSeconds = 5
	}
}

func (c *Config) Validate() error {
	if !strings.HasPrefix(c.Token, "wft_") {
		return errors.New("Upload-Token fehlt oder hat das falsche Format (beginnt mit wft_)")
	}
	if !strings.HasPrefix(c.Server, "https://") && !strings.HasPrefix(c.Server, "http://localhost") &&
		!strings.HasPrefix(c.Server, "http://127.0.0.1") {
		return errors.New("Server-Adresse muss mit https:// beginnen")
	}
	if c.WowDir == "" && len(c.Files) == 0 {
		return errors.New("kein WoW-Ordner angegeben")
	}
	return nil
}

func SaveConfig(path string, c *Config) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	// Enthält den Token: nur für den eigenen Benutzer lesbar.
	return os.WriteFile(path, data, 0o600)
}
