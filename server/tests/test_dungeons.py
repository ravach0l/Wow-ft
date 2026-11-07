"""Dungeon-Planer: Stufen-Tabelle, Zuordnung von Instanznamen, Endpunkt."""

from wowft import dungeons

from .conftest import upload_token
from .test_api import ingest, setup_group


def test_table_is_consistent():
    keys = [d.key for d in dungeons.DUNGEONS]
    assert len(keys) == len(set(keys))
    for d in dungeons.DUNGEONS:
        assert 1 <= d.min <= d.max <= 60, d.key
        assert d.size >= 5


def test_instance_names_de_and_en():
    assert dungeons.keys_for_instance("Die Todesminen") == ["dm"]
    assert dungeons.keys_for_instance("The Deadmines") == ["dm"]
    assert dungeons.keys_for_instance("Zul'Farrak") == ["zf"]
    # Flügel teilen sich den Instanznamen
    assert dungeons.keys_for_instance("Scharlachrotes Kloster") == ["sm_gy", "sm_lib", "sm_arm", "sm_cath"]
    assert set(dungeons.keys_for_instance("Schwarzfelsspitze")) == {"lbrs", "ubrs"}
    assert dungeons.keys_for_instance("Irgendwo") == []
    assert dungeons.keys_for_instance(None) == []


def test_endpoint(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    r = alice.get(f"/api/groups/{g['id']}/dungeons").json()
    assert any(d["key"] == "dm" and d["min"] == 17 and d["name"] == "Die Todesminen" for d in r["dungeons"])
    assert "names" not in r["dungeons"][0]
    by_name = {c["name"]: c for c in r["characters"]}
    testa = by_name["Testa"]
    assert (testa["level"], testa["faction"], testa["ownerName"]) == (13, "Alliance", "bob")
    # Boss „Edwin VanCleef“ in „Die Todesminen“ aus der Fixture
    assert testa["cleared"] == ["dm"]
    assert by_name["Twinka"]["cleared"] == []

    # Boss-Kills ausgeblendet: dann auch kein „schon besiegt“
    cid = testa["id"]
    assert bob.patch(f"/api/characters/{cid}", json={"share": {"bosses": False}}).status_code == 200
    r = alice.get(f"/api/groups/{g['id']}/dungeons").json()
    assert next(c for c in r["characters"] if c["id"] == cid)["cleared"] == []
    # Fremde sehen nichts
    assert make_client("eve").get(f"/api/groups/{g['id']}/dungeons").status_code == 404
