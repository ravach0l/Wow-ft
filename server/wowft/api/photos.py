from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from .. import privacy
from ..auth import CurrentUser, DbSession, TokenUser
from ..config import get_settings
from ..models import Character, Photo, Snapshot
from .groups import user_can_see
from .ingest import _read_limited

router = APIRouter(prefix="/api", tags=["photos"])


def photo_dir() -> Path:
    return Path(get_settings().data_dir) / "photos"


@router.post("/characters/{char_id}/photos", status_code=201)
async def upload_photo(char_id: int, t: int, request: Request, session: DbSession, user: TokenUser):
    """Vom Uploader: zugeschnittenes JPEG zu einem /ft foto-Zeitpunkt."""
    char = session.get(Character, char_id)
    if char is None or char.user_id != user.id:
        raise HTTPException(404, "Charakter nicht gefunden")
    if t not in (char.state or {}).get("photoRequests", []):
        raise HTTPException(400, "Zu diesem Zeitpunkt wurde kein Foto angefordert")
    if session.scalar(select(Photo).where(Photo.character_id == char_id, Photo.ts == t)):
        raise HTTPException(409, "Foto ist schon da")
    body = await _read_limited(request, get_settings().max_photo_bytes)
    if not body.startswith(b"\xff\xd8\xff"):
        raise HTTPException(415, "Nur JPEG")

    level = session.scalar(
        select(Snapshot.level)
        .where(Snapshot.character_id == char_id, Snapshot.ts <= t + 60)
        .order_by(Snapshot.ts.desc())
        .limit(1)
    )
    rel = Path(str(char_id)) / f"{t}.jpg"
    target = photo_dir() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    # Kontext aus dem Addon (/ft foto): Level und Zone zum Zeitpunkt der Aufnahme
    info = next((i for i in (char.state or {}).get("photoInfo", []) if i.get("t") == t), {})
    zone = " · ".join(p for p in (info.get("zone"), info.get("subzone")) if p) or None
    photo = Photo(character_id=char_id, ts=t, level=info.get("level") or level, zone=zone, path=str(rel))
    session.add(photo)
    session.commit()
    return {"id": photo.id}


def _visible_photo(photo_id: int, user, session) -> tuple[Photo, Character]:
    photo = session.get(Photo, photo_id)
    char = photo and session.get(Character, photo.character_id)
    if photo is None or char is None or not user_can_see(session, user, char):
        raise HTTPException(404, "Foto nicht gefunden")
    if not privacy.is_shared(char, "photo", user.id):
        raise HTTPException(404, "Foto nicht gefunden")
    return photo, char


@router.get("/photos/{photo_id}")
def get_photo(photo_id: int, user: CurrentUser, session: DbSession):
    photo, _ = _visible_photo(photo_id, user, session)
    path = (photo_dir() / photo.path).resolve()
    if not path.is_relative_to(photo_dir().resolve()) or not path.is_file():
        raise HTTPException(404, "Foto nicht gefunden")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: int, user: CurrentUser, session: DbSession):
    photo, char = _visible_photo(photo_id, user, session)
    if char.user_id != user.id:
        raise HTTPException(403, "Nur eigene Fotos können gelöscht werden")
    (photo_dir() / photo.path).unlink(missing_ok=True)
    session.delete(photo)
    session.commit()
    return {"ok": True}


def photos_of(session, char_id: int, hide_zone: bool = False) -> list[dict]:
    rows = session.scalars(select(Photo).where(Photo.character_id == char_id).order_by(Photo.ts.desc()))
    return [
        {
            "id": p.id,
            "url": f"/api/photos/{p.id}",
            "ts": p.ts,
            "level": p.level,
            "zone": None if hide_zone else p.zone,
        }
        for p in rows
    ]
