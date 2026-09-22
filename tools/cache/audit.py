import json

from sqlalchemy import select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City
from driver_leaderboard.services.cache_service import read_cached_leaderboard
from driver_leaderboard.services.leaderboard_service import get_published_leaderboard


def main() -> int:
    missing = 0
    stale = 0
    checked = 0
    with SessionLocal() as session:
        for city_id in session.scalars(select(City.id).order_by(City.id)):
            authoritative = get_published_leaderboard(session, city_id=city_id)
            cached = read_cached_leaderboard(city_id)
            if cached is None:
                missing += 1
                continue
            checked += 1
            if cached["generation_id"] != authoritative["generation_id"]:
                stale += 1
    result = {
        "passed": missing == 0 and stale == 0,
        "cities_checked": checked,
        "missing_cities": missing,
        "stale_cities": stale,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
