# Datenvertrag v1

Die Schnittstelle zwischen Addon, Uploader und Server ist die Datei
`WTF/Account/<ACCOUNT>/SavedVariables/WowFT.lua`. Beispiel: [`fixtures/WowFT.lua`](../fixtures/WowFT.lua),
dieselben Daten als JSON: [`fixtures/ingest.json`](../fixtures/ingest.json).

## Ablauf

1. Das Addon schreibt `WowFTDB`. WoW speichert die Datei nur bei Logout oder `/reload`.
2. Der Uploader schickt die Datei **unverändert** (gzip) an `POST /api/ingest`.
3. Der Server liest sie mit einem eigenen Parser (`server/wowft/svparse.py`), der nur
   Tabellenliterale versteht und nie Lua ausführt, und speichert neue Einträge.

Es gibt damit nur einen Parser (auf dem Server). Der manuelle Upload auf der Webseite
nutzt denselben Weg.

## Struktur

```lua
WowFTDB = {
  schema = 1,                -- bei inkompatiblen Änderungen hochzählen
  addonVersion = "0.1.0",
  ui = { ... },              -- nur fürs Addon, wird vom Server ignoriert
  characters = {
    ["<GUID>"] = { ... },     -- Schlüssel ist UnitGUID("player")
  },
}
```

### Charakter

| Feld | Typ | Herkunft | Bemerkung |
|---|---|---|---|
| `guid` | string | `UnitGUID("player")` | **Eindeutiger Schlüssel.** Forever hat keine Realms. |
| `name` | string | `UnitName` | |
| `realm` | string? | `GetRealmName` | nur zur Info, nicht Teil des Schlüssels |
| `region` | string? | `GetCurrentRegionName` | z. B. `EU` |
| `class` | string | `UnitClass` (Token) | z. B. `WARRIOR` |
| `race` | string | `UnitRace` (Token) | z. B. `Human` |
| `faction` | string | `UnitFactionGroup` | `Alliance` / `Horde` |
| `updated` | int | `time()` | |
| `snapshots` | Liste | | Ringpuffer, max. 50 |
| `levelUps` | Liste | | vollständig |
| `settings` | Tabelle | | ab Phase 4 (Gold teilen usw.) |

### Snapshot

| Feld | Typ | Herkunft |
|---|---|---|
| `t` | int | `time()` (Unix-Sekunden) |
| `level` | int | `UnitLevel` |
| `xp`, `xpMax` | int | `UnitXP`, `UnitXPMax` |
| `rested` | int | `GetXPExhaustion() or 0` |
| `zone` | string | `GetRealZoneText` |
| `playedTotal`, `playedLevel` | int? | `TIME_PLAYED_MSG`, dazwischen hochgerechnet |
| `gold` | int? | ab Phase 4, nur wenn freigegeben |

Snapshots entstehen bei Login (nach der `/played`-Antwort), Level-Up, Zonenwechsel
(höchstens einmal pro Minute), alle 15 Minuten und beim Logout.

### Level-Up

`{ t, level, playedTotal }` – wird nie gekürzt.

## Regeln

- Zeiten sind Unix-Sekunden (UTC).
- Der Server ignoriert unbekannte Felder; neue optionale Felder brauchen kein neues Schema.
- Eindeutigkeit auf dem Server: Snapshot (Charakter, `t`), Ereignis (Charakter, `t`, Typ).
  Doppelte Uploads sind deshalb harmlos.
- Eine GUID gehört dem Konto, das sie zuerst hochgeladen hat. Uploads derselben GUID
  von einem anderen Konto werden übersprungen (Antwortfeld `skipped`).
- Lua kennt keinen Unterschied zwischen leerer Liste und leerer Tabelle; der Server
  behandelt `{}` bei Listenfeldern als leere Liste.
