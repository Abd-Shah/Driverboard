import json

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, Driver, LeaderboardGeneration
from driver_leaderboard.services.worker_service import outbox_metrics
from tools.audit.checks import run_checks, serialize


def main() -> int:
    with SessionLocal() as session:
        counts = {
            "cities": session.scalar(select(func.count()).select_from(City)),
            "drivers": session.scalar(select(func.count()).select_from(Driver)),
            "published_generations": session.scalar(
                select(func.count())
                .select_from(LeaderboardGeneration)
                .where(LeaderboardGeneration.status == "published")
            ),
        }
        metrics = outbox_metrics(session)
        checks = run_checks(session)
    result = {
        "phase": 3,
        "counts": counts,
        "outbox": metrics,
        "audit": {"passed": all(check.passed for check in checks), "checks": serialize(checks)},
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["audit"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
