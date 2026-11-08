import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from . import __version__, auth, weekly
from .api import admin, characters, groups, icons, ingest, me, pairing, photos, recipes, requests
from .config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Hintergrundaufgaben: Wochenrückblick (sonntags) prüfen."""
    task = asyncio.create_task(weekly.loop()) if get_settings().weekly_job else None
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WowFT",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="wowft_session",
        max_age=60 * 60 * 24 * 30,
        same_site="lax",
        https_only=settings.cookie_secure,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": __version__}

    app.include_router(auth.router)
    app.include_router(ingest.router)
    app.include_router(me.router)
    app.include_router(groups.router)
    app.include_router(characters.router)
    app.include_router(photos.router)
    app.include_router(admin.router)
    app.include_router(pairing.router)
    app.include_router(icons.router)
    app.include_router(requests.router)
    app.include_router(recipes.router)

    if settings.static_dir:
        _mount_spa(app, Path(settings.static_dir))
    return app


def _mount_spa(app: FastAPI, root: Path) -> None:
    """Liefert das gebaute Frontend aus; unbekannte Pfade bekommen index.html."""
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "auth/")):
            raise HTTPException(404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            immutable = path.startswith("assets/")
            cache = "public, max-age=31536000, immutable" if immutable else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
