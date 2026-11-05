from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WOWFT_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/wowft.db"
    secret_key: str = "dev-unsicher-bitte-setzen"
    base_url: str = "http://localhost:8000"
    cookie_secure: bool = False

    # Authentik (OIDC). Beispiel:
    # https://auth.example.org/application/o/wowft/.well-known/openid-configuration
    oidc_metadata_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    # Nur für lokale Entwicklung und Tests: Login ohne Authentik.
    dev_login: bool = False

    static_dir: str = ""
    data_dir: str = "./data"  # Fotos liegen in <data_dir>/photos
    max_photo_bytes: int = 3 * 1024 * 1024
    max_upload_bytes: int = 5 * 1024 * 1024
    max_level: int = 60

    ingest_rate_per_minute: int = 30
    auth_rate_per_minute: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
