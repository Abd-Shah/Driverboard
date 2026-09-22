import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from driver_leaderboard.models import City, Driver, DriverScore, ExpirationRun
from driver_leaderboard.services.leaderboard_service import build_and_publish_generation
from driver_leaderboard.services.scoring_service import recalculate_driver_score


def run_city_expiration(
    session: Session, *, city_id: uuid.UUID, effective_at: datetime | None = None
) -> ExpirationRun:
    effective_at = effective_at or datetime.now(UTC)
    existing = session.execute(
        select(ExpirationRun).where(
            ExpirationRun.city_id == city_id,
            ExpirationRun.effective_at == effective_at,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    session.execute(select(City).where(City.id == city_id).with_for_update()).scalar_one()
    expiration = ExpirationRun(
        id=uuid.uuid4(),
        city_id=city_id,
        effective_at=effective_at,
        status="running",
        affected_drivers=0,
    )
    session.add(expiration)
    session.flush()
    driver_ids = session.scalars(
        select(Driver.id).where(Driver.city_id == city_id).order_by(Driver.stable_id)
    ).all()
    affected = 0
    for driver_id in driver_ids:
        previous = session.get(DriverScore, (city_id, driver_id))
        previous_values = (
            (
                previous.rating_sum,
                previous.contributing_review_count,
                previous.eligible,
            )
            if previous
            else None
        )
        updated = recalculate_driver_score(
            session,
            city_id=city_id,
            driver_id=driver_id,
            calculated_at=effective_at,
        )
        current_values = (
            updated.rating_sum,
            updated.contributing_review_count,
            updated.eligible,
        )
        affected += int(previous_values != current_values)
    if affected:
        generation = build_and_publish_generation(
            session, city_id=city_id, published_at=effective_at
        )
        expiration.published_generation_id = generation.id
    expiration.affected_drivers = affected
    expiration.status = "completed"
    expiration.completed_at = datetime.now(UTC)
    session.commit()
    if affected:
        from driver_leaderboard.services.cache_service import refresh_city_cache

        refresh_city_cache(session, city_id=city_id)
    return expiration


def serialize_expiration(run: ExpirationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "city_id": str(run.city_id),
        "effective_at": run.effective_at,
        "status": run.status,
        "affected_drivers": run.affected_drivers,
        "published_generation_id": (
            str(run.published_generation_id) if run.published_generation_id else None
        ),
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
