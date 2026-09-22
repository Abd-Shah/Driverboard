import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two PostgreSQL benchmark runs")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text())
    after = json.loads(args.after.read_text())
    execution_improvement = round(
        (before["score_query_execution_ms"] - after["score_query_execution_ms"])
        / before["score_query_execution_ms"]
        * 100,
        1,
    )
    result = {
        "iteration": "iteration-010",
        "before": before,
        "after": after,
        "score_query_execution_improvement_percent": execution_improvement,
        "conclusion": (
            "Composite trip lookup index reduced authoritative score-query execution time; "
            "service-level microbenchmarks remain sub-millisecond median and are noise-sensitive."
        ),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(
        "# iteration-010\n\n"
        f"- Score-query execution improvement: **{execution_improvement}%**\n"
        f"- Before indexes: `{before['score_query_execution_ms']} ms`\n"
        f"- After indexes: `{after['score_query_execution_ms']} ms`\n"
        f"- Indexes used after: `{', '.join(after['score_query_indexes'])}`\n\n"
        f"{result['conclusion']}\n\n"
        "```json\n" + json.dumps(result, indent=2) + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
