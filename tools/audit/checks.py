from dataclasses import asdict, dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    violations: int


CHECKS = {
    "one_current_version_per_review": """
        SELECT count(*) FROM (
          SELECT review_id FROM review_versions WHERE is_current
          GROUP BY review_id HAVING count(*) > 1
        ) violations
    """,
    "rating_in_range": "SELECT count(*) FROM review_versions WHERE rating NOT BETWEEN 1 AND 5",
    "trip_city_matches_driver_city": """
        SELECT count(*) FROM trips t JOIN drivers d ON d.id = t.driver_id
        WHERE t.city_id <> d.city_id
    """,
    "review_has_version": """
        SELECT count(*) FROM reviews r LEFT JOIN review_versions rv ON rv.review_id = r.id
        WHERE rv.id IS NULL
    """,
    "exactly_one_current_version_per_review": """
        SELECT count(*) FROM (
          SELECT r.id FROM reviews r LEFT JOIN review_versions rv
            ON rv.review_id = r.id AND rv.is_current
          GROUP BY r.id HAVING count(rv.id) <> 1
        ) violations
    """,
    "versions_are_sequential": """
        SELECT count(*) FROM (
          SELECT review_id FROM review_versions GROUP BY review_id
          HAVING min(version) <> 1 OR max(version) <> count(*)
        ) violations
    """,
    "current_version_is_latest": """
        SELECT count(*) FROM review_versions current_version
        WHERE current_version.is_current AND current_version.version < (
          SELECT max(candidate.version) FROM review_versions candidate
          WHERE candidate.review_id = current_version.review_id
        )
    """,
    "idempotency_result_review_exists": """
        SELECT count(*) FROM idempotency_requests ir
        LEFT JOIN reviews r ON r.id = (ir.response_body->>'review_id')::uuid
        WHERE ir.operation = 'upsert_review' AND r.id IS NULL
    """,
    "every_driver_has_score": """
        SELECT count(*) FROM drivers d
        LEFT JOIN driver_scores ds ON ds.driver_id = d.id AND ds.city_id = d.city_id
        WHERE ds.driver_id IS NULL
    """,
    "score_city_matches_driver_city": """
        SELECT count(*) FROM driver_scores ds
        JOIN drivers d ON d.id = ds.driver_id
        WHERE ds.city_id <> d.city_id
    """,
    "score_window_is_90_days": """
        SELECT count(*) FROM driver_scores
        WHERE calculated_at - window_start <> interval '90 days'
    """,
    "score_eligibility_matches_count": """
        SELECT count(*) FROM driver_scores
        WHERE eligible <> (contributing_review_count >= 20)
    """,
    "score_matches_authoritative_reviews": """
        SELECT count(*) FROM driver_scores ds
        LEFT JOIN LATERAL (
          SELECT coalesce(sum(rv.rating), 0)::bigint AS rating_sum,
                 count(rv.id)::bigint AS review_count
          FROM trips t
          JOIN reviews r ON r.trip_id = t.id
          JOIN review_versions rv ON rv.review_id = r.id AND rv.is_current
          WHERE t.city_id = ds.city_id
            AND t.driver_id = ds.driver_id
            AND t.completed_at >= ds.window_start
            AND t.completed_at <= ds.calculated_at
            AND r.deleted_at IS NULL
            AND NOT r.moderation_excluded
        ) authoritative ON true
        WHERE ds.rating_sum <> authoritative.rating_sum
           OR ds.contributing_review_count <> authoritative.review_count
    """,
    "one_published_generation_per_city": """
        SELECT count(*) FROM (
          SELECT c.id FROM cities c
          LEFT JOIN leaderboard_generations lg
            ON lg.city_id = c.id AND lg.status = 'published'
          GROUP BY c.id HAVING count(lg.id) <> 1
        ) violations
    """,
    "generation_versions_are_sequential": """
        SELECT count(*) FROM (
          SELECT city_id FROM leaderboard_generations GROUP BY city_id
          HAVING min(version) <> 1 OR max(version) <> count(*)
        ) violations
    """,
    "published_ranks_are_contiguous": """
        SELECT count(*) FROM leaderboard_generations lg
        LEFT JOIN LATERAL (
          SELECT count(*) AS entry_count, min(rank) AS min_rank, max(rank) AS max_rank
          FROM leaderboard_entries le WHERE le.generation_id = lg.id
        ) entries ON true
        WHERE lg.status = 'published'
          AND entries.entry_count > 0
          AND (entries.min_rank <> 1 OR entries.max_rank <> entries.entry_count)
    """,
    "published_leaderboard_matches_scores": """
        WITH expected AS (
          SELECT ds.city_id, ds.driver_id, ds.rating_sum,
                 ds.contributing_review_count,
                 row_number() OVER (
                   PARTITION BY ds.city_id
                   ORDER BY ds.rating_sum::numeric / ds.contributing_review_count DESC,
                            ds.contributing_review_count DESC,
                            d.stable_id ASC
                 ) AS expected_rank
          FROM driver_scores ds
          JOIN drivers d ON d.id = ds.driver_id
          WHERE ds.eligible
        ), published AS (
          SELECT lg.city_id, le.driver_id, le.rating_sum,
                 le.contributing_review_count, le.rank
          FROM leaderboard_generations lg
          JOIN leaderboard_entries le ON le.generation_id = lg.id
          WHERE lg.status = 'published'
        )
        SELECT count(*) FROM (
          SELECT coalesce(e.city_id, p.city_id), coalesce(e.driver_id, p.driver_id)
          FROM (SELECT * FROM expected WHERE expected_rank <= 100) e
          FULL OUTER JOIN published p
            ON p.city_id = e.city_id AND p.driver_id = e.driver_id
          WHERE e.driver_id IS NULL OR p.driver_id IS NULL
             OR p.rank <> e.expected_rank
             OR p.rating_sum <> e.rating_sum
             OR p.contributing_review_count <> e.contributing_review_count
        ) violations
    """,
    "published_generation_has_freshness": """
        SELECT count(*) FROM leaderboard_generations
        WHERE status = 'published'
          AND (published_at IS NULL OR source_scores_calculated_at IS NULL)
    """,
    "moderation_decisions_are_sequential": """
        SELECT count(*) FROM (
          SELECT review_id FROM moderation_decisions GROUP BY review_id
          HAVING min(decision_number) <> 1 OR max(decision_number) <> count(*)
        ) violations
    """,
    "moderation_state_matches_latest_decision": """
        SELECT count(*) FROM reviews r
        LEFT JOIN LATERAL (
          SELECT action FROM moderation_decisions md
          WHERE md.review_id = r.id ORDER BY decision_number DESC LIMIT 1
        ) latest ON true
        WHERE r.moderation_excluded <> coalesce(latest.action = 'exclude', false)
    """,
    "moderation_changed_state_is_correct": """
        WITH ordered AS (
          SELECT changed_state, action,
                 lag(action) OVER (
                   PARTITION BY review_id ORDER BY decision_number
                 ) AS prior_action
          FROM moderation_decisions
        )
        SELECT count(*) FROM ordered
        WHERE changed_state <> (
          (action = 'exclude') <> coalesce(prior_action = 'exclude', false)
        )
    """,
    "moderation_idempotency_result_exists": """
        SELECT count(*) FROM idempotency_requests ir
        LEFT JOIN moderation_decisions md
          ON md.id = (ir.response_body->>'decision_id')::uuid
        WHERE ir.operation = 'moderate_review' AND md.id IS NULL
    """,
    "deletion_idempotency_result_exists": """
        SELECT count(*) FROM idempotency_requests ir
        LEFT JOIN reviews r ON r.id = (ir.response_body->>'review_id')::uuid
        WHERE ir.operation = 'delete_review' AND r.id IS NULL
    """,
    "at_most_one_active_rebuild_per_city": """
        SELECT count(*) FROM (
          SELECT city_id FROM rebuild_jobs WHERE status IN ('running', 'ready')
          GROUP BY city_id HAVING count(*) > 1
        ) violations
    """,
    "rebuild_candidate_scores_match_authoritative": """
        SELECT count(*) FROM rebuild_candidate_scores cs
        JOIN rebuild_jobs rj ON rj.id = cs.rebuild_id
        LEFT JOIN LATERAL (
          SELECT coalesce(sum(rv.rating), 0)::bigint AS rating_sum,
                 count(rv.id)::bigint AS review_count
          FROM trips t
          JOIN reviews r ON r.trip_id = t.id
          JOIN review_versions rv ON rv.review_id = r.id AND rv.is_current
          WHERE t.city_id = cs.city_id
            AND t.driver_id = cs.driver_id
            AND t.completed_at >= rj.calculated_at - interval '90 days'
            AND t.completed_at <= rj.calculated_at
            AND r.deleted_at IS NULL
            AND NOT r.moderation_excluded
        ) authoritative ON true
        WHERE rj.status = 'ready'
          AND (cs.rating_sum <> authoritative.rating_sum
           OR cs.contributing_review_count <> authoritative.review_count
           OR cs.eligible <> (authoritative.review_count >= 20))
    """,
    "rebuild_generation_state_matches_job": """
        SELECT count(*) FROM rebuild_jobs rj
        JOIN leaderboard_generations lg ON lg.id = rj.candidate_generation_id
        WHERE (rj.status = 'ready' AND lg.status <> 'candidate')
           OR (rj.status = 'published' AND lg.status NOT IN ('published', 'superseded'))
           OR (rj.status = 'discarded' AND lg.status <> 'discarded')
    """,
    "published_rebuild_has_successful_comparison": """
        SELECT count(*) FROM rebuild_jobs
        WHERE status = 'published'
          AND coalesce((comparison_summary->>'audit_passed')::boolean, false) = false
    """,
    "completed_expiration_has_valid_publication": """
        SELECT count(*) FROM expiration_runs
        WHERE status = 'completed'
          AND (
            (affected_drivers > 0 AND published_generation_id IS NULL)
            OR (affected_drivers = 0 AND published_generation_id IS NOT NULL)
          )
    """,
    "scores_cover_latest_expiration": """
        SELECT count(*) FROM driver_scores ds
        JOIN (
          SELECT city_id, max(effective_at) AS effective_at
          FROM expiration_runs WHERE status = 'completed' GROUP BY city_id
        ) latest ON latest.city_id = ds.city_id
        WHERE ds.calculated_at < latest.effective_at
    """,
    "expiration_generation_belongs_to_city": """
        SELECT count(*) FROM expiration_runs er
        JOIN leaderboard_generations lg ON lg.id = er.published_generation_id
        WHERE er.city_id <> lg.city_id
    """,
    "completed_outbox_event_has_ledger": """
        SELECT count(*) FROM outbox_events oe
        LEFT JOIN processed_outbox_events pe ON pe.event_id = oe.id
        WHERE oe.status = 'completed' AND pe.event_id IS NULL
    """,
    "processed_ledger_event_is_completed": """
        SELECT count(*) FROM processed_outbox_events pe
        JOIN outbox_events oe ON oe.id = pe.event_id
        WHERE oe.status <> 'completed'
    """,
    "failed_outbox_event_exhausted_retries": """
        SELECT count(*) FROM outbox_events
        WHERE status = 'failed' AND attempts < 5
    """,
    "completed_outbox_event_has_processing_time": """
        SELECT count(*) FROM outbox_events
        WHERE status = 'completed' AND processed_at IS NULL
    """,
}


def run_checks(session: Session) -> list[CheckResult]:
    results = []
    for name, query in CHECKS.items():
        violations = int(session.execute(text(query)).scalar_one())
        results.append(CheckResult(name=name, passed=violations == 0, violations=violations))
    return results


def serialize(results: list[CheckResult]) -> list[dict[str, object]]:
    return [asdict(result) for result in results]
