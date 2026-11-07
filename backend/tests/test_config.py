from app.core.config import Settings


def test_settings_defaults_validate() -> None:
    settings = Settings()
    assert settings.app_env
    assert settings.app_version == "0.1.0"
    assert settings.data_dir.startswith("/")
