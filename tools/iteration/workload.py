from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from driver_leaderboard.models import Review, ReviewVersion, Trip
from driver_leaderboard.services.moderation_service import moderate_review
from driver_leaderboard.services.review_service import (
    IdempotencyConflict,
    delete_review,
    upsert_review,
)


@dataclass
class WorkloadMetrics:
    initial_submissions: int = 0
    corrections: int = 0
    idempotent_replays: int = 0
    rejected_conflicts: int = 0
    deletions: int = 0
    deletion_replays: int = 0
    moderation_exclusions: int = 0
    moderation_restorations: int = 0
    moderation_replays: int = 0


def run_review_workload(session: Session) -> dict[str, int]:
    metrics = WorkloadMetrics()
    unrated = (
        session.execute(
            select(Trip)
            .outerjoin(Review, Review.trip_id == Trip.id)
            .where(Review.id.is_(None))
            .order_by(Trip.stable_id)
        )
        .scalars()
        .all()
    )
    rated = (
        session.execute(
            select(Trip).join(Review, Review.trip_id == Trip.id).order_by(Trip.stable_id).limit(10)
        )
        .scalars()
        .all()
    )

    for index, trip in enumerate(unrated):
        key = f"iteration-002-initial-{index}"
        result = upsert_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            rating=5,
            idempotency_key=key,
        )
        metrics.initial_submissions += int(result.created)
        replay = upsert_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            rating=5,
            idempotency_key=key,
        )
        metrics.idempotent_replays += int(replay.replayed)

    for index, trip in enumerate(rated):
        current_rating = session.execute(
            select(ReviewVersion.rating)
            .join(Review, Review.id == ReviewVersion.review_id)
            .where(Review.trip_id == trip.id, ReviewVersion.is_current.is_(True))
        ).scalar_one()
        new_rating = 4 if current_rating == 5 else 5
        key = f"iteration-002-correction-{index}"
        result = upsert_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            rating=new_rating,
            idempotency_key=key,
        )
        metrics.corrections += int(not result.created)
        replay = upsert_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            rating=new_rating,
            idempotency_key=key,
        )
        metrics.idempotent_replays += int(replay.replayed)
        try:
            upsert_review(
                session,
                trip_id=trip.id,
                rider_id=trip.rider_id,
                rating=1,
                idempotency_key=key,
            )
        except IdempotencyConflict:
            session.rollback()
            metrics.rejected_conflicts += 1

    moderation_targets = session.execute(
        select(Review, Trip).join(Trip, Trip.id == Review.trip_id).order_by(Trip.stable_id).limit(5)
    ).all()
    for index, (review, trip) in enumerate(moderation_targets[:2]):
        key = f"iteration-005-delete-{index}"
        deleted = delete_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            idempotency_key=key,
        )
        metrics.deletions += int(deleted.body["changed_state"])
        replay = delete_review(
            session,
            trip_id=trip.id,
            rider_id=trip.rider_id,
            idempotency_key=key,
        )
        metrics.deletion_replays += int(replay.replayed)

    for index, (review, _) in enumerate(moderation_targets[2:]):
        exclude_key = f"iteration-005-exclude-{index}"
        excluded = moderate_review(
            session,
            review_id=review.id,
            moderator_id="moderator_iteration",
            action="exclude",
            reason="iteration workload",
            idempotency_key=exclude_key,
        )
        metrics.moderation_exclusions += int(excluded.body["changed_state"])
        replay = moderate_review(
            session,
            review_id=review.id,
            moderator_id="moderator_iteration",
            action="exclude",
            reason="iteration workload",
            idempotency_key=exclude_key,
        )
        metrics.moderation_replays += int(replay.replayed)
        if index < 2:
            restored = moderate_review(
                session,
                review_id=review.id,
                moderator_id="moderator_iteration",
                action="restore",
                reason="iteration workload restore",
                idempotency_key=f"iteration-005-restore-{index}",
            )
            metrics.moderation_restorations += int(restored.body["changed_state"])

    return asdict(metrics)
