from driver_leaderboard.services.leaderboard_service import LEADERBOARD_LIMIT


def test_leaderboard_is_limited_to_top_one_hundred() -> None:
    assert LEADERBOARD_LIMIT == 100
