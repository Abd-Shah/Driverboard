import argparse
import json
import uuid
from datetime import datetime

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.services.expiration_service import (
    run_city_expiration,
    serialize_expiration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance a city's rolling score window")
    parser.add_argument("--city-id", required=True, type=uuid.UUID)
    parser.add_argument("--effective-at", type=datetime.fromisoformat)
    args = parser.parse_args()
    with SessionLocal() as session:
        run = run_city_expiration(session, city_id=args.city_id, effective_at=args.effective_at)
        result = serialize_expiration(run)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
