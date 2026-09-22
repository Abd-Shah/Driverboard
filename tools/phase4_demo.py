import json

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, Driver, Review
from driver_leaderboard.services.cache_service import read_cached_leaderboard
from driver_leaderboard.services.leaderboard_service import get_published_leaderboard
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
        for city_id in session.scalars(select(City.id)):
            cache_value = read_cached_leaderboard(city_id)
            if cache_value is None:
                continue
            cached += 1
            authoritative = get_published_leaderboard(session, city_id=city_id)
            stale += cache_value["generation_id"] != authoritative["generation_id"]
        checks = run_checks(session)
    result = {
        "phase": 4,
        "counts": counts,
        "cache": {"cities_cached": cached, "stale_cities": stale},
        "database_audit": {"passed": all(check.passed for check in checks)},
    }
    result["passed"] = result["database_audit"]["passed"] and stale == 0
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
