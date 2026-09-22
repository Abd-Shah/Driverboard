import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from driver_leaderboard.models import ExpirationRun, OutboxEvent, ProcessedOutboxEvent
from driver_leaderboard.services.leaderboard_service import build_and_publish_generation
from driver_leaderboard.services.scoring_service import recalculate_driver_score

MAX_ATTEMPTS = 5


class WorkerBatchError(Exception):
    def __init__(self, event_ids: list[uuid.UUID], cause: Exception):
        self.event_ids = event_ids
        self.cause = cause
        super().__init__(str(cause))


@dataclass
class WorkerBatchResult:
    events_processed: int = 0
    drivers_recalculated: int = 0
    generations_published: int = 0
    published_city_ids: list[str] | None = None


def failure_outcome(attempts_after_failure: int) -> tuple[str, int | None]:
    if attempts_after_failure >= MAX_ATTEMPTS:
        return "failed", None
    return "pending", 2 ** (attempts_after_failure - 1)


def process_batch(
    session: Session,
    *,
    limit: int = 100,
    processed_at: datetime | None = None,
    fail_after_claim: bool = False,
) -> WorkerBatchResult:
    available_at = processed_at or datetime.now(UTC)
    events = session.scalars(
        select(OutboxEvent)
        .where(
            OutboxEvent.status == "pending",
            OutboxEvent.next_attempt_at <= available_at,
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    if not events:
        return WorkerBatchResult()
    if processed_at is None:
        latest_expiration = session.scalar(
            select(func.max(ExpirationRun.effective_at)).where(
                ExpirationRun.city_id.in_({event.city_id for event in events})
            )
        )
        processed_at = max(available_at, latest_expiration or available_at)
    event_ids = [event.id for event in events]
    try:
        for event in events:
            event.status = "processing"
            event.attempts += 1
        session.flush()
        if fail_after_claim:
            raise RuntimeError("injected worker failure")

        city_drivers: dict[uuid.UUID, set[uuid.UUID]] = {}
        for event in events:
            if session.get(ProcessedOutboxEvent, event.id) is None:
                city_drivers.setdefault(event.city_id, set()).add(event.driver_id)
        recalculated = 0
        published = 0
        for city_id, driver_ids in city_drivers.items():
            for driver_id in driver_ids:
                recalculate_driver_score(
                    session,
                    city_id=city_id,
                    driver_id=driver_id,
                    calculated_at=processed_at,
                )
                recalculated += 1
            build_and_publish_generation(session, city_id=city_id, published_at=processed_at)
            published += 1
        for event in events:
            if session.get(ProcessedOutboxEvent, event.id) is None:
                session.add(ProcessedOutboxEvent(event_id=event.id, processed_at=processed_at))
            event.status = "completed"
            event.processed_at = processed_at
            event.last_error = None
        session.commit()
    except Exception as exc:
        session.rollback()
        raise WorkerBatchError(event_ids, exc) from exc
    result = WorkerBatchResult(
        events_processed=len(events),
        drivers_recalculated=recalculated,
        generations_published=published,
        published_city_ids=[str(city_id) for city_id in city_drivers],
    )
    from driver_leaderboard.services.cache_service import refresh_city_cache

    for city_id in city_drivers:
        refresh_city_cache(session, city_id=city_id)
    return result


def record_batch_failure(
    session: Session,
    *,
    event_ids: list[uuid.UUID],
    error: str,
    failed_at: datetime | None = None,
) -> None:
    failed_at = failed_at or datetime.now(UTC)
    events = session.scalars(
        select(OutboxEvent).where(OutboxEvent.id.in_(event_ids)).with_for_update()
    ).all()
    for event in events:
        event.attempts += 1
        event.last_error = error[:1000]
        status, delay = failure_outcome(event.attempts)
        event.status = status
        if delay is not None:
            event.next_attempt_at = failed_at + timedelta(seconds=delay)
    session.commit()


def drain_outbox(session_factory, *, batch_size: int = 100) -> WorkerBatchResult:
    total = WorkerBatchResult(published_city_ids=[])
    while True:
        with session_factory() as session:
            result = process_batch(session, limit=batch_size)
        if result.events_processed == 0:
            total.published_city_ids = sorted(set(total.published_city_ids or []))
            return total
        total.events_processed += result.events_processed
        total.drivers_recalculated += result.drivers_recalculated
        total.generations_published += result.generations_published
        total.published_city_ids.extend(result.published_city_ids or [])


def outbox_metrics(session: Session) -> dict[str, float | int | None]:
    now = datetime.now(UTC)
    pending = int(
        session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "pending")
        )
        or 0
    )
    oldest = session.scalar(
        select(func.min(OutboxEvent.created_at)).where(OutboxEvent.status == "pending")
    )
    return {
        "pending_events": pending,
        "processing_events": int(
            session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.status == "processing")
            )
            or 0
        ),
        "completed_events": int(
            session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.status == "completed")
            )
            or 0
        ),
        "failed_events": int(
            session.scalar(
                select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "failed")
            )
            or 0
        ),
        "oldest_pending_age_seconds": (
            round((now - oldest).total_seconds(), 3) if oldest is not None else None
        ),
    }


def serialize_batch(result: WorkerBatchResult) -> dict[str, object]:
    return asdict(result)
