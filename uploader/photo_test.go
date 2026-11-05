package main

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func writePNG(t *testing.T, path string, w, h int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			// Mitte rot, Rand blau: so lässt sich der Zuschnitt prüfen.
			c := color.RGBA{0, 0, 255, 255}
			if x > w/2-h/4 && x < w/2+h/4 {
				c = color.RGBA{255, 0, 0, 255}
			}
			img.Set(x, y, c)
		}
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := png.Encode(f, img); err != nil {
		t.Fatal(err)
	}
}

func TestScreenshotDir(t *testing.T) {
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "_forever_", "screenshots", "x.txt"), "")
	sv := filepath.Join(root, "_forever_", "WTF", "Account", "A", "SavedVariables", "WowFT.lua")
	if got := ScreenshotDir(sv); got != filepath.Join(root, "_forever_", "screenshots") {
		t.Fatalf("got %q", got)
	}
}

func TestFindScreenshotPicksClosest(t *testing.T) {
	dir := t.TempDir()
	at := time.Unix(1793863500, 0)
	files := map[string]time.Duration{
		"WoWScrnShot_early.jpg": -time.Hour,
		"WoWScrnShot_a.jpg":     20 * time.Second,
		"WoWScrnShot_b.png":     3 * time.Second,
		"WoWScrnShot_c.tga":     time.Second,
		"WoWScrnShot_late.jpg":  10 * time.Minute,
	}
	for name, off := range files {
		p := filepath.Join(dir, name)
		writeFile(t, p, "x")
		_ = os.Chtimes(p, at.Add(off), at.Add(off))
	}
	if got := filepath.Base(FindScreenshot(dir, at)); got != "WoWScrnShot_b.png" {
		t.Fatalf("got %s", got)
	}
	if FindScreenshot(dir, at.Add(time.Hour*5)) != "" {
		t.Fatal("kein Bild im Zeitfenster erwartet")
	}
}

func TestMakePortrait(t *testing.T) {
	p := filepath.Join(t.TempDir(), "shot.png")
	writePNG(t, p, 1920, 1080)
	data, err := MakePortrait(p)
	if err != nil {
		t.Fatal(err)
	}
	img, err := jpeg.Decode(bytes.NewReader(data))
	if err != nil {
		t.Fatal(err)
	}
	if b := img.Bounds(); b.Dx() != photoWidth || b.Dy() != photoHeight {
		t.Fatalf("Größe %v", b)
	}
	r, _, bl, _ := img.At(photoWidth/2, photoHeight/2).RGBA()
	if r>>8 < 200 || bl>>8 > 60 {
		t.Fatalf("Mitte sollte rot sein: r=%d b=%d", r>>8, bl>>8)
	}
}

func TestWatcherUploadsPhoto(t *testing.T) {
	at := int64(1793863500)
	up := &fakeUploader{result: &Result{Characters: 1, PhotoRequests: []PhotoRequest{{CharacterID: 7, Name: "Testa", T: at}}}}
	w, sv, state := newTestWatcher(t, up)
	shot := filepath.Join(filepath.Dir(sv), "..", "..", "..", "..", "Screenshots", "WoWScrnShot_1.png")
	writePNG(t, shot, 800, 600)
	_ = os.Chtimes(shot, time.Unix(at+2, 0), time.Unix(at+2, 0))

	w.Poll(time.Now())
	if len(up.photos) != 1 || !strings.HasPrefix(up.photos[0], "7:1793863500:") {
		t.Fatalf("photos: %v", up.photos)
	}
	// Bei weiteren Uploads wird dasselbe Foto nicht erneut geschickt.
	writeFile(t, sv, "v2")
	future := time.Now().Add(time.Hour)
	_ = os.Chtimes(sv, future, future)
	w.Poll(time.Now().Add(time.Minute))
	w.Poll(time.Now().Add(2 * time.Minute))
	if len(up.calls) != 2 || len(up.photos) != 1 {
		t.Fatalf("calls=%d photos=%v", len(up.calls), up.photos)
	}
	if data, _ := os.ReadFile(state); !strings.Contains(string(data), "photo:7:1793863500") {
		t.Fatal("Foto nicht im Status vermerkt")
	}
}

func TestClientUploadPhoto(t *testing.T) {
	var got []byte
	var path string
	status := http.StatusCreated
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path = r.URL.RequestURI()
		got, _ = io.ReadAll(r.Body)
		w.WriteHeader(status)
		w.Write([]byte(`{}`))
	}))
	defer srv.Close()
	c := NewClient(srv.URL, "wft_x")
	if err := c.UploadPhoto(3, 99, []byte{1, 2}); err != nil {
		t.Fatal(err)
	}
	if path != "/api/characters/3/photos?t=99" || len(got) != 2 {
		t.Fatalf("path=%s body=%v", path, got)
	}
	status = http.StatusConflict
	if err := c.UploadPhoto(3, 99, []byte{1}); err != nil {
		t.Fatal("409 sollte als Erfolg gelten")
	}
	status = http.StatusBadRequest
	if err := c.UploadPhoto(3, 99, []byte{1}); err == nil {
		t.Fatal("400 sollte ein Fehler sein")
	}
}
