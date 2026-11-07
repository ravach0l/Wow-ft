"""Material-Wünsche: anlegen, wer hat's, erledigen, Rechte, Ablauf, Discord."""

from wowft import discord
from wowft.api import requests as req_api

from .conftest import upload_token
from .test_api import ingest, setup_group


def test_request_flow(make_client, sv_text, monkeypatch):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())  # bob hat 25 Kupfererz, 40 Leinenstoff
    url = f"/api/groups/{g['id']}/requests"

    # Name ohne ID wird einem bekannten Material zugeordnet (Groß-/Kleinschreibung egal).
    r = alice.post(url, json={"itemName": "kupfererz", "count": 10})
    assert r.status_code == 201, r.text
    w = r.json()
    assert (w["itemId"], w["itemName"], w["count"], w["mine"]) == (2770, "kupfererz", 10, True)
    assert [(h["name"], h["count"]) for h in w["holders"]] == [("Testa", 25)]

    # Unbekanntes Material geht auch, nur ohne Besitzer.
    alice.post(url, json={"itemName": "Arkanitbarren", "count": 2})
    lst = bob.get(url).json()
    assert [x["itemName"] for x in lst] == ["Arkanitbarren", "kupfererz"]
    assert lst[1]["mine"] is False and lst[1]["canManage"] is False
    # Bob ist selbst Besitzer, deshalb erscheint er bei seinem eigenen Wunsch nicht als „hat“.
    own = bob.post(url, json={"itemName": "Leinenstoff", "count": 5}).json()
    assert own["holders"] == []

    # Rechte: bob darf alices Wunsch nicht erledigen, alice (Gruppenleitung) bobs schon.
    kid = lst[1]["id"]
    assert bob.post(f"/api/requests/{kid}/done").status_code == 403
    assert alice.post(f"/api/requests/{own['id']}/done").status_code == 200
    assert alice.post(f"/api/requests/{kid}/done").status_code == 200
    assert [x["itemName"] for x in bob.get(url).json()] == ["Arkanitbarren"]
    assert alice.delete(f"/api/requests/{lst[0]['id']}").status_code == 200
    assert bob.get(url).json() == []

    # Fremde sehen und ändern nichts.
    eve = make_client("eve")
    assert eve.get(url).status_code == 404
    assert eve.post(url, json={"itemName": "x", "count": 1}).status_code == 404
    assert eve.delete(f"/api/requests/{kid}").status_code == 404


def test_hidden_materials_do_not_leak(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    cid = bob.get("/api/me/characters").json()[0]["id"]
    bob.patch(f"/api/characters/{cid}", json={"share": {"materials": False}})
    w = alice.post(f"/api/groups/{g['id']}/requests", json={"itemName": "Kupfererz", "count": 1}).json()
    assert w["holders"] == []


def test_requests_expire(make_client, monkeypatch):
    alice, bob, g = setup_group(make_client)
    url = f"/api/groups/{g['id']}/requests"
    alice.post(url, json={"itemName": "Kupfererz", "count": 1})
    later = req_api.now() + req_api.TTL + 1
    monkeypatch.setattr(req_api, "now", lambda: later)
    assert alice.get(url).json() == []


def test_validation_and_limit(make_client, monkeypatch):
    alice, bob, g = setup_group(make_client)
    url = f"/api/groups/{g['id']}/requests"
    assert alice.post(url, json={"itemName": "", "count": 1}).status_code == 422
    assert alice.post(url, json={"itemName": "x", "count": 0}).status_code == 422
    monkeypatch.setattr(req_api, "MAX_OPEN_PER_USER", 2)
    codes = [alice.post(url, json={"itemName": f"x{i}", "count": 1}).status_code for i in range(3)]
    assert codes == [201, 201, 429]


def test_discord_post(make_client, sv_text, monkeypatch):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    alice.patch(f"/api/groups/{g['id']}", json={"discordWebhook": "https://discord.com/api/webhooks/1/abc"})
    sent = []
    monkeypatch.setattr(discord, "send", lambda posts: sent.extend(posts))
    alice.post(f"/api/groups/{g['id']}/requests", json={"itemName": "Kupfererz", "count": 10})
    expected = "**alice** sucht 10× Kupfererz – Testa hat 25"
    assert sent == [("https://discord.com/api/webhooks/1/abc", expected)]
