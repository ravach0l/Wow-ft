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
  if i == 1 then return "Verbessertes Heldenhaftes", "Interface\\Icons\\Ability_Warrior_BattleShout", 1, 1, 3, 3 end
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
    for name in ["Util.lua", "Collect.lua", "Combat.lua", "Recipes.lua", "Core.lua"]:
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
    # Auch ungelernte Talente (Rang 0) kommen mit, für die Baumansicht.
    assert [(t.name, t.rank, t.max, t.tier, t.col) for t in c.talents[1].talents.values()] == [
        ("Verbessertes Heldenhaftes", 3, 3, 1, 1),
        ("Taktiker", 0, 5, 1, 2),
    ]
    # Klassik-API: Icon als Pfad (daraus wird der Bildname), keine Zauber-ID.
    first = c.talents[1].talents[1]
    assert first.icon == "Interface\\Icons\\Ability_Warrior_BattleShout" and first.spell is None
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


FOREVER_API = r"""
-- Forever (Client 1.60.1, Interface 16001): alte Classic-Funktionen fehlen, neue Namensräume da.
GetNumSkillLines, GetSkillLineInfo, GetNumFactions, GetFactionInfo = nil, nil, nil, nil
GetNumTalentTabs, GetTalentTabInfo, GetNumTalents, GetTalentInfo = nil, nil, nil, nil
GetItemInfoInstant, GetContainerNumSlots, GetContainerItemInfo = nil, nil, nil

function GetProfessions() return 4, nil, nil, 7, 8 end
local profs = { [4] = { "Kräuterkunde", 1, 75, 150 }, [7] = { "Angeln", 1, 10, 75 }, [8] = { "Kochen", 1, 5, 75 } }
function GetProfessionInfo(i) local p = profs[i]; return p[1], p[2], p[3], p[4] end

C_Reputation = {
  GetNumFactions = function() return 3 end,
  GetFactionDataByIndex = function(i)
    return ({
      { name = "Horde", isHeader = true, isHeaderWithRep = false },
      { name = "Orgrimmar", factionID = 76, reaction = 5, currentStanding = 4200,
        currentReactionThreshold = 3000, nextReactionThreshold = 9000, isHeader = false },
      { name = "Darnassus", factionID = 69, reaction = 4, currentStanding = 0,
        currentReactionThreshold = 0, nextReactionThreshold = 3000, isHeader = true, isHeaderWithRep = true },
    })[i]
  end,
}

C_ClassTalents = { GetActiveConfigID = function() return 456595 end }
C_SpecializationInfo = {
  GetSpecialization = function() return 1 end,
  GetSpecializationInfo = function() return 102, "Gleichgewicht" end,
}
C_Spell = {
  GetSpellName = function(id) return "Zauber " .. id end,
  GetSpellTexture = function(id) return 130000 + id end,
}
C_Traits = {
  GetConfigInfo = function() return { treeIDs = { 672 } } end,
  GetTreeNodes = function() return { 10, 11, 12 } end,
  GetNodeInfo = function(_, nodeID)
    return ({
      [10] = { currentRank = 2, maxRanks = 3, entryIDs = { 100 }, posX = 1, posY = 2 },
      [11] = { currentRank = 0, maxRanks = 1, entryIDs = { 101 }, posX = 2, posY = 2 },
      [12] = { currentRank = 1, maxRanks = 1, activeEntry = { entryID = 102 }, entryIDs = { 102, 103 }, posX = 3, posY = 5 },
    })[nodeID]
  end,
  GetEntryInfo = function(_, entryID) return { definitionID = entryID + 1000 } end,
  GetDefinitionInfo = function(defID)
    if defID == 1102 then return { overrideName = "Mondfeuer" } end
    return { spellID = defID }
  end,
}

C_Item = { GetItemInfoInstant = function(id) return id, "", "", "", 0, (id == 2589) and 7 or 2 end }
C_Container = {
  GetContainerNumSlots = function(bag) return bag == 0 and 2 or 0 end,
  GetContainerItemInfo = function(_, slot)
    return ({ { itemID = 2589, stackCount = 12, hyperlink = "|Hitem:2589|h[Leinenstoff]|h" },
              { itemID = 6948, stackCount = 1, hyperlink = "|Hitem:6948|h[Ruhestein]|h" } })[slot]
  end,
}
"""


def test_collectors_with_forever_api(lua):
    lua.execute(FOREVER_API)
    skills = lua.eval("NS.Collect.Skills()")
    assert [(s.name, s.rank, s.max, s.header) for s in skills.values()] == [
        ("Kräuterkunde", 75, 150, "Berufe"),
        ("Angeln", 10, 75, "Nebenberufe"),
        ("Kochen", 5, 75, "Nebenberufe"),
    ]

    rep = lua.eval("NS.Collect.Reputation()")
    assert [(r.id, r.name, r.standing, r.value, r.min, r.max) for r in rep.values()] == [
        (76, "Orgrimmar", 5, 4200, 3000, 9000),
        (69, "Darnassus", 4, 0, 0, 3000),
    ]

    tabs = lua.eval("NS.Collect.Talents()")
    tab = tabs[1]
    assert (tab.name, tab.points) == ("Gleichgewicht", 3)
    talents = list(tab.talents.values())
    assert [(t.name, t.rank, t.max) for t in talents] == [
        ("Zauber 1100", 2, 3),
        ("Zauber 1101", 0, 1),
        ("Mondfeuer", 1, 1),
    ]
    # Moderne Talentbäume: Zauber-ID und Icon-Datei-ID für die Bilder auf der Webseite.
    assert [(t.spell, t.icon) for t in talents][0] == (1100, 131100)

    mats = lua.eval("NS.Collect.Materials({0})")
    assert [(m.id, m.name, m.count) for m in mats.values()] == [(2589, "Leinenstoff", 12)]


def test_all_collectors_report_no_errors_with_forever_api(lua):
    lua.execute(FOREVER_API)
    lua.execute("FIRE('PLAYER_LOGIN'); NS.Collect.All(NS.CurrentCharacter())")
    errors = char(lua).apiErrors
    assert not list(errors.keys()), dict(errors)


UI_STUBS = r"""
FRAMES = {}
local function stub(kind)
  local o = { kind = kind, scripts = {}, shown = true, points = {}, text = "", checked = false }
  setmetatable(o, { __index = function(t) return function() return t end end })
  function o:SetScript(name, fn) self.scripts[name] = fn end
  function o:SetShown(s) self.shown = s end
  function o:IsShown() return self.shown end
  function o:Show() self.shown = true; if self.scripts.OnShow then self.scripts.OnShow(self) end end
  function o:Hide() self.shown = false end
  function o:SetText(t) self.text = t end
  function o:GetText() return self.text end
  function o:SetChecked(c) self.checked = c end
  function o:GetChecked() return self.checked end
  function o:CreateTexture() return stub("texture") end
  function o:CreateFontString() return stub("fontstring") end
  function o:GetWidth() return 140 end
  function o:GetCenter() return 0, 0 end
  function o:GetEffectiveScale() return 1 end
  FRAMES[#FRAMES + 1] = o
  return o
end
Minimap = stub("minimap")
BUTTON = nil
UISpecialFrames = {}
tinsert = table.insert
function CreateFrame(kind, name) local f = stub(kind); f.name = name; if name == "WowFTMinimapButton" then BUTTON = f end return f end
function GetCursorPosition() return CURSOR[1], CURSOR[2] end
CURSOR = { 0, 200 }
TIP = {}
GameTooltip = {
  SetOwner = function(_, owner) TIP.owner = owner; TIP.lines = {} end,
  AddLine = function(_, text) TIP.lines[#TIP.lines + 1] = text end,
  Show = function() end, Hide = function() TIP.owner = nil end,
  GetOwner = function() return TIP.owner end,
}
function FIND(kind, text)
  for _, f in ipairs(FRAMES) do
    if f.kind == kind and (text == nil or f.text == text) then return f end
  end
end
function FIND_ALL(kind)
  local out = {}
  for _, f in ipairs(FRAMES) do if f.kind == kind then out[#out + 1] = f end end
  return out
end
"""


def load_ui(lua):
    lua.execute(UI_STUBS)
    loader = lua.eval("function(src, name) return load(src, '@' .. name) end")
    for name in ("UI.lua", "Settings.lua"):
        loader((ADDON / name).read_text(), name)("WowFT", lua.globals().NS)
    lua.execute("FIRE('PLAYER_LOGIN')")


def test_minimap_button(lua):
    load_ui(lua)

    assert lua.eval("BUTTON ~= nil")
    # Tooltip: Level, XP-Anteil (500 von 8800) und Snapshot-Stand.
    lua.execute("BUTTON.scripts.OnEnter(BUTTON)")
    tip = " | ".join(lua.eval("TIP.lines").values())
    assert "WowFT" in tip and "Level 12 · 5% XP" in tip and "Snapshot" in tip

    # Linksklick öffnet die Einstellungen, ein zweiter schließt sie wieder.
    lua.execute("BUTTON.scripts.OnClick(BUTTON, 'LeftButton')")
    assert lua.eval("FIND('Frame', nil) ~= nil and FRAMES[#FRAMES] ~= nil")
    assert lua.eval("(function() for _, f in ipairs(FIND_ALL('Frame')) do if f.name == 'WowFTSettingsFrame' then return f.shown end end end)()")
    lua.execute("BUTTON.scripts.OnClick(BUTTON, 'LeftButton')")
    assert not lua.eval("(function() for _, f in ipairs(FIND_ALL('Frame')) do if f.name == 'WowFTSettingsFrame' then return f.shown end end end)()")

    # Ziehen: Cursor direkt über der Minimap-Mitte -> 90 Grad, wird gemerkt.
    lua.execute("BUTTON.scripts.OnDragStart(BUTTON); BUTTON.scripts.OnUpdate(BUTTON)")
    assert lua.eval("WowFTDB.ui.minimapAngle") == pytest.approx(90)

    # /ft hide blendet den Button aus, /ft show wieder ein.
    lua.execute("SlashCmdList.WOWFT('hide')")
    assert lua.eval("BUTTON.shown") is False and lua.eval("WowFTDB.ui.shown") is False
    lua.execute("SlashCmdList.WOWFT('show')")
    assert lua.eval("BUTTON.shown") is True


def test_normalize_upload(lua):
    n = lambda server, token: tuple(lua.eval("function(a, b) return NS.Util.NormalizeUpload(a, b) end")(server, token))
    assert n("https://wow.example.org/", " wft_Ab-1_x ") == ("https://wow.example.org", "wft_Ab-1_x", None)
    assert n("", "") == ("", "", None)  # leer = nicht gesetzt
    assert n("http://localhost:8000", "wft_a")[0] == "http://localhost:8000"
    assert n("", "geheim")[2] and n("", "wft_ mit leerzeichen")[2]
    assert n("http://wow.example.org", "")[2]  # nur https
    assert n("ftp://x", "")[2]
    # Code fürs Spiel von der Webseite, Schreibweise egal
    assert n("", " wft abcd-efgh ") == ("", "WFT-ABCD-EFGH", None)
    assert n("", "WFT-ABCD-EFG")[2]  # zu kurz
    assert n("", "WFT-ABCD-EFG0")[2]  # 0 kommt im Code nicht vor


def settings_frame(lua):
    return lua.eval("(function() for _, f in ipairs(FIND_ALL('Frame')) do if f.name == 'WowFTSettingsFrame' then return f end end end)()")


def test_settings_window_saves_values(lua):
    load_ui(lua)
    lua.execute("SlashCmdList.WOWFT('config')")
    assert settings_frame(lua).shown is True
    assert lua.eval("WowFTDB.upload ~= nil")

    boxes = lua.eval("FIND_ALL('EditBox')")
    server_box, token_box = boxes[1], boxes[2]
    checks = lua.eval("FIND_ALL('CheckButton')")
    gold, material, minimap = checks[1], checks[2], checks[3]
    save = lua.eval("FIND('Button', 'Speichern')")

    # Gültige Eingabe wird übernommen; Gold an, Material aus, Button weg.
    server_box.text, token_box.text = "https://wow.example.org/", "wft_abc123"
    gold.checked, material.checked, minimap.checked = True, False, False
    save.scripts.OnClick(save)
    db = lua.eval("WowFTDB")
    assert (db.upload.server, db.upload.token) == ("https://wow.example.org", "wft_abc123")
    c = char(lua)
    assert c.settings.trackGold is True and c.settings.trackMaterials is False and c.materials is None
    assert lua.eval("BUTTON.shown") is False and db.ui.shown is False
    assert "Einstellungen gespeichert" in lua.eval("WOWSTATE.lastMessage")

    # Ungültiger Token: nichts wird überschrieben, Fehler steht im Fenster.
    token_box.text = "falsch"
    save.scripts.OnClick(save)
    assert lua.eval("WowFTDB.upload.token") == "wft_abc123"
    status = lua.eval("FIND_ALL('fontstring')")
    assert any("wft_" in (f.text or "") and "ff6666" in (f.text or "") for f in status.values())

    # Code fürs Spiel: einheitlich gespeichert und im Fenster ganz angezeigt.
    token_box.text = "wft abcd efgh"
    save.scripts.OnClick(save)
    assert lua.eval("WowFTDB.upload.token") == "WFT-ABCD-EFGH"
    status = lua.eval("FIND_ALL('fontstring')")
    assert any("Code WFT-ABCD-EFGH gespeichert" in (f.text or "") for f in status.values())

    # Leere Felder löschen die Werte (Schlüssel fehlen dann in der Datei).
    server_box.text, token_box.text = "", ""
    save.scripts.OnClick(save)
    assert lua.eval("WowFTDB.upload.server") is None and lua.eval("WowFTDB.upload.token") is None


def test_settings_window_loads_current_values(lua):
    load_ui(lua)
    lua.execute("WowFTDB.upload.server = 'https://a.example.org'; WowFTDB.upload.token = 'wft_vorhanden99'")
    lua.execute("SlashCmdList.WOWFT('einstellungen')")
    boxes = lua.eval("FIND_ALL('EditBox')")
    assert (boxes[1].text, boxes[2].text) == ("https://a.example.org", "wft_vorhanden99")
    # Material ist standardmäßig an, Gold aus.
    checks = lua.eval("FIND_ALL('CheckButton')")
    assert (checks[1].checked, checks[2].checked, checks[3].checked) == (False, True, True)
    # Der Token erscheint im Status nur gekürzt.
    texts = [f.text for f in lua.eval("FIND_ALL('fontstring')").values()]
    assert any("wft_…den99"[:4] in t and "…" in t and "wft_vorhanden99" not in t for t in texts)


def test_character_name_with_surname(lua):
    # Forever: GetUnitName liefert den vollen Namen.
    lua.execute("function GetUnitName(unit, withRealm) return 'Simmen Taler' end")
    lua.execute("FIRE('PLAYER_LOGIN')")
    assert char(lua).name == "Simmen Taler"


def test_character_name_falls_back_to_unitname_pair(lua):
    # Ohne GetUnitName: UnitName gibt (Vorname, Nachname) zurück.
    lua.execute("GetUnitName = nil; function UnitName() return 'Simmen', 'Taler' end")
    lua.execute("FIRE('PLAYER_LOGIN')")
    assert char(lua).name == "Simmen Taler"


def test_character_name_classic_single_name(lua):
    # Klassische Namen ohne Nachnamen bleiben unverändert.
    lua.execute("GetUnitName = nil")
    lua.execute("FIRE('PLAYER_LOGIN')")
    assert char(lua).name == "Testa"


def test_livetest_sends_on_all_paths(lua):
    lua.execute("""
      WOWSTATE.sent = {}
      WOWSTATE.logging = false
      function LoggingChat(on) if on ~= nil then WOWSTATE.logging = on end return WOWSTATE.logging end
      function SendChatMessage(msg, kind, _, target) table.insert(WOWSTATE.sent, kind .. ':' .. target .. ':' .. msg) end
      UnitName = function() return "Simmen", "Taler" end
      GetUnitName = nil
    """)
    loader = lua.eval("function(src, name) return load(src, '@' .. name) end")
    loader((ADDON / "Live.lua").read_text(), "Live.lua")("WowFT", lua.globals().NS)
    lua.execute("FIRE('PLAYER_LOGIN'); SlashCmdList.WOWFT('livetest')")
    st = lua.globals().WOWSTATE
    assert st.logging is True  # Chat-Protokoll eingeschaltet
    sent = [st.sent[i] for i in range(1, len(st.sent) + 1)]
    stamp = st.time
    assert sent == [
        f"WHISPER:Simmen:WFTLIVE {stamp} whisper-vorname",
        f"WHISPER:Simmen Taler:WFTLIVE {stamp} whisper-leer",
        f"WHISPER:Simmen-Taler:WFTLIVE {stamp} whisper-strich",
    ]
    assert "/chatlog" in st.lastMessage


# --- Addon 0.5.0: Todesursache, Rezepte, Ruhestein, Foto-Infos, /ft share ------------


def fire_cleu(lua, *args):
    g = lua.globals()
    g.CLEU_ARGS = lua.table(*args)
    lua.execute("CombatLogGetCurrentEventInfo = function() return unpack(CLEU_ARGS, 1, 20) end")
    lua.execute("FIRE('COMBAT_LOG_EVENT_UNFILTERED')")


ME = "Player-4711-0ABC1234"


def test_death_records_killer(lua):
    lua.execute("FIRE('PLAYER_LOGIN')")
    # Treffer auf andere werden ignoriert
    fire_cleu(lua, 1, "SWING_DAMAGE", False, "Creature-1", "Wolf", 0, 0, "Player-anders", "X", 0, 0, 30, -1)
    fire_cleu(lua, 1, "SWING_DAMAGE", False, "Creature-2", "Kobold", 0, 0, ME, "Testa", 0, 0, 12, -1)
    fire_cleu(lua, 1, "SPELL_DAMAGE", False, "Creature-3", "Defias-Wegelagerer", 0, 0, ME, "Testa", 0, 0,
              1752, "Finsterer Stoß", 1, 45, 7)
    lua.execute("FIRE('PLAYER_DEAD')")
    k = lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].deathLog[1].killer")
    assert (k.source, k.spell, k.amount, k.overkill) == ("Defias-Wegelagerer", "Finsterer Stoß", 45, 7)


def test_death_environment_and_stale_hits(lua):
    lua.execute("FIRE('PLAYER_LOGIN')")
    fire_cleu(lua, 1, "ENVIRONMENTAL_DAMAGE", False, None, None, 0, 0, ME, "Testa", 0, 0, "Falling", 300, 120)
    lua.execute("FIRE('PLAYER_DEAD')")
    k = lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].deathLog[1].killer")
    assert (k.environment, k.amount, k.overkill) == ("Falling", 300, 120)
    # Treffer älter als 10 s zählen nicht
    fire_cleu(lua, 1, "SWING_DAMAGE", False, "Creature-2", "Kobold", 0, 0, ME, "Testa", 0, 0, 12, -1)
    lua.execute("WOWSTATE.gametime = WOWSTATE.gametime + 60; FIRE('PLAYER_DEAD')")
    assert lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].deathLog[2].killer") is None


def test_recipes_classic_tradeskill(lua):
    lua.execute("""
      GetTradeSkillLine = function() return "Schmiedekunst", 87, 150 end
      local R = {
        { "Schmiedekunst", "header" },
        { "Rauer Schärfstein", "easy", "|Hitem:2862|h[Rauer Schärfstein]|h", { { "Rauer Stein", 1, 3001 } } },
        { "Kupferkettengürtel", "optimal", "|Hitem:2851|h[Kupferkettengürtel]|h",
          { { "Kupferbarren", 6, 2840 }, { "Leichtes Leder", 1, 2318 } } },
      }
      GetNumTradeSkills = function() return #R end
      GetTradeSkillInfo = function(i) return R[i][1], R[i][2] end
      GetTradeSkillItemLink = function(i) return R[i][3] end
      GetTradeSkillNumReagents = function(i) return R[i][4] and #R[i][4] or 0 end
      GetTradeSkillReagentInfo = function(i, j) local r = R[i][4][j]; return r[1], nil, r[2] end
      GetTradeSkillReagentItemLink = function(i, j) return "|Hitem:" .. R[i][4][j][3] .. "|h" end
    """)
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TRADE_SKILL_SHOW'); FIRE('TRADE_SKILL_UPDATE'); RUN_TIMERS()")
    rec = lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].recipes")
    assert len(rec) == 1 and rec[1].profession == "Schmiedekunst"
    lst = rec[1].list
    assert [lst[i].name for i in range(1, len(lst) + 1)] == ["Rauer Schärfstein", "Kupferkettengürtel"]
    belt = lst[2]
    assert belt.item == 2851
    assert [(r.id, r.name, r.count) for r in belt.reagents.values()] == [(2840, "Kupferbarren", 6), (2318, "Leichtes Leder", 1)]
    # Erneutes Scannen ersetzt den Beruf statt ihn zu doppeln
    lua.execute("FIRE('TRADE_SKILL_UPDATE'); RUN_TIMERS()")
    assert len(lua.eval("WowFTDB.characters['Player-4711-0ABC1234'].recipes")) == 1


def test_bind_and_photo_info(lua):
    lua.execute("GetBindLocation = function() return 'Goldhain' end; GetSubZoneText = function() return 'Gasthaus' end")
    lua.execute("FIRE('PLAYER_LOGIN'); FIRE('TIME_PLAYED_MSG', 10, 10); RUN_TIMERS()")
    assert char(lua).bind == "Goldhain"
    lua.execute("""
      local photo = {}
      NS.Photo = photo
    """)
    loader = lua.eval("function(src, name) return load(src, '@' .. name) end")
    loader((ADDON / "Photo.lua").read_text(), "Photo.lua")("WowFT", lua.globals().NS)
    lua.execute("NS.Photo.Record(1793869999)")
    info = char(lua).photoInfo[1]
    assert (info.t, info.level, info.zone, info.subzone) == (1793869999, 12, "Westfall", "Gasthaus")


def test_share(lua):
    lua.execute("""
      WOWSTATE.sent = {}
      function SendChatMessage(msg, kind) table.insert(WOWSTATE.sent, kind .. '|' .. msg) end
      IsInGroup = function() return true end
    """)
    lua.execute("FIRE('PLAYER_LOGIN'); SlashCmdList.WOWFT('share'); SlashCmdList.WOWFT('share gilde')")
    sent = lua.globals().WOWSTATE.sent
    assert sent[1] == "PARTY|[WowFT] Testa · Level 12 (5%) · Westfall · wow.the-birds.xyz"
    assert sent[2].startswith("GUILD|")
    lua.execute("SlashCmdList.WOWFT('share irgendwo')")
    assert "Ziel unbekannt" in lua.globals().WOWSTATE.lastMessage
