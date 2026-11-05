package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

var Version = "0.1.0"

type Result struct {
	Characters int      `json:"characters"`
	Snapshots  int      `json:"snapshots"`
	Events     int      `json:"events"`
	Skipped    []string `json:"skipped"`
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

func (c *Client) Upload(content []byte) (*Result, error) {
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	if _, err := zw.Write(content); err != nil {
		return nil, err
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, c.Server+"/api/ingest", &buf)
	if err != nil {
		return nil, &UploadError{Message: err.Error(), Permanent: true}
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", "text/x-lua; charset=utf-8")
	req.Header.Set("Content-Encoding", "gzip")
	req.Header.Set("User-Agent", "wowft-uploader/"+Version)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, &UploadError{Message: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))

	if resp.StatusCode != http.StatusOK {
		var detail struct {
			Detail any `json:"detail"`
		}
		msg := string(body)
		if json.Unmarshal(body, &detail) == nil && detail.Detail != nil {
			msg = fmt.Sprint(detail.Detail)
		}
		permanent := resp.StatusCode >= 400 && resp.StatusCode < 500 && resp.StatusCode != http.StatusTooManyRequests
		return nil, &UploadError{Status: resp.StatusCode, Message: msg, Permanent: permanent}
	}
	var r Result
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, &UploadError{Status: resp.StatusCode, Message: "unerwartete Antwort"}
	}
	return &r, nil
}
