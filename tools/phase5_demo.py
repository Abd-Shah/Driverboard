import json

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, Driver, Review
from driver_leaderboard.services.cache_service import read_cached_leaderboard
from driver_leaderboard.services.leaderboard_service import get_published_leaderboard
from driver_leaderboard.services.worker_service import outbox_metrics
from tools.audit.checks import run_checks


def main() -> int:
    cached = 0
    stale = 0
    with SessionLocal() as session:
        counts = {
            "cities": session.scalar(select(func.count()).select_from(City)),
            "drivers": session.scalar(select(func.count()).select_from(Driver)),
            "reviews": session.scalar(select(func.count()).select_from(Review)),
        }
        queue = outbox_metrics(session)
        for city_id in session.scalars(select(City.id)):
            cache_value = read_cached_leaderboard(city_id)
            if cache_value is None:
                continue
            cached += 1
            authoritative = get_published_leaderboard(session, city_id=city_id)
            stale += cache_value["generation_id"] != authoritative["generation_id"]
        checks = run_checks(session)
    passed = (
        all(check.passed for check in checks)
        and stale == 0
        and queue["pending_events"] == 0
        and queue["failed_events"] == 0
    )
    result = {
        "phase": 5,
        "counts": counts,
        "outbox": queue,
        "cache": {"cities_cached": cached, "stale_cities": stale},
        "database_audit": {"passed": all(check.passed for check in checks)},
        "passed": passed,
    }
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
