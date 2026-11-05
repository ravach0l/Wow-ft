package main

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	_ "image/png" // PNG-Screenshots lesen
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	photoWidth   = 600
	photoHeight  = 800
	photoBefore  = 10 * time.Second // Dateizeit darf leicht vor dem Addon-Zeitstempel liegen
	photoAfter   = 90 * time.Second
	photoQuality = 85
)

// ScreenshotDir leitet aus .../_forever_/WTF/Account/X/SavedVariables/WowFT.lua
// den Ordner .../_forever_/Screenshots ab.
func ScreenshotDir(svPath string) string {
	flavor := svPath
	for i := 0; i < 5; i++ {
		flavor = filepath.Dir(flavor)
	}
	return childFold(flavor, "Screenshots")
}

// FindScreenshot sucht das Bild, das am nächsten nach dem Zeitpunkt t entstand.
func FindScreenshot(dir string, t time.Time) string {
	if dir == "" {
		return ""
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return ""
	}
	best, bestDiff := "", time.Duration(math.MaxInt64)
	for _, e := range entries {
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if e.IsDir() || (ext != ".jpg" && ext != ".jpeg" && ext != ".png") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		diff := info.ModTime().Sub(t)
		if diff < -photoBefore || diff > photoAfter {
			continue
		}
		if diff < 0 {
			diff = -diff
		}
		if diff < bestDiff {
			best, bestDiff = filepath.Join(dir, e.Name()), diff
		}
	}
	return best
}

// MakePortrait schneidet die Bildmitte im Hochformat 3:4 aus (dort steht das
// Modell aus /ft foto) und verkleinert auf 600×800 als JPEG.
func MakePortrait(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	src, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	b := src.Bounds()
	cropH := b.Dy() * 94 / 100
	cropW := cropH * 3 / 4
	if cropW > b.Dx() {
		cropW = b.Dx()
		cropH = cropW * 4 / 3
	}
	crop := image.Rect(0, 0, cropW, cropH).Add(image.Pt(
		b.Min.X+(b.Dx()-cropW)/2,
		b.Min.Y+(b.Dy()-cropH)/2,
	))
	dst := scale(src, crop, photoWidth, photoHeight)
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, dst, &jpeg.Options{Quality: photoQuality}); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// scale verkleinert den Ausschnitt mit Flächenmittelung (gute Qualität beim Verkleinern).
func scale(src image.Image, r image.Rectangle, w, h int) *image.RGBA {
	dst := image.NewRGBA(image.Rect(0, 0, w, h))
	sx := float64(r.Dx()) / float64(w)
	sy := float64(r.Dy()) / float64(h)
	for y := 0; y < h; y++ {
		y0 := r.Min.Y + int(float64(y)*sy)
		y1 := max(y0+1, r.Min.Y+int(float64(y+1)*sy))
		for x := 0; x < w; x++ {
			x0 := r.Min.X + int(float64(x)*sx)
			x1 := max(x0+1, r.Min.X+int(float64(x+1)*sx))
			var rs, gs, bs, n uint64
			for yy := y0; yy < y1; yy++ {
				for xx := x0; xx < x1; xx++ {
					cr, cg, cb, _ := src.At(xx, yy).RGBA()
					rs, gs, bs, n = rs+uint64(cr), gs+uint64(cg), bs+uint64(cb), n+1
				}
			}
			dst.Set(x, y, color.RGBA64{uint16(rs / n), uint16(gs / n), uint16(bs / n), 0xffff})
		}
	}
	return dst
}
