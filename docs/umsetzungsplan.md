# WoW Forever Freundes-Tracker – Umsetzungsplan

Grundlage: das Konzept „WoW Forever Freundes-Tracker – Konzept“ (Claude Doc).
Dieser Plan zerlegt die fünf Phasen aus dem Konzept in kleine Programmierschritte.
Jeder Schritt ist so geschnitten, dass er in einem Commit/PR (bzw. einer
Claude-Code-Sitzung) fertig wird und ein prüfbares Ergebnis hat.

Legende: **Größe** S ≈ 1–2 h, M ≈ halber Tag, L ≈ ganzer Tag.

---

## Leitentscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Repo-Struktur | Monorepo: `addon/`, `uploader/`, `server/`, `web/`, `deploy/`, `fixtures/`, `docs/` | Datenvertrag, Fixtures und CI an einer Stelle |
| Namen | Addon-Ordner `WowFT`, SavedVariable `WowFTDB`, Slash-Befehl `/ft` | kurz, kollisionsarm |
| Server | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite | wie im Konzept; Alembic, damit Phase 3/4 ohne Umbau migrieren |
| Uploader | **Go**, ohne Fremdabhängigkeiten, eine kleine .exe | schickt die Datei roh (gzip); kein Parser im Uploader |
| Lua-Parser | nur auf dem Server (`server/wowft/svparse.py`, **führt nie Lua aus**) | ein Parser für Uploader-Upload und manuellen Upload |
| Web | Vite + React + TypeScript, Diagramm als eigenes SVG | leichtgewichtig, mobil zuerst |
| Auslieferung | ein Docker-Image: FastAPI liefert API und gebautes Frontend aus, Caddy davor | ein Container, keine CORS-Fragen |
| Login | Authentik per OIDC, kein Magic-Link | Authentik läuft bereits für die D&D-Accounts |
| Charakter-Schlüssel | `UnitGUID("player")` | Forever hat keine Realms (Mega-Server pro Region) |
| Rate-Limit | im Server, nicht in Caddy | Standard-Caddy hat kein Rate-Limit-Modul |
| Domain | `wow.the-birds.xyz` | |

### Abweichungen/Ergänzungen zum Konzept

- Forever hat **keine Realms**. `characters` ist über die **`guid`** eindeutig; `realm` und
  `region` werden nur zur Info gespeichert.
- Für das Charakterbild kommt eine achte Tabelle **`photos`** dazu (Phase 4).
- XP-pro-Level-Tabelle (1–60) als Konstante auf dem Server, für „Zeit bis 60“.
  Classic-Werte als Startpunkt, für Forever prüfen.
- Statusfenster im Spiel kann nur „zuletzt gespeichert“ zeigen, nicht „zuletzt hochgeladen“
  (das Addon erfährt nichts vom Uploader). Die Upload-Bestätigung zeigt der Uploader.

---

## Stand

| Schritt | Stand |
|---|---|
| 0.1 Client-Prüfung | Realms geklärt (keine); Rest offen, Checkliste in `docs/client-check.md` |
| 0.2 Repo-Gerüst, CI | erledigt |
| 0.3 Datenvertrag | erledigt (`docs/datenvertrag.md`, `fixtures/`) |
| 1.1–1.5 Addon-MVP | erledigt, im Spiel noch ungetestet |
| 2.1–2.9 Server, Uploader, Übersicht, Deployment | erledigt (Uploader in Go statt Python) |
| 3.1 Authentik-Login, 3.2 Gruppen/Einladungen, 3.3 Tokens, 3.4 Sichtbarkeit, 3.6 manueller Upload, 3.7 Härtung | erledigt |
| 3.5 Uploader für Freunde | Einrichtungsdialog, Autostart, Release-Build erledigt; Tray-Symbol offen |
| 4.1–4.3 Verlauf, Detail, Feed | Grundversion erledigt (Level-Verlauf, Level-Up-Feed) |
| 4.4–4.6, Phase 5 | offen |

---

## Phase 0 – Fundament (vor allem anderen)

### 0.1 Client-Prüfung in Forever — S, manuell
Im Spiel mit `/dump` prüfen und Ergebnis in `docs/client-check.md` festhalten:
- Interface-Nummer für die `.toc` (`/dump select(4, GetBuildInfo())`).
- Vorhanden? `UnitXP`, `UnitXPMax`, `GetXPExhaustion`, `RequestTimePlayed`, `GetZoneText`,
  `GetMoney`, `GetInventoryItemLink`, `GetSkillLineInfo`, `C_Container` vs. `GetContainerItemInfo`,
  `BNSendGameData`.
- Ist der SavedVariables-Bug aus der Beta behoben? (Wert setzen, `/reload`, Neustart, prüfen.)
- Pfad der SavedVariables-Datei: `WTF/Account/<ACCOUNT>/SavedVariables/WowFT.lua`.
- Offene Frage aus dem Konzept: gibt es eine Blizzard-Profil-API für Forever?

**Fertig, wenn:** `docs/client-check.md` beantwortet alle Punkte.

### 0.2 Repo-Gerüst und CI — S
- Ordnerstruktur, `README.md`, `.gitignore`, `.editorconfig`.
- GitHub Actions: `luacheck` (Addon), `ruff` + `pytest` (sv-parse, uploader, server),
  `eslint` + `tsc` + `vitest` (web). Jobs laufen nur, wenn ihr Ordner sich ändert.

**Fertig, wenn:** leerer CI-Lauf ist grün.

### 0.3 Datenvertrag v1 — M (wichtigster Schritt)
`docs/datenvertrag.md` + Beispieldatei `fixtures/WowFT.lua` + `fixtures/ingest.json`.

SavedVariables (Lua):
```lua
WowFTDB = {
  schema = 1,
  addonVersion = "0.1.0",
  characters = {
    ["Realm-Name"] = {
      name = "Name", realm = "Realm", class = "WARRIOR", race = "Human", faction = "Alliance",
      snapshots = {   -- Ringpuffer, max. 50
        { t = 1793860000, level = 23, xp = 4100, xpMax = 13000, rested = 2300,
          playedTotal = 182340, playedLevel = 5120, zone = "Redridge Mountains" },
      },
      levelUps = {    -- vollständig, nie gekürzt
        { t = 1793850000, level = 23, playedTotal = 177220 },
      },
      photoRequests = { 1793860100 },   -- ab Phase 4
      settings = { shareGold = false, shareMaterials = true },
    },
  },
}
```

Ingest-JSON (Uploader → Server): `{ "uploaderVersion": "…", "schema": 1, "characters": { … } }`
– dieselbe Struktur, nur als JSON. Pydantic-Modelle auf dem Server spiegeln das 1:1.

Regeln: Zeit immer Unix-Sekunden (UTC), unbekannte Felder werden ignoriert
(vorwärtskompatibel), `schema` wird bei inkompatiblen Änderungen hochgezählt.

**Fertig, wenn:** Fixtures existieren und von Schritt 2.3/2.4 als Testdaten benutzt werden können.

---

## Phase 1 – Addon-MVP

### 1.1 Addon-Gerüst — S
- `addon/WowFT/WowFT.toc` (Interface aus 0.1, `## SavedVariables: WowFTDB`), `Core.lua`.
- Namespace-Tabelle, Event-Frame, Initialisierung von `WowFTDB` mit Defaults und Schema-Migration.
- `/ft` (Hilfe), `/ft status`.

**Fertig, wenn:** Addon lädt fehlerfrei, `WowFTDB` erscheint nach `/reload` in der Datei.

### 1.2 Snapshot-Erfassung — M
- Stammdaten bei `PLAYER_LOGIN` (Name, Realm, Klasse als Token, Rasse, Fraktion).
- Snapshot bei: Login, `PLAYER_LEVEL_UP`, `ZONE_CHANGED_NEW_AREA` (gedrosselt), alle 15 min,
  `PLAYER_LOGOUT`. `PLAYER_XP_UPDATE` nur zwischenspeichern, nicht jedes Mal snapshotten.
- `RequestTimePlayed()` bei Login + Logout; Chat-Ausgabe von `TIME_PLAYED_MSG` unterdrücken,
  wenn das Addon selbst gefragt hat.
- Ringpuffer 50 Einträge; Logik in eigener Datei (`Buffer.lua`) ohne WoW-API, damit testbar.

**Fertig, wenn:** nach 30 min Spielen + Logout stehen plausible Snapshots in der Datei.

### 1.3 Level-Ups — S
- Bei `PLAYER_LEVEL_UP` Eintrag mit neuem Level, Zeit und (nach `TIME_PLAYED_MSG`) Spielzeit.
- Nie gekürzt.

### 1.4 Statusfenster — M
- Kleines verschiebbares Fenster: Level, XP-Balken mit Rested-Anteil, „zuletzt gespeichert vor …“,
  Hinweis „/reload zum Synchronisieren“. Position wird gespeichert, `/ft show|hide`.

### 1.5 Tests und Testlauf — S
- `busted`-Tests für Ringpuffer und Schema-Migration (mit minimalen WoW-API-Mocks).
- `luacheck`-Konfiguration mit WoW-Globals.
- Checkliste für den Testlauf „du allein“ in `docs/testlauf-phase1.md`.

---

## Phase 2 – Server, Uploader, Übersicht

### 2.1 `sv-parse`: SavedVariables → JSON — M
- Tokenizer + rekursiver Parser für Lua-Tabellenliterale (Strings mit Escapes, Zahlen, Booleans,
  `nil`, `[key] =`, `key =`, Array-Teil, Kommentare). Kein `eval`, keine Lua-Laufzeit.
- Arrays (`{a, b}`) werden zu Listen, sonst Dicts. Größen- und Tiefenlimit.
- Tests gegen `fixtures/WowFT.lua` und kaputte Eingaben.

**Fertig, wenn:** `python -m sv_parse fixtures/WowFT.lua` gibt `fixtures/ingest.json` aus.

### 2.2 Server-Gerüst — S
- FastAPI-App, Settings über Umgebungsvariablen, `/healthz`, Logging, pytest mit Test-DB.

### 2.3 Datenmodell + erste Migration — M
- Tabellen: `users`, `groups`, `group_members`, `tokens`, `characters` (+`realm`), `snapshots`, `events`.
- Eindeutig: `snapshots(character_id, zeitpunkt)`, `events(character_id, zeitpunkt, typ)`,
  `characters(user_id, realm, name)`.
- Admin-CLI: `python -m wowft admin create-user|create-group|add-member|create-token`
  (bis es in Phase 3 eine Oberfläche gibt). Token wird nur einmal angezeigt, gespeichert als SHA-256.

### 2.4 `POST /api/ingest` — M
- `Authorization: Bearer <token>` → Benutzer; widerrufene Tokens → 401.
- Validierung per Pydantic, Body-Limit (z. B. 2 MB).
- Charaktere anlegen/aktualisieren, Snapshots und Level-Ups (als `events` Typ `level_up`)
  mit `INSERT … ON CONFLICT DO NOTHING`.
- Antwort: Anzahl neuer Snapshots/Ereignisse.

**Fertig, wenn:** zweimal derselbe Upload → beim zweiten Mal 0 neue Einträge.

### 2.5 `GET /api/groups/{id}/overview` + Kennzahlen — M
- Jüngster Snapshot je sichtbarem Charakter der Gruppe, Besitzername, Zeitpunkt des
  jüngsten Uploads der Gruppe.
- Abgeleitet: XP pro Stunde Spielzeit (über letzte N Level-Ups/Snapshots),
  geschätzte Spielzeit bis 60 (XP-Tabelle), Abstand zum Führenden.
- In Phase 2 noch ohne Login: Zugriff hinter Basic-Auth in Caddy.

### 2.6 Uploader v1 — M
- Konfiguration (`config.toml`): Server-URL, Token, WoW-Ordner, Account-Name(n).
- Beobachtet die SavedVariables-Datei (watchdog), wartet nach Änderung ~3 s (Datei wird
  stückweise geschrieben), parst mit `sv-parse`, sendet an `/api/ingest`.
- Wiederholung mit Backoff bei Netzfehlern, Logdatei, `--once` für manuellen Lauf.
- Merkt sich den Hash der letzten erfolgreich gesendeten Datei.

### 2.7 Web-Gerüst — M
- Vite + React + TS, Router, API-Client, Design-Tokens (dunkles Thema, Klassenfarben).
- Kopfzeile „jüngster Upload vor …“ (wird ab > 24 h deutlich als veraltet markiert).

### 2.8 Gruppenübersicht — L
- Karte je Charakter: Name in Klassenfarbe, große Level-Zahl, XP-Balken mit hellem Rested-Teil,
  Zone, „vor 2 Std.“, Klassen-Symbol als Platzhalter fürs Bild.
- Sortierung nach Level/XP, XP pro Stunde, Spielzeit (Umschalter oben).
- Gruppierung nach Person, Twinks eingeklappt.
- Vitest-Tests für Sortierung und Zeitformatierung.

### 2.9 Deployment auf mediavault — M
- Mehrstufiges `Dockerfile` (Web bauen → in Python-Image kopieren), `docker-compose.yml`
  mit Volume für SQLite (und später Fotos), Alembic-Migration beim Start.
- Caddy-Block für `wow.the-birds.xyz` (vorerst mit Basic-Auth).
- Tägliches Backup via `sqlite3 .backup`.

**Meilenstein Phase 2:** Du spielst, loggst aus, und die Karte auf dem Handy zeigt den neuen Stand.

---

## Phase 3 – Freunde an Bord

### 3.1 Login über Authentik (OIDC) — M
- Authlib, Session-Cookie (`HttpOnly`, `Secure`, `SameSite=Lax`), `users.auth_sub`.
- `/api/me`, Logout. Basic-Auth in Caddy entfällt danach.

### 3.2 Gruppen und Einladungen — M
- Gruppe anlegen, Einladungslink mit `invite_code` (neu erzeugbar), Beitreten nach Login,
  Rollen `owner`/`member`.
- Autorisierung: alle `GET`-Endpunkte prüfen Gruppenmitgliedschaft (Tests!).

### 3.3 Token-Verwaltung im Profil — S
- Token erzeugen (einmal anzeigen, mit Kopieren-Knopf), Liste, Widerrufen.

### 3.4 Sichtbarkeit pro Charakter — S
- Schalter „in Gruppe zeigen“, „Gold zeigen“; Filter in allen Abfragen.

### 3.5 Uploader für Freunde — L
- Erststart-Dialog: Token eingeben, WoW-Ordner automatisch suchen (Standardpfade), Account wählen.
- Tray-Symbol mit Status „zuletzt hochgeladen …“, Autostart (Windows: Startup-Ordner).
- PyInstaller-Build für Windows im GitHub-Actions-Windows-Runner, Release-Asset.
- Linux: `systemd --user`-Unit für dich.

### 3.6 Manueller Upload auf der Web-Seite — S
- `.lua`-Datei hochladen → Server parst mit `sv-parse` → gleiche Logik wie Ingest.

### 3.7 Härtung — S
- Rate-Limit in Caddy für `/api/ingest` und Login, Sicherheits-Header,
  nur Ingest und Login öffentlich, Prüfung der Body-Limits.

**Meilenstein Phase 3:** Ein Freund klickt den Link, loggt sich ein, installiert die .exe
und erscheint nach dem nächsten Logout auf der Seite.

---

## Phase 4 – Verlauf, Feed, Erweiterungen

### 4.1 Verlauf und Rennen-Diagramm — M
- `GET /api/characters/{id}/history` (Snapshots + Ereignisse).
- Rennen-Ansicht: Level über Zeit, eine Linie pro Charakter, Umschalter x-Achse
  Kalenderzeit ↔ Spielzeit.

### 4.2 Charakter-Detail — M
- Level-Verlauf, Kennzahlen (XP/h, Zeit bis 60); Bereiche für die Erweiterungen unten
  erscheinen, sobald Daten da sind.

### 4.3 Aktivitäts-Feed — M
- `GET /api/groups/{id}/feed`. Ereignisse kommen vom Addon (Level-Up) oder werden beim Ingest
  durch Vergleich mit dem vorigen Stand abgeleitet (Beruf erreicht 75/150/225/300,
  neues episches Item, Dungeon abgeschlossen).

### 4.4 Addon-Erweiterungen — je S–M, einzeln testen (Risiko „API weicht ab“)
Jede Erweiterung: Addon-Erfassung → Datenvertrag ergänzen (`extras`) → Ingest → Anzeige.
1. Tode (`PLAYER_DEAD`) – S
2. Gold (`GetMoney`, standardmäßig nicht geteilt) – S
3. Berufe und Waffenfertigkeiten (`GetSkillLineInfo`) – S
4. Ausrüstung (`GetInventoryItemLink`, Item-ID/Name/Qualität; `PLAYER_EQUIPMENT_CHANGED`) – M
5. Handwerksmaterialien in Taschen + letzter Bankstand (`BANKFRAME_OPENED`), nur Item-Klasse
   „Handelswaren“, abschaltbar; Gruppen-Übersicht „wer hat wie viel“ – M
6. Ruf wichtiger Fraktionen (`GetFactionInfo`) – S
7. Talente (`GetTalentInfo`) – M
8. Abgeschlossene Dungeons – M (Erkennung prüfen; ggf. weglassen)
9. Forever-Sammelziele – erst wenn klar ist, wie die API sie abbildet

### 4.5 Charakterbild — L
- Addon: `/ft foto` öffnet Vollbild-Ansicht mit 3D-Modell vor neutralem Hintergrund,
  schreibt Zeitstempel in `photoRequests`.
- Uploader: beobachtet `Screenshots/`, nimmt den ersten Screenshot innerhalb von 2 min nach dem
  Zeitstempel, schneidet zu (Pillow), lädt per `POST /api/characters/{id}/photos` hoch.
- Server: Tabelle `photos`, Dateien im Volume, Größenlimit; Web: jüngstes Bild auf der Karte,
  Galerie im Detail.

### 4.6 Discord-Webhook — S
- Pro Gruppe optional eine Webhook-URL; neue Feed-Ereignisse werden gepostet.

---

## Phase 5 – Optional live im Spiel

### 5.1 Machbarkeit — S
- Funktioniert `BNSendGameData` in Forever? Größenlimit, Drosselung.

### 5.2 Protokoll und Austausch — M
- Präfix `WOWFT`, kompakte Nachricht (Level, XP-Anteil, Zone), Versand bei Level-Up und
  höchstens alle paar Minuten; Empfang und Ablage im Addon.

### 5.3 Freundesliste im Addon-Fenster — M

---

## Querschnitt (läuft immer mit)

- **Tests:** Parser, Ingest-Deduplizierung und Autorisierung haben Pflicht-Tests.
- **Datenvertrag:** jede Änderung zuerst in `docs/datenvertrag.md` + Fixtures.
- **Versionen:** Addon, Uploader und Schema getrennt versionieren; Server akzeptiert alte Schemata.
- **Datenschutz:** nichts übertragen, was im Konzept als „bewusst weggelassen“ steht.

## Empfohlene Reihenfolge der ersten Sitzungen

1. 0.1 Client-Prüfung (du, im Spiel) und parallel 0.2 Repo-Gerüst
2. 0.3 Datenvertrag
3. 1.1 → 1.3 Addon erfasst Daten
4. 2.1 Parser → 2.2–2.4 Server mit Ingest
5. 2.6 Uploader → 2.7/2.8 Übersicht → 2.9 Deployment

Danach ist Phase 1+2 durch und das Ding schon im Alltag nützlich.

## Entschieden

- Login nur über Authentik.
- Uploader in Go (eine kleine Datei, keine Laufzeit nötig).
- Domain bleibt `wow.the-birds.xyz`.
