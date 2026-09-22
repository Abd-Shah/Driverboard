import argparse
import json
import time
from pathlib import Path

from sqlalchemy import select, text

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.models import City, Driver
from driver_leaderboard.services.leaderboard_service import get_published_leaderboard
from driver_leaderboard.services.scoring_service import get_driver_score, serialize_score


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * percentile) - 1))
    return round(ordered[index], 3)


def _latencies(session, city_ids, driver_pairs, reads: int) -> dict[str, float]:
    leaderboard_times = []
    score_times = []
    for index in range(reads):
        city_id = city_ids[index % len(city_ids)]
        started = time.perf_counter()
        get_published_leaderboard(session, city_id=city_id)
        leaderboard_times.append((time.perf_counter() - started) * 1000)

        score_city_id, driver_id = driver_pairs[index % len(driver_pairs)]
        started = time.perf_counter()
        serialize_score(get_driver_score(session, city_id=score_city_id, driver_id=driver_id))
        score_times.append((time.perf_counter() - started) * 1000)
    return {
        "leaderboard_read_p50_ms": _percentile(leaderboard_times, 0.50),
        "leaderboard_read_p95_ms": _percentile(leaderboard_times, 0.95),
        "score_read_p50_ms": _percentile(score_times, 0.50),
        "score_read_p95_ms": _percentile(score_times, 0.95),
    }


def _collect_indexes(node: dict, found: set[str]) -> None:
    index_name = node.get("Index Name")
    if index_name:
        found.add(index_name)
    for child in node.get("Plans", []):
        _collect_indexes(child, found)


def run_benchmark(*, reads: int) -> dict[str, object]:
    with SessionLocal() as session:
        city_ids = session.scalars(select(City.id).order_by(City.name)).all()
        driver_pairs = session.execute(
            select(Driver.city_id, Driver.id).order_by(Driver.stable_id)
        ).all()
        metrics = _latencies(session, city_ids, driver_pairs, reads)
        city_id, driver_id = driver_pairs[0]
        plan_value = session.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                SELECT coalesce(sum(rv.rating), 0), count(rv.id)
                FROM trips t
                JOIN reviews r ON r.trip_id = t.id
                JOIN review_versions rv ON rv.review_id = r.id AND rv.is_current
                WHERE t.city_id = :city_id
                  AND t.driver_id = :driver_id
                  AND t.completed_at >= now() - interval '90 days'
                  AND t.completed_at <= now()
                  AND r.deleted_at IS NULL
                  AND NOT r.moderation_excluded
                """
            ),
            {"city_id": city_id, "driver_id": driver_id},
        ).scalar_one()
        plan = plan_value[0]
        indexes: set[str] = set()
        _collect_indexes(plan["Plan"], indexes)
    return {
        "reads_per_endpoint": reads,
        **metrics,
        "score_query_planning_ms": round(plan["Planning Time"], 3),
        "score_query_execution_ms": round(plan["Execution Time"], 3),
        "score_query_indexes": sorted(indexes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Phase 2 PostgreSQL read paths")
    parser.add_argument("--reads", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("reports/postgres-benchmark.json"))
    args = parser.parse_args()
    result = run_benchmark(reads=args.reads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    markdown = args.output.with_suffix(".md")
    markdown.write_text(
        "# PostgreSQL benchmark\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
