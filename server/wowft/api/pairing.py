"""Uploader koppeln, ohne einen Token abzutippen.

Gerätecode (wie beim Anmelden eines Fernsehers):
  1. Uploader: POST /api/pair/start  -> kurzer Code (für den Menschen) + geheimer Schlüssel
  2. Browser:  GET  /api/pair/{code} und POST /api/pair/{code}/approve (angemeldet)
  3. Uploader: POST /api/pair/poll mit dem Schlüssel -> neuer Upload-Token (genau einmal)

Code fürs Spiel (Rückweg, falls der Browser-Weg nicht passt):
  1. Browser:  POST /api/pair/game-code (angemeldet) -> Code WFT-XXXX-XXXX, 15 Minuten gültig
  2. Spiel:    Code ins Token-Feld der Einstellungen, /reload
  3. Uploader: POST /api/pair/redeem mit dem Code -> neuer Upload-Token (genau einmal)
"""

from __future__ import annotations

import hashlib
import re
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import CurrentUser, DbSession, client_ip, limiter, new_token
from ..config import get_settings
from ..models import Pairing, User, now

router = APIRouter(prefix="/api/pair", tags=["pairing"])

# Ohne leicht verwechselbare Zeichen (0/O, 1/I/L).
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
DEVICE_TTL = 10 * 60
GAME_TTL = 15 * 60
POLL_INTERVAL = 3
GAME_PREFIX = "WFT"


def _random(n: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def normalize(code: str) -> str:
    """Großbuchstaben, ohne Leerzeichen und Bindestriche: 'k7q-4mx' -> 'K7Q4MX'."""
    return re.sub(r"[\s-]", "", code or "").upper()


def device_display(code: str) -> str:
    return f"{code[:3]}-{code[3:]}"


def game_display(code: str) -> str:
    return f"{GAME_PREFIX}-{code[3:7]}-{code[7:]}"


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _cleanup(session: Session) -> None:
    session.execute(delete(Pairing).where(Pairing.expires < now()))


def _token_name(device_name: str | None, fallback: str) -> str:
    name = (device_name or "").strip()[:80]
    return name or fallback


def _limit(request: Request, key: str) -> None:
    limiter.check(f"pair-{key}:" + client_ip(request), get_settings().auth_rate_per_minute)


def _insert_unique(session: Session, make) -> Pairing:
    """Legt eine Kopplung an; bei (sehr unwahrscheinlicher) Code-Kollision neuer Versuch."""
    for _ in range(5):
        p = make()
        session.add(p)
        try:
            session.commit()
            return p
        except IntegrityError:
            session.rollback()
    raise HTTPException(503, "Bitte gleich noch einmal versuchen")


# --- Gerätecode ---------------------------------------------------------------


class StartIn(BaseModel):
    deviceName: str | None = Field(default=None, max_length=100)


@router.post("/start")
def start(body: StartIn, request: Request, session: DbSession):
    _limit(request, "start")
    _cleanup(session)
    secret = secrets.token_urlsafe(32)
    p = _insert_unique(
        session,
        lambda: Pairing(
            kind="device",
            user_code=_random(6),
            device_hash=_hash(secret),
            device_name=(body.deviceName or "").strip()[:100] or None,
            expires=now() + DEVICE_TTL,
        ),
    )
    code = device_display(p.user_code)
    base = get_settings().base_url.rstrip("/")
    return {
        "userCode": code,
        "deviceCode": secret,
        "verifyUrl": f"{base}/koppeln?code={code}",
        "expiresIn": DEVICE_TTL,
        "interval": POLL_INTERVAL,
    }


def _open_device_pairing(session: Session, code: str) -> Pairing:
    p = session.scalar(select(Pairing).where(Pairing.kind == "device", Pairing.user_code == normalize(code)))
    if p is None or p.expires < now():
        raise HTTPException(404, "Code unbekannt oder abgelaufen. Im Uploader einen neuen anzeigen lassen.")
    return p


@router.get("/{code}")
def info(code: str, request: Request, user: CurrentUser, session: DbSession):
    _limit(request, "info")
    p = _open_device_pairing(session, code)
    return {
        "userCode": device_display(p.user_code),
        "deviceName": p.device_name,
        "approved": p.user_id is not None,
        "expiresIn": max(0, p.expires - now()),
    }


@router.post("/{code}/approve")
def approve(code: str, request: Request, user: CurrentUser, session: DbSession):
    _limit(request, "info")
    p = _open_device_pairing(session, code)
    if p.user_id is not None and p.user_id != user.id:
        raise HTTPException(409, "Dieser Code wurde schon von jemand anderem bestätigt")
    p.user_id = user.id
    session.commit()
    return {"ok": True, "deviceName": p.device_name}


class PollIn(BaseModel):
    deviceCode: str = Field(min_length=10, max_length=200)


@router.post("/poll")
def poll(body: PollIn, request: Request, session: DbSession):
    """Vom Uploader. 'pending' bis zur Bestätigung, dann einmalig der Token."""
    limiter.check("pair-poll:" + client_ip(request), 60)
    p = session.scalar(select(Pairing).where(Pairing.device_hash == _hash(body.deviceCode)))
    if p is None or p.expires < now():
        raise HTTPException(404, "Kopplung abgelaufen. Bitte neu starten.")
    if p.user_id is None:
        return {"status": "pending"}
    user = session.get(User, p.user_id)
    assert user is not None
    session.delete(p)
    tok, plain = new_token(
        session, user, _token_name(p.device_name, "Uploader")
    )  # committet auch das Löschen
    return {"status": "ok", "token": plain, "userName": user.name, "tokenName": tok.name}


# --- Code fürs Spiel --------------------------------------------------------------


@router.post("/game-code", status_code=201)
def game_code(request: Request, user: CurrentUser, session: DbSession):
    _limit(request, "game")
    _cleanup(session)
    # Ältere, noch offene Spielcodes dieser Person verfallen: Es gilt immer nur der neueste.
    session.execute(delete(Pairing).where(Pairing.kind == "game", Pairing.user_id == user.id))
    p = _insert_unique(
        session,
        lambda: Pairing(
            kind="game", user_code=GAME_PREFIX + _random(8), user_id=user.id, expires=now() + GAME_TTL
        ),
    )
    return {"code": game_display(p.user_code), "expiresIn": GAME_TTL}


class RedeemIn(BaseModel):
    code: str = Field(min_length=6, max_length=40)
    deviceName: str | None = Field(default=None, max_length=100)


@router.post("/redeem")
def redeem(body: RedeemIn, request: Request, session: DbSession):
    """Vom Uploader: Code aus dem Spiel gegen einen Upload-Token tauschen (einmalig)."""
    _limit(request, "redeem")
    code = normalize(body.code)
    p = session.scalar(select(Pairing).where(Pairing.kind == "game", Pairing.user_code == code))
    if p is None or p.expires < now() or p.user_id is None:
        raise HTTPException(404, "Code unbekannt, schon benutzt oder abgelaufen")
    user = session.get(User, p.user_id)
    assert user is not None
    session.delete(p)
    tok, plain = new_token(session, user, _token_name(body.deviceName, "Uploader (Code aus dem Spiel)"))
    return {"status": "ok", "token": plain, "userName": user.name, "tokenName": tok.name}
