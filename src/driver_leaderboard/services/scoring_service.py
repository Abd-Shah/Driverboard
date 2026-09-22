import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from driver_leaderboard.models import Driver, DriverScore, Review, ReviewVersion, Trip

WINDOW_DAYS = 90
ELIGIBILITY_REVIEW_COUNT = 20


class ScoreNotFound(Exception):
    pass


def is_eligible(review_count: int) -> bool:
    return review_count >= ELIGIBILITY_REVIEW_COUNT


def is_trip_in_window(*, completed_at: datetime, calculated_at: datetime) -> bool:
    return calculated_at - timedelta(days=WINDOW_DAYS) <= completed_at <= calculated_at


def _aggregate(
    session: Session,
    *,
    city_id: uuid.UUID,
    driver_id: uuid.UUID,
    window_start: datetime,
    calculated_at: datetime,
) -> tuple[int, int]:
    rating_sum, count = session.execute(
        select(func.coalesce(func.sum(ReviewVersion.rating), 0), func.count(ReviewVersion.id))
        .select_from(Trip)
        .join(Review, Review.trip_id == Trip.id)
        .join(
            ReviewVersion,
            (ReviewVersion.review_id == Review.id) & ReviewVersion.is_current.is_(True),
        )
        .where(
            Trip.city_id == city_id,
            Trip.driver_id == driver_id,
            Trip.completed_at >= window_start,
            Trip.completed_at <= calculated_at,
            Review.deleted_at.is_(None),
            Review.moderation_excluded.is_(False),
        )
    ).one()
    return int(rating_sum), int(count)


def recalculate_driver_score(
    session: Session,
    *,
    city_id: uuid.UUID,
    driver_id: uuid.UUID,
    calculated_at: datetime | None = None,
) -> DriverScore:
    calculated_at = calculated_at or datetime.now(UTC)
    window_start = calculated_at - timedelta(days=WINDOW_DAYS)
    rating_sum, count = _aggregate(
        session,
        city_id=city_id,
        driver_id=driver_id,
        window_start=window_start,
        calculated_at=calculated_at,
    )
    score = session.get(DriverScore, (city_id, driver_id))
    if score is None:
        score = DriverScore(city_id=city_id, driver_id=driver_id)
        session.add(score)
    score.rating_sum = rating_sum
    score.contributing_review_count = count
    score.eligible = is_eligible(count)
    score.window_start = window_start
    score.calculated_at = calculated_at
    session.flush()
    return score


def rebuild_city_scores(
    session: Session, *, city_id: uuid.UUID, calculated_at: datetime | None = None
) -> dict[str, int]:
    calculated_at = calculated_at or datetime.now(UTC)
    driver_ids = session.scalars(
        select(Driver.id).where(Driver.city_id == city_id).order_by(Driver.stable_id)
    ).all()
    session.execute(delete(DriverScore).where(DriverScore.city_id == city_id))
    session.flush()
    eligible = 0
    contributing_reviews = 0
    for driver_id in driver_ids:
        score = recalculate_driver_score(
            session,
            city_id=city_id,
            driver_id=driver_id,
            calculated_at=calculated_at,
        )
        eligible += int(score.eligible)
        contributing_reviews += score.contributing_review_count
    total_current_reviews = int(
        session.scalar(
            select(func.count(ReviewVersion.id))
            .select_from(Trip)
            .join(Review, Review.trip_id == Trip.id)
            .join(
                ReviewVersion,
                (ReviewVersion.review_id == Review.id) & ReviewVersion.is_current.is_(True),
            )
            .where(Trip.city_id == city_id)
            .where(Review.deleted_at.is_(None), Review.moderation_excluded.is_(False))
        )
        or 0
    )
    session.commit()
    return {
        "drivers_scored": len(driver_ids),
        "eligible_drivers": eligible,
        "ineligible_drivers": len(driver_ids) - eligible,
        "contributing_reviews": contributing_reviews,
        "outside_window_reviews": total_current_reviews - contributing_reviews,
    }


def serialize_score(score: DriverScore) -> dict[str, Any]:
    average = None
    if score.contributing_review_count:
        average = (Decimal(score.rating_sum) / Decimal(score.contributing_review_count)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    return {
        "city_id": str(score.city_id),
        "driver_id": str(score.driver_id),
        "rating_sum": score.rating_sum,
        "contributing_review_count": score.contributing_review_count,
        "average_rating": average,
        "eligible": score.eligible,
        "window_start": score.window_start,
        "calculated_at": score.calculated_at,
    }


def get_driver_score(session: Session, *, city_id: uuid.UUID, driver_id: uuid.UUID) -> DriverScore:
    score = session.get(DriverScore, (city_id, driver_id))
    if score is None:
        raise ScoreNotFound("driver score not found")
    return score
