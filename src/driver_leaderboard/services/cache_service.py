import json
import uuid
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from threading import Lock
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from driver_leaderboard.config import get_settings
from driver_leaderboard.services.leaderboard_service import get_published_leaderboard

_metrics: Counter[str] = Counter()
_metrics_lock = Lock()


def _record(name: str) -> None:
    with _metrics_lock:
        _metrics[name] += 1


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime, Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


@lru_cache
def redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )


def cache_key(city_id: uuid.UUID) -> str:
    return f"driver-leaderboard:city:{city_id}:published"


def read_cached_leaderboard(city_id: uuid.UUID) -> dict[str, Any] | None:
    if not get_settings().cache_enabled:
        return None
    try:
        payload = redis_client().get(cache_key(city_id))
    except RedisError:
        _record("errors")
        return None
    if payload is None:
        _record("misses")
        return None
    _record("hits")
    return json.loads(payload)


def write_cached_leaderboard(city_id: uuid.UUID, leaderboard: dict[str, Any]) -> bool:
    if not get_settings().cache_enabled:
        return False
    try:
        redis_client().setex(
            cache_key(city_id),
            get_settings().leaderboard_cache_ttl_seconds,
            json.dumps(leaderboard, default=_json_default),
        )
    except RedisError:
        _record("errors")
        return False
    _record("writes")
    return True


def get_cached_or_authoritative_leaderboard(
    session: Session, *, city_id: uuid.UUID
) -> dict[str, Any]:
    cached = read_cached_leaderboard(city_id)
    if cached is not None:
        return cached
    leaderboard = get_published_leaderboard(session, city_id=city_id)
    write_cached_leaderboard(city_id, leaderboard)
    return leaderboard


def refresh_city_cache(session: Session, *, city_id: uuid.UUID) -> bool:
    return write_cached_leaderboard(
        city_id, get_published_leaderboard(session, city_id=city_id)
    )


def cache_metrics() -> dict[str, float | int | bool]:
    with _metrics_lock:
        values = dict(_metrics)
    hits = values.get("hits", 0)
    misses = values.get("misses", 0)
    reads = hits + misses
    return {
        "enabled": get_settings().cache_enabled,
        "hits": hits,
        "misses": misses,
        "writes": values.get("writes", 0),
        "errors": values.get("errors", 0),
        "hit_rate": round(hits / reads, 4) if reads else 0.0,
    }
