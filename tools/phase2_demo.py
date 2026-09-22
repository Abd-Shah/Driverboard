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
    Trip,
)
from tools.audit.checks import run_checks, serialize


def main() -> int:
    with SessionLocal() as session:
        counts = {
            "cities": session.scalar(select(func.count()).select_from(City)),
            "drivers": session.scalar(select(func.count()).select_from(Driver)),
            "trips": session.scalar(select(func.count()).select_from(Trip)),
            "reviews": session.scalar(select(func.count()).select_from(Review)),
            "driver_scores": session.scalar(select(func.count()).select_from(DriverScore)),
            "published_generations": session.scalar(
                select(func.count())
                .select_from(LeaderboardGeneration)
                .where(LeaderboardGeneration.status == "published")
            ),
            "published_entries": session.scalar(
                select(func.count())
                .select_from(LeaderboardEntry)
                .join(
                    LeaderboardGeneration,
                    LeaderboardGeneration.id == LeaderboardEntry.generation_id,
                )
                .where(LeaderboardGeneration.status == "published")
            ),
        }
        checks = run_checks(session)
    result = {
        "phase": 2,
        "counts": counts,
        "audit": {"passed": all(check.passed for check in checks), "checks": serialize(checks)},
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["audit"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
