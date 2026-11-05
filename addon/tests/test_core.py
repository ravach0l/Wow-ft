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

-- Phase 4
function GetMoney() return 123456 end
local SKILLS = {
  { "Berufe", true }, { "Bergbau", false, nil, 87, nil, nil, 150 },
  { "Waffenfertigkeiten", true }, { "Schwerter", false, nil, 60, nil, nil, 60 },
}
function GetNumSkillLines() return #SKILLS end
function GetSkillLineInfo(i) return unpack(SKILLS[i], 1, 7) end
function GetInventoryItemLink(_, slot)
  if slot == 16 then return "|cff0070dd|Hitem:2042:0:0:0|h[Klinge des Testers]|h|r" end
end
function GetInventoryItemQuality(_, slot) return slot == 16 and 3 or nil end
local FACTIONS = {
  { "Allianz", nil, 0, 0, 0, 0, false, false, true, false, false, false, false, 469 },
  { "Sturmwind", nil, 5, 3000, 9000, 4500, false, false, false, false, true, false, true, 72 },
}
function GetNumFactions() return #FACTIONS end
function GetFactionInfo(i) return unpack(FACTIONS[i], 1, 14) end
function GetNumTalentTabs() return 1 end
function GetTalentTabInfo() return 161, "Waffen" end
function GetNumTalents() return 2 end
function GetTalentInfo(_, i)
  if i == 1 then return "Verbessertes Heldenhaftes", nil, 1, 1, 3, 3 end
  return "Taktiker", nil, 1, 2, 0, 5
end
local BAGS = {
  [0] = { { itemID = 2770, stackCount = 12, hyperlink = "|Hitem:2770|h[Kupfererz]|h" },
          { itemID = 6948, stackCount = 1, hyperlink = "|Hitem:6948|h[Ruhestein]|h" } },
  [1] = { { itemID = 2770, stackCount = 8, hyperlink = "|Hitem:2770|h[Kupfererz]|h" } },
  [-1] = { { itemID = 2589, stackCount = 20, hyperlink = "|Hitem:2589|h[Leinenstoff]|h" } },
}
C_Container = {
  GetContainerNumSlots = function(bag) return BAGS[bag] and #BAGS[bag] or 0 end,
  GetContainerItemInfo = function(bag, slot) return BAGS[bag] and BAGS[bag][slot] end,
}
function GetItemInfoInstant(id)
  local class = (id == 2770 or id == 2589) and 7 or 15
  return id, "", "", "", 0, class, 0
end
function GetItemInfo() return nil end
function GetInstanceInfo() return "Die Todesminen", "party" end
NUM_BAG_SLOTS = 4
NUM_BANKBAGSLOTS = 6
BANK_CONTAINER = -1
unpack = unpack or table.unpack

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
    for name in ["Util.lua", "Collect.lua", "Core.lua"]:
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


def char(lua):
    return lua.eval("WowFTDB.characters['Player-4711-0ABC1234']")


def test_collects_phase4_state(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10); RUN_TIMERS()")
    c = char(lua)
    skills = [(c.skills[i].name, c.skills[i].rank, c.skills[i].header) for i in range(1, len(c.skills) + 1)]
    assert skills == [("Bergbau", 87, "Berufe"), ("Schwerter", 60, "Waffenfertigkeiten")]
    eq = c.equipment[1]
    assert (eq.slot, eq.id, eq.name, eq.quality) == (16, 2042, "Klinge des Testers", 3)
    assert len(c.reputation) == 1 and c.reputation[1].name == "Sturmwind" and c.reputation[1].standing == 5
    assert c.talents[1].name == "Waffen" and c.talents[1].points == 3
    bags = c.materials.bags
    assert len(bags) == 1 and (bags[1].id, bags[1].name, bags[1].count) == (2770, "Kupfererz", 20)
    assert c.materials.bank is None
    assert c.snapshots[1].gold == 123456


def test_bank_scan(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('BANKFRAME_OPENED')")
    bank = char(lua).materials.bank
    assert (bank[1].id, bank[1].count) == (2589, 20)
    assert char(lua).materials.bankScanned == lua.globals().WOWSTATE.time


def test_bag_update_is_debounced(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10); RUN_TIMERS()")
    lua.execute("FIRE('BAG_UPDATE_DELAYED'); FIRE('BAG_UPDATE_DELAYED'); FIRE('UPDATE_FACTION')")
    assert len(lua.globals().WOWSTATE.timers) == 1


def test_api_error_is_isolated(lua):
    lua.execute("GetTalentInfo = function() error('kaputt') end")
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10); RUN_TIMERS()")
    c = char(lua)
    assert c.talents is None
    assert "kaputt" in c.apiErrors.talents
    assert len(c.skills) == 2


def test_death_and_boss(lua):
    lua.execute("FIRE('PLAYER_LOGIN')")
    lua.execute("FIRE('PLAYER_DEAD'); FIRE('ENCOUNTER_END', 1, 'Edwin VanCleef', 1, 5, 1)")
    lua.execute("FIRE('ENCOUNTER_END', 2, 'Wipe', 1, 5, 0)")
    c = char(lua)
    assert c.deaths == 1 and c.deathLog[1].zone == "Westfall"
    assert len(c.bossKills) == 1
    assert (c.bossKills[1].name, c.bossKills[1].instance) == ("Edwin VanCleef", "Die Todesminen")


def test_settings_commands(lua):
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10); RUN_TIMERS()")
    lua.execute("SlashCmdList.WOWFT('gold aus'); SlashCmdList.WOWFT('material aus')")
    lua.execute("WOWSTATE.time = WOWSTATE.time + 5; NS.TakeSnapshot('manual'); NS.Collect.All(NS.CurrentCharacter())")
    c = char(lua)
    assert c.snapshots[2].gold is None
    assert c.materials is None
