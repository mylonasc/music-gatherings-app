from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MUSIC_GATHERINGS_", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    data_dir: str = "/data"
    database_url: str = "sqlite:////data/database/app.sqlite3"
    max_object_bytes: int = 50 * 1024 * 1024
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: float = 300.0
    worker_max_retries: int = 3
    online_provider_urls: dict[str, str] = {
        "fake": "http://ingestion-fake:8001",
        "genius": "http://ingestion-genius:8002",
        "ultimate_guitar": "http://ingestion-ultimate-guitar:8003",
    }
    processor_url: str = "http://processor:8004"
    processor_timeout_seconds: float = 60.0
    provider_timeout_seconds: float = 15.0
    session_ttl_seconds: int = 7 * 24 * 3600
    session_cookie_name: str = "mg_session"
    session_cookie_secure: bool = False
    online_search_per_user_per_hour: int = 30
    online_import_per_user_per_hour: int = 20
    login_max_attempts: int = 10
    login_window_seconds: int = 300
    request_access_max_attempts: int = 10
    request_access_window_seconds: int = 3600
    log_level: str = "INFO"

    @model_validator(mode="after")
    def production_cookies(self) -> Self:
        if self.app_env == "production":
            self.session_cookie_secure = True
        return self


def get_settings() -> Settings:
    return Settings()
