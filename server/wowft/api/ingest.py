import zlib

from fastapi import APIRouter, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..auth import CurrentUser, DbSession, TokenUser, client_ip, limiter
from ..config import get_settings
from ..ingest import IngestError, decode, store
from ..models import User

router = APIRouter(prefix="/api", tags=["ingest"])


async def _read_limited(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "Datei zu groß")
        chunks.append(chunk)
    return b"".join(chunks)


def _gunzip(body: bytes, limit: int) -> bytes:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = d.decompress(body, limit + 1)
    except zlib.error as e:
        raise HTTPException(400, "gzip-Daten fehlerhaft") from e
    if len(out) > limit or d.unconsumed_tail:
        raise HTTPException(413, "Datei zu groß")
    return out


def _ingest(session: Session, user: User, body: bytes, content_type: str | None) -> dict:
    try:
        data = decode(body, content_type)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    return store(session, user, data)


@router.post("/ingest")
async def ingest(request: Request, session: DbSession, user: TokenUser):
    """Vom Uploader: Rohinhalt von WowFT.lua (optional gzip) oder JSON."""
    settings = get_settings()
    limiter.check(f"ingest:{user.id}", settings.ingest_rate_per_minute)
    limiter.check("ingest-ip:" + client_ip(request), settings.ingest_rate_per_minute * 2)
    body = await _read_limited(request, settings.max_upload_bytes)
    if request.headers.get("content-encoding", "").lower() == "gzip":
        body = _gunzip(body, settings.max_upload_bytes)
    return _ingest(session, user, body, request.headers.get("content-type"))


@router.post("/me/upload")
async def manual_upload(file: UploadFile, session: DbSession, user: CurrentUser):
    """Manueller Upload der WowFT.lua über die Web-Seite."""
    settings = get_settings()
    limiter.check(f"ingest:{user.id}", settings.ingest_rate_per_minute)
    body = await file.read(settings.max_upload_bytes + 1)
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(413, "Datei zu groß")
    return _ingest(session, user, body, None)
