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

Migrationen laufen beim Start automatisch. Die Datenbank liegt in `deploy/data/wowft.db`.

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
`wowft-uploader.exe` (Windows), Linux- und macOS-Binary sowie `WowFT-addon.zip`.

Für Freunde:
1. `WowFT-addon.zip` nach `World of Warcraft/_<version>_/Interface/AddOns/` entpacken.
2. Auf der Webseite anmelden, Einladungslink öffnen, unter „Profil“ Token erzeugen.
3. `wowft-uploader.exe` starten, Token einfügen, Ordner bestätigen, Autostart mit „J“.

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
