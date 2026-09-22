from driver_leaderboard.services.worker_service import failure_outcome


def test_worker_retries_with_exponential_backoff_then_fails() -> None:
    assert failure_outcome(1) == ("pending", 1)
    assert failure_outcome(2) == ("pending", 2)
    assert failure_outcome(3) == ("pending", 4)
    assert failure_outcome(4) == ("pending", 8)
    assert failure_outcome(5) == ("failed", None)
