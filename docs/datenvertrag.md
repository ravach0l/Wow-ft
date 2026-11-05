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

## Zugangsdaten im Spiel (`WowFTDB.upload`)

Im Einstellungsfenster (Minimap-Button) trägt man Server und Upload-Token ein. Das Addon hat
kein Netzwerk; die Werte stehen deshalb in der Datei, und der **Uploader liest sie dort**.

- Werte aus dem Spiel haben Vorrang vor `config.json` (sie sind das Neuere). Ungültige Werte
  (Token ohne `wft_`, Server ohne `https://`) ignoriert der Uploader.
- Der Uploader **leert den Token im Block, bevor er die Datei sendet**. Er geht nur im
  `Authorization`-Header mit. Der Server ignoriert den Block zusätzlich (`extra="ignore"`) und
  speichert ihn nicht (Test `test_ingest_ignores_upload_block`).
- Beim manuellen Upload auf der Webseite wird nichts entfernt: Dort sendet man die Datei selbst,
  und der Block wird vom Server verworfen.
- Der Token liegt im Klartext in `WowFT.lua`, wie bisher in `config.json` (dort mit Rechten 600).

## Struktur

```lua
WowFTDB = {
  schema = 1,                -- bei inkompatiblen Änderungen hochzählen
  addonVersion = "0.1.0",
  ui = { ... },              -- nur fürs Addon, wird vom Server ignoriert
  upload = {                 -- Zugangsdaten aus dem Einstellungsfenster, nur für den Uploader
    server = "https://…",    -- optional; fehlt er, gilt die Adresse aus der Uploader-Konfiguration
    token = "wft_…",         -- optional; fehlt er, gilt der Token aus der Uploader-Konfiguration
  },
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

### Phase 4 (alles optional, pro Charakter)

| Feld | Inhalt | Herkunft | Wann |
|---|---|---|---|
| `deaths` | Anzahl Tode | `PLAYER_DEAD` | laufend |
| `deathLog` | `{ t, level, zone }`, max. 50 | `PLAYER_DEAD` | laufend |
| `bossKills` | `{ t, id, name, instance, level }`, max. 100 | `ENCOUNTER_END` (success) | laufend |
| `skills` | `{ name, rank, max, header }` | `GetSkillLineInfo` | Login, Änderung, Logout |
| `equipment` | `{ slot, id, name, quality }` | `GetInventoryItemLink/Quality` | dto. |
| `reputation` | `{ id, name, standing, value, min, max }` | `GetFactionInfo` | dto. |
| `talents` | `{ name, points, talents = { {name, rank, max, tier, col} } }` | `GetTalentInfo` | dto. |
| `materials` | `{ bags = {…}, bank = {…}, bankScanned }`, Einträge `{ id, name, count }` | Taschen-API, nur Item-Klasse 7 (Handwerkswaren) | Taschen laufend, Bank beim Öffnen |
| `photoRequests` | Zeitpunkte von `/ft foto`-Screenshots, max. 20 | `SCREENSHOT_SUCCEEDED` | bei `/ft foto` |
| `settings` | `trackGold`, `trackMaterials` | `/ft gold an\|aus`, `/ft material an\|aus` | |
| `apiErrors` | Fehlermeldung je Sammler, falls die Forever-API abweicht | `pcall` | nur zur Diagnose, Server ignoriert es |

Snapshots enthalten zusätzlich `gold` (Kupfer, `GetMoney`), außer bei `/ft gold aus`.
Auf der Webseite ist Gold standardmäßig verborgen (pro Charakter freischaltbar).

Der Server speichert den jüngsten Stand am Charakter und erzeugt Feed-Ereignisse aus
Änderungen: Beruf über 75/150/225/300, neues Item ab „selten“, Ruf ab „Wohlwollend“.
Der erste Upload eines Abschnitts erzeugt keine solchen Ereignisse.

### Fotos

1. `/ft foto` zeigt das 3D-Modell vor neutralem Hintergrund; „Foto aufnehmen“ löst einen Screenshot aus
   (sonst die Screenshot-Taste). Der Zeitpunkt landet in `photoRequests`.
2. Nach `/reload` antwortet `POST /api/ingest` mit `photoRequests` (noch fehlende Fotos).
3. Der Uploader sucht in `<Spielordner>/Screenshots` das JPG/PNG mit Dateizeit −10 s…+90 s,
   schneidet die Mitte im Format 3:4 aus, verkleinert auf 600×800 und schickt es an
   `POST /api/characters/{id}/photos?t=<Zeitpunkt>`.

## Regeln

- Zeiten sind Unix-Sekunden (UTC).
- Der Server ignoriert unbekannte Felder; neue optionale Felder brauchen kein neues Schema.
- Eindeutigkeit auf dem Server: Snapshot (Charakter, `t`), Ereignis (Charakter, `t`, Typ, Schlüssel).
  Doppelte Uploads sind deshalb harmlos.
- Eine GUID gehört dem Konto, das sie zuerst hochgeladen hat. Uploads derselben GUID
  von einem anderen Konto werden übersprungen (Antwortfeld `skipped`).
- Lua kennt keinen Unterschied zwischen leerer Liste und leerer Tabelle; der Server
  behandelt `{}` bei Listenfeldern als leere Liste.
