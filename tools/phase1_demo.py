import json

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import (
    City,
    Driver,
    DriverScore,
    LeaderboardEntry,
    LeaderboardGeneration,
    Review,
    ReviewVersion,
    Trip,
)
from tools.audit.checks import run_checks, serialize


def main() -> int:
    with SessionLocal() as session:
        city = session.execute(select(City).order_by(City.name).limit(1)).scalar_one()
        generation = session.execute(
            select(LeaderboardGeneration).where(
                LeaderboardGeneration.city_id == city.id,
                LeaderboardGeneration.status == "published",
            )
        ).scalar_one()
        counts = {
            "drivers": session.scalar(select(func.count()).select_from(Driver)),
            "trips": session.scalar(select(func.count()).select_from(Trip)),
            "reviews": session.scalar(select(func.count()).select_from(Review)),
            "review_versions": session.scalar(select(func.count()).select_from(ReviewVersion)),
            "driver_scores": session.scalar(select(func.count()).select_from(DriverScore)),
            "leaderboard_entries": session.scalar(
                select(func.count())
                .select_from(LeaderboardEntry)
                .where(LeaderboardEntry.generation_id == generation.id)
            ),
        }
        checks = run_checks(session)
    result = {
        "phase": 1,
        "city": city.name,
        "published_generation": generation.version,
        "counts": counts,
        "audit": {"passed": all(check.passed for check in checks), "checks": serialize(checks)},
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["audit"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
