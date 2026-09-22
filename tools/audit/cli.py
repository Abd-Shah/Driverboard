import json

from driver_leaderboard.database import SessionLocal
from tools.audit.checks import run_checks, serialize


def main() -> int:
    with SessionLocal() as session:
        results = run_checks(session)
    passed = all(result.passed for result in results)
    print(json.dumps({"passed": passed, "checks": serialize(results)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
