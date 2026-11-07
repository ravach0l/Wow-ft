from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from .. import icons
from ..auth import CurrentUser

router = APIRouter(prefix="/api", tags=["icons"])


@router.get("/icons/{name}.jpg")
async def icon(name: str, _: CurrentUser):
    """Talent-Icon aus dem Zwischenspeicher (beim ersten Abruf von Wowhead geladen)."""
    path = await run_in_threadpool(icons.icon_file, name.lower())
    if path is None:
        raise HTTPException(404, "Icon nicht gefunden")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=2592000"})
