# CLAUDE.md

Lies zuerst `docs/UEBERGABE.md`: Architektur, Stand und nächste Schritte.

Kurz:
- Monorepo: `addon/` (Lua), `uploader/` (Go), `server/` (FastAPI, SQLite, Alembic), `web/` (React/Vite), `deploy/`.
- Datenformat zwischen den Teilen: `docs/datenvertrag.md`, Beispiel `fixtures/WowFT.lua`.
- Sprache für UI, Doku und Commit-Messages: Deutsch.
- Vor dem Commit die Tests des geänderten Teils laufen lassen (Befehle in `docs/UEBERGABE.md`, Abschnitt 6).
- Datenbankänderungen nur über neue Alembic-Migrationen; bestehende Migrationen nicht ändern.
- Forever hat keine Realms: Charaktere werden über die GUID identifiziert.
