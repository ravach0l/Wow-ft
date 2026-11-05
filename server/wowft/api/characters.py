from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..auth import CurrentUser, DbSession
from ..config import get_settings
from ..events import SKILL_CATEGORIES, SLOTS, STANDINGS
from ..models import Character, Event, Snapshot
from .groups import character_state, event_out, user_can_see
from .photos import photos_of

router = APIRouter(prefix="/api", tags=["characters"])


@router.get("/characters/{char_id}/history")
def history(char_id: int, user: CurrentUser, session: DbSession):
    c = session.get(Character, char_id)
    if c is None or not user_can_see(session, user, c):
        raise HTTPException(404, "Charakter nicht gefunden")
    snaps = session.scalars(select(Snapshot).where(Snapshot.character_id == c.id).order_by(Snapshot.ts))
    events = session.scalars(select(Event).where(Event.character_id == c.id).order_by(Event.ts.desc()))
    return {
        "character": character_state(session, c, get_settings().max_level),
        "snapshots": [
            {
                "ts": s.ts,
                "level": s.level,
                "xp": s.xp,
                "xpMax": s.xp_max,
                "playedTotal": s.played_total,
                "zone": s.zone,
            }
            for s in snaps
        ],
        "events": [event_out(e, c) for e in events],
        "state": _state_out(c.state or {}),
        "photos": photos_of(session, c.id),
    }


def _state_out(state: dict) -> dict:
    """Bereitet den Addon-Stand für die Anzeige auf (Kategorien, Namen)."""
    skills = []
    for s in state.get("skills") or []:
        category = SKILL_CATEGORIES.get((s.get("header") or "").strip().lower())
        if category:
            skills.append({**s, "category": category})
    reps = [{**r, "standingName": STANDINGS.get(r.get("standing"), "")} for r in state.get("reputation", [])]
    return {
        "skills": skills,
        "equipment": sorted(
            [{**e, "slotName": SLOTS.get(e.get("slot"), "")} for e in state.get("equipment") or []],
            key=lambda e: e.get("slot") or 0,
        ),
        "reputation": sorted(
            reps,
            key=lambda r: (-(r.get("standing") or 0), r.get("name") or ""),
        ),
        "talents": state.get("talents") or [],
        "materials": state.get("materials"),
        "deaths": state.get("deaths"),
    }
