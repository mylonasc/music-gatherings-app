from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MUSIC_GATHERINGS_", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    data_dir: str = "/data"
    database_url: str = "sqlite:////data/database/app.sqlite3"
    max_object_bytes: int = 50 * 1024 * 1024
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
