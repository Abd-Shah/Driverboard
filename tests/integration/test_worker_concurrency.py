import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import OutboxEvent, Review, ReviewVersion, Trip
from driver_leaderboard.services.review_service import upsert_review
from driver_leaderboard.services.worker_service import drain_outbox, process_batch

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires migrated local PostgreSQL"
)


def test_two_workers_claim_distinct_events_without_double_processing() -> None:
    drain_outbox(SessionLocal)
    with SessionLocal() as session:
        targets = session.execute(
            select(Trip, ReviewVersion.rating)
            .join(Review, Review.trip_id == Trip.id)
            .join(ReviewVersion, ReviewVersion.review_id == Review.id)
            .where(Review.deleted_at.is_(None), ReviewVersion.is_current.is_(True))
            .order_by(Trip.stable_id)
            .limit(2)
        ).all()
    for trip, rating in targets:
        with SessionLocal() as session:
            upsert_review(
                session,
                trip_id=trip.id,
                rider_id=trip.rider_id,
                rating=1 if rating != 1 else 5,
                idempotency_key=f"worker-concurrency-{uuid.uuid4()}",
            )
    with SessionLocal() as session:
        event_ids = session.scalars(
            select(OutboxEvent.id)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.desc())
            .limit(2)
        ).all()

    def work(_: int) -> int:
        with SessionLocal() as session:
            return process_batch(session, limit=1).events_processed

    with ThreadPoolExecutor(max_workers=2) as executor:
        processed = sum(executor.map(work, range(2)))
    assert processed == 2
    with SessionLocal() as session:
        completed = session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.id.in_(event_ids), OutboxEvent.status == "completed")
        )
    assert completed == 2
