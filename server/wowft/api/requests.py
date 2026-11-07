"""Material-Wünsche: „Ich suche 10 Kupferbarren“ – mit Hinweis, wer in der Gruppe welche hat."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import discord
from ..auth import CurrentUser, DbSession
from ..models import Group, GroupMember, MaterialRequest, User, now
from .groups import _membership, group_materials

router = APIRouter(prefix="/api", tags=["requests"])

TTL = 7 * 86400
MAX_OPEN_PER_USER = 20


def _norm(name: str | None) -> str:
    return " ".join((name or "").lower().split())


def _holders(req: MaterialRequest, items: list[dict]) -> list[dict]:
    """Wer (außer dem Suchenden selbst) hat das Material? Zuordnung über Item-ID, sonst Name."""
    for item in items:
        same = item["id"] == req.item_id if req.item_id else _norm(item["name"]) == _norm(req.item_name)
        if same:
            return [
                {**h, "count": h["bags"] + h["bank"]}
                for h in item["holders"]
                if h["ownerId"] != req.user_id and h["bags"] + h["bank"] > 0
            ]
    return []


def _out(req: MaterialRequest, items: list[dict], viewer: User, can_manage: bool) -> dict:
    return {
        "id": req.id,
        "itemId": req.item_id,
        "itemName": req.item_name,
        "count": req.count,
        "userId": req.user_id,
        "userName": req.user.name,
        "mine": req.user_id == viewer.id,
        "canManage": can_manage,
        "holders": _holders(req, items),
    }


def _open(session: Session, group_id: int):
    return session.scalars(
        select(MaterialRequest)
        .where(
            MaterialRequest.group_id == group_id,
            MaterialRequest.done.is_(None),
            MaterialRequest.expires > now(),
        )
        .order_by(MaterialRequest.created.desc(), MaterialRequest.id.desc())
    )


@router.get("/groups/{group_id}/requests")
def list_requests(group_id: int, user: CurrentUser, session: DbSession):
    m = _membership(session, group_id, user)
    items = group_materials(session, group_id, user.id)
    return [_out(r, items, user, r.user_id == user.id or m.role == "owner") for r in _open(session, group_id)]


class RequestIn(BaseModel):
    itemName: str = Field(min_length=1, max_length=150)
    itemId: int | None = Field(default=None, ge=1)
    count: int = Field(ge=1, le=9999)


@router.post("/groups/{group_id}/requests", status_code=201)
def create_request(
    group_id: int, body: RequestIn, user: CurrentUser, session: DbSession, background: BackgroundTasks
):
    _membership(session, group_id, user)
    open_mine = session.scalar(
        select(func.count()).where(
            MaterialRequest.group_id == group_id,
            MaterialRequest.user_id == user.id,
            MaterialRequest.done.is_(None),
            MaterialRequest.expires > now(),
        )
    )
    if open_mine >= MAX_OPEN_PER_USER:
        raise HTTPException(429, f"Höchstens {MAX_OPEN_PER_USER} offene Wünsche")
    items = group_materials(session, group_id, user.id)
    name = " ".join(body.itemName.split())
    item_id = body.itemId
    if item_id is None:  # über den Namen einem bekannten Material zuordnen
        item_id = next((i["id"] for i in items if _norm(i["name"]) == _norm(name)), None)
    req = MaterialRequest(
        group_id=group_id,
        user_id=user.id,
        item_id=item_id,
        item_name=name,
        count=body.count,
        expires=now() + TTL,
    )
    session.add(req)
    session.commit()
    session.refresh(req)

    group = session.get(Group, group_id)
    if group and group.discord_webhook:
        holders = _holders(req, items)
        text = f"**{user.name}** sucht {req.count}× {req.item_name}"
        if holders:
            text += " – " + ", ".join(f"{h['name']} hat {h['count']}" for h in holders[:5])
        background.add_task(discord.send, [(group.discord_webhook, text)])
    return _out(req, items, user, can_manage=True)


def _managed(session: Session, request_id: int, user: User) -> MaterialRequest:
    req = session.get(MaterialRequest, request_id)
    member = req and session.get(GroupMember, (req.group_id, user.id))
    if req is None or member is None:
        raise HTTPException(404, "Wunsch nicht gefunden")
    if req.user_id != user.id and member.role != "owner":
        raise HTTPException(403, "Nur wer den Wunsch eingetragen hat (oder die Gruppenleitung)")
    return req


@router.post("/requests/{request_id}/done")
def mark_done(request_id: int, user: CurrentUser, session: DbSession):
    req = _managed(session, request_id, user)
    req.done = now()
    session.commit()
    return {"ok": True}


@router.delete("/requests/{request_id}")
def delete_request(request_id: int, user: CurrentUser, session: DbSession):
    req = _managed(session, request_id, user)
    session.delete(req)
    session.commit()
    return {"ok": True}
