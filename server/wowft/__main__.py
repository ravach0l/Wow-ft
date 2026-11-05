"""Startet den Server: erst Migrationen, dann uvicorn.

python -m wowft            # Server auf 0.0.0.0:8000
python -m wowft migrate    # nur Migrationen
"""

import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

from .config import get_settings


def migrate() -> None:
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")


def main() -> None:
    migrate()
    if sys.argv[1:] == ["migrate"]:
        return
    uvicorn.run(
        "wowft.main:app",
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
