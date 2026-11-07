"""Anmeldung über Authentik (OIDC), Upload-Tokens und ein einfaches Rate-Limit."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from typing import Annotated

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import get_session
from .models import Token, User, now

TOKEN_PREFIX = "wft_"

DbSession = Annotated[Session, Depends(get_session)]

# --------------------------------------------------------------------------
# Rate-Limit (pro Schlüssel, gleitendes Fenster von 60 s, im Speicher)
# --------------------------------------------------------------------------


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, per_minute: int) -> None:
        t = time.monotonic()
        q = self.hits[key]
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= per_minute:
            raise HTTPException(429, "Zu viele Anfragen, bitte kurz warten")
        q.append(t)

    def reset(self) -> None:
        self.hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------
# Upload-Tokens
# --------------------------------------------------------------------------


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(session: Session, user: User, name: str) -> tuple[Token, str]:
    plain = TOKEN_PREFIX + secrets.token_urlsafe(32)
    tok = Token(user_id=user.id, name=name, hash=hash_token(plain), prefix=plain[:10])
    session.add(tok)
    session.commit()
    return tok, plain


def user_from_token(request: Request, session: DbSession) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.startswith(TOKEN_PREFIX):
        raise HTTPException(401, "Upload-Token fehlt")
    tok = session.scalar(select(Token).where(Token.hash == hash_token(value.strip())))
    if tok is None or tok.revoked is not None:
        raise HTTPException(401, "Upload-Token ungültig oder widerrufen")
    # Sofort speichern: „zuletzt benutzt“ soll auch dann stimmen, wenn der Upload danach
    # abgelehnt wird (z. B. Datei nicht lesbar). Sonst sähe „nie“ wie „nie angekommen“ aus.
    tok.last_used = now()
    session.commit()
    user = session.get(User, tok.user_id)
    assert user is not None
    return user


TokenUser = Annotated[User, Depends(user_from_token)]


# --------------------------------------------------------------------------
# Web-Login (Session-Cookie)
# --------------------------------------------------------------------------


def current_user(request: Request, session: DbSession) -> User:
    uid = request.session.get("uid")
    user = session.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Nicht angemeldet")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def is_admin(user: User) -> bool:
    admins = {a.strip().lower() for a in get_settings().admin_users.split(",") if a.strip()}
    ids = {user.name.lower(), (user.email or "").lower(), user.auth_sub.lower()}
    return bool(admins & ids)


def admin_user(user: CurrentUser) -> User:
    if not is_admin(user):
        raise HTTPException(403, "Nur für Admins")
    return user


AdminUser = Annotated[User, Depends(admin_user)]

router = APIRouter(prefix="/auth", tags=["auth"])
_oauth: OAuth | None = None


def oauth(settings: Settings) -> OAuth:
    global _oauth
    if _oauth is None:
        if not settings.oidc_metadata_url:
            raise HTTPException(503, "Login ist nicht konfiguriert (WOWFT_OIDC_METADATA_URL)")
        _oauth = OAuth()
        _oauth.register(
            name="authentik",
            server_metadata_url=settings.oidc_metadata_url,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            client_kwargs={"scope": "openid profile email"},
        )
    return _oauth


def _safe_next(target: str | None) -> str:
    # Nur relative Pfade innerhalb der Seite, keine offenen Weiterleitungen.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


def _login_user(request: Request, session: Session, sub: str, name: str, email: str | None) -> User:
    user = session.scalar(select(User).where(User.auth_sub == sub))
    if user is None:
        user = User(auth_sub=sub, name=name, email=email)
        session.add(user)
    else:
        user.name = name
        user.email = email
    session.commit()
    request.session.clear()
    request.session["uid"] = user.id
    return user


@router.get("/login")
async def login(request: Request, next: str | None = None):
    settings = get_settings()
    limiter.check("auth:" + client_ip(request), settings.auth_rate_per_minute)
    request.session["next"] = _safe_next(next)
    client = oauth(settings).create_client("authentik")
    return await client.authorize_redirect(request, settings.base_url.rstrip("/") + "/auth/callback")


@router.get("/callback")
async def callback(request: Request, session: DbSession):
    settings = get_settings()
    limiter.check("auth:" + client_ip(request), settings.auth_rate_per_minute)
    client = oauth(settings).create_client("authentik")
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        raise HTTPException(400, f"Anmeldung fehlgeschlagen: {e.error}") from e
    info = token.get("userinfo") or {}
    sub = info.get("sub")
    if not sub:
        raise HTTPException(400, "Authentik hat keine Benutzer-ID geliefert")
    name = info.get("preferred_username") or info.get("name") or info.get("email") or "Unbekannt"
    target = request.session.get("next", "/")
    _login_user(request, session, f"authentik:{sub}", name, info.get("email"))
    return RedirectResponse(_safe_next(target), status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/dev-login")
async def dev_login(request: Request, session: DbSession, name: str = "dev", next: str | None = None):
    """Nur mit WOWFT_DEV_LOGIN=true: Anmeldung ohne Authentik für lokale Tests."""
    if not get_settings().dev_login:
        raise HTTPException(404)
    _login_user(request, session, f"dev:{name}", name, None)
    return RedirectResponse(_safe_next(next), status_code=303)
