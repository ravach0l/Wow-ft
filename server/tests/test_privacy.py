"""Freigaben: Was Gruppenmitglieder von einem Charakter sehen (privacy.py).

Die Prüfung muss auf dem Server stattfinden: Ausgeblendetes darf in keiner Antwort stehen
(Übersicht, Detailseite, Feed, Material, Rennen, Foto, Discord).
"""

import pytest

from wowft import discord, privacy

from .conftest import upload_token
from .test_api import ingest, setup_group
from .test_phase4 import JPEG, bump


@pytest.fixture
def world(make_client, sv_text, settings, monkeypatch):
    """alice (Betrachterin, Admin) und bob (Besitzer von „Testa“) in einer Gruppe, zwei Uploads.

    Der Rennen-Modus ist an, damit die Spielzeit überhaupt sichtbar sein kann.
    """
    monkeypatch.setattr(settings, "admin_users", "alice")
    alice, bob, g = setup_group(make_client)
    assert alice.patch("/api/admin/features", json={"race": True}).status_code == 200
    tok = upload_token(bob)
    ingest(bob, tok, sv_text.encode())
    ingest(bob, tok, bump(sv_text).encode())
    cid = bob.get("/api/me/characters").json()[0]["id"]
    return alice, bob, g, cid, tok


def share(client, cid, **changes):
    r = client.patch(f"/api/characters/{cid}", json={"share": changes})
    assert r.status_code == 200, r.text
    return r.json()


def overview_of(client, g, cid):
    ov = client.get(f"/api/groups/{g['id']}/overview").json()
    return next(c for c in ov["characters"] if c["id"] == cid)


def test_defaults_show_everything_except_gold(world):
    alice, _, g, cid, _ = world
    c = overview_of(alice, g, cid)
    assert c["playedTotal"] is not None and c["zone"] and c["deaths"] == 2
    assert c["gold"] is None  # wie bisher: Gold ist standardmäßig verborgen
    assert c["hidden"] == ["gold"]
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert h["state"]["equipment"] and h["state"]["skills"] and h["state"]["reputation"]
    assert h["state"]["talents"] and h["state"]["materials"]


def test_pace_hides_playtime_and_derived_values(world):
    alice, bob, g, cid, _ = world
    before = overview_of(alice, g, cid)
    assert before["xpPerHour"] is not None and before["etaSeconds"] is not None
    share(bob, cid, pace=False)
    c = overview_of(alice, g, cid)
    # Das Tempo ergibt sich aus der Spielzeit; wer eines zeigt, verrät das andere.
    assert (c["playedTotal"], c["playedLevel"], c["xpPerHour"], c["etaSeconds"]) == (None, None, None, None)
    assert "pace" in c["hidden"]
    # Level und XP bleiben sichtbar.
    assert c["level"] == before["level"] and c["xp"] == before["xp"] and c["totalXp"] == before["totalXp"]
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert all(s["playedTotal"] is None for s in h["snapshots"])
    # Der Besitzer sieht weiterhin alles.
    own = overview_of(bob, g, cid)
    assert own["playedTotal"] == before["playedTotal"] and own["hidden"] == []


def test_zone_deaths_and_gold(world):
    alice, bob, g, cid, _ = world
    share(bob, cid, zone=False, deaths=False)
    c = overview_of(alice, g, cid)
    assert c["zone"] is None and c["deaths"] is None
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert all(s["zone"] is None for s in h["snapshots"]) and h["state"]["deaths"] is None
    # Gold geht über denselben Weg (und weiterhin über das alte Feld).
    assert overview_of(alice, g, cid)["gold"] is None
    share(bob, cid, gold=True)
    assert overview_of(alice, g, cid)["gold"] == 123456
    assert bob.patch(f"/api/characters/{cid}", json={"goldVisible": False}).json()["share"]["gold"] is False
    assert overview_of(alice, g, cid)["gold"] is None
    # Der Besitzer sieht sein Gold immer.
    assert overview_of(bob, g, cid)["gold"] == 123456


def test_state_sections(world):
    alice, bob, _, cid, _ = world
    share(bob, cid, gear=False, skills=False, reputation=False, talents=False, materials=False)
    h = alice.get(f"/api/characters/{cid}/history").json()
    st = h["state"]
    assert st["equipment"] == [] and st["skills"] == [] and st["reputation"] == []
    assert st["talents"] == [] and st["materials"] is None
    assert {"gear", "skills", "reputation", "talents", "materials"} <= set(h["hidden"])
    # Besitzer: unverändert vollständig.
    own = bob.get(f"/api/characters/{cid}/history").json()["state"]
    assert own["equipment"] and own["skills"] and own["materials"]


def test_feed_and_history_events_are_filtered(world):
    alice, bob, g, cid, _ = world

    def texts(client):
        return {e["text"] for e in client.get(f"/api/groups/{g['id']}/feed").json()}

    assert {"hat Bergbau auf 150 gebracht", "ist bei Sturmwind jetzt Wohlwollend"} <= texts(alice)
    share(bob, cid, skills=False, reputation=False)
    seen = texts(alice)
    assert "hat Bergbau auf 150 gebracht" not in seen and "ist bei Sturmwind jetzt Wohlwollend" not in seen
    assert "trägt jetzt [Klinge des Testers]" in seen  # Ausrüstung blieb freigegeben
    hist = {e["text"] for e in alice.get(f"/api/characters/{cid}/history").json()["events"]}
    assert "hat Bergbau auf 150 gebracht" not in hist
    # Der Besitzer sieht nach wie vor alles.
    assert "hat Bergbau auf 150 gebracht" in texts(bob)


def test_feed_limit_counts_only_visible_events(world):
    alice, bob, g, cid, _ = world
    share(bob, cid, gear=False, skills=False, reputation=False, deaths=False, bosses=False)
    # Alles Ausgeblendete zählt nicht gegen das Limit und taucht nicht auf.
    feed = alice.get(f"/api/groups/{g['id']}/feed", params={"limit": 1}).json()
    assert all(e["type"] not in privacy.EVENT_CATEGORY for e in feed)


def test_materials_endpoint(world):
    alice, bob, g, cid, _ = world
    url = f"/api/groups/{g['id']}/materials"
    assert alice.get(url).json()
    share(bob, cid, materials=False)
    assert alice.get(url).json() == []
    assert bob.get(url).json()  # der Besitzer sieht seine eigenen


def test_race_playtime_axis(world):
    alice, bob, g, cid, _ = world
    url = f"/api/groups/{g['id']}/race"
    testa = next(s for s in alice.get(url).json() if s["name"] == "Testa")
    assert testa["points"][0][1] == 36000
    share(bob, cid, pace=False)
    testa = next(s for s in alice.get(url).json() if s["name"] == "Testa")
    assert all(p[1] is None for p in testa["points"]) and testa["points"][0][2] > 12  # Level bleibt


def test_photo_is_not_served_when_hidden(world, settings, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    alice, bob, g, cid, tok = world
    from .conftest import FIXTURES  # noqa: PLC0415

    sv = (FIXTURES / "WowFT.lua").read_text(encoding="utf-8")
    req = ingest(bob, tok, sv.encode()).json()["photoRequests"][0]
    auth = {"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}
    assert (
        bob.post(
            f"/api/characters/{cid}/photos", params={"t": req["t"]}, content=JPEG, headers=auth
        ).status_code
        == 201
    )

    url = overview_of(alice, g, cid)["photoUrl"]
    assert alice.get(url).status_code == 200
    share(bob, cid, photo=False)
    # Weder die Adresse in der Übersicht noch der direkte Abruf verraten das Bild.
    assert overview_of(alice, g, cid)["photoUrl"] is None
    assert alice.get(url).status_code == 404
    assert alice.get(f"/api/characters/{cid}/history").json()["photos"] == []
    assert bob.get(url).status_code == 200  # Besitzer


def test_discord_respects_shares(make_client, sv_text, monkeypatch):
    alice, bob, g = setup_group(make_client)
    hook = "https://discord.com/api/webhooks/123/abc-DEF"
    alice.patch(f"/api/groups/{g['id']}", json={"discordWebhook": hook})
    cid = None
    sent = []
    monkeypatch.setattr(discord, "send", lambda posts: sent.extend(posts))
    monkeypatch.setattr(discord, "now", lambda: 1793870000)
    tok = upload_token(bob)
    ingest(bob, tok, sv_text.encode())
    cid = bob.get("/api/me/characters").json()[0]["id"]
    share(bob, cid, skills=False)
    ingest(bob, tok, bump(sv_text).encode())
    text = "\n".join(t for _, t in sent)
    assert "Bergbau" not in text  # ausgeblendet: gehört nicht nach Discord
    assert "Klinge des Testers" in text  # freigegeben


def test_patch_validation_and_merge(world):
    _, bob, _, cid, _ = world
    r = bob.patch(f"/api/characters/{cid}", json={"share": {"unsinn": False}})
    assert r.status_code == 422 and "unsinn" in r.text
    out = share(bob, cid, zone=False)
    assert out["share"]["zone"] is False and out["share"]["gear"] is True
    out = share(bob, cid, gear=False)  # frühere Einstellung bleibt erhalten
    assert out["share"]["zone"] is False and out["share"]["gear"] is False
    assert set(out["share"]) == privacy.KEYS
    # Fremde dürfen fremde Charaktere nicht ändern.
    # (alice besitzt „Testa“ nicht)


def test_only_owner_can_change_shares(world):
    alice, _, _, cid, _ = world
    r = alice.patch(f"/api/characters/{cid}", json={"share": {"zone": False}})
    assert r.status_code == 404


def test_hidden_character_stays_hidden(world):
    alice, bob, g, cid, _ = world
    bob.patch(f"/api/characters/{cid}", json={"visible": False})
    assert alice.get(f"/api/characters/{cid}/history").status_code == 404
    ids = [c["id"] for c in alice.get(f"/api/groups/{g['id']}/overview").json()["characters"]]
    assert cid not in ids  # Bobs zweiter Charakter bleibt sichtbar
