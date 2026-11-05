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

local function UpdateMeta()
  local _, classToken = UnitClass("player")
  local _, raceToken = UnitRace("player")
  char.name = UnitName("player")
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
  }
  local list = char.snapshots
  local last = list[#list]
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
  TakeSnapshot("logout")
end

for event in pairs(handlers) do
  frame:RegisterEvent(event)
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
  if cmd == "show" then
    ns.UI.SetShown(true)
  elseif cmd == "hide" then
    ns.UI.SetShown(false)
  elseif cmd == "snap" then
    TakeSnapshot("manual")
    Print("Snapshot gespeichert. Mit /reload wird er auf die Platte geschrieben.")
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
  else
    Print("Befehle: /ft show | hide | status | snap")
  end
end
