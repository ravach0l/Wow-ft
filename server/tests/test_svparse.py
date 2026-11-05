import json

import pytest

from wowft.svparse import ParseError, parse

from .conftest import FIXTURES


def test_fixture_matches_json(sv_text):
    data = parse(sv_text)["WowFTDB"]
    expected = json.loads((FIXTURES / "ingest.json").read_text(encoding="utf-8"))
    assert data == expected


def test_values():
    text = r"""
    A = { 1, 2.5, -3, 1e3, 0x1F, true, false, "x\"y\\z\n", 'q', [[lang]] }
    B = { ["a b"] = { }, c = nil, [5] = "fünf", -- Kommentar
          --[[ block ]] d = { [1] = "x", [2] = "y" } }
    C = "\195\164\195\182"
    """
    out = parse(text)
    assert out["A"] == [1, 2.5, -3, 1000, 31, True, False, 'x"y\\z\n', "q", "lang"]
    assert out["B"] == {"a b": {}, "5": "fünf", "d": ["x", "y"]}
    assert out["C"] == "äö"


@pytest.mark.parametrize(
    "text",
    ["A = {", 'A = "offen', "A = { 1 2 }", "= 1", "A = os.execute('rm')", "A = function() end"],
)
def test_errors(text):
    with pytest.raises(ParseError):
        parse(text)


def test_depth_limit():
    with pytest.raises(ParseError):
        parse("A = " + "{" * 40 + "}" * 40)


@pytest.mark.parametrize("text", ["A = { 1,", "A = ", 'A = "\\x"', "A = {[1] = }", "A = { [", "A = '"])
def test_truncated(text):
    with pytest.raises(ParseError):
        parse(text)
