from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auth import CurrentUser, DbSession, is_admin, new_token
from ..features import get_features
from ..models import Character, GroupMember, Token, now

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
def me(user: CurrentUser, session: DbSession):
    memberships = session.scalars(select(GroupMember).where(GroupMember.user_id == user.id)).all()
    return {
        "id": user.id,
        "name": user.name,
        "isAdmin": is_admin(user),
        "features": get_features(session),
        "groups": [
            {"id": m.group.id, "name": m.group.name, "role": m.role}
            for m in sorted(memberships, key=lambda m: m.joined)
        ],
    }


# --- Upload-Tokens ----------------------------------------------------------


def _token_out(t: Token) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "prefix": t.prefix,
        "created": t.created,
        "lastUsed": t.last_used,
        "revoked": t.revoked,
    }


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("/tokens")
def list_tokens(user: CurrentUser, session: DbSession):
    tokens = session.scalars(select(Token).where(Token.user_id == user.id).order_by(Token.created)).all()
    return [_token_out(t) for t in tokens]


@router.post("/tokens", status_code=201)
def create_token(body: TokenIn, user: CurrentUser, session: DbSession):
    tok, plain = new_token(session, user, body.name)
    return {**_token_out(tok), "token": plain}


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: int, user: CurrentUser, session: DbSession):
    tok = session.get(Token, token_id)
    if tok is None or tok.user_id != user.id:
        raise HTTPException(404, "Token nicht gefunden")
    if tok.revoked is None:
        tok.revoked = now()
        session.commit()
    return _token_out(tok)


# --- Eigene Charaktere --------------------------------------------------------


def character_out(c: Character) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "class": c.class_,
        "race": c.race,
        "faction": c.faction,
        "region": c.region,
        "visible": c.visible,
        "goldVisible": c.gold_visible,
        "lastUpload": c.last_upload,
    }


@router.get("/me/characters")
def my_characters(user: CurrentUser, session: DbSession):
    chars = session.scalars(select(Character).where(Character.user_id == user.id).order_by(Character.name))
    return [character_out(c) for c in chars]


class CharacterPatch(BaseModel):
    visible: bool | None = None
    goldVisible: bool | None = None


@router.patch("/characters/{char_id}")
def patch_character(char_id: int, body: CharacterPatch, user: CurrentUser, session: DbSession):
    c = session.get(Character, char_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(404, "Charakter nicht gefunden")
    if body.visible is not None:
        c.visible = body.visible
    if body.goldVisible is not None:
        c.gold_visible = body.goldVisible
    session.commit()
    return character_out(c)
