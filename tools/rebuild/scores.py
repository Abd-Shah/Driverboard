import argparse
import json
import uuid

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.services.scoring_service import rebuild_city_scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild derived scores for one city")
    parser.add_argument("--city-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    with SessionLocal() as session:
        result = rebuild_city_scores(session, city_id=args.city_id)
    print(json.dumps({"city_id": str(args.city_id), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
