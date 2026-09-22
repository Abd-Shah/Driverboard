from driver_leaderboard.config import Settings


def test_settings_have_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+psycopg://")
