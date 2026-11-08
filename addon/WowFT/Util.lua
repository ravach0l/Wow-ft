-- Reine Hilfsfunktionen ohne WoW-API, damit sie außerhalb des Spiels testbar sind.
local _, ns = ...

ns.VERSION = "0.5.0"
ns.SCHEMA = 1
ns.MAX_SNAPSHOTS = 50
ns.SNAPSHOT_INTERVAL = 15 * 60 -- Sekunden zwischen periodischen Snapshots
ns.ZONE_THROTTLE = 60          -- mindestens so viele Sekunden zwischen Zonen-Snapshots
ns.COLLECT_DELAY = 3           -- Sekunden Sammelpause nach Änderungen (Taschen, Ruf, ...)
ns.MAX_DEATHLOG = 50
ns.MAX_BOSSKILLS = 100
ns.MAX_PHOTO_REQUESTS = 20

local Util = {}
ns.Util = Util

-- Hängt `item` an `list` an und entfernt die ältesten Einträge über `max`.
function Util.Push(list, item, max)
  list[#list + 1] = item
  local overflow = #list - max
  if overflow > 0 then
    for _ = 1, overflow do
      table.remove(list, 1)
    end
  end
  return list
end

-- Legt fehlende Felder an und migriert alte Schemata. Gibt die DB zurück.
function Util.InitDB(db)
  if type(db) ~= "table" then
    db = {}
  end
  db.schema = db.schema or ns.SCHEMA
  -- Hier landen künftige Migrationen: if db.schema < 2 then ... end
  db.schema = ns.SCHEMA
  db.addonVersion = ns.VERSION
  db.characters = db.characters or {}
  db.ui = db.ui or { shown = true }
  -- Zugangsdaten für den Uploader (Server, Token). Wird vom Uploader gelesen und
  -- vor dem Hochladen geleert; der Server ignoriert den Block.
  db.upload = db.upload or {}
  return db
end

-- Prüft Eingaben aus dem Einstellungsfenster. Leer ist erlaubt (= nicht gesetzt).
-- Regeln wie im Uploader (config.go): Token beginnt mit wft_, Server mit https://
-- (oder http://localhost / http://127.0.0.1 zum Entwickeln).
-- Gibt server, token zurück, bei ungültiger Eingabe nil, nil, Fehlertext.
-- Code fürs Spiel von der Webseite (Profil): WFT-XXXX-XXXX, Schreibweise egal.
-- Gibt ihn einheitlich formatiert zurück oder nil.
function Util.GameCode(text)
  local compact = (text or ""):gsub("[%s%-]", ""):upper()
  local c = "[A-HJ-NP-Z2-9]"
  if compact:match("^WFT" .. c:rep(8) .. "$") then
    return ("WFT-%s-%s"):format(compact:sub(4, 7), compact:sub(8, 11))
  end
  return nil
end

function Util.NormalizeUpload(server, token)
  server = (server or ""):match("^%s*(.-)%s*$"):gsub("/+$", "")
  token = (token or ""):match("^%s*(.-)%s*$")
  local code = Util.GameCode(token)
  if code then
    token = code
  elseif token ~= "" and not token:match("^wft_[%w_%-]+$") then
    return nil, nil, "Bitte den Token (beginnt mit wft_) oder den Code fürs Spiel (WFT-XXXX-XXXX) eintragen."
  end
  local secure = server:match("^https://%S+$")
  local local_dev = server:match("^http://localhost") or server:match("^http://127%.0%.0%.1")
  if server ~= "" and not (secure or local_dev) then
    return nil, nil, "Die Server-Adresse muss mit https:// beginnen."
  end
  return server, token, nil
end

function Util.InitCharacter(db, guid)
  local c = db.characters[guid]
  if not c then
    c = {}
    db.characters[guid] = c
  end
  c.guid = guid
  c.snapshots = c.snapshots or {}
  c.levelUps = c.levelUps or {}
  c.settings = c.settings or {}
  c.deaths = c.deaths or 0
  c.deathLog = c.deathLog or {}
  c.bossKills = c.bossKills or {}
  c.photoRequests = c.photoRequests or {}
  return c
end

-- Schätzt die Spielzeit zwischen zwei TIME_PLAYED_MSG-Antworten.
-- `now` ist eine monotone Uhr in Sekunden (im Spiel GetTime()).
local Played = {}
Played.__index = Played
Util.Played = Played

function Played.New()
  return setmetatable({ total = nil, level = nil, at = nil }, Played)
end

function Played:Set(total, level, now)
  self.total, self.level, self.at = total, level, now
end

function Played:Known()
  return self.total ~= nil
end

-- Neues Level: die Spielzeit im Level beginnt bei 0.
function Played:ResetLevel(now)
  if self:Known() then
    local total = self:Get(now)
    self:Set(total, 0, now)
  end
end

function Played:Get(now)
  if not self:Known() then
    return nil, nil
  end
  local delta = math.floor(math.max(0, now - self.at))
  return self.total + delta, self.level + delta
end

-- Kurze relative Zeitangabe auf Deutsch.
function Util.Ago(seconds)
  seconds = math.max(0, math.floor(seconds))
  if seconds < 60 then
    return "gerade eben"
  elseif seconds < 3600 then
    return ("vor %d Min."):format(math.floor(seconds / 60))
  elseif seconds < 86400 then
    return ("vor %d Std."):format(math.floor(seconds / 3600))
  end
  return ("vor %d Tagen"):format(math.floor(seconds / 86400))
end
