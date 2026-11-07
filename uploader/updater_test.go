package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// fakeRelease spielt die GitHub-API und die Release-Dateien nach.
func fakeRelease(t *testing.T, tag string, bin []byte, sum string) *httptest.Server {
	t.Helper()
	name := AssetName(runtime.GOOS, runtime.GOARCH)
	if sum == "" {
		h := sha256.Sum256(bin)
		sum = hex.EncodeToString(h[:])
	}
	var srv *httptest.Server
	srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/latest":
			json.NewEncoder(w).Encode(map[string]any{
				"tag_name": tag,
				"assets": []map[string]string{
					{"name": name, "browser_download_url": srv.URL + "/dl/" + name},
					{"name": "SHA256SUMS.txt", "browser_download_url": srv.URL + "/dl/SHA256SUMS.txt"},
				},
			})
		case "/dl/SHA256SUMS.txt":
			fmt.Fprintf(w, "%s  %s\n%s  WowFT-addon.zip\n", sum, name, strings.Repeat("0", 64))
		case "/dl/" + name:
			w.Write(bin)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

// withFakeExe ersetzt die laufende Datei durch eine Testdatei.
func withFakeExe(t *testing.T, version string) string {
	t.Helper()
	exe := filepath.Join(t.TempDir(), "wowft-uploader")
	if err := os.WriteFile(exe, []byte("alt"), 0o755); err != nil {
		t.Fatal(err)
	}
	oldVersion, oldPath, oldAPI := Version, executablePath, updateAPI
	Version = version
	executablePath = func() (string, error) { return exe, nil }
	t.Cleanup(func() { Version, executablePath, updateAPI = oldVersion, oldPath, oldAPI })
	return exe
}

func TestUpdateReplacesExecutable(t *testing.T) {
	exe := withFakeExe(t, "0.3.1")
	srv := fakeRelease(t, "v0.4.0", []byte("neu"), "")
	updateAPI = srv.URL + "/latest"

	res, err := NewUpdater(t.Logf).Check()
	if err != nil || !res.Replaced || res.Latest != "0.4.0" {
		t.Fatalf("%+v %v", res, err)
	}
	if data, _ := os.ReadFile(exe); string(data) != "neu" {
		t.Fatalf("Datei: %q", data)
	}
	if runtime.GOOS != "windows" {
		if _, err := os.Stat(exe + ".old"); !os.IsNotExist(err) {
			t.Fatal("alte Datei übrig")
		}
	}
	if st, _ := os.Stat(exe); st.Mode().Perm()&0o100 == 0 {
		t.Fatal("neue Datei nicht ausführbar")
	}
	if _, err := os.Stat(exe + ".new"); !os.IsNotExist(err) {
		t.Fatal("Zwischendatei übrig")
	}
}

func TestUpdateSkipsWhenCurrentOrDev(t *testing.T) {
	for _, tc := range []struct{ version, tag string }{{"0.4.0", "v0.4.0"}, {"0.5.0", "v0.4.0"}, {"dev", "v9.9.9"}} {
		exe := withFakeExe(t, tc.version)
		srv := fakeRelease(t, tc.tag, []byte("neu"), "")
		updateAPI = srv.URL + "/latest"
		res, err := NewUpdater(t.Logf).Check()
		if err != nil || res.Replaced {
			t.Fatalf("%s/%s: %+v %v", tc.version, tc.tag, res, err)
		}
		if data, _ := os.ReadFile(exe); string(data) != "alt" {
			t.Fatalf("%s: Datei verändert", tc.version)
		}
	}
}

func TestUpdateRejectsBadChecksum(t *testing.T) {
	exe := withFakeExe(t, "0.3.1")
	srv := fakeRelease(t, "v0.4.0", []byte("manipuliert"), strings.Repeat("a", 64))
	updateAPI = srv.URL + "/latest"
	res, err := NewUpdater(t.Logf).Check()
	if err == nil || res.Replaced || !strings.Contains(err.Error(), "Prüfsumme") {
		t.Fatalf("%+v %v", res, err)
	}
	if data, _ := os.ReadFile(exe); string(data) != "alt" {
		t.Fatal("Datei trotz falscher Prüfsumme ersetzt")
	}
}

func TestUpdateWithoutChecksumsFails(t *testing.T) {
	withFakeExe(t, "0.3.1")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"tag_name":"v0.4.0","assets":[]}`))
	}))
	defer srv.Close()
	updateAPI = srv.URL
	if _, err := NewUpdater(t.Logf).Check(); err == nil {
		t.Fatal("Fehler erwartet, wenn Dateien im Release fehlen")
	}
}

func TestRunUpdatesRestartsAfterReplace(t *testing.T) {
	exe := withFakeExe(t, "0.3.1")
	srv := fakeRelease(t, "v0.4.0", []byte("neu"), "")
	updateAPI = srv.URL + "/latest"
	restarted := false
	old := restartSelf
	// Neustart mit dem Pfad von vor dem Austausch (os.Executable zeigt danach auf *.old).
	restartSelf = func(path string) { restarted = path == exe }
	t.Cleanup(func() { restartSelf = old })
	NewUpdater(t.Logf).RunUpdates(make(chan struct{}))
	if !restarted {
		t.Fatal("kein Neustart")
	}
}

func TestAssetNameAndChecksums(t *testing.T) {
	if AssetName("windows", "amd64") != "wowft-uploader.exe" || AssetName("linux", "arm64") != "wowft-uploader-linux-arm64" {
		t.Fatal("Dateinamen passen nicht zum Release-Workflow")
	}
	sums := parseChecksums([]byte(strings.Repeat("A", 64) + "  wowft-uploader.exe\nkaputt\n" + strings.Repeat("b", 64) + " *x\n"))
	if sums["wowft-uploader.exe"] != strings.Repeat("a", 64) || sums["x"] != strings.Repeat("b", 64) || len(sums) != 2 {
		t.Fatalf("%v", sums)
	}
}

func TestCleanupOldExecutable(t *testing.T) {
	exe := withFakeExe(t, "0.3.1")
	os.WriteFile(exe+".old", []byte("x"), 0o644)
	CleanupOldExecutable()
	if _, err := os.Stat(exe + ".old"); !os.IsNotExist(err) {
		t.Fatal("alte Datei nicht entfernt")
	}
}
