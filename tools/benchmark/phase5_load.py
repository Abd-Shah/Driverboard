import argparse
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import (
    City,
    ExpirationRun,
    OutboxEvent,
    RebuildJob,
    Review,
    ReviewVersion,
    Trip,
)
from driver_leaderboard.services.cache_service import (
    cache_metrics,
    get_cached_or_authoritative_leaderboard,
)
from driver_leaderboard.services.review_service import upsert_review
from driver_leaderboard.services.worker_service import outbox_metrics, process_batch
from tools.benchmark.concurrent import _percentile


def run_load(*, reads: int, writes: int, clients: int, batch_size: int) -> dict[str, object]:
    with SessionLocal() as session:
        city_ids = session.scalars(select(City.id).order_by(City.id)).all()
        protected_cities = select(RebuildJob.city_id).distinct()
        write_city_id = session.scalar(
            select(City.id).where(City.id.not_in(protected_cities)).order_by(City.id).limit(1)
        )
        if write_city_id is None:
            raise RuntimeError("no city is available for an isolated load workload")
        targets = session.execute(
            select(Trip.id, Trip.rider_id, ReviewVersion.rating)
            .join(Review, Review.trip_id == Trip.id)
            .join(ReviewVersion, ReviewVersion.review_id == Review.id)
            .where(
                Trip.city_id == write_city_id,
                Review.deleted_at.is_(None),
                ReviewVersion.is_current.is_(True),
            )
            .order_by(Trip.stable_id)
            .limit(writes)
        ).all()
        latest_expiration = session.scalar(select(func.max(ExpirationRun.effective_at)))
    processing_time = max(datetime.now(UTC), latest_expiration) if latest_expiration else None
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    stop_worker = threading.Event()
    writes_finished = threading.Event()
    queue_samples: list[int] = []
    worker_totals = {"events": 0, "drivers": 0, "generations": 0, "batches": 0}

    def worker_loop() -> None:
        while not stop_worker.is_set():
            with SessionLocal() as session:
                metrics = outbox_metrics(session)
                queue_samples.append(int(metrics["pending_events"]))
                batch = process_batch(
                    session,
                    limit=batch_size,
                    processed_at=processing_time,
                )
            if batch.events_processed:
                worker_totals["events"] += batch.events_processed
                worker_totals["drivers"] += batch.drivers_recalculated
                worker_totals["generations"] += batch.generations_published
                worker_totals["batches"] += 1
            elif writes_finished.is_set():
                return
            else:
                time.sleep(0.01)

    worker = threading.Thread(target=worker_loop, daemon=True)
    worker.start()

    def read_once(index: int) -> float:
        operation_started = time.perf_counter()
        with SessionLocal() as session:
            get_cached_or_authoritative_leaderboard(
                session, city_id=city_ids[index % len(city_ids)]
            )
        return (time.perf_counter() - operation_started) * 1000

    def write_once(index: int) -> float:
        trip_id, rider_id, rating = targets[index]
        operation_started = time.perf_counter()
        with SessionLocal() as session:
            upsert_review(
                session,
                trip_id=trip_id,
                rider_id=rider_id,
                rating=1 if rating != 1 else 5,
                idempotency_key=f"phase5-load-{uuid.uuid4()}",
            )
        return (time.perf_counter() - operation_started) * 1000

    with ThreadPoolExecutor(max_workers=clients) as executor:
        read_future = executor.submit(lambda: list(executor.map(read_once, range(reads))))
        write_times = list(executor.map(write_once, range(len(targets))))
        writes_finished.set()
        read_times = read_future.result()
    worker.join(timeout=120)
    if worker.is_alive():
        stop_worker.set()
        raise RuntimeError("worker did not converge within 120 seconds")
    duration = time.perf_counter() - started
    with SessionLocal() as session:
        final_outbox = outbox_metrics(session)
        completed = int(
            session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(
                    OutboxEvent.created_at >= started_at,
                    OutboxEvent.status == "completed",
                )
            )
            or 0
        )
    return {
        "parameters": {
            "reads": reads,
            "writes": len(targets),
            "clients": clients,
            "worker_batch_size": batch_size,
            "write_city_id": str(write_city_id),
        },
        "duration_seconds": round(duration, 3),
        "combined_operations_per_second": round((reads + len(targets)) / duration, 1),
        "read_p50_ms": _percentile(read_times, 0.50),
        "read_p95_ms": _percentile(read_times, 0.95),
        "write_p50_ms": _percentile(write_times, 0.50),
        "write_p95_ms": _percentile(write_times, 0.95),
        "peak_pending_events": max(queue_samples, default=0),
        "events_created_and_completed": completed,
        "worker": worker_totals,
        "final_outbox": final_outbox,
        "cache": cache_metrics(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 mixed load and convergence test")
    parser.add_argument("--reads", type=int, default=20_000)
    parser.add_argument("--writes", type=int, default=1_000)
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("reports/iteration-018-load.json"))
    args = parser.parse_args()
    result = run_load(
        reads=args.reads,
        writes=args.writes,
        clients=args.clients,
        batch_size=args.batch_size,
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(
        "# Iteration 018: mixed load and convergence\n\n```json\n"
        + json.dumps(result, indent=2)
        + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
