import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from driver_leaderboard.models import OutboxEvent


def enqueue_contribution_change(
    session: Session,
    *,
    event_type: str,
    city_id: uuid.UUID,
    driver_id: uuid.UUID,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
) -> OutboxEvent:
    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        city_id=city_id,
        driver_id=driver_id,
        aggregate_id=aggregate_id,
        payload=payload,
        status="pending",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    return event
