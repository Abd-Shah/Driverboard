import argparse
import json
from pathlib import Path


def improvement(before: float, after: float) -> float:
    return round((before - after) / before * 100, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Phase 2 and Phase 3 load results")
    parser.add_argument("--phase2", type=Path, default=Path("reports/iteration-011-load.json"))
    parser.add_argument("--phase3", type=Path, default=Path("reports/iteration-014-load.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/iteration-014-comparison.json"))
    args = parser.parse_args()
    phase2 = json.loads(args.phase2.read_text())
    phase3 = json.loads(args.phase3.read_text())
    result = {
        "review_write_p95_improvement_percent": improvement(
            phase2["review_write_p95_ms"], phase3["review_write_p95_ms"]
        ),
        "review_write_throughput_improvement_percent": round(
            (
                phase3["review_writes_per_second"]
                / phase2["review_writes_per_second"]
                - 1
            )
            * 100,
            1,
        ),
        "phase2": phase2,
        "phase3": phase3,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(
        "# Iteration 014: asynchronous write comparison\n\n"
        f"- Write p95 improvement: {result['review_write_p95_improvement_percent']}%\n"
        "- Write throughput improvement: "
        f"{result['review_write_throughput_improvement_percent']}%\n\n"
        "```json\n" + json.dumps(result, indent=2) + "\n```\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
