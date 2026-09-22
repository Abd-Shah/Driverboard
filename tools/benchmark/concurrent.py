import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, Review, ReviewVersion, Trip
from driver_leaderboard.services.cache_service import (
    cache_metrics,
    get_cached_or_authoritative_leaderboard,
)
from driver_leaderboard.services.review_service import upsert_review
from driver_leaderboard.services.worker_service import drain_outbox, outbox_metrics, serialize_batch


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * percentile) - 1))
    return round(ordered[index], 3)


def run_concurrent_benchmark(
    *, reads: int, writes: int, workers: int, drain_worker: bool = False
) -> dict[str, object]:
    with SessionLocal() as session:
        city_ids = session.scalars(select(City.id).order_by(City.name)).all()
        write_targets = session.execute(
            select(Trip.id, Trip.rider_id, ReviewVersion.rating)
            .join(Review, Review.trip_id == Trip.id)
            .join(ReviewVersion, ReviewVersion.review_id == Review.id)
            .where(Review.deleted_at.is_(None), ReviewVersion.is_current.is_(True))
            .order_by(Trip.stable_id)
            .limit(writes)
        ).all()

    def read_once(index: int) -> float:
        started = time.perf_counter()
        with SessionLocal() as session:
            get_cached_or_authoritative_leaderboard(
                session, city_id=city_ids[index % len(city_ids)]
            )
        return (time.perf_counter() - started) * 1000

    read_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        read_times = list(executor.map(read_once, range(reads)))
    read_duration = time.perf_counter() - read_started

    def write_once(target) -> float:
        trip_id, rider_id, rating = target
        started = time.perf_counter()
        with SessionLocal() as session:
            upsert_review(
                session,
                trip_id=trip_id,
                rider_id=rider_id,
                rating=1 if rating != 1 else 5,
                idempotency_key=f"phase2-benchmark-{uuid.uuid4()}",
            )
        return (time.perf_counter() - started) * 1000

    write_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        write_times = list(executor.map(write_once, write_targets))
    write_duration = time.perf_counter() - write_started
    with SessionLocal() as session:
        before_drain = outbox_metrics(session)
    result: dict[str, object] = {
        "workers": workers,
        "leaderboard_reads": reads,
        "leaderboard_reads_per_second": round(reads / read_duration, 1),
        "leaderboard_read_p50_ms": _percentile(read_times, 0.50),
        "leaderboard_read_p95_ms": _percentile(read_times, 0.95),
        "review_writes": len(write_times),
        "review_writes_per_second": (
            round(len(write_times) / write_duration, 1) if write_times else 0.0
        ),
        "review_write_p50_ms": _percentile(write_times, 0.50),
        "review_write_p95_ms": _percentile(write_times, 0.95),
        "outbox_before_drain": before_drain,
        "cache": cache_metrics(),
    }
    if drain_worker:
        convergence_started = time.perf_counter()
        worker_result = drain_outbox(SessionLocal)
        convergence_duration = time.perf_counter() - convergence_started
        with SessionLocal() as session:
            after_drain = outbox_metrics(session)
        result["worker"] = {
            **serialize_batch(worker_result),
            "convergence_duration_ms": round(convergence_duration * 1000, 3),
            "outbox_after_drain": after_drain,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Concurrent leaderboard service benchmark")
    parser.add_argument("--reads", type=int, default=1000)
    parser.add_argument("--writes", type=int, default=50)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--drain-worker", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("reports/concurrent-load.json"))
    args = parser.parse_args()
    result = run_concurrent_benchmark(
        reads=args.reads,
        writes=args.writes,
        workers=args.workers,
        drain_worker=args.drain_worker,
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(
        "# Concurrent service benchmark\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
