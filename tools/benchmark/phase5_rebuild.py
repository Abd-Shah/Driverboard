import json
import time
from pathlib import Path

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, DriverScore, RebuildJob, Trip
from driver_leaderboard.services.rebuild_service import publish_rebuild, start_rebuild


def main() -> int:
    with SessionLocal() as session:
        protected_cities = select(RebuildJob.city_id).distinct()
        city_id = session.scalar(
            select(City.id)
            .join(Trip, Trip.city_id == City.id)
            .where(City.id.not_in(protected_cities))
            .group_by(City.id)
            .order_by(func.count(Trip.id).desc(), City.id)
            .limit(1)
        )
        trip_count = int(
            session.scalar(select(func.count()).select_from(Trip).where(Trip.city_id == city_id))
            or 0
        )
        score = session.scalar(
            select(DriverScore)
            .where(DriverScore.city_id == city_id)
            .order_by(DriverScore.driver_id)
            .limit(1)
        )
        if score is None:
            raise RuntimeError("selected city has no derived score to corrupt")
        score.rating_sum += 1
        session.commit()
        started = time.perf_counter()
        job = start_rebuild(session, city_id=city_id)
        build_seconds = time.perf_counter() - started
        comparison = dict(job.comparison_summary or {})
        publish_started = time.perf_counter()
        published = publish_rebuild(session, rebuild_id=job.id)
        publish_seconds = time.perf_counter() - publish_started
    total_seconds = build_seconds + publish_seconds
    result = {
        "city_id": str(city_id),
        "trips_rebuilt": trip_count,
        "injected_score_corruption": True,
        "detected_live_score_mismatches": comparison.get("live_score_mismatches", 0),
        "candidate_entries": comparison.get("candidate_entries", 0),
        "build_seconds": round(build_seconds, 3),
        "publish_seconds": round(publish_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "target_seconds": 1_800,
        "target_met": total_seconds < 1_800,
        "status": published.status,
    }
    output = Path("reports/iteration-020-rebuild.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    output.with_suffix(".md").write_text(
        "# Iteration 020: rebuild recovery\n\n```json\n"
        + json.dumps(result, indent=2)
        + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0 if result["target_met"] and result["detected_live_score_mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
