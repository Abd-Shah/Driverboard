import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from driver_leaderboard.models import DriverScore
from driver_leaderboard.services.scoring_service import serialize_score


def test_average_is_derived_and_rounded_for_display() -> None:
    calculated_at = datetime(2026, 9, 20, tzinfo=UTC)
    score = DriverScore(
        city_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        rating_sum=93,
        contributing_review_count=22,
        eligible=True,
        window_start=calculated_at - timedelta(days=90),
        calculated_at=calculated_at,
    )

    assert serialize_score(score)["average_rating"] == Decimal("4.2273")
