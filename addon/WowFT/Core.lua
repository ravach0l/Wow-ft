-- Erfasst Kernwerte des eigenen Charakters und legt sie in WowFTDB ab.
-- WoW schreibt WowFTDB erst bei Logout oder /reload auf die Platte;
-- der Uploader schickt die Datei danach an den Server.
local _, ns = ...
local Util = ns.Util

local played = Util.Played.New()
local char -- Tabelle des aktuellen Charakters in WowFTDB
local lastZoneSnapshot = 0
local waitingForLoginPlayed = false
local suppressedFrames = {}

local function Print(msg)
  DEFAULT_CHAT_FRAME:AddMessage("|cff7fbfffWowFT|r " .. msg)
end
ns.Print = Print

---------------------------------------------------------------------------
-- /played ohne Chat-Ausgabe anfragen
---------------------------------------------------------------------------
local function RequestPlayedQuietly()
  for i = 1, (NUM_CHAT_WINDOWS or 10) do
    local frame = _G["ChatFrame" .. i]
    if frame and frame:IsEventRegistered("TIME_PLAYED_MSG") then
      frame:UnregisterEvent("TIME_PLAYED_MSG")
      suppressedFrames[#suppressedFrames + 1] = frame
    end
  end
  RequestTimePlayed()
end

local function RestoreChatFrames()
  for i = 1, #suppressedFrames do
    suppressedFrames[i]:RegisterEvent("TIME_PLAYED_MSG")
  end
  wipe(suppressedFrames)
end

---------------------------------------------------------------------------
-- Daten erfassen
---------------------------------------------------------------------------
local function RegionName()
  if GetCurrentRegionName then
    local ok, name = pcall(GetCurrentRegionName)
    if ok then
      return name
    end
  end
  return nil
end

-- Forever: Charaktere haben Vor- und Nachnamen. UnitName liefert beide Teile als zwei
-- Werte (der zweite steht dort, wo sonst der Realm kommt), GetUnitName(unit, false) den
-- zusammengesetzten Namen ("Simmen Taler").
local function FullName()
  if GetUnitName then
    local ok, name = pcall(GetUnitName, "player", false)
    if ok and type(name) == "string" and name ~= "" then
      return name
    end
  end
  local name, surname = UnitName("player")
  if surname and surname ~= "" then
    return name .. " " .. surname
  end
  return name
end

local function UpdateMeta()
  local _, classToken = UnitClass("player")
  local _, raceToken = UnitRace("player")
  char.name = FullName()
  char.realm = GetRealmName() -- Forever hat keine wählbaren Realms; nur zur Info
  char.region = RegionName()
  char.class = classToken
  char.race = raceToken
  char.faction = UnitFactionGroup("player")
  char.updated = time()
end

local function TakeSnapshot(reason)
  if not char then
    return
  end
  local total, inLevel = played:Get(GetTime())
  local snap = {
    t = time(),
    level = UnitLevel("player"),
    xp = UnitXP("player"),
    xpMax = UnitXPMax("player"),
    rested = GetXPExhaustion() or 0,
    zone = GetRealZoneText() or GetZoneText(),
    playedTotal = total,
    playedLevel = inLevel,
    gold = char.settings.trackGold ~= false and GetMoney() or nil,
  }
  local list = char.snapshots
  local last = list[#list]
  -- Beim Logout/Reload liefert WoW manchmal Müll (altes Level, XP-Max 0). Das Level sinkt nie;
  -- XP-Max 0 gibt es nur auf Maximallevel (dann hatte auch der Snapshot davor 0).
  if last and (snap.level < last.level or (snap.xpMax == 0 and (last.xpMax or 0) > 0)) then
    ns.lastSnapshotReason = "verworfen (" .. tostring(reason) .. ")"
    return
  end
  if last and last.t == snap.t then
    list[#list] = snap -- gleicher Zeitpunkt: ersetzen statt doppeln
  else
    Util.Push(list, snap, ns.MAX_SNAPSHOTS)
  end
  char.updated = snap.t
  ns.lastSnapshotReason = reason
  if ns.UI then
    ns.UI.Refresh()
  end
end
ns.TakeSnapshot = TakeSnapshot

function ns.CurrentCharacter()
  return char
end

---------------------------------------------------------------------------
-- Phase 4: Zustand sammeln (gebündelt, damit Taschen-Events nicht spammen)
---------------------------------------------------------------------------
local collectPending = false
local bankOpen = false

local function ScheduleCollect()
  if collectPending or not char then
    return
  end
  collectPending = true
  C_Timer.After(ns.COLLECT_DELAY, function()
    collectPending = false
    ns.Collect.All(char)
    if bankOpen then
      ns.Collect.Bank(char)
    end
  end)
end
ns.ScheduleCollect = ScheduleCollect

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local frame = CreateFrame("Frame")
local handlers = {}

function handlers.PLAYER_LOGIN()
  WowFTDB = Util.InitDB(WowFTDB)
  ns.db = WowFTDB
  local guid = UnitGUID("player")
  char = Util.InitCharacter(WowFTDB, guid)
  UpdateMeta()

  waitingForLoginPlayed = true
  RequestPlayedQuietly()
  -- Falls /played nicht antwortet, trotzdem einen Snapshot anlegen.
  C_Timer.After(10, function()
    if waitingForLoginPlayed then
      waitingForLoginPlayed = false
      RestoreChatFrames()
      TakeSnapshot("login")
    end
  end)

  C_Timer.NewTicker(ns.SNAPSHOT_INTERVAL, function()
    TakeSnapshot("interval")
  end)

  if ns.UI then
    ns.UI.Init()
  end
  -- Etwas warten, bis Item- und Fraktionsdaten geladen sind.
  C_Timer.After(5, function()
    ns.Collect.All(char)
  end)
end

function handlers.TIME_PLAYED_MSG(total, inLevel)
  played:Set(total, inLevel, GetTime())
  RestoreChatFrames()
  if waitingForLoginPlayed then
    waitingForLoginPlayed = false
    TakeSnapshot("login")
  end
end

function handlers.PLAYER_LEVEL_UP(newLevel)
  if not char then
    return
  end
  played:ResetLevel(GetTime())
  local total = played:Get(GetTime())
  char.levelUps[#char.levelUps + 1] = {
    t = time(),
    level = newLevel,
    playedTotal = total,
  }
  -- UnitLevel liefert direkt nach dem Event teils noch das alte Level.
  C_Timer.After(2, function()
    TakeSnapshot("levelup")
    RequestPlayedQuietly()
  end)
end

function handlers.ZONE_CHANGED_NEW_AREA()
  local now = GetTime()
  if now - lastZoneSnapshot >= ns.ZONE_THROTTLE then
    lastZoneSnapshot = now
    TakeSnapshot("zone")
  end
end

function handlers.PLAYER_XP_UPDATE()
  if ns.UI then
    ns.UI.Refresh()
  end
end

function handlers.PLAYER_LOGOUT()
  -- Hier nichts sammeln: Beim Logout/Reload liefern Berufe-, Taschen- und Ausrüstungs-APIs leere
  -- Listen und würden den guten Stand überschreiben. Der steht von Login und Ereignissen her bereit.
  TakeSnapshot("logout")
end

function handlers.PLAYER_DEAD()
  if not char then
    return
  end
  char.deaths = (char.deaths or 0) + 1
  Util.Push(char.deathLog, {
    t = time(),
    level = UnitLevel("player"),
    zone = GetRealZoneText() or GetZoneText(),
  }, ns.MAX_DEATHLOG)
end

-- Boss besiegt (Dungeons und Schlachtzüge).
function handlers.ENCOUNTER_END(encounterID, encounterName, _, _, success)
  if not char or success ~= 1 then
    return
  end
  local instance = GetInstanceInfo()
  Util.Push(char.bossKills, {
    t = time(),
    id = encounterID,
    name = encounterName,
    instance = instance,
    level = UnitLevel("player"),
  }, ns.MAX_BOSSKILLS)
end

function handlers.BANKFRAME_OPENED()
  bankOpen = true
  if char then
    ns.Collect.Bank(char)
  end
end

function handlers.BANKFRAME_CLOSED()
  bankOpen = false
end

for _, event in ipairs({
  "SKILL_LINES_CHANGED",
  "PLAYER_EQUIPMENT_CHANGED",
  "UPDATE_FACTION",
  "CHARACTER_POINTS_CHANGED",
  "BAG_UPDATE_DELAYED",
  "PLAYERBANKSLOTS_CHANGED",
}) do
  handlers[event] = ScheduleCollect
end

-- Unbekannte Events (andere Client-Version) dürfen das Addon nicht stoppen.
for event in pairs(handlers) do
  pcall(frame.RegisterEvent, frame, event)
end
frame:SetScript("OnEvent", function(_, event, ...)
  handlers[event](...)
end)

---------------------------------------------------------------------------
-- Slash-Befehle
---------------------------------------------------------------------------
SLASH_WOWFT1 = "/ft"
SlashCmdList.WOWFT = function(input)
  local cmd = strlower(strtrim(input or ""))
  if not char and cmd ~= "" then
    Print("Noch nicht initialisiert.")
    return
  end
  if cmd == "show" then
    ns.UI.SetShown(true)
  elseif cmd == "hide" then
    ns.UI.SetShown(false)
  elseif cmd == "foto" then
    ns.Photo.Open()
  elseif cmd == "config" or cmd == "einstellungen" or cmd == "settings" then
    ns.Settings.Toggle()
  elseif cmd == "gold an" or cmd == "gold aus" then
    char.settings.trackGold = cmd == "gold an"
    Print("Gold wird " .. (char.settings.trackGold and "erfasst." or "nicht mehr erfasst."))
  elseif cmd == "material an" or cmd == "material aus" then
    char.settings.trackMaterials = cmd == "material an"
    if not char.settings.trackMaterials then
      char.materials = nil
    end
    Print("Handwerksmaterialien werden " .. (char.settings.trackMaterials and "erfasst." or "nicht mehr erfasst."))
  elseif cmd == "snap" then
    TakeSnapshot("manual")
    Print("Snapshot gespeichert. Mit /reload wird er auf die Platte geschrieben.")
  elseif cmd == "api" then
    WowFTDB.probe = ns.Collect.Probe()
    Print(("API-Prüfung gespeichert (%d Funktionen vorhanden, %d fehlen). Jetzt /reload."):format(
      #WowFTDB.probe.present,
      #WowFTDB.probe.missing
    ))
  elseif cmd == "status" then
    if not char then
      Print("Noch nicht initialisiert.")
      return
    end
    local last = char.snapshots[#char.snapshots]
    Print(("%d Snapshots, %d Level-Ups. Letzter Snapshot: %s."):format(
      #char.snapshots,
      #char.levelUps,
      last and Util.Ago(time() - last.t) or "keiner"
    ))
    for key, err in pairs(char.apiErrors or {}) do
      Print(("API-Problem bei %s: %s"):format(key, err))
    end
  else
    Print("Befehle: /ft config | show | hide | status | snap | foto | gold an|aus | material an|aus")
  end
end
