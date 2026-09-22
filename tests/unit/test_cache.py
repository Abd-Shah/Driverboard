import uuid
from types import SimpleNamespace

from redis.exceptions import ConnectionError

from driver_leaderboard.services import cache_service


class FailingRedis:
    def get(self, key: str) -> None:
        raise ConnectionError("redis unavailable")

    def setex(self, key: str, ttl: int, value: str) -> None:
        raise ConnectionError("redis unavailable")


def test_cache_failure_behaves_like_a_miss(monkeypatch) -> None:
    monkeypatch.setattr(
        cache_service,
        "get_settings",
        lambda: SimpleNamespace(cache_enabled=True, leaderboard_cache_ttl_seconds=120),
    )
    monkeypatch.setattr(cache_service, "redis_client", lambda: FailingRedis())

    assert cache_service.read_cached_leaderboard(uuid.uuid4()) is None


def test_cache_write_failure_is_non_fatal(monkeypatch) -> None:
    monkeypatch.setattr(
        cache_service,
        "get_settings",
        lambda: SimpleNamespace(cache_enabled=True, leaderboard_cache_ttl_seconds=120),
    )
    monkeypatch.setattr(cache_service, "redis_client", lambda: FailingRedis())

    assert cache_service.write_cached_leaderboard(uuid.uuid4(), {"version": 1}) is False
