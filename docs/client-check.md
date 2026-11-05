# Client-Prüfung in WoW Forever (Schritt 0.1)

Im Spiel ausführen und Ergebnis hier eintragen. Ergebnisse beeinflussen die
Interface-Nummer in der `.toc` und welche Erweiterungen aus Phase 4 machbar sind.

## Bereits geklärt

- **Realms:** Forever hat keine wählbaren Realms, sondern einen Mega-Server pro Region
  (Amerika, Europa, Asien) mit Spielstil-Auswahl (Normal, PvP, RP, später Hardcore).
  Quellen: [Wowhead](https://www.wowhead.com/forever/news/no-more-realms-in-wow-forever-382866),
  [Icy Veins](https://www.icy-veins.com/wow/news/there-will-be-no-server-realms-in-warcraft-forever/),
  [Blizzard Watch](https://blizzardwatch.com/2026/09/13/world-warcraft-forever-will-realmless/).
  → Charaktere werden über die **GUID** identifiziert; `GetRealmName()` wird nur zur Info gespeichert.

## Noch zu prüfen

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Interface-Nummer | `/dump select(4, GetBuildInfo())` | (in `.toc` eintragen, aktuell 11507) |
| Ordnername der Spielversion | Explorer: `World of Warcraft\_????_` | |
| GUID-Format | `/dump UnitGUID("player")` | |
| Realm-Name (was kommt zurück?) | `/dump GetRealmName()` | |
| Region | `/dump GetCurrentRegionName()` | |
| Spielstil/Ruleset per API? | später | |
| XP-Werte | `/dump UnitXP("player"), UnitXPMax("player"), GetXPExhaustion()` | |
| XP pro Level wie Classic? | `UnitXPMax` auf Level 10/20/30 mit `server/wowft/metrics.py` vergleichen | |
| `/played` | `/dump RequestTimePlayed` | |
| SavedVariables-Bug behoben? | `/ft snap`, `/reload`, Spiel neu starten, `/ft status` | |
| Taschen-API (Phase 4) | `/dump C_Container ~= nil` | |
| Phase-4-Sammler insgesamt | `/ft status` zeigt „API-Problem bei …“, falls etwas fehlt | |
| Boss-Kills | Dungeon-Boss legen, `/reload`, Feed prüfen (`ENCOUNTER_END` vorhanden?) | |
| Foto | `/ft foto` → „Foto aufnehmen“ – darf ein Addon `Screenshot()` aufrufen? | |
| Screenshot-Format | Ordner `Screenshots`: .jpg? (TGA wird nicht unterstützt) | |
| Skill-API (Phase 4) | `/dump GetSkillLineInfo(1)` | |
| Battle.net-Addon-Nachrichten (Phase 5) | `/dump BNSendGameData ~= nil` | |
| Profil-API von Blizzard für Forever? | Web-Recherche | |
