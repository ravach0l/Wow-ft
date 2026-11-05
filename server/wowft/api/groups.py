import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import discord, metrics
from ..auth import CurrentUser, DbSession
from ..config import get_settings
from ..events import describe
from ..features import enabled
from ..models import Character, Event, Group, GroupMember, Photo, Snapshot, User

router = APIRouter(prefix="/api", tags=["groups"])

SNAPSHOTS_FOR_METRICS = 300


def _membership(session: Session, group_id: int, user: User) -> GroupMember:
    m = session.get(GroupMember, (group_id, user.id))
    if m is None:
        # 404 statt 403: fremde Gruppen sollen nicht erkennbar sein.
        raise HTTPException(404, "Gruppe nicht gefunden")
    return m


def _require_owner(session: Session, group_id: int, user: User) -> GroupMember:
    m = _membership(session, group_id, user)
    if m.role != "owner":
        raise HTTPException(403, "Nur die Gruppenleitung darf das")
    return m


def _visible_characters(session: Session, group_id: int) -> list[Character]:
    member_ids = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    return list(
        session.scalars(
            select(Character).where(Character.user_id.in_(member_ids), Character.visible.is_(True))
        )
    )


def user_can_see(session: Session, user: User, char: Character) -> bool:
    if char.user_id == user.id:
        return True
    if not char.visible:
        return False
    mine = select(GroupMember.group_id).where(GroupMember.user_id == user.id)
    shared = session.scalar(
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.user_id == char.user_id, GroupMember.group_id.in_(mine))
    )
    return bool(shared)


def _group_out(g: Group, me: GroupMember) -> dict:
    out = {
        "id": g.id,
        "name": g.name,
        "role": me.role,
        "members": [
            {"id": m.user.id, "name": m.user.name, "role": m.role}
            for m in sorted(g.members, key=lambda m: m.joined)
        ],
    }
    if me.role == "owner":
        out["inviteCode"] = g.invite_code
        out["discordWebhook"] = g.discord_webhook
    return out


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    # Leerer String entfernt den Webhook.
    discordWebhook: str | None = Field(default=None, max_length=300)


@router.patch("/groups/{group_id}")
def patch_group(group_id: int, body: GroupPatch, user: CurrentUser, session: DbSession):
    m = _require_owner(session, group_id, user)
    if body.name is not None:
        m.group.name = body.name
    if body.discordWebhook is not None:
        url = body.discordWebhook.strip()
        if url and not discord.valid_webhook(url):
            raise HTTPException(422, "Das ist keine Discord-Webhook-Adresse")
        m.group.discord_webhook = url or None
    session.commit()
    return _group_out(m.group, m)


@router.post("/groups", status_code=201)
def create_group(body: GroupIn, user: CurrentUser, session: DbSession):
    g = Group(name=body.name, invite_code=secrets.token_urlsafe(9))
    session.add(g)
    session.flush()
    m = GroupMember(group_id=g.id, user_id=user.id, role="owner")
    session.add(m)
    session.commit()
    session.refresh(g)
    return _group_out(g, m)


@router.get("/groups/{group_id}")
def get_group(group_id: int, user: CurrentUser, session: DbSession):
    m = _membership(session, group_id, user)
    return _group_out(m.group, m)


@router.post("/groups/{group_id}/invite")
def rotate_invite(group_id: int, user: CurrentUser, session: DbSession):
    m = _require_owner(session, group_id, user)
    m.group.invite_code = secrets.token_urlsafe(9)
    session.commit()
    return _group_out(m.group, m)


@router.delete("/groups/{group_id}/members/{user_id}")
def remove_member(group_id: int, user_id: int, user: CurrentUser, session: DbSession):
    me = _membership(session, group_id, user)
    if user_id != user.id and me.role != "owner":
        raise HTTPException(403, "Nur die Gruppenleitung darf andere entfernen")
    target = session.get(GroupMember, (group_id, user_id))
    if target is None:
        raise HTTPException(404, "Mitglied nicht gefunden")
    if target.role == "owner":
        owners = session.scalar(
            select(func.count()).where(GroupMember.group_id == group_id, GroupMember.role == "owner")
        )
        if owners == 1:
            raise HTTPException(400, "Die letzte Leitung kann die Gruppe nicht verlassen")
    session.delete(target)
    session.commit()
    return {"ok": True}


@router.get("/invites/{code}")
def invite_info(code: str, user: CurrentUser, session: DbSession):
    g = session.scalar(select(Group).where(Group.invite_code == code))
    if g is None:
        raise HTTPException(404, "Einladung ungültig")
    return {"id": g.id, "name": g.name, "member": session.get(GroupMember, (g.id, user.id)) is not None}


@router.post("/invites/{code}/join")
def join(code: str, user: CurrentUser, session: DbSession):
    g = session.scalar(select(Group).where(Group.invite_code == code))
    if g is None:
        raise HTTPException(404, "Einladung ungültig")
    m = session.get(GroupMember, (g.id, user.id))
    if m is None:
        m = GroupMember(group_id=g.id, user_id=user.id, role="member")
        session.add(m)
        session.commit()
        session.refresh(g)
    return _group_out(g, m)


# --- Übersicht und Feed ---------------------------------------------------------


def character_state(session: Session, c: Character, max_level: int) -> dict | None:
    snaps = list(
        session.scalars(
            select(Snapshot)
            .where(Snapshot.character_id == c.id)
            .order_by(Snapshot.ts.desc())
            .limit(SNAPSHOTS_FOR_METRICS)
        )
    )
    if not snaps:
        return None
    snaps.reverse()
    s = snaps[-1]
    rate = metrics.xp_per_hour(snaps)
    photo_id = session.scalar(
        select(Photo.id).where(Photo.character_id == c.id).order_by(Photo.ts.desc()).limit(1)
    )
    return {
        "id": c.id,
        "name": c.name,
        "class": c.class_,
        "race": c.race,
        "faction": c.faction,
        "region": c.region,
        "ownerId": c.user_id,
        "ownerName": c.user.name,
        "ts": s.ts,
        "lastUpload": c.last_upload,
        "level": s.level,
        "xp": s.xp,
        "xpMax": s.xp_max,
        "rested": s.rested,
        "zone": s.zone,
        "playedTotal": s.played_total,
        "playedLevel": s.played_level,
        "gold": s.gold if c.gold_visible else None,
        "totalXp": metrics.total_xp(s.level, s.xp),
        "xpPerHour": round(rate) if rate else None,
        "etaSeconds": metrics.eta_seconds(s.level, s.xp, rate, max_level),
        "deaths": (c.state or {}).get("deaths"),
        "photoUrl": f"/api/photos/{photo_id}" if photo_id else None,
    }


@router.get("/groups/{group_id}/overview")
def overview(group_id: int, user: CurrentUser, session: DbSession):
    m = _membership(session, group_id, user)
    max_level = get_settings().max_level
    chars = []
    for c in _visible_characters(session, group_id):
        state = character_state(session, c, max_level)
        if state:
            chars.append(state)
    leader = max((c["totalXp"] for c in chars), default=0)
    for c in chars:
        c["behindLeader"] = leader - c["totalXp"]
    return {
        "group": {"id": m.group.id, "name": m.group.name},
        "maxLevel": max_level,
        "lastUpload": max((c["lastUpload"] or 0 for c in chars), default=None) or None,
        "characters": chars,
    }


def event_out(e: Event, c: Character) -> dict:
    return {
        "id": e.id,
        "ts": e.ts,
        "type": e.type,
        "data": e.data,
        "text": describe(e.type, e.data),
        "character": {"id": c.id, "name": c.name, "class": c.class_},
        "ownerName": c.user.name,
    }


@router.get("/groups/{group_id}/feed")
def feed(group_id: int, user: CurrentUser, session: DbSession, limit: int = 50):
    _membership(session, group_id, user)
    chars = {c.id: c for c in _visible_characters(session, group_id)}
    if not chars:
        return []
    events = session.scalars(
        select(Event)
        .where(Event.character_id.in_(chars.keys()))
        .order_by(Event.ts.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [event_out(e, chars[e.character_id]) for e in events]


# --- Rennen und Material ---------------------------------------------------------

RACE_MAX_POINTS = 200


def _thin(points: list, limit: int) -> list:
    if len(points) <= limit:
        return points
    step = len(points) / limit
    picked = [points[int(i * step)] for i in range(limit - 1)]
    return [*picked, points[-1]]


@router.get("/groups/{group_id}/race")
def race(group_id: int, user: CurrentUser, session: DbSession):
    """Level-Verlauf aller sichtbaren Charaktere: [Zeitpunkt, Spielzeit, Level+Anteil]."""
    _membership(session, group_id, user)
    if not enabled(session, "race"):
        raise HTTPException(404, "Das Rennen-Modul ist ausgeschaltet")
    series = []
    for c in _visible_characters(session, group_id):
        snaps = session.scalars(select(Snapshot).where(Snapshot.character_id == c.id).order_by(Snapshot.ts))
        points = [
            [s.ts, s.played_total, round(s.level + (s.xp / s.xp_max if s.xp_max else 0), 3)] for s in snaps
        ]
        if points:
            series.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "class": c.class_,
                    "ownerName": c.user.name,
                    "points": _thin(points, RACE_MAX_POINTS),
                }
            )
    return series


@router.get("/groups/{group_id}/materials")
def materials(group_id: int, user: CurrentUser, session: DbSession):
    """Handwerksmaterialien der Gruppe: wer hat wie viel (Taschen + letzter Bankstand)."""
    _membership(session, group_id, user)
    items: dict[int, dict] = {}
    for c in _visible_characters(session, group_id):
        mats = (c.state or {}).get("materials") or {}
        per_item: dict[int, dict] = {}
        for where in ("bags", "bank"):
            for m in mats.get(where) or []:
                entry = per_item.setdefault(m["id"], {"name": m.get("name"), "bags": 0, "bank": 0})
                entry[where] += m.get("count") or 0
                entry["name"] = entry["name"] or m.get("name")
        for item_id, e in per_item.items():
            item = items.setdefault(item_id, {"id": item_id, "name": e["name"], "total": 0, "holders": []})
            item["name"] = item["name"] or e["name"]
            item["total"] += e["bags"] + e["bank"]
            item["holders"].append(
                {
                    "characterId": c.id,
                    "name": c.name,
                    "class": c.class_,
                    "ownerName": c.user.name,
                    "bags": e["bags"],
                    "bank": e["bank"],
                    "bankScanned": mats.get("bankScanned"),
                }
            )
    out = sorted(items.values(), key=lambda i: (i["name"] or "").lower())
    for i in out:
        i["holders"].sort(key=lambda h: -(h["bags"] + h["bank"]))
    return out
