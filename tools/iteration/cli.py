import argparse
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, DriverScore, LeaderboardGeneration
from driver_leaderboard.services.expiration_service import run_city_expiration
from driver_leaderboard.services.leaderboard_service import build_and_publish_generation
from driver_leaderboard.services.rebuild_service import publish_rebuild, start_rebuild
from driver_leaderboard.services.scoring_service import rebuild_city_scores
from driver_leaderboard.services.worker_service import (
    WorkerBatchError,
    drain_outbox,
    outbox_metrics,
    process_batch,
    record_batch_failure,
    serialize_batch,
)
from tools.audit.checks import run_checks, serialize
from tools.iteration.report import write_reports
from tools.iteration.seed import reset_and_seed
from tools.iteration.workload import run_review_workload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a repeatable project iteration")
    parser.add_argument("--name", default="iteration-014")
    parser.add_argument("--cities", type=int, default=10)
    parser.add_argument("--drivers", type=int, default=500)
    parser.add_argument("--reviews", type=int, default=15000)
    parser.add_argument("--unrated-trips", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    started = time.perf_counter()
    with SessionLocal() as session:
        dataset = reset_and_seed(
            session,
            cities=args.cities,
            drivers=args.drivers,
            reviews=args.reviews,
            unrated_trips=args.unrated_trips,
            seed=args.seed,
        )
        workload = run_review_workload(session)
        retry_exercise = {"injected_failure": False, "recovered": False}
        try:
            with SessionLocal() as failure_session:
                process_batch(failure_session, limit=1, fail_after_claim=True)
        except WorkerBatchError as exc:
            retry_exercise["injected_failure"] = True
            with SessionLocal() as failure_record_session:
                record_batch_failure(
                    failure_record_session,
                    event_ids=exc.event_ids,
                    error=str(exc.cause),
                    failed_at=datetime.now(UTC) - timedelta(seconds=2),
                )
        worker_result = drain_outbox(SessionLocal, batch_size=100)
        with SessionLocal() as metrics_session:
            worker_metrics = outbox_metrics(metrics_session)
            retry_exercise["recovered"] = worker_metrics["pending_events"] == 0
        workload["worker"] = {
            **serialize_batch(worker_result),
            **worker_metrics,
            "retry_exercise": retry_exercise,
        }
        city_ids = session.scalars(select(City.id).order_by(City.name)).all()
        score_rebuilds = []
        published_generations = []
        for city_id in city_ids:
            score_rebuilds.append(rebuild_city_scores(session, city_id=city_id))
            generation = build_and_publish_generation(session, city_id=city_id)
            session.commit()
            published_generations.append(
                {
                    "city_id": str(city_id),
                    "version": generation.version,
                    "generation_id": str(generation.id),
                }
            )
        workload["score_rebuild"] = {
            "cities": len(score_rebuilds),
            "drivers_scored": sum(item["drivers_scored"] for item in score_rebuilds),
            "eligible_drivers": sum(item["eligible_drivers"] for item in score_rebuilds),
            "ineligible_drivers": sum(item["ineligible_drivers"] for item in score_rebuilds),
            "contributing_reviews": sum(item["contributing_reviews"] for item in score_rebuilds),
            "outside_window_reviews": sum(
                item["outside_window_reviews"] for item in score_rebuilds
            ),
        }
        workload["published_generations"] = published_generations
        city_id = city_ids[0]
        corrupted_score = session.scalar(
            select(DriverScore)
            .where(DriverScore.city_id == city_id)
            .order_by(DriverScore.driver_id)
            .limit(1)
        )
        if corrupted_score is None:
            raise RuntimeError("no driver score available for rebuild exercise")
        corrupted_score.rating_sum += 1
        session.commit()
        rebuild = start_rebuild(session, city_id=city_id)
        comparison = dict(rebuild.comparison_summary or {})
        published_rebuild = publish_rebuild(session, rebuild_id=rebuild.id)
        workload["staged_rebuild"] = {
            "rebuild_id": str(rebuild.id),
            "live_score_mismatches": comparison.get("live_score_mismatches", 0),
            "candidate_entries": comparison.get("candidate_entries", 0),
            "published": published_rebuild.status == "published",
        }
        expiration_runs = [
            run_city_expiration(
                session,
                city_id=expiration_city_id,
                effective_at=datetime.now(UTC) + timedelta(days=2),
            )
            for expiration_city_id in city_ids
        ]
        workload["expiration"] = {
            "runs": len(expiration_runs),
            "affected_drivers": sum(run.affected_drivers for run in expiration_runs),
            "published_generations": sum(
                run.published_generation_id is not None for run in expiration_runs
            ),
        }
        final_generations = session.execute(
            select(LeaderboardGeneration.city_id, LeaderboardGeneration.version).where(
                LeaderboardGeneration.status == "published"
            )
        ).all()
        workload["final_published_generations"] = {
            str(final_city_id): version for final_city_id, version in final_generations
        }
        checks = run_checks(session)
    report = {
        "name": args.name,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "parameters": {"seed": args.seed},
        "dataset": dataset,
        "workload": workload,
        "audit": {"passed": all(c.passed for c in checks), "checks": serialize(checks)},
    }
    paths = write_reports(report, args.output_dir)
    print(f"audit={'PASS' if report['audit']['passed'] else 'FAIL'} reports={paths[0]},{paths[1]}")
    return 0 if report["audit"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
