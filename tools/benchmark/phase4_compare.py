import json
from pathlib import Path


def main() -> int:
    postgres = json.loads(Path("reports/iteration-017-postgres-read.json").read_text())
    redis = json.loads(Path("reports/iteration-017-redis-read.json").read_text())
    result = {
        "dataset": {"cities": 100, "drivers": 10_000, "reviews": 500_000},
        "read_p95_improvement_percent": round(
            (postgres["leaderboard_read_p95_ms"] - redis["leaderboard_read_p95_ms"])
            / postgres["leaderboard_read_p95_ms"]
            * 100,
            1,
        ),
        "read_throughput_multiplier": round(
            redis["leaderboard_reads_per_second"]
            / postgres["leaderboard_reads_per_second"],
            2,
        ),
        "postgres": postgres,
        "redis": redis,
    }
    output = Path("reports/iteration-017-cache-comparison.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    output.with_suffix(".md").write_text(
        "# Iteration 017: Redis read comparison\n\n"
        f"- Read p95 improvement: {result['read_p95_improvement_percent']}%\n"
        f"- Throughput multiplier: {result['read_throughput_multiplier']}x\n\n"
        "```json\n" + json.dumps(result, indent=2) + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
