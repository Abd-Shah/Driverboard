from datetime import UTC, datetime, timedelta

from driver_leaderboard.services.scoring_service import is_eligible, is_trip_in_window


def test_driver_becomes_eligible_at_twenty_reviews() -> None:
    assert is_eligible(19) is False
    assert is_eligible(20) is True
    assert is_eligible(21) is True


def test_rolling_window_includes_exact_boundary() -> None:
    calculated_at = datetime(2026, 9, 20, 12, tzinfo=UTC)
    assert is_trip_in_window(
        completed_at=calculated_at - timedelta(days=90), calculated_at=calculated_at
    )
    assert not is_trip_in_window(
        completed_at=calculated_at - timedelta(days=90, microseconds=1),
        calculated_at=calculated_at,
    )
    assert not is_trip_in_window(
        completed_at=calculated_at + timedelta(microseconds=1), calculated_at=calculated_at
    )
