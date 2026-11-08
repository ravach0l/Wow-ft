package main

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"time"
)

// Messtest für „fast live“ (Gegenstück: addon/WowFT/Live.lua, /ft livetest).
// Liest Logs/WoWChatLog.txt mit und zeigt, welche WFTLIVE-Zeilen ankommen und mit welcher
// Verzögerung seit dem Absenden im Spiel.

var liveLineRe = regexp.MustCompile(`WFTLIVE (\d{9,11}) (\S+)`)

// ChatLogFiles findet WoWChatLog.txt in allen Spielordnern unter wowDir.
func ChatLogFiles(wowDir string) []string {
	roots := []string{wowDir}
	if entries, err := os.ReadDir(wowDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				roots = append(roots, filepath.Join(wowDir, e.Name()))
			}
		}
	}
	var out []string
	for _, r := range roots {
		if f := childFold(childFold(r, "Logs"), "WoWChatLog.txt"); f != "" {
			out = append(out, f)
		}
	}
	return out
}

// LiveHit ist eine gefundene Testzeile.
type LiveHit struct {
	Stamp int64
	Kind  string
	Line  string
}

// readNew liest ab offset neu hinzugekommene vollständige Zeilen und liefert den neuen Offset.
// Wird die Datei kleiner (neu angelegt), beginnt es von vorn.
func readNew(path string, offset int64) ([]string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, offset, err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return nil, offset, err
	}
	if st.Size() < offset {
		offset = 0
	}
	if st.Size() == offset {
		return nil, offset, nil
	}
	if _, err := f.Seek(offset, io.SeekStart); err != nil {
		return nil, offset, err
	}
	data, err := io.ReadAll(io.LimitReader(f, 4<<20))
	if err != nil {
		return nil, offset, err
	}
	end := bytes.LastIndexByte(data, '\n')
	if end < 0 {
		return nil, offset, nil // noch keine vollständige Zeile
	}
	var lines []string
	for _, l := range bytes.Split(data[:end], []byte("\n")) {
		lines = append(lines, string(bytes.TrimRight(l, "\r")))
	}
	return lines, offset + int64(end) + 1, nil
}

func parseLive(line string) (LiveHit, bool) {
	m := liveLineRe.FindStringSubmatch(line)
	if m == nil {
		return LiveHit{}, false
	}
	stamp, _ := strconv.ParseInt(m[1], 10, 64)
	return LiveHit{Stamp: stamp, Kind: m[2], Line: line}, true
}

// RunLiveTest beobachtet die Chat-Protokolle bis zum Ablauf von maxWait.
func RunLiveTest(wowDir string, out io.Writer, maxWait time.Duration, stop <-chan struct{}) {
	fmt.Fprintln(out, "Fast-live-Messtest: Im Spiel /ft livetest eingeben (gern mehrmals, im Abstand von einer Minute).")
	fmt.Fprintln(out, "Hier erscheint, welche Testzeilen in WoWChatLog.txt ankommen und wie spät. Beenden mit Strg+C.")
	offsets := map[string]int64{}
	announced := map[string]bool{}
	deadline := time.Now().Add(maxWait)
	tick := time.NewTicker(250 * time.Millisecond)
	defer tick.Stop()
	for time.Now().Before(deadline) {
		for _, f := range ChatLogFiles(wowDir) {
			if !announced[f] {
				announced[f] = true
				if st, err := os.Stat(f); err == nil {
					offsets[f] = st.Size() // nur Neues zählt
				}
				fmt.Fprintf(out, "Beobachte %s\n", f)
			}
			lines, off, err := readNew(f, offsets[f])
			if err != nil {
				continue
			}
			offsets[f] = off
			for _, l := range lines {
				if hit, ok := parseLive(l); ok {
					delay := time.Since(time.Unix(hit.Stamp, 0)).Round(time.Second)
					fmt.Fprintf(out, "%s  angekommen: %-18s nach %s\n", time.Now().Format("15:04:05"), hit.Kind, delay)
				}
			}
		}
		if len(announced) == 0 && time.Now().Second()%15 == 0 {
			fmt.Fprintln(out, "Noch keine Logs/WoWChatLog.txt – /ft livetest schaltet das Chat-Protokoll ein.")
		}
		select {
		case <-stop:
			return
		case <-tick.C:
		}
	}
	fmt.Fprintln(out, "Messtest beendet.")
}
