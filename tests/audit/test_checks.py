from tools.audit.checks import CHECKS


def test_baseline_audit_contains_authoritative_invariants() -> None:
    assert set(CHECKS) == {
        "one_current_version_per_review",
        "rating_in_range",
        "trip_city_matches_driver_city",
        "review_has_version",
        "exactly_one_current_version_per_review",
        "versions_are_sequential",
        "current_version_is_latest",
        "idempotency_result_review_exists",
        "every_driver_has_score",
        "score_city_matches_driver_city",
        "score_window_is_90_days",
        "score_eligibility_matches_count",
        "score_matches_authoritative_reviews",
        "one_published_generation_per_city",
        "generation_versions_are_sequential",
        "published_ranks_are_contiguous",
        "published_leaderboard_matches_scores",
        "published_generation_has_freshness",
        "moderation_decisions_are_sequential",
        "moderation_state_matches_latest_decision",
        "moderation_changed_state_is_correct",
        "moderation_idempotency_result_exists",
        "deletion_idempotency_result_exists",
        "at_most_one_active_rebuild_per_city",
        "rebuild_candidate_scores_match_authoritative",
        "rebuild_generation_state_matches_job",
        "published_rebuild_has_successful_comparison",
        "completed_expiration_has_valid_publication",
        "scores_cover_latest_expiration",
        "expiration_generation_belongs_to_city",
        "completed_outbox_event_has_ledger",
        "processed_ledger_event_is_completed",
        "failed_outbox_event_exhausted_retries",
        "completed_outbox_event_has_processing_time",
    }


def test_audit_queries_are_read_only() -> None:
    assert all(query.lstrip().upper().startswith(("SELECT", "WITH")) for query in CHECKS.values())
