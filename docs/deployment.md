# Deployment auf mediavault

## 1. Authentik

1. **Applications → Providers → Create → OAuth2/OpenID Provider**
   - Name: `wowft`
   - Client type: *Confidential*
   - Redirect URIs: `https://wow.the-birds.xyz/auth/callback` (strict)
   - Scopes: `openid`, `email`, `profile` (Standard-Mappings)
2. **Applications → Create**: Name „Freundes-Tracker“, Slug `wowft`, Provider `wowft`.
3. Client-ID und -Secret in `deploy/.env` eintragen. Die Metadata-URL ist
   `https://<authentik>/application/o/wowft/.well-known/openid-configuration`.
4. Freunde brauchen ein Authentik-Konto. Am einfachsten über einen Enrollment-Flow
   mit Einladung (Directory → Invitations), wie bei den D&D-Accounts.
   Wer in keiner Gruppe ist, sieht nichts. Wer die App nur bestimmten Leuten
   zeigen will, bindet in Authentik eine Gruppen-Policy an die Application.

## 2. Server

```sh
git clone https://github.com/ravach0l/wow-ft.git && cd wow-ft/deploy
cp .env.example .env    # SECRET_KEY, OIDC-Werte eintragen
docker compose up -d --build
curl -s http://127.0.0.1:8085/healthz
```

Der Container läuft als Benutzer mit UID 10001. Legt Docker `deploy/data` als root an, kann er die
Datenbank nicht öffnen („unable to open database file“). Dann einmalig den Besitzer setzen und neu starten:

```sh
docker run --rm -v "$PWD/data:/x" alpine chown 10001:10001 /x
docker compose restart wowft
```

Läuft Caddy selbst in Docker, den Container zusätzlich in dessen Netzwerk hängen
(z. B. per `docker-compose.override.yml` mit `networks: [heimserver_net]`, `external: true`)
und im Caddyfile `reverse_proxy wowft:8000` eintragen.

Migrationen laufen beim Start automatisch. Trag in `.env` unter `WOWFT_ADMIN_USERS`
deinen Authentik-Benutzernamen ein: Dann erscheint im Profil der Bereich „Admin: Module“,
in dem du z. B. das Level-Rennen (standardmäßig aus) für alle einschaltest. Die Datenbank liegt in `deploy/data/wowft.db`.

## 3. Caddy

Den Block aus [`deploy/Caddyfile`](../deploy/Caddyfile) übernehmen und Caddy neu laden.
Ein Rate-Limit ist im Server eingebaut (Standard-Caddy hat keins):
30 Uploads pro Minute und Token, 20 Login-Aufrufe pro Minute und IP.

## 4. Backup

`deploy/backup.sh` legt eine konsistente Kopie nach `deploy/backups/` und behält 30 Tage.
Per cron täglich aufrufen.

## 5. Update

```sh
git pull && cd deploy && docker compose up -d --build
```

## 6. Uploader und Addon verteilen

Ein Git-Tag `v0.1.0` startet `.github/workflows/release.yml` und hängt an das Release:
`wowft-uploader.exe` (Windows), Linux (amd64, arm64), macOS sowie `WowFT-addon.zip`.

Für Freunde:
1. `WowFT-addon.zip` nach `World of Warcraft/_<version>_/Interface/AddOns/` entpacken.
2. Auf der Webseite anmelden, Einladungslink öffnen und beitreten.
3. `wowft-uploader.exe` starten, koppeln (Code im Browser bestätigen), Ordner bestätigen,
   Autostart mit „J“. Ersatzweg: im Profil „Code fürs Spiel“ erzeugen, im Spiel ins Token-Feld
   eintragen, `/reload`; der Uploader tauscht ihn gegen einen Token.

### Linux (Lutris, Bottles, Steam/Proton, Heroic, Wine)

Das Addon läuft unter Wine/Proton wie unter Windows. Der Uploader ist ein natives Linux-Programm:

```sh
install -m 755 wowft-uploader-linux-amd64 ~/.local/bin/wowft-uploader
wowft-uploader -setup
```

- Findet der Uploader WoW nicht an den bekannten Orten, durchsucht er Home, `/mnt`, `/media`
  (unter Windows alle Laufwerke) nach dem Spielordner: eine `Wow*.exe` beliebigen Namens
  oder die Ordner `WTF` und `Interface` nebeneinander. `wowft-uploader -find` zeigt die Treffer.
- Bekannte Orte: `~/Games/*` (Lutris),
  Bottles (auch Flatpak), Steam-`compatdata` (auch Flatpak), Heroic, `~/.wine`,
  `~/.local/share/wineprefixes`. Sonst den Pfad zu `…/drive_c/Program Files (x86)/World of Warcraft`
  von Hand eingeben.
- Groß-/Kleinschreibung von `WTF/Account/…/SavedVariables` ist egal.
- Autostart: Mit systemd wird ein Benutzerdienst angelegt und sofort gestartet
  (`systemctl --user status wowft-uploader`, Log: `journalctl --user -u wowft-uploader -f`).
  Ohne systemd entsteht ein XDG-Autostart-Eintrag für die Desktop-Anmeldung.
  Ein- und ausschalten: `wowft-uploader -autostart on|off`.
- Konfiguration und Log liegen in `~/.config/wowft/`.

### Windows

Hinweis: Die .exe ist nicht signiert. Windows SmartScreen fragt beim ersten Start
nach („Weitere Informationen → Trotzdem ausführen“).

## Lokale Entwicklung

```sh
# Server mit Login ohne Authentik
cd server && pip install -e ".[dev]"
WOWFT_DEV_LOGIN=true python -m wowft
# Frontend mit Proxy auf den Server
cd web && npm install && npm run dev
# http://localhost:5173/auth/dev-login?name=ich
```
