package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func TestReadNewAndParse(t *testing.T) {
	f := filepath.Join(t.TempDir(), "WoWChatLog.txt")
	writeFile(t, f, "11/8 20:00:00.000  alt\r\n")
	lines, off, err := readNew(f, 0)
	if err != nil || len(lines) != 1 || lines[0] != "11/8 20:00:00.000  alt" {
		t.Fatalf("%v %v", lines, err)
	}
	// halbe Zeile wird erst gelesen, wenn sie vollständig ist
	fh, _ := os.OpenFile(f, os.O_APPEND|os.O_WRONLY, 0)
	fh.WriteString("11/8 20:00:01.000  [Simmen] flüstert: WFTLIVE 1793995200 whisper-vorname")
	if lines, off2, _ := readNew(f, off); len(lines) != 0 || off2 != off {
		t.Fatal("unvollständige Zeile gelesen")
	}
	fh.WriteString("\r\n")
	fh.Close()
	lines, _, _ = readNew(f, off)
	hit, ok := parseLive(lines[0])
	if !ok || hit.Stamp != 1793995200 || hit.Kind != "whisper-vorname" {
		t.Fatalf("%+v %v", hit, ok)
	}
	// Datei neu angelegt (kleiner): von vorn
	writeFile(t, f, "x\n")
	if lines, _, _ := readNew(f, 999); len(lines) != 1 {
		t.Fatal("Neuanlage nicht erkannt")
	}
}

func TestChatLogFilesAndRun(t *testing.T) {
	wow := t.TempDir()
	log := filepath.Join(wow, "_forever_", "logs", "WoWChatLog.txt")
	writeFile(t, log, "vorher WFTLIVE 1000000000 alt\n")
	if got := ChatLogFiles(wow); len(got) != 1 || got[0] != log {
		t.Fatalf("got %v", got)
	}
	var out bytes.Buffer
	stop := make(chan struct{})
	done := make(chan struct{})
	go func() { RunLiveTest(wow, &out, 5*time.Second, stop); close(done) }()
	time.Sleep(400 * time.Millisecond)
	fh, _ := os.OpenFile(log, os.O_APPEND|os.O_WRONLY, 0)
	fh.WriteString("[x] WFTLIVE " + itoa(time.Now().Add(-3*time.Second).Unix()) + " addmessage\n")
	fh.Close()
	time.Sleep(600 * time.Millisecond)
	close(stop)
	<-done
	s := out.String()
	if !strings.Contains(s, "addmessage") || !(strings.Contains(s, "nach 3s") || strings.Contains(s, "nach 4s")) || strings.Contains(s, "alt") {
		t.Fatalf("Ausgabe:\n%s", s)
	}
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }
