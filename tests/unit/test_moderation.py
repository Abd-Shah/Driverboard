from driver_leaderboard.services.moderation_service import decision_changes_state


def test_moderation_changes_only_when_requested_state_differs() -> None:
    assert decision_changes_state(currently_excluded=False, action="exclude") is True
    assert decision_changes_state(currently_excluded=True, action="exclude") is False
    assert decision_changes_state(currently_excluded=True, action="restore") is True
    assert decision_changes_state(currently_excluded=False, action="restore") is False
