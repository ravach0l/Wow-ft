from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from wowft import auth, config, db

SERVER = Path(__file__).resolve().parents[1]
FIXTURES = SERVER.parent / "fixtures"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("WOWFT_DATABASE_URL", url)
    monkeypatch.setenv("WOWFT_DEV_LOGIN", "true")
    monkeypatch.setenv("WOWFT_SECRET_KEY", "test")
    # Keine echten Anfragen an Wowhead in Tests (tests/test_icons.py ersetzt die Abfragen gezielt).
    monkeypatch.setenv("WOWFT_ICON_LOOKUP", "false")
    monkeypatch.setenv("WOWFT_DATA_DIR", str(tmp_path / "data"))
    config.get_settings.cache_clear()
    db.reset_engine()
    auth.limiter.reset()
    command.upgrade(Config(str(SERVER / "alembic.ini")), "head")
    yield config.get_settings()
    db.reset_engine()
    config.get_settings.cache_clear()


@pytest.fixture
def make_client(settings):
    from wowft.main import create_app

    def make(name: str | None = None) -> TestClient:
        client = TestClient(create_app())
        if name:
            r = client.get("/auth/dev-login", params={"name": name}, follow_redirects=False)
            assert r.status_code == 303
        return client

    return make


@pytest.fixture
def sv_text():
    return (FIXTURES / "WowFT.lua").read_text(encoding="utf-8")


def upload_token(client: TestClient) -> str:
    r = client.post("/api/tokens", json={"name": "PC"})
    assert r.status_code == 201
    return r.json()["token"]
