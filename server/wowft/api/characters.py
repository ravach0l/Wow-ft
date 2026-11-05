from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..auth import CurrentUser, DbSession
from ..config import get_settings
from ..models import Character, Event, Snapshot
from .groups import character_state, event_out, user_can_see

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
    }
