"""Addon 0.5.0 auf dem Server: Todesursache, Rezepte, Ruhestein, Foto-Zone, Wochenrückblick."""

import json
from datetime import datetime, timedelta

from wowft import db, discord, weekly
from wowft.models import Group

from .conftest import FIXTURES, upload_token
from .test_api import setup_group
from .test_phase4 import JPEG

TESTA = "Player-4711-0ABC1234"


def data():
    d = json.loads((FIXTURES / "ingest.json").read_text(encoding="utf-8"))
    c = d["characters"][TESTA]
    c["deathLog"][0]["killer"] = {"source": "Defias-Wegelagerer", "spell": "Finsterer Stoß", "amount": 45}
    c["deathLog"][1]["killer"] = {"environment": "Falling", "amount": 300}
    c["bind"] = "Goldhain"
    c["photoInfo"] = [{"t": 1793863500, "level": 13, "zone": "Westfall", "subzone": "Späherkuppe"}]
    c["recipes"] = [
        {
            "profession": "Schmiedekunst",
            "scanned": 1793863000,
            "list": [
                {
                    "name": "Kupferkettengürtel",
                    "item": 2851,
                    "reagents": [
                        {"id": 2770, "name": "Kupfererz", "count": 6},
                        {"id": 9999, "name": "Seltsames", "count": 1},
                    ],
                },
                {
                    "name": "Rauer Schärfstein",
                    "item": 2862,
                    "reagents": [{"id": 2835, "name": "Rauer Stein", "count": 1}],
                },
            ],
        }
    ]
    return d


def post(client, token, payload):
    r = client.post(
        "/api/ingest",
        content=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def world(make_client):
    alice, bob, g = setup_group(make_client)
    tok = upload_token(bob)
    post(bob, tok, data())
    cid = next(c["id"] for c in bob.get("/api/me/characters").json() if c["name"] == "Testa")
    return alice, bob, g, cid, tok


def test_death_cause_in_feed(make_client):
    alice, _, g, _, _ = world(make_client)
    texts = [e["text"] for e in alice.get(f"/api/groups/{g['id']}/feed").json() if e["type"] == "death"]
    assert "ist gestorben in Westfall (Defias-Wegelagerer, Finsterer Stoß)" in texts
    assert "ist gestorben in Die Todesminen (Sturz)" in texts


def test_recipes_search_with_materials(make_client):
    alice, bob, g, cid, _ = world(make_client)
    url = f"/api/groups/{g['id']}/recipes"
    assert alice.get(url, params={"q": "k"}).json()["results"] == []  # mindestens 2 Zeichen
    r = alice.get(url, params={"q": "kupfer"}).json()
    assert r["known"] == 2
    (belt,) = r["results"]
    assert (belt["name"], belt["profession"], belt["item"]) == ("Kupferkettengürtel", "Schmiedekunst", 2851)
    assert [c["name"] for c in belt["crafters"]] == ["Testa"]
    ore, odd = belt["reagents"]
    assert (ore["name"], ore["count"], ore["total"]) == ("Kupfererz", 6, 25)
    assert [(h["name"], h["count"]) for h in ore["holders"]] == [("Testa", 25)]
    assert odd["holders"] == [] and odd["total"] == 0
    # Berufe ausgeblendet: keine Rezepte
    bob.patch(f"/api/characters/{cid}", json={"share": {"skills": False}})
    assert alice.get(url, params={"q": "kupfer"}).json()["results"] == []


def test_bind_recipes_summary_and_photo_zone(make_client):
    alice, bob, g, cid, tok = world(make_client)
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert h["state"]["bind"] == "Goldhain"
    assert h["state"]["recipes"] == [{"profession": "Schmiedekunst", "count": 2, "scanned": 1793863000}]
    url = f"/api/characters/{cid}/photos"
    auth = {"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}
    assert bob.post(url, params={"t": 1793863500}, content=JPEG, headers=auth).status_code == 201
    photo = alice.get(f"/api/characters/{cid}/history").json()["photos"][0]
    assert (photo["level"], photo["zone"]) == (13, "Westfall · Späherkuppe")
    # Aufenthaltsort ausgeblendet: kein Ruhestein, keine Foto-Zone
    bob.patch(f"/api/characters/{cid}", json={"share": {"zone": False}})
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert h["state"]["bind"] is None and h["photos"][0]["zone"] is None


def test_empty_recipes_do_not_overwrite(make_client):
    alice, bob, g, cid, tok = world(make_client)
    d = data()
    d["characters"][TESTA]["recipes"] = []
    post(bob, tok, d)
    assert alice.get(f"/api/characters/{cid}/history").json()["state"]["recipes"][0]["count"] == 2


def sunday_after(ts: int, hour: int) -> datetime:
    d = datetime.fromtimestamp(ts, weekly.TZ)
    d = d + timedelta(days=(6 - d.weekday()))
    return d.replace(hour=hour, minute=30, second=0, microsecond=0)


def test_weekly_report_text_and_schedule(make_client, monkeypatch):
    alice, bob, g, cid, _ = world(make_client)
    sunday = sunday_after(1793863600, 19)
    with db.new_session() as s:
        text = weekly.build_report(s, s.get(Group, g["id"]), sunday)
    assert text.startswith("**Wochenrückblick Die Runde**")
    assert "Testa (bob): 12 → 13" in text
    assert "Edwin VanCleef (Testa)" in text
    assert "**Tode**: 2" in text

    sent = []
    monkeypatch.setattr(discord, "send", lambda posts: sent.extend(posts))
    assert weekly.run_once(sunday) == 0  # ohne Webhook nichts
    alice.patch(f"/api/groups/{g['id']}", json={"discordWebhook": "https://discord.com/api/webhooks/1/abc"})
    assert weekly.run_once(sunday - timedelta(hours=2)) == 0  # vor 19 Uhr
    assert weekly.run_once(sunday) == 1 and sent[0][0] == "https://discord.com/api/webhooks/1/abc"
    assert weekly.run_once(sunday + timedelta(hours=1)) == 0  # nur einmal pro Woche
    # abschaltbar
    assert alice.patch(f"/api/groups/{g['id']}", json={"weeklyReport": False}).json()["weeklyReport"] is False
    assert weekly.run_once(sunday + timedelta(days=7)) == 0


def test_weekly_hides_hidden_categories(make_client):
    alice, bob, g, cid, _ = world(make_client)
    bob.patch(f"/api/characters/{cid}", json={"share": {"deaths": False, "bosses": False}})
    with db.new_session() as s:
        text = weekly.build_report(s, s.get(Group, g["id"]), sunday_after(1793863600, 19))
    assert "Tode" not in text and "VanCleef" not in text and "12 → 13" in text


def test_weekly_endpoints_owner_only(make_client, monkeypatch):
    alice, bob, g, _, _ = world(make_client)
    assert bob.get(f"/api/groups/{g['id']}/weekly").status_code == 403
    assert alice.get(f"/api/groups/{g['id']}/weekly").status_code == 200
    assert alice.post(f"/api/groups/{g['id']}/weekly/send").status_code == 400  # kein Webhook
    alice.patch(f"/api/groups/{g['id']}", json={"discordWebhook": "https://discord.com/api/webhooks/1/abc"})
    sent = []
    monkeypatch.setattr(discord, "send", lambda posts: sent.extend(posts))
    assert alice.post(f"/api/groups/{g['id']}/weekly/send").status_code == 200
    assert len(sent) == 1
