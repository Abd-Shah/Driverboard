import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Numeric, cast, func, select, update
from sqlalchemy.orm import Session

from driver_leaderboard.models import (
    City,
    Driver,
    DriverScore,
    LeaderboardEntry,
    LeaderboardGeneration,
)

LEADERBOARD_LIMIT = 100


class LeaderboardNotFound(Exception):
    pass


def build_and_publish_generation(
    session: Session, *, city_id: uuid.UUID, published_at: datetime | None = None
) -> LeaderboardGeneration:
    published_at = published_at or datetime.now(UTC)
    city = session.execute(select(City).where(City.id == city_id).with_for_update()).scalar_one()
    current_max = session.scalar(
        select(func.max(LeaderboardGeneration.version)).where(
            LeaderboardGeneration.city_id == city.id
        )
    )
    generation = LeaderboardGeneration(
        id=uuid.uuid4(),
        city_id=city.id,
        version=(current_max or 0) + 1,
        status="building",
        source_scores_calculated_at=session.scalar(
            select(func.max(DriverScore.calculated_at)).where(DriverScore.city_id == city.id)
        ),
    )
    session.add(generation)
    session.flush()

    average = cast(DriverScore.rating_sum, Numeric) / DriverScore.contributing_review_count
    ranked = session.execute(
        select(DriverScore, Driver.stable_id)
        .join(Driver, Driver.id == DriverScore.driver_id)
        .where(DriverScore.city_id == city.id, DriverScore.eligible.is_(True))
        .order_by(
            average.desc(),
            DriverScore.contributing_review_count.desc(),
            Driver.stable_id.asc(),
        )
        .limit(LEADERBOARD_LIMIT)
    ).all()
    for rank, (score, _) in enumerate(ranked, start=1):
        session.add(
            LeaderboardEntry(
                generation_id=generation.id,
                rank=rank,
                driver_id=score.driver_id,
                rating_sum=score.rating_sum,
                contributing_review_count=score.contributing_review_count,
            )
        )
    session.flush()

    session.execute(
        update(LeaderboardGeneration)
        .where(
            LeaderboardGeneration.city_id == city.id,
            LeaderboardGeneration.status == "published",
        )
        .values(status="superseded")
    )
    session.flush()
    generation.status = "published"
    generation.published_at = published_at
    session.flush()
    return generation


def get_published_leaderboard(session: Session, *, city_id: uuid.UUID) -> dict[str, Any]:
    generation = session.execute(
        select(LeaderboardGeneration).where(
            LeaderboardGeneration.city_id == city_id,
            LeaderboardGeneration.status == "published",
        )
    ).scalar_one_or_none()
    if generation is None:
        raise LeaderboardNotFound("published leaderboard not found")
    rows = session.execute(
        select(LeaderboardEntry, Driver.stable_id)
        .join(Driver, Driver.id == LeaderboardEntry.driver_id)
        .where(LeaderboardEntry.generation_id == generation.id)
        .order_by(LeaderboardEntry.rank)
    ).all()
    entries = []
    for entry, stable_id in rows:
        average = (Decimal(entry.rating_sum) / Decimal(entry.contributing_review_count)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        entries.append(
            {
                "rank": entry.rank,
                "driver_id": str(entry.driver_id),
                "stable_driver_id": stable_id,
                "average_rating": average,
                "contributing_review_count": entry.contributing_review_count,
            }
        )
    return {
        "city_id": str(generation.city_id),
        "generation_id": str(generation.id),
        "version": generation.version,
        "generated_at": generation.created_at,
        "published_at": generation.published_at,
        "source_scores_calculated_at": generation.source_scores_calculated_at,
        "entry_count": len(entries),
        "entries": entries,
    }
