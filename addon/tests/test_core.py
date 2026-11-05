"""Spielt einen Login-Ablauf mit nachgebauter WoW-API durch und prüft WowFTDB."""

from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

ADDON = Path(__file__).resolve().parents[1] / "WowFT"

MOCK = r"""
local S = { time = 1793860000, gametime = 100, level = 12, xp = 500, xpMax = 8800,
            rested = 1200, zone = "Westfall", timers = {}, events = {}, frames = {} }
WOWSTATE = S

function time() return S.time end
function GetTime() return S.gametime end
function UnitGUID() return "Player-4711-0ABC1234" end
function UnitName() return "Testa" end
function UnitClass() return "Krieger", "WARRIOR", 1 end
function UnitRace() return "Mensch", "Human", 1 end
function UnitFactionGroup() return "Alliance", "Allianz" end
function UnitLevel() return S.level end
function UnitXP() return S.xp end
function UnitXPMax() return S.xpMax end
function GetXPExhaustion() return S.rested end
function GetRealZoneText() return S.zone end
function GetZoneText() return S.zone end
function GetRealmName() return "Forever" end
function GetCurrentRegionName() return "EU" end
function RequestTimePlayed() S.playedRequested = (S.playedRequested or 0) + 1 end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function strlower(s) return string.lower(s) end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
NUM_CHAT_WINDOWS = 1
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) S.lastMessage = m end }
SlashCmdList = {}

local function newFrame()
  local f = { events = {}, scripts = {} }
  function f:RegisterEvent(e) self.events[e] = true end
  function f:UnregisterEvent(e) self.events[e] = nil end
  function f:IsEventRegistered(e) return self.events[e] == true end
  function f:SetScript(name, fn) self.scripts[name] = fn end
  S.frames[#S.frames + 1] = f
  return f
end
ChatFrame1 = newFrame()
ChatFrame1:RegisterEvent("TIME_PLAYED_MSG")
function CreateFrame() return newFrame() end

C_Timer = {
  After = function(_, fn) S.timers[#S.timers + 1] = fn end,
  NewTicker = function() end,
}

function FIRE(event, ...)
  for _, f in ipairs(S.frames) do
    if f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
  end
end

function RUN_TIMERS()
  local timers = S.timers
  S.timers = {}
  for _, fn in ipairs(timers) do fn() end
end
"""


@pytest.fixture
def lua():
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK)
    ns = lua.table()
    loader = lua.eval("function(src, name) return load(src, '@' .. name) end")
    for name in ["Util.lua", "Core.lua"]:
        loader((ADDON / name).read_text(), name)("WowFT", ns)
    lua.globals().NS = ns
    return lua


def snapshots(lua):
    return lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].snapshots")


def test_login_snapshot_with_played(lua):
    g = lua.globals()
    lua.execute("FIRE('PLAYER_LOGIN')")
    char = lua.eval("WowFTDB.characters['Player-4711-0ABC1234']")
    assert char.name == "Testa"
    assert char["class"] == "WARRIOR"
    assert char.region == "EU"
    # Chat-Ausgabe von /played ist unterdrückt, bis die Antwort kommt.
    assert g.ChatFrame1.events["TIME_PLAYED_MSG"] is None
    lua.execute("FIRE('TIME_PLAYED_MSG', 36000, 1800)")
    assert g.ChatFrame1.events["TIME_PLAYED_MSG"] is True
    snaps = snapshots(lua)
    assert len(snaps) == 1
    s = snaps[1]
    assert (s.level, s.xp, s.xpMax, s.rested, s.zone) == (12, 500, 8800, 1200, "Westfall")
    assert (s.playedTotal, s.playedLevel) == (36000, 1800)
    # Der Fallback-Timer legt keinen zweiten Snapshot an.
    lua.execute("RUN_TIMERS()")
    assert len(snapshots(lua)) == 1


def test_login_without_played_answer(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); RUN_TIMERS()")
    s = snapshots(lua)[1]
    assert s.playedTotal is None


def test_level_up_and_logout(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 36000, 1800)")
    lua.execute("""
      WOWSTATE.gametime = WOWSTATE.gametime + 600
      WOWSTATE.time = WOWSTATE.time + 600
      FIRE('PLAYER_LEVEL_UP', 13)
      WOWSTATE.level = 13; WOWSTATE.xp = 40; WOWSTATE.xpMax = 10100
      WOWSTATE.time = WOWSTATE.time + 2; WOWSTATE.gametime = WOWSTATE.gametime + 2
      RUN_TIMERS()
    """)
    ups = lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].levelUps")
    assert len(ups) == 1
    assert (ups[1].level, ups[1].playedTotal) == (13, 36600)
    snaps = snapshots(lua)
    assert len(snaps) == 2
    assert (snaps[2].level, snaps[2].playedLevel) == (13, 2)

    lua.execute("WOWSTATE.time = WOWSTATE.time + 60; FIRE('PLAYER_LOGOUT')")
    assert len(snapshots(lua)) == 3


def test_same_second_replaces(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10)")
    lua.execute("NS.TakeSnapshot('manual')")
    assert len(snapshots(lua)) == 1


def test_slash_status(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10)")
    lua.execute("SlashCmdList.WOWFT('status')")
    assert "1 Snapshots" in lua.globals().WOWSTATE.lastMessage
