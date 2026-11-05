"""Tests für addon/WowFT/Util.lua, ausgeführt mit eingebettetem Lua (lupa)."""

from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

UTIL = Path(__file__).resolve().parents[1] / "WowFT" / "Util.lua"


@pytest.fixture
def ns():
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    chunk = lua.eval("function(src) return load(src, '@Util.lua') end")(UTIL.read_text())
    ns = lua.table()
    chunk("WowFT", ns)
    ns.lua = lua
    return ns


def to_list(lua_table):
    return [lua_table[i] for i in range(1, len(lua_table) + 1)]


def test_push_trims_oldest(ns):
    lst = ns.lua.table()
    for i in range(1, 8):
        ns.Util.Push(lst, i, 5)
    assert to_list(lst) == [3, 4, 5, 6, 7]


def test_init_db_creates_defaults(ns):
    db = ns.Util.InitDB(None)
    assert db.schema == ns.SCHEMA
    assert db.addonVersion == ns.VERSION
    assert db.characters is not None
    assert db.ui.shown is True


def test_init_db_keeps_existing(ns):
    db = ns.lua.eval("{ characters = { x = { name = 'A' } }, ui = { shown = false } }")
    db = ns.Util.InitDB(db)
    assert db.characters.x.name == "A"
    assert db.ui.shown is False


def test_init_character(ns):
    db = ns.Util.InitDB(None)
    c = ns.Util.InitCharacter(db, "Player-1-ABC")
    assert c.guid == "Player-1-ABC"
    assert len(c.snapshots) == 0
    c.name = "A"
    assert ns.Util.InitCharacter(db, "Player-1-ABC").name == "A"


def test_played_estimate(ns):
    p = ns.Util.Played.New()
    assert p.Known(p) is False
    assert p.Get(p, 10) == (None, None)
    p.Set(p, 1000, 100, 50.0)
    assert p.Get(p, 80.7) == (1030, 130)
    p.ResetLevel(p, 90.0)
    assert p.Get(p, 100.0) == (1050, 10)


@pytest.mark.parametrize(
    "seconds,text",
    [(5, "gerade eben"), (125, "vor 2 Min."), (7300, "vor 2 Std."), (200000, "vor 2 Tagen")],
)
def test_ago(ns, seconds, text):
    assert ns.Util.Ago(seconds) == text
