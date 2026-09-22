import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import Review, ReviewVersion, Trip
from driver_leaderboard.services.review_service import IdempotencyConflict, upsert_review

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires migrated local PostgreSQL"
)


def test_concurrent_corrections_are_serialized_and_conflicts_roll_back() -> None:
    with SessionLocal() as session:
        review, trip, current = session.execute(
            select(Review, Trip, ReviewVersion)
            .join(Trip, Trip.id == Review.trip_id)
            .join(ReviewVersion, ReviewVersion.review_id == Review.id)
            .where(ReviewVersion.is_current.is_(True), Review.deleted_at.is_(None))
            .limit(1)
        ).one()
        initial_max = session.scalar(
            select(func.max(ReviewVersion.version)).where(ReviewVersion.review_id == review.id)
        )
        rating_a = 1 if current.rating != 1 else 2
        rating_b = 5 if rating_a != 5 and current.rating != 5 else 4
        trip_id, rider_id, review_id = trip.id, trip.rider_id, review.id

    def correct(rating: int) -> None:
        with SessionLocal() as session:
            upsert_review(
                session,
                trip_id=trip_id,
                rider_id=rider_id,
                rating=rating,
                idempotency_key=f"concurrency-{uuid.uuid4()}",
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(correct, (rating_a, rating_b)))

    with SessionLocal() as session:
        final_max = session.scalar(
            select(func.max(ReviewVersion.version)).where(ReviewVersion.review_id == review_id)
        )
        current_count = session.scalar(
            select(func.count())
            .select_from(ReviewVersion)
            .where(ReviewVersion.review_id == review_id, ReviewVersion.is_current.is_(True))
        )
        assert final_max == initial_max + 2
        assert current_count == 1
        before_conflict = final_max
        key = f"rollback-{uuid.uuid4()}"
        upsert_review(
            session,
            trip_id=trip_id,
            rider_id=rider_id,
            rating=rating_a,
            idempotency_key=key,
        )
        with pytest.raises(IdempotencyConflict):
            upsert_review(
                session,
                trip_id=trip_id,
                rider_id=rider_id,
                rating=rating_b,
                idempotency_key=key,
            )
        session.rollback()
        after_conflict = session.scalar(
            select(func.max(ReviewVersion.version)).where(ReviewVersion.review_id == review_id)
        )
        assert after_conflict in (before_conflict, before_conflict + 1)
