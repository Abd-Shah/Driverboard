# Phase 2 Completion Guide

Phase 2 validates the synchronous PostgreSQL architecture across multiple city partitions
and adds measured query optimization and concurrent service baselines.

## Iterations

- Iteration 009: five-city correctness baseline with 100 drivers and 3,050 trips.
- Iteration 010: before/after PostgreSQL plans and evidence-based indexing.
- Iteration 011: ten cities, 500 drivers, 15,500 trips, concurrent reads and writes.

## Final measured dataset

```text
Cities:                    10
Drivers:                  500
Trips:                 15,500
Reviews:               15,500
Eligible drivers:         471 before the simulated expiration step
Contributing reviews:  11,615
Outside-window reviews: 3,882
```

## Concurrent local benchmark

Environment: local Apple Silicon host, PostgreSQL 16 in Docker, 10 client threads.

```text
Leaderboard reads:       1,000
Read throughput:       1,077.7 operations/second
Read p50:                 7.640 ms
Read p95:                18.328 ms

Review corrections:          50
Write throughput:         131.6 operations/second
Write p50:                69.055 ms
Write p95:               110.603 ms
```

These are local service/database measurements, not production or Uber-scale claims.

## Query optimization evidence

The authoritative score aggregation changed from separate trip indexes to
`ix_trips_city_driver_completed`. In the recorded Iteration 010 dataset, execution time
fell from 0.618 ms to 0.201 ms (67.5%). Service microbenchmark differences below 1 ms are
treated as noise.

## Verification

```bash
docker compose up -d db
source .venv/bin/activate
alembic upgrade head
pytest
RUN_POSTGRES_TESTS=1 pytest tests/integration/test_concurrent_corrections.py
ruff check .
python -m tools.audit.cli
python -m tools.phase2_demo
```

## Reproduce the final dataset

```bash
python -m tools.iteration.cli \
  --name iteration-011 \
  --cities 10 \
  --drivers 500 \
  --reviews 15000 \
  --unrated-trips 500
```

## Phase boundary

The synchronous architecture remains comfortably usable at this project scale, so Phase
2 does not add Redis or a broker. Phase 3 will introduce a transactional outbox and worker
to decouple accepted review writes from derived-score and leaderboard publication.

