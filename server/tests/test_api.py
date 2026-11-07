import gzip
import json

from .conftest import FIXTURES, upload_token


def ingest(client, token, body, **headers):
    return client.post(
        "/api/ingest",
        content=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain", **headers},
    )


def setup_group(make_client):
    alice = make_client("alice")
    bob = make_client("bob")
    g = alice.post("/api/groups", json={"name": "Die Runde"}).json()
    assert bob.post(f"/api/invites/{g['inviteCode']}/join").status_code == 200
    return alice, bob, g


def test_requires_login(make_client):
    c = make_client()
    assert c.get("/api/me").status_code == 401
    assert c.get("/healthz").json()["ok"] is True


def test_dev_login_disabled(make_client, monkeypatch, settings):
    monkeypatch.setattr(settings, "dev_login", False)
    c = make_client()
    assert c.get("/auth/dev-login", params={"name": "x"}, follow_redirects=False).status_code == 404


def test_ingest_lua_is_idempotent(make_client, sv_text):
    alice = make_client("alice")
    tok = upload_token(alice)
    r = ingest(alice, tok, sv_text.encode())
    assert r.status_code == 200, r.text
    req = [{"characterId": 1, "name": "Testa", "t": 1793863500}]
    assert r.json() == {"characters": 2, "snapshots": 4, "events": 4, "skipped": [], "photoRequests": req}
    r = ingest(alice, tok, sv_text.encode())
    assert r.json() == {"characters": 2, "snapshots": 0, "events": 0, "skipped": [], "photoRequests": req}
    chars = alice.get("/api/me/characters").json()
    assert {c["name"] for c in chars} == {"Testa", "Twinka"}


def test_ingest_ignores_upload_block(make_client, sv_text):
    """Das Addon legt Server und Token im Block WowFTDB.upload ab (für den Uploader).
    Der Server muss ihn ignorieren und darf ihn nirgends speichern."""
    secret = "wft_darf_nirgends_landen"
    block = f'["upload"] = {{\n["server"] = "https://wow.example.org",\n["token"] = "{secret}",\n}},\n'
    assert '["characters"] = {' in sv_text
    with_upload = sv_text.replace('["characters"] = {', block + '["characters"] = {', 1)
    alice = make_client("alice")
    token = upload_token(alice)
    plain = ingest(alice, token, sv_text)
    r = ingest(alice, token, with_upload)
    assert r.status_code == 200, r.text
    # Gleiche Daten, gleiches Ergebnis: Der Block ändert nichts an der Auswertung.
    assert r.json()["characters"] == plain.json()["characters"]
    assert secret not in r.text
    assert secret not in alice.get("/api/me/characters").text


def test_ingest_gzip_and_json(make_client, sv_text):
    alice = make_client("alice")
    tok = upload_token(alice)
    r = ingest(alice, tok, gzip.compress(sv_text.encode()), **{"Content-Encoding": "gzip"})
    assert r.json()["snapshots"] == 4
    body = (FIXTURES / "ingest.json").read_bytes()
    r = ingest(alice, tok, body, **{"Content-Type": "application/json"})
    assert r.json()["snapshots"] == 0


def test_ingest_rejects_bad_token_and_data(make_client, sv_text):
    alice = make_client("alice")
    assert ingest(alice, "wft_falsch", sv_text.encode()).status_code == 401
    tok = upload_token(alice)
    assert ingest(alice, tok, b"WowFTDB = { kaputt").status_code == 422
    assert ingest(alice, tok, b"Anderes = {}").status_code == 422
    assert ingest(alice, tok, b'WowFTDB = { ["schema"] = 99 }').status_code == 422


def test_last_used_is_set_even_if_upload_is_rejected(make_client):
    alice = make_client("alice")
    tok = upload_token(alice)
    assert alice.get("/api/tokens").json()[0]["lastUsed"] is None
    assert ingest(alice, tok, b"WowFTDB = { kaputt").status_code == 422
    assert alice.get("/api/tokens").json()[0]["lastUsed"] is not None


def test_revoked_token(make_client, sv_text):
    alice = make_client("alice")
    tok = upload_token(alice)
    tid = alice.get("/api/tokens").json()[0]["id"]
    assert alice.delete(f"/api/tokens/{tid}").json()["revoked"]
    assert ingest(alice, tok, sv_text.encode()).status_code == 401


def test_body_limit(make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    alice = make_client("alice")
    tok = upload_token(alice)
    assert ingest(alice, tok, b"x" * 200).status_code == 413
    bomb = gzip.compress(b"x" * 10_000)
    assert ingest(alice, tok, bomb, **{"Content-Encoding": "gzip"}).status_code == 413


def test_same_guid_other_user_is_skipped(make_client, sv_text):
    alice = make_client("alice")
    bob = make_client("bob")
    ingest(alice, upload_token(alice), sv_text.encode())
    r = ingest(bob, upload_token(bob), sv_text.encode())
    assert r.json()["skipped"] == ["Testa", "Twinka"]
    assert bob.get("/api/me/characters").json() == []


def test_overview_and_visibility(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())

    ov = alice.get(f"/api/groups/{g['id']}/overview").json()
    by_name = {c["name"]: c for c in ov["characters"]}
    testa = by_name["Testa"]
    assert testa["level"] == 13
    assert testa["ownerName"] == "bob"
    assert testa["zone"] == 'Dämmerwald "Duskwood"'
    assert testa["behindLeader"] == 0
    assert by_name["Twinka"]["behindLeader"] > 0
    # Die Spielzeit ist für andere verborgen, solange der Rennen-Modus aus ist (Standard),
    # das Tempo ebenfalls (Standard: nicht freigegeben). Details: tests/test_privacy.py.
    assert testa["playedTotal"] is None and testa["playedLevel"] is None
    assert testa["xpPerHour"] is None and testa["etaSeconds"] is None
    assert testa["gold"] is None
    # Der Besitzer sieht sein Tempo: 13 -> 13, 3060 XP in 1600 s Spielzeit, über die Levelgrenze
    mine = bob.get(f"/api/groups/{g['id']}/overview").json()["characters"]
    own = next(c for c in mine if c["name"] == "Testa")
    assert own["xpPerHour"] > 0 and own["etaSeconds"] > 0

    twinka_id = by_name["Twinka"]["id"]
    assert bob.patch(f"/api/characters/{twinka_id}", json={"visible": False}).json()["visible"] is False
    ov = alice.get(f"/api/groups/{g['id']}/overview").json()
    assert [c["name"] for c in ov["characters"]] == ["Testa"]
    assert alice.get(f"/api/characters/{twinka_id}/history").status_code == 404
    assert bob.get(f"/api/characters/{twinka_id}/history").status_code == 200
    # Fremde Charaktere darf man nicht ändern.
    assert alice.patch(f"/api/characters/{testa['id']}", json={"visible": False}).status_code == 404


def test_feed_and_history(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    feed = alice.get(f"/api/groups/{g['id']}/feed").json()
    by_type = {e["type"]: e for e in feed}
    assert set(by_type) == {"level_up", "death", "boss"}
    assert by_type["level_up"]["text"] == "hat Level 13 erreicht"
    assert by_type["boss"]["text"] == "hat Edwin VanCleef besiegt (Die Todesminen)"
    assert feed[0]["ts"] >= feed[-1]["ts"]
    cid = feed[0]["character"]["id"]
    h = alice.get(f"/api/characters/{cid}/history").json()
    assert len(h["snapshots"]) == 3
    assert h["character"]["name"] == "Testa"


def test_outsider_sees_nothing(make_client, sv_text):
    alice, bob, g = setup_group(make_client)
    ingest(bob, upload_token(bob), sv_text.encode())
    eve = make_client("eve")
    assert eve.get(f"/api/groups/{g['id']}/overview").status_code == 404
    assert eve.get(f"/api/groups/{g['id']}/feed").status_code == 404
    cid = alice.get(f"/api/groups/{g['id']}/overview").json()["characters"][0]["id"]
    assert eve.get(f"/api/characters/{cid}/history").status_code == 404
    assert eve.get(f"/api/groups/{g['id']}").status_code == 404


def test_group_roles(make_client):
    alice, bob, g = setup_group(make_client)
    gb = bob.get(f"/api/groups/{g['id']}").json()
    assert "inviteCode" not in gb
    assert bob.post(f"/api/groups/{g['id']}/invite").status_code == 403
    new = alice.post(f"/api/groups/{g['id']}/invite").json()["inviteCode"]
    assert new != g["inviteCode"]
    eve = make_client("eve")
    assert eve.post(f"/api/invites/{g['inviteCode']}/join").status_code == 404
    assert eve.get(f"/api/invites/{new}").json()["name"] == "Die Runde"
    alice_id = alice.get("/api/me").json()["id"]
    assert bob.delete(f"/api/groups/{g['id']}/members/{alice_id}").status_code == 403
    assert alice.delete(f"/api/groups/{g['id']}/members/{alice_id}").status_code == 400
    bob_id = bob.get("/api/me").json()["id"]
    assert bob.delete(f"/api/groups/{g['id']}/members/{bob_id}").status_code == 200
    assert bob.get("/api/me").json()["groups"] == []


def test_manual_upload(make_client, sv_text):
    alice = make_client("alice")
    r = alice.post("/api/me/upload", files={"file": ("WowFT.lua", sv_text.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["snapshots"] == 4


def test_rate_limit(make_client, settings, monkeypatch, sv_text):
    monkeypatch.setattr(settings, "ingest_rate_per_minute", 2)
    alice = make_client("alice")
    tok = upload_token(alice)
    codes = [ingest(alice, tok, sv_text.encode()).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_safe_next_redirect(make_client):
    c = make_client()
    r = c.get("/auth/dev-login", params={"name": "x", "next": "//evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"
    r = c.get("/auth/dev-login", params={"name": "x", "next": "/invite/abc"}, follow_redirects=False)
    assert r.headers["location"] == "/invite/abc"


def test_fixture_json_is_valid():
    json.loads((FIXTURES / "ingest.json").read_text(encoding="utf-8"))


def test_login_without_oidc_config(make_client):
    assert make_client().get("/auth/login", follow_redirects=False).status_code == 503
