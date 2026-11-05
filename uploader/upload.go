package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"
)

var Version = "0.1.0"

type PhotoRequest struct {
	CharacterID int    `json:"characterId"`
	Name        string `json:"name"`
	T           int64  `json:"t"`
}

type Result struct {
	Characters    int            `json:"characters"`
	Snapshots     int            `json:"snapshots"`
	Events        int            `json:"events"`
	Skipped       []string       `json:"skipped"`
	PhotoRequests []PhotoRequest `json:"photoRequests"`
}

// UploadError unterscheidet dauerhafte Fehler (Datei/Token kaputt) von
// vorübergehenden (Netz, Server, Rate-Limit).
type UploadError struct {
	Status    int
	Message   string
	Permanent bool
}

func (e *UploadError) Error() string {
	if e.Status == 0 {
		return e.Message
	}
	return fmt.Sprintf("HTTP %d: %s", e.Status, e.Message)
}

type Client struct {
	Server string
	Token  string
	HTTP   *http.Client
}

func NewClient(server, token string) *Client {
	return &Client{Server: server, Token: token, HTTP: &http.Client{Timeout: 60 * time.Second}}
}

// SetCredentials ersetzt Server und Token (z. B. mit den im Spiel eingetragenen Werten).
func (c *Client) SetCredentials(server, token string) {
	c.Server, c.Token = server, token
}

func (c *Client) post(path, contentType string, body io.Reader, gzipped bool) ([]byte, error) {
	req, err := http.NewRequest(http.MethodPost, c.Server+path, body)
	if err != nil {
		return nil, &UploadError{Message: err.Error(), Permanent: true}
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", contentType)
	if gzipped {
		req.Header.Set("Content-Encoding", "gzip")
	}
	req.Header.Set("User-Agent", "wowft-uploader/"+Version)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, &UploadError{Message: err.Error()}
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var detail struct {
			Detail any `json:"detail"`
		}
		msg := string(data)
		if json.Unmarshal(data, &detail) == nil && detail.Detail != nil {
			msg = fmt.Sprint(detail.Detail)
		}
		permanent := resp.StatusCode >= 400 && resp.StatusCode < 500 && resp.StatusCode != http.StatusTooManyRequests
		return nil, &UploadError{Status: resp.StatusCode, Message: msg, Permanent: permanent}
	}
	return data, nil
}

func (c *Client) Upload(content []byte) (*Result, error) {
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	if _, err := zw.Write(content); err != nil {
		return nil, err
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	data, err := c.post("/api/ingest", "text/x-lua; charset=utf-8", &buf, true)
	if err != nil {
		return nil, err
	}
	var r Result
	if err := json.Unmarshal(data, &r); err != nil {
		return nil, &UploadError{Message: "unerwartete Antwort"}
	}
	return &r, nil
}

// UploadPhoto schickt ein Charakterbild. Ein schon vorhandenes Foto (409) gilt als Erfolg.
func (c *Client) UploadPhoto(characterID int, t int64, jpegData []byte) error {
	path := fmt.Sprintf("/api/characters/%d/photos?t=%d", characterID, t)
	_, err := c.post(path, "image/jpeg", bytes.NewReader(jpegData), false)
	var ue *UploadError
	if errors.As(err, &ue) && ue.Status == http.StatusConflict {
		return nil
	}
	return err
}
