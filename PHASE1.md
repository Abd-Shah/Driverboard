# Phase 1 Completion Guide

Phase 1 proves the complete correctness-first system on FastAPI and PostgreSQL.

## Delivered capabilities

- Immutable review versions with idempotent submission and correction.
- Soft deletion and rider restoration.
- Immutable moderation exclusion/restoration decisions.
- Exact rolling 90-day driver scores and 20-review eligibility.
- Deterministic, versioned top-100 city leaderboards.
- Isolated rebuild candidates with comparison, stale protection, publish, and discard.
- Durable idempotent expiration runs.
- Independent audits and reproducible iteration reports.

## Verification

```bash
docker compose up -d db
source .venv/bin/activate
alembic upgrade head
pytest
RUN_POSTGRES_TESTS=1 pytest tests/integration/test_concurrent_corrections.py
ruff check .
python -m tools.audit.cli
python -m tools.phase1_demo
```

## Run the final workload again

```bash
python -m tools.iteration.cli \
  --name iteration-008 \
  --drivers 50 \
  --reviews 1500 \
  --unrated-trips 50
```

Reports are written to `reports/iteration-008.md` and JSON. The workload intentionally
exercises retries, conflicts, corrections, deletion, moderation, rebuild-based corruption
recovery, and expiration before running the complete audit suite.

## Demonstrate the API

```bash
uvicorn driver_leaderboard.main:app --reload
```

Open `http://localhost:8000/docs`. Every HTTP response includes `X-Request-ID`; requests
emit structured JSON timing logs.

## Phase boundary

Redis, message brokers, workers, multi-region operation, and production authentication
are not Phase 1 requirements. They should be introduced only in later measured iterations.

