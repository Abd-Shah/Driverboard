import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import (
    City,
    ExpirationRun,
    RebuildJob,
    Review,
    ReviewVersion,
    Trip,
)
from driver_leaderboard.services.review_service import upsert_review
from driver_leaderboard.services.worker_service import (
    WorkerBatchError,
    outbox_metrics,
    process_batch,
    record_batch_failure,
    serialize_batch,
)


def main() -> int:
    with SessionLocal() as session:
        protected_cities = select(RebuildJob.city_id).distinct()
        city_id = session.scalar(
            select(City.id).where(City.id.not_in(protected_cities)).order_by(City.id).limit(1)
        )
        targets = session.execute(
            select(Trip.id, Trip.rider_id, ReviewVersion.rating)
            .join(Review, Review.trip_id == Trip.id)
            .join(ReviewVersion, ReviewVersion.review_id == Review.id)
            .where(
                Trip.city_id == city_id,
                Review.deleted_at.is_(None),
                ReviewVersion.is_current.is_(True),
            )
            .order_by(Trip.stable_id.desc())
            .limit(100)
        ).all()
        latest_expiration = session.scalar(select(func.max(ExpirationRun.effective_at)))
    processing_time = max(datetime.now(UTC), latest_expiration) if latest_expiration else None
    for trip_id, rider_id, rating in targets:
        with SessionLocal() as session:
            upsert_review(
                session,
                trip_id=trip_id,
                rider_id=rider_id,
                rating=1 if rating != 1 else 5,
                idempotency_key=f"phase5-failure-{uuid.uuid4()}",
            )
    failure_recorded = False
    try:
        with SessionLocal() as session:
            process_batch(
                session,
                limit=100,
                processed_at=processing_time,
                fail_after_claim=True,
            )
    except WorkerBatchError as exc:
        with SessionLocal() as session:
            record_batch_failure(
                session,
                event_ids=exc.event_ids,
                error=str(exc.cause),
                failed_at=(processing_time or datetime.now(UTC)) - timedelta(seconds=2),
            )
        failure_recorded = True
    recovery_started = time.perf_counter()
    with SessionLocal() as session:
        recovered = process_batch(session, limit=100, processed_at=processing_time)
    recovery_ms = round((time.perf_counter() - recovery_started) * 1000, 3)
    with SessionLocal() as session:
        metrics = outbox_metrics(session)
    result = {
        "events_enqueued": len(targets),
        "failure_recorded": failure_recorded,
        "recovery_ms": recovery_ms,
        "recovered_batch": serialize_batch(recovered),
        "final_outbox": metrics,
    }
    output = Path("reports/iteration-019-worker-recovery.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    output.with_suffix(".md").write_text(
        "# Iteration 019: worker recovery\n\n```json\n"
        + json.dumps(result, indent=2)
        + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0 if failure_recorded and metrics["pending_events"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
