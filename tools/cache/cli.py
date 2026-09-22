import argparse
import json
import uuid

from sqlalchemy import select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City
from driver_leaderboard.services.cache_service import refresh_city_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Warm published city leaderboards in Redis")
    parser.add_argument("--city-id")
    args = parser.parse_args()
    with SessionLocal() as session:
        city_ids = (
            [uuid.UUID(args.city_id)]
            if args.city_id
            else session.scalars(select(City.id).order_by(City.id)).all()
        )
        warmed = sum(refresh_city_cache(session, city_id=city_id) for city_id in city_ids)
    print(json.dumps({"cities_considered": len(city_ids), "cities_warmed": warmed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
