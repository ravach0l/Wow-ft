"""Uploader koppeln: Gerätecode (Browser bestätigt) und Code fürs Spiel."""

from wowft.api import pairing
from wowft.models import now

from .test_api import ingest


def start(client, name="Kathis-PC"):
    r = client.post("/api/pair/start", json={"deviceName": name})
    assert r.status_code == 200, r.text
    return r.json()


def test_device_flow(make_client, sv_text):
    device = make_client()  # der Uploader: nicht angemeldet
    alice = make_client("alice")
    s = start(device)
    assert len(s["userCode"]) == 7 and s["userCode"][3] == "-"
    assert s["verifyUrl"].endswith(f"/koppeln?code={s['userCode']}")

    assert device.post("/api/pair/poll", json={"deviceCode": s["deviceCode"]}).json() == {"status": "pending"}
    # Die Bestätigung braucht eine Anmeldung.
    assert device.get(f"/api/pair/{s['userCode']}").status_code == 401
    # Klein geschrieben und ohne Bindestrich geht auch.
    info = alice.get(f"/api/pair/{s['userCode'].lower().replace('-', '')}").json()
    assert info["deviceName"] == "Kathis-PC" and info["approved"] is False
    assert alice.post(f"/api/pair/{s['userCode']}/approve").json()["ok"] is True

    r = device.post("/api/pair/poll", json={"deviceCode": s["deviceCode"]}).json()
    assert r["status"] == "ok" and r["token"].startswith("wft_") and r["userName"] == "alice"
    # Der Token funktioniert und gehört alice.
    assert ingest(device, r["token"], sv_text.encode()).status_code == 200
    assert {c["name"] for c in alice.get("/api/me/characters").json()} == {"Testa", "Twinka"}
    assert [t["name"] for t in alice.get("/api/tokens").json()] == ["Kathis-PC"]
    # Genau einmal: danach ist die Kopplung weg.
    assert device.post("/api/pair/poll", json={"deviceCode": s["deviceCode"]}).status_code == 404
    assert alice.get(f"/api/pair/{s['userCode']}").status_code == 404


def test_device_code_secret_is_required(make_client):
    device = make_client()
    alice = make_client("alice")
    s = start(device)
    alice.post(f"/api/pair/{s['userCode']}/approve")
    # Wer nur den kurzen Code kennt, bekommt keinen Token.
    assert device.post("/api/pair/poll", json={"deviceCode": s["userCode"] + "xxxxxxx"}).status_code == 404


def test_cannot_take_over_approved_code(make_client):
    device = make_client()
    alice, eve = make_client("alice"), make_client("eve")
    s = start(device)
    alice.post(f"/api/pair/{s['userCode']}/approve")
    assert eve.post(f"/api/pair/{s['userCode']}/approve").status_code == 409


def test_device_code_expires(make_client, monkeypatch):
    device = make_client()
    alice = make_client("alice")
    s = start(device)
    later = now() + pairing.DEVICE_TTL + 5
    monkeypatch.setattr(pairing, "now", lambda: later)
    assert alice.post(f"/api/pair/{s['userCode']}/approve").status_code == 404
    assert device.post("/api/pair/poll", json={"deviceCode": s["deviceCode"]}).status_code == 404


def test_game_code_flow(make_client, sv_text):
    device = make_client()
    alice = make_client("alice")
    assert device.post("/api/pair/game-code").status_code == 401
    first = alice.post("/api/pair/game-code").json()["code"]
    g = alice.post("/api/pair/game-code").json()
    code = g["code"]
    assert code.startswith("WFT-") and len(code) == 13 and g["expiresIn"] == pairing.GAME_TTL
    # Nur der neueste Code gilt.
    assert device.post("/api/pair/redeem", json={"code": first}).status_code == 404

    r = device.post(
        "/api/pair/redeem", json={"code": code.lower().replace("-", " "), "deviceName": "PC"}
    ).json()
    assert r["status"] == "ok" and r["token"].startswith("wft_") and r["userName"] == "alice"
    assert ingest(device, r["token"], sv_text.encode()).status_code == 200
    # Einmalig.
    assert device.post("/api/pair/redeem", json={"code": code}).status_code == 404


def test_game_code_expires(make_client, monkeypatch):
    device = make_client()
    alice = make_client("alice")
    code = alice.post("/api/pair/game-code").json()["code"]
    later = now() + pairing.GAME_TTL + 5
    monkeypatch.setattr(pairing, "now", lambda: later)
    assert device.post("/api/pair/redeem", json={"code": code}).status_code == 404


def test_rate_limit_on_redeem(make_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_per_minute", 3)
    device = make_client()
    codes = [device.post("/api/pair/redeem", json={"code": f"WFT-AAAA-AAA{i}"}).status_code for i in range(4)]
    assert codes == [404, 404, 404, 429]
