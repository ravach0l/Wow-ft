"""Talent-Icons: Zauber-ID -> Icon-Name (Wowhead) -> zwischengespeichertes Bild."""

import httpx

from wowft import icons
from wowft.models import SpellIcon

from .conftest import upload_token
from .test_api import ingest

JPEG = b"\xff\xd8\xff\xe0" + b"1" * 50

SV = """WowFTDB = {
["schema"] = 1,
["characters"] = {
["Player-1-DRU"] = {
["guid"] = "Player-1-DRU", ["name"] = "Elune", ["class"] = "DRUID",
["snapshots"] = { { ["t"] = 1793860000, ["level"] = 10, ["xp"] = 1, ["xpMax"] = 7600 } },
["talents"] = {
  { ["name"] = "Druid", ["points"] = 1, ["talents"] = {
    { ["name"] = "Genesis", ["rank"] = 1, ["max"] = 5, ["tier"] = 0, ["col"] = 2,
      ["spell"] = 57810, ["icon"] = 135730 },
    { ["name"] = "Wild Growth", ["rank"] = 0, ["max"] = 1, ["tier"] = 6, ["col"] = 9, ["spell"] = 48438 },
    { ["name"] = "Unbekannt", ["rank"] = 0, ["max"] = 1, ["tier"] = 6, ["col"] = 1, ["spell"] = 999999 },
    { ["name"] = "Klassik", ["rank"] = 2, ["max"] = 5, ["tier"] = 1, ["col"] = 1,
      ["icon"] = "Interface\\\\Icons\\\\Spell_Nature_StarFall" },
  } },
},
},
},
}
"""


class FakeWowhead(httpx.MockTransport):
    """Antwortet wie nether.wowhead.com (Forever kennt nichts, Retail schon) und wie der Bilderserver."""

    def __init__(self):
        self.calls = []
        super().__init__(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if "zamimg" in url:
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        if any(f"/{env}/" in url for env in ("forever", "classic", "tbc", "wotlk", "cata")):
            return httpx.Response(200, json={"error": "Entity not found"})
        spell = url.rsplit("/", 1)[1]
        known = {"57810": "ability_druid_genesis", "48438": "ability_druid_flourish"}
        if spell in known:
            return httpx.Response(200, json={"name": "x", "icon": known[spell]})
        return httpx.Response(200, json={"error": "Entity not found"})


def use_fake(monkeypatch, settings):
    fake = FakeWowhead()
    monkeypatch.setattr(settings, "icon_lookup", True)
    real_client = httpx.Client

    monkeypatch.setattr(icons.httpx, "Client", lambda **kw: real_client(transport=fake, **kw))
    monkeypatch.setattr(icons.httpx, "get", lambda url, **kw: real_client(transport=fake).get(url))
    return fake


def test_icon_from_path():
    assert icons.icon_from_path("Interface\\Icons\\Spell_Nature_StarFall") == "spell_nature_starfall"
    assert icons.icon_from_path("Interface/Icons/INV_Misc_Book_09.blp") == "inv_misc_book_09"
    assert icons.icon_from_path(135730) is None
    # Nur der Dateiname zählt, und nur einfache Zeichen.
    assert icons.icon_from_path("../../etc/passwd") == "passwd"
    assert icons.icon_from_path("Interface\\Icons\\Böse Datei") is None


def test_upload_resolves_icons_in_background(make_client, settings, monkeypatch):
    fake = use_fake(monkeypatch, settings)
    bob = make_client("bob")
    assert ingest(bob, upload_token(bob), SV.encode()).status_code == 200
    # Die Hintergrundaufgabe lief nach der Antwort (TestClient führt sie aus).
    lookups = [c for c in fake.calls if "tooltip" in c]
    assert {c.rsplit("/", 1)[1] for c in lookups} == {"57810", "48438", "999999"}
    assert any("/forever/" in c for c in lookups)  # Forever wird zuerst gefragt

    cid = bob.get("/api/me/characters").json()[0]["id"]
    talents = bob.get(f"/api/characters/{cid}/history").json()["state"]["talents"][0]["talents"]
    urls = {t["name"]: t["iconUrl"] for t in talents}
    assert urls == {
        "Genesis": "/api/icons/ability_druid_genesis.jpg",
        "Wild Growth": "/api/icons/ability_druid_flourish.jpg",
        "Unbekannt": None,
        "Klassik": "/api/icons/spell_nature_starfall.jpg",
    }

    # Zweiter Upload: bekannte Zauber werden nicht erneut abgefragt.
    before = len(fake.calls)
    ingest(bob, upload_token(bob), SV.encode())
    assert len(fake.calls) == before


def test_icon_image_is_cached(make_client, settings, monkeypatch, tmp_path):
    fake = use_fake(monkeypatch, settings)
    bob = make_client("bob")
    assert make_client().get("/api/icons/ability_druid_flourish.jpg").status_code == 401
    r = bob.get("/api/icons/ability_druid_flourish.jpg")
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    n = len(fake.calls)
    assert bob.get("/api/icons/ability_druid_flourish.jpg").content == JPEG
    assert len(fake.calls) == n  # aus dem Zwischenspeicher
    assert bob.get("/api/icons/..%2F..%2Fsecret.jpg").status_code in (404, 422)
    assert bob.get("/api/icons/Bad-Name.jpg").status_code == 404


def test_lookup_disabled_does_nothing(make_client, settings):
    bob = make_client("bob")
    assert ingest(bob, upload_token(bob), SV.encode()).status_code == 200
    assert bob.get("/api/icons/ability_druid_flourish.jpg").status_code == 404


def test_not_found_is_retried_after_a_week(make_client, settings, monkeypatch):
    from wowft import db

    use_fake(monkeypatch, settings)
    bob = make_client("bob")
    ingest(bob, upload_token(bob), SV.encode())
    with db.new_session() as s:
        assert s.get(SpellIcon, 999999).icon is None
        assert icons.missing(s, {999999, 48438}) == []
        later = icons.now() + icons.RETRY_AFTER + 1
        monkeypatch.setattr(icons, "now", lambda: later)
        assert icons.missing(s, {999999, 48438}) == [999999]
