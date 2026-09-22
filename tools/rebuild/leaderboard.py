import argparse
import json
import uuid

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.services.leaderboard_service import build_and_publish_generation


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish a city leaderboard")
    parser.add_argument("--city-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    with SessionLocal() as session:
        generation = build_and_publish_generation(session, city_id=args.city_id)
        session.commit()
        result = {
            "city_id": str(generation.city_id),
            "generation_id": str(generation.id),
            "version": generation.version,
            "status": generation.status,
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
