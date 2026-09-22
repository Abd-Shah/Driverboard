import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from driver_leaderboard.models import (
    IdempotencyRequest,
    ModerationDecision,
    Review,
    Trip,
)
from driver_leaderboard.services.outbox_service import enqueue_contribution_change
from driver_leaderboard.services.review_service import IdempotencyConflict, ReviewNotFound


@dataclass(frozen=True)
class ModerationResult:
    body: dict[str, Any]
    replayed: bool = False


def decision_changes_state(*, currently_excluded: bool, action: str) -> bool:
    return currently_excluded != (action == "exclude")


def _hash_request(
    *,
    review_id: uuid.UUID,
    moderator_id: str,
    action: str,
    reason: str | None,
) -> str:
    payload = json.dumps(
        {
            "review_id": str(review_id),
            "moderator_id": moderator_id,
            "action": action,
            "reason": reason,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def moderate_review(
    session: Session,
    *,
    review_id: uuid.UUID,
    moderator_id: str,
    action: str,
    reason: str | None,
    idempotency_key: str,
) -> ModerationResult:
    request_hash = _hash_request(
        review_id=review_id,
        moderator_id=moderator_id,
        action=action,
        reason=reason,
    )
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(idempotency_key, 0))))
    existing_request = session.get(IdempotencyRequest, idempotency_key)
    if existing_request:
        if existing_request.request_hash != request_hash:
            raise IdempotencyConflict("idempotency key was already used with different content")
        replay_body = dict(existing_request.response_body)
        replay_body["idempotent_replay"] = True
        return ModerationResult(body=replay_body, replayed=True)

    row = session.execute(
        select(Review, Trip)
        .join(Trip, Trip.id == Review.trip_id)
        .where(Review.id == review_id)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise ReviewNotFound("review not found")
    review, trip = row
    desired_excluded = action == "exclude"
    changed_state = decision_changes_state(
        currently_excluded=review.moderation_excluded, action=action
    )
    next_number = (
        session.scalar(
            select(func.max(ModerationDecision.decision_number)).where(
                ModerationDecision.review_id == review.id
            )
        )
        or 0
    ) + 1
    decision = ModerationDecision(
        id=uuid.uuid4(),
        review_id=review.id,
        decision_number=next_number,
        action=action,
        moderator_id=moderator_id,
        reason=reason,
        changed_state=changed_state,
    )
    session.add(decision)
    review.moderation_excluded = desired_excluded
    session.flush()

    if changed_state and review.deleted_at is None:
        enqueue_contribution_change(
            session,
            event_type=f"moderation.{action}",
            city_id=trip.city_id,
            driver_id=trip.driver_id,
            aggregate_id=review.id,
            payload={"review_id": str(review.id), "decision_id": str(decision.id)},
        )

    body: dict[str, Any] = {
        "decision_id": str(decision.id),
        "review_id": str(review.id),
        "decision_number": decision.decision_number,
        "action": action,
        "excluded": desired_excluded,
        "changed_state": changed_state,
        "idempotent_replay": False,
    }
    session.add(
        IdempotencyRequest(
            key=idempotency_key,
            operation="moderate_review",
            request_hash=request_hash,
            response_status=200,
            response_body=body,
        )
    )
    session.commit()
    return ModerationResult(body=body)
