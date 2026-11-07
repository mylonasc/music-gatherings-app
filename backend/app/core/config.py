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
    session_ttl_seconds: int = 7 * 24 * 3600
    session_cookie_name: str = "mg_session"
    session_cookie_secure: bool = False
    login_max_attempts: int = 10
    login_window_seconds: int = 300
    request_access_max_attempts: int = 10
    request_access_window_seconds: int = 3600
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
