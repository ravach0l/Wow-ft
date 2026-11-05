from wowft import discord, events

from .conftest import upload_token
from .test_api import ingest, setup_group

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def bump(sv_text: str) -> str:
    """Zweiter Upload: Bergbau 87 -> 160, neues blaues Item, Sturmwind wohlwollend."""
    return (
        sv_text.replace('["rank"] = 87', '["rank"] = 160')
        .replace('["id"] = 2042', '["id"] = 9999')
        .replace('["standing"] = 5', '["standing"] = 6')
        .replace('["t"] = 1793863600', '["t"] = 1793870000')
    )


def test_derive_rules():
    prev = {
        "skills": [{"name": "Bergbau", "rank": 70, "header": "Berufe"}],
        "equipment": [{"slot": 16, "id": 1, "quality": 3}],
        "reputation": [{"id": 72, "name": "Sturmwind", "standing": 5}],
    }
    new = {
        "skills": [
            {"name": "Bergbau", "rank": 151, "header": "Berufe"},
            {"name": "Schwerter", "rank": 160, "header": "Waffenfertigkeiten"},
            {"name": "Kochkunst", "rank": 80, "header": "Secondary Skills"},
        ],
        "equipment": [{"slot": 16, "id": 2, "quality": 3, "name": "Neu"}, {"slot": 1, "id": 5, "quality": 2}],
        "reputation": [{"id": 72, "name": "Sturmwind", "standing": 6}],
    }
    got = sorted((t, k) for t, k, _ in events.derive(prev, new))
    assert got == [
        ("item", "16:2"),
        ("reputation", "72:6"),
        ("skill", "Bergbau:150"),
        ("skill", "Bergbau:75"),
        ("skill", "Kochkunst:75"),
    ]
    # Erster Stand erzeugt nichts.
    assert events.derive({}, new) == []


def test_state_derived_events_and_history(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    tok = upload_token(bob)
    ingest(bob, tok, sv_text.encode())
    r = ingest(bob, tok, bump(sv_text).encode())
    assert r.json()["events"] == 3

    feed = alice.get(f"/api/groups/{g['id']}/feed").json()
    texts = {e["text"] for e in feed}
    assert "hat Bergbau auf 150 gebracht" in texts
    assert "trägt jetzt [Klinge des Testers]" in texts
    assert "ist bei Sturmwind jetzt Wohlwollend" in texts

    cid = feed[0]["character"]["id"]
    h = alice.get(f"/api/characters/{cid}/history").json()
    st = h["state"]
    assert [s["category"] for s in st["skills"]] == ["profession", "secondary", "weapon"]
    assert st["equipment"][0]["slotName"] == "Brust"
    assert st["reputation"][0]["standingName"] == "Wohlwollend"
    assert st["talents"][0]["points"] == 3
    assert st["deaths"] == 2
    assert h["character"]["deaths"] == 2


def test_materials(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    mats = alice.get(f"/api/groups/{g['id']}/materials").json()
    by_name = {m["name"]: m for m in mats}
    assert by_name["Kupfererz"]["total"] == 25
    h = by_name["Kupfererz"]["holders"][0]
    assert (h["name"], h["bags"], h["bank"], h["ownerName"]) == ("Testa", 20, 5, "bob")
    assert by_name["Leinenstoff"]["total"] == 40


def test_race(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    race = alice.get(f"/api/groups/{g['id']}/race").json()
    testa = next(s for s in race if s["name"] == "Testa")
    assert testa["points"][0] == [1793860000, 36000, round(12 + 500 / 8800, 3)]
    assert len(testa["points"]) == 3


def test_photo_flow(make_client, sv_text, settings, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    alice, bob, g = setup_group(make_client)
    tok = upload_token(bob)
    req = ingest(bob, tok, sv_text.encode()).json()["photoRequests"][0]
    url = f"/api/characters/{req['characterId']}/photos"
    auth = {"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}

    assert bob.post(url, params={"t": 123456789000}, content=JPEG, headers=auth).status_code == 400
    assert bob.post(url, params={"t": req["t"]}, content=b"GIF89a", headers=auth).status_code == 415
    r = bob.post(url, params={"t": req["t"]}, content=JPEG, headers=auth)
    assert r.status_code == 201, r.text
    assert bob.post(url, params={"t": req["t"]}, content=JPEG, headers=auth).status_code == 409
    # Danach wird das Foto nicht mehr angefordert.
    assert ingest(bob, tok, sv_text.encode()).json()["photoRequests"] == []

    ov = alice.get(f"/api/groups/{g['id']}/overview").json()
    testa = next(c for c in ov["characters"] if c["name"] == "Testa")
    img = alice.get(testa["photoUrl"])
    assert img.status_code == 200 and img.content == JPEG
    h = alice.get(f"/api/characters/{testa['id']}/history").json()
    assert h["photos"][0]["level"] == 13

    eve = make_client("eve")
    assert eve.get(testa["photoUrl"]).status_code == 404
    pid = h["photos"][0]["id"]
    assert alice.delete(f"/api/photos/{pid}").status_code == 403
    assert bob.delete(f"/api/photos/{pid}").status_code == 200
    # Fremder Token darf keine Fotos für fremde Charaktere hochladen.
    other = upload_token(alice)
    r = alice.post(
        url, params={"t": req["t"]}, content=JPEG, headers={**auth, "Authorization": f"Bearer {other}"}
    )
    assert r.status_code == 404


def test_discord_webhook(make_client, sv_text, monkeypatch):
    alice, bob, g = setup_group(make_client)
    gid = g["id"]
    bad = alice.patch(f"/api/groups/{gid}", json={"discordWebhook": "https://evil.example/x"})
    assert bad.status_code == 422
    hook = "https://discord.com/api/webhooks/123/abc-DEF"
    assert alice.patch(f"/api/groups/{gid}", json={"discordWebhook": hook}).json()["discordWebhook"] == hook
    assert bob.patch(f"/api/groups/{gid}", json={"discordWebhook": ""}).status_code == 403
    assert "discordWebhook" not in bob.get(f"/api/groups/{gid}").json()

    sent = []
    monkeypatch.setattr(discord, "send", lambda posts: sent.extend(posts))
    tok = upload_token(bob)
    # Alte Ereignisse (älter als 12 h) werden nicht gepostet.
    monkeypatch.setattr(discord, "now", lambda: 1794000000)
    ingest(bob, tok, sv_text.encode())
    assert sent == []
    fresh = bump(sv_text)
    monkeypatch.setattr(discord, "now", lambda: 1793870000)
    ingest(bob, tok, fresh.encode())
    assert len(sent) == 1
    url, text = sent[0]
    assert url == hook
    assert "**Testa** (bob) hat Bergbau auf 150 gebracht" in text


def test_discord_send_handles_errors(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("weg")

    monkeypatch.setattr(httpx, "post", boom)
    discord.send([("https://discord.com/api/webhooks/1/x", "hi")])  # wirft nicht


def test_valid_webhook():
    assert discord.valid_webhook("https://discordapp.com/api/webhooks/1/a_b-c")
    assert not discord.valid_webhook("https://discord.com.evil.io/api/webhooks/1/a")
    assert not discord.valid_webhook("http://discord.com/api/webhooks/1/a")
