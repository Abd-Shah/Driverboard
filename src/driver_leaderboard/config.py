from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://leaderboard:leaderboard@localhost:5432/leaderboard"
    cache_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    leaderboard_cache_ttl_seconds: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
