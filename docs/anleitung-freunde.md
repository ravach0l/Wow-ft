# WowFT einrichten (Windows)

Mit WowFT sieht unsere Runde auf einer Webseite, wer welches Level hat, was passiert ist
und welche Materialien jeder dabeihat. Dafür brauchst du ein kleines Addon im Spiel und ein
kleines Programm, das die Daten hochlädt. Dauert etwa 10 Minuten.

**Du brauchst:** Windows, WoW Forever und von Dominic zwei Links:
einen **Konto-Einladungslink** und einen **Gruppen-Link**.

## 1. Konto anlegen

Öffne den Konto-Einladungslink und wähle Benutzername, E-Mail und Passwort.

## 2. Der Gruppe beitreten

Melde dich auf <https://wow.the-birds.xyz> an, öffne dann den Gruppen-Link und klicke auf
**Beitreten**.

## 3. Token erzeugen

Auf der Webseite: **Profil → Token erzeugen**. Kopiere den Token (beginnt mit `wft_`).
Er ist dein Schlüssel zum Hochladen. Gib ihn nicht weiter.

## 4. Addon installieren

1. Lade [WowFT-addon.zip](https://github.com/ravach0l/Wow-ft/releases/latest/download/WowFT-addon.zip) herunter.
2. Entpacke die ZIP-Datei so, dass der Ordner `WowFT` hier landet:
   `C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\`
   (Liegt WoW woanders, nimm den Ordner `_forever_` deiner Installation.)
3. Starte WoW. Unter „Addons“ sollte **WowFT** aktiv sein.

## 5. Token im Spiel eintragen

Klicke an der Minimap auf den **WowFT-Button** (ein kleines Buch), füge den Token ein, klicke
**Speichern** und tippe dann `/reload`.

## 6. Uploader installieren

1. Lade [wowft-uploader.exe](https://github.com/ravach0l/Wow-ft/releases/latest/download/wowft-uploader.exe) herunter
   und lege sie in einen festen Ordner, zum Beispiel `Dokumente\WowFT`.
2. Starte sie per Doppelklick. Windows warnt eventuell („Der Computer wurde durch Windows
   geschützt“): Klicke auf **Weitere Informationen → Trotzdem ausführen**. Die Datei ist
   nicht signiert, das ist normal.
3. Beantworte die Fragen:
   - **Server:** Enter drücken.
   - **Upload-Token:** Enter drücken (er steht schon im Spiel).
   - **WoW-Ordner:** den gefundenen Ordner bestätigen.
   - **Autostart:** `J`, damit der Uploader beim Anmelden von selbst startet.

## Fertig

Spiele wie gewohnt. Sobald du dich **ausloggst oder `/reload` tippst**, erscheint dein Stand
nach wenigen Sekunden auf der Webseite.

## Gut zu wissen

- **Nichts geht live:** WoW speichert die Daten nur bei Logout oder `/reload`. Die Webseite
  zeigt oben, wann der letzte Upload kam.
- **Foto:** `/ft foto` öffnet eine Fotoansicht deines Charakters. Das Bild landet auf der Seite.
- **Gold** wird nicht gemeldet, solange du es nicht einschaltest (Button → Einstellungen).
- **Button weg?** `/ft show`. Alle Befehle: `/ft`.

## Wenn etwas nicht klappt

- Im Spiel: `/ft status` zeigt, ob das Addon Probleme hat.
- Der Uploader schreibt ein Protokoll nach `%APPDATA%\wowft\uploader.log`
  (in die Adresszeile des Explorers einfügen).
- Neuen Token erzeugt? Im Spiel eintragen (Schritt 5), `/reload`.
- Sonst melde dich bei Dominic und schick ihm die Log-Datei.
