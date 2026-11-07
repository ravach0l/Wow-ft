# WowFT einrichten (Windows)

Mit WowFT sieht unsere Runde auf einer Webseite, wer welches Level hat, was passiert ist
und welche Materialien jeder dabeihat. Dafür brauchst du ein kleines Programm, den Uploader.
Er installiert auch das Addon im Spiel. Dauert etwa 5 Minuten.

**Du brauchst:** Windows, WoW Forever und von Dominic zwei Links:
einen **Konto-Einladungslink** und einen **Gruppen-Link**.

## 1. Konto anlegen

Öffne den Konto-Einladungslink und wähle Benutzername, E-Mail und Passwort.

## 2. Der Gruppe beitreten

Melde dich auf <https://wow.the-birds.xyz> an, öffne dann den Gruppen-Link und klicke auf
**Beitreten**.

## 3. Uploader installieren und koppeln

1. Lade [wowft-uploader.exe](https://github.com/ravach0l/Wow-ft/releases/latest/download/wowft-uploader.exe) herunter
   und lege sie in einen festen Ordner, zum Beispiel `Dokumente\WowFT`.
2. Starte sie per Doppelklick. Windows warnt eventuell („Der Computer wurde durch Windows
   geschützt“): Klicke auf **Weitere Informationen → Trotzdem ausführen**. Die Datei ist
   nicht signiert, das ist normal.
3. Beantworte die Fragen:
   - **Server:** Enter drücken.
   - **Koppeln:** Enter drücken. Der Uploader zeigt einen kurzen Code (z. B. `K7Q-4MX`) und öffnet
     die Webseite. Prüfe, dass dort derselbe Code steht, und klicke auf **Koppeln**.
     Einen Token musst du nicht kopieren.
   - **WoW-Ordner:** den gefundenen Ordner bestätigen. Der Uploader installiert jetzt das
     Addon **WowFT** selbst und hält es später aktuell.
   - **Autostart:** `J`, damit der Uploader beim Anmelden von selbst startet.

### Klappt das Koppeln im Browser nicht?

Dann geht es über das Spiel: Auf der Webseite unter **Profil → Code fürs Spiel erzeugen**
bekommst du einen Code wie `WFT-7KQ4-MX2P`. Im Spiel auf den **WowFT-Button** an der Minimap
(ein kleines Buch) klicken, den Code ins Token-Feld tippen, **Speichern**, dann `/reload`.
Der Uploader koppelt sich damit beim nächsten Speichern selbst. Der Code gilt 15 Minuten und
nur einmal.

## Fertig

Starte WoW (läuft es schon: neu einloggen). Unter „Addons“ ist **WowFT** jetzt aktiv, an der
Minimap erscheint ein kleines Buch.

Spiele wie gewohnt. Sobald du dich **ausloggst oder `/reload` tippst**, erscheint dein Stand
nach wenigen Sekunden auf der Webseite.

## Gut zu wissen

- **Updates kommen von selbst:** Der Uploader prüft täglich, ob es eine neue Version gibt, und
  aktualisiert sich und das Addon selbst. Neue Addon-Versionen wirken nach `/reload`.

- **Nichts geht live:** WoW speichert die Daten nur bei Logout oder `/reload`. Die Webseite
  zeigt oben, wann der letzte Upload kam.
- **Foto:** `/ft foto` öffnet eine Fotoansicht deines Charakters. Das Bild landet auf der Seite.
- **Was andere sehen:** Auf der Webseite unter **Profil → „Was sehen die anderen?“** kannst du je
  Charakter ausblenden, was du nicht zeigen willst (Gold, Ausrüstung, Ruf, Aufenthaltsort, Tode,
  Foto, Spielzeit, Tempo und mehr). Level und XP sehen immer alle. **Gold und Tempo sind standardmäßig verborgen.**
  Deine **Spielzeit** sehen andere nur, wenn Dominic den Rennen-Modus einschaltet. Dein **Tempo**
  (XP pro Stunde) sehen sie nur, wenn du es freigibst. Aus Tempo und Level ließe sich die Spielzeit
  ungefähr errechnen, deshalb ist es standardmäßig aus.
- **Gar nicht erst aufnehmen:** Wer Gold oder Material nicht einmal hochladen will, schaltet es im
  Spiel unter Einstellungen ab. Das Addon nimmt dann nichts Neues dazu. (Was schon früher
  aufgenommen und hochgeladen wurde, bleibt auf dem Server und lässt sich dort ausblenden.)
- **Button weg?** `/ft show`. Alle Befehle: `/ft`.

## Wenn etwas nicht klappt

- Im Spiel: `/ft status` zeigt, ob das Addon Probleme hat.
- Der Uploader schreibt ein Protokoll nach `%APPDATA%\wowft\uploader.log`
  (in die Adresszeile des Explorers einfügen).
- Neuen Code fürs Spiel erzeugt? Im Spiel ins Token-Feld eintragen (siehe „Klappt das Koppeln im
  Browser nicht?“), dann `/reload`.
- Sonst melde dich bei Dominic und schick ihm die Log-Datei.

### Addon von Hand installieren

Nur nötig, wenn der Uploader meldet, dass er das Addon nicht installieren konnte (z. B. fehlende
Schreibrechte oder mehrere Spielversionen ohne Forever-Ordner):
[WowFT-addon.zip](https://github.com/ravach0l/Wow-ft/releases/latest/download/WowFT-addon.zip)
herunterladen und so entpacken, dass der Ordner `WowFT` in
`World of Warcraft\_forever_\Interface\AddOns\` liegt.
