# WoW Forever Freundes-Tracker

Ein Addon sammelt Level, XP und Spielzeit pro Charakter, ein Uploader schickt
die Daten an einen Server, und eine Webseite zeigt die ganze Freundesrunde
auf einen Blick, auch am Handy.

```
Spiel ──► addon/ (WowFT.lua) ──► uploader/ (Go) ──► server/ (FastAPI, SQLite) ◄── web/ (React)
```

| Ordner | Inhalt |
|---|---|
| `addon/WowFT` | WoW-Addon: Snapshots, Level-Ups, Statusfenster, `/ft` |
| `uploader` | Go-Programm: beobachtet `WowFT.lua`, lädt sie hoch |
| `server` | FastAPI: Ingest, Authentik-Login, Gruppen, Tokens, Kennzahlen |
| `web` | React-Oberfläche: Übersicht, Feed, Charakter-Detail, Profil |
| `deploy` | Docker Compose, Caddy, Backup, systemd-Unit für den Uploader |
| `fixtures` | Beispiel-SavedVariables für Tests |
| `docs` | Plan, Datenvertrag, Deployment, Client-Prüfung |

- **Einstieg und Übergabe: [`docs/UEBERGABE.md`](docs/UEBERGABE.md)**
- Plan und Stand: [`docs/umsetzungsplan.md`](docs/umsetzungsplan.md)
- Datenformat: [`docs/datenvertrag.md`](docs/datenvertrag.md)
- Installation: [`docs/deployment.md`](docs/deployment.md)
- Noch im Spiel zu prüfen: [`docs/client-check.md`](docs/client-check.md)

## Tests

```sh
pytest addon/tests                                  # Addon (mit lupa)
cd server && pytest && ruff check .                 # Server
cd uploader && go generate ./... && go test ./...                        # Uploader
cd web && npm test && npm run build                 # Web
```
