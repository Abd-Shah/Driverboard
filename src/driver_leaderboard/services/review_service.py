import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from driver_leaderboard.models import IdempotencyRequest, Review, ReviewVersion, Trip
from driver_leaderboard.services.outbox_service import enqueue_contribution_change


class ReviewServiceError(Exception):
    status_code = 400


class TripNotFound(ReviewServiceError):
    status_code = 404


class RiderDoesNotOwnTrip(ReviewServiceError):
    status_code = 403


class ReviewNotFound(ReviewServiceError):
    status_code = 404


class IdempotencyConflict(ReviewServiceError):
    status_code = 409


@dataclass(frozen=True)
class ReviewResult:
    body: dict[str, Any]
    created: bool
    replayed: bool = False


def _request_hash(*, trip_id: uuid.UUID, rider_id: uuid.UUID, rating: int) -> str:
    payload = json.dumps(
        {"trip_id": str(trip_id), "rider_id": str(rider_id), "rating": rating},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _delete_request_hash(*, trip_id: uuid.UUID, rider_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"trip_id": str(trip_id), "rider_id": str(rider_id), "action": "delete"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _lock_idempotency_key(session: Session, key: str) -> None:
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


def upsert_review(
    session: Session,
    *,
    trip_id: uuid.UUID,
    rider_id: uuid.UUID,
    rating: int,
    idempotency_key: str,
) -> ReviewResult:
    request_hash = _request_hash(trip_id=trip_id, rider_id=rider_id, rating=rating)
    # Serialize requests sharing a key before reading its durable result. This prevents
    # concurrent retries from both observing a missing idempotency record.
    _lock_idempotency_key(session, idempotency_key)
    existing_request = session.get(IdempotencyRequest, idempotency_key)
    if existing_request:
        if existing_request.request_hash != request_hash:
            raise IdempotencyConflict("idempotency key was already used with different content")
        replay_body = dict(existing_request.response_body)
        replay_body["idempotent_replay"] = True
        return ReviewResult(
            body=replay_body, created=existing_request.response_status == 201, replayed=True
        )

    trip = session.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one_or_none()
    if trip is None:
        raise TripNotFound("trip not found")
    if trip.rider_id != rider_id:
        raise RiderDoesNotOwnTrip("rider does not own this trip")

    review = session.execute(select(Review).where(Review.trip_id == trip_id)).scalar_one_or_none()
    created = review is None
    if review is None:
        review = Review(id=uuid.uuid4(), trip_id=trip_id)
        session.add(review)
        session.flush()

    current = session.execute(
        select(ReviewVersion)
        .where(ReviewVersion.review_id == review.id, ReviewVersion.is_current.is_(True))
        .with_for_update()
    ).scalar_one_or_none()

    was_deleted = review.deleted_at is not None
    contributed_before = not was_deleted and not review.moderation_excluded
    review.deleted_at = None
    rating_changed = current is None or current.rating != rating
    contributes_after = not review.moderation_excluded
    contribution_changed = contributed_before != contributes_after or (
        rating_changed and contributes_after
    )
    if not rating_changed:
        version = current
    else:
        next_version = 1 if current is None else current.version + 1
        if current is not None:
            current.is_current = False
            session.flush()
        version = ReviewVersion(
            id=uuid.uuid4(),
            review_id=review.id,
            version=next_version,
            rating=rating,
            is_current=True,
        )
        session.add(version)
        session.flush()

    if contribution_changed:
        enqueue_contribution_change(
            session,
            event_type="review.upserted",
            city_id=trip.city_id,
            driver_id=trip.driver_id,
            aggregate_id=review.id,
            payload={"trip_id": str(trip.id), "review_id": str(review.id)},
        )

    body: dict[str, Any] = {
        "review_id": str(review.id),
        "trip_id": str(trip.id),
        "current_version": version.version,
        "rating": version.rating,
        "created_at": version.created_at.isoformat(),
        "idempotent_replay": False,
    }
    status = 201 if created else 200
    session.add(
        IdempotencyRequest(
            key=idempotency_key,
            operation="upsert_review",
            request_hash=request_hash,
            response_status=status,
            response_body=body,
        )
    )
    session.commit()
    return ReviewResult(body=body, created=created)


def delete_review(
    session: Session,
    *,
    trip_id: uuid.UUID,
    rider_id: uuid.UUID,
    idempotency_key: str,
) -> ReviewResult:
    request_hash = _delete_request_hash(trip_id=trip_id, rider_id=rider_id)
    _lock_idempotency_key(session, idempotency_key)
    existing_request = session.get(IdempotencyRequest, idempotency_key)
    if existing_request:
        if existing_request.request_hash != request_hash:
            raise IdempotencyConflict("idempotency key was already used with different content")
        replay_body = dict(existing_request.response_body)
        replay_body["idempotent_replay"] = True
        return ReviewResult(body=replay_body, created=False, replayed=True)

    trip = session.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one_or_none()
    if trip is None:
        raise TripNotFound("trip not found")
    if trip.rider_id != rider_id:
        raise RiderDoesNotOwnTrip("rider does not own this trip")
    review = session.execute(
        select(Review).where(Review.trip_id == trip_id).with_for_update()
    ).scalar_one_or_none()
    if review is None:
        raise ReviewNotFound("review not found")

    changed_state = review.deleted_at is None
    if changed_state:
        review.deleted_at = datetime.now(UTC)
        session.flush()
    if changed_state and not review.moderation_excluded:
        enqueue_contribution_change(
            session,
            event_type="review.deleted",
            city_id=trip.city_id,
            driver_id=trip.driver_id,
            aggregate_id=review.id,
            payload={"trip_id": str(trip.id), "review_id": str(review.id)},
        )

    body: dict[str, Any] = {
        "review_id": str(review.id),
        "trip_id": str(trip.id),
        "deleted": True,
        "changed_state": changed_state,
        "idempotent_replay": False,
    }
    session.add(
        IdempotencyRequest(
            key=idempotency_key,
            operation="delete_review",
            request_hash=request_hash,
            response_status=200,
            response_body=body,
        )
    )
    session.commit()
    return ReviewResult(body=body, created=False)


def get_current_review(session: Session, *, trip_id: uuid.UUID) -> dict[str, Any]:
    row = session.execute(
        select(Review, ReviewVersion)
        .join(ReviewVersion, ReviewVersion.review_id == Review.id)
        .where(
            Review.trip_id == trip_id,
            Review.deleted_at.is_(None),
            ReviewVersion.is_current.is_(True),
        )
    ).one_or_none()
    if row is None:
        raise ReviewNotFound("review not found")
    review, version = row
    return {
        "review_id": str(review.id),
        "trip_id": str(trip_id),
        "current_version": version.version,
        "rating": version.rating,
        "created_at": version.created_at.isoformat(),
        "idempotent_replay": False,
    }
