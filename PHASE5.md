# Phase 5 completion

Phase 5 is the final validation phase. It applies concurrent traffic, controlled Redis and
worker failures, deliberate derived-state corruption, recovery timing, and final audits to
the Phase 4 dataset of 100 cities, 10,000 drivers, and more than 500,000 reviews.

## Iteration 018: mixed load and worker lag

The load runner issued 20,000 cached leaderboard reads and 1,000 real review corrections
with 20 clients while a worker processed 100-event batches.

| Metric | Result |
| --- | ---: |
| Total duration | 6.706 seconds |
| Combined throughput | 3,131.4 operations/second |
| Read p95 | 6.357 ms |
| Write p95 | 113.647 ms |
| Peak pending events | 751 |
| Events converged | 1,000 |
| Final pending/failed | 0 / 0 |
| Cache hit rate | 99.49% |

The worker reduced 1,000 events to 958 driver recalculations and 13 city generations.

## Iteration 019: failure recovery

Redis was deliberately stopped during 2,000 reads. Every request fell back to PostgreSQL,
measuring 41.155 ms p95 and 732.3 reads/second. After restart, all 100 city keys were
warmed and independently verified.

A separate 100-event worker batch failed after claiming its rows. The transaction rolled
back, retry metadata was recorded, and the complete batch recovered in 500.303 ms with one
generation publication and no pending or failed events.

## Iteration 020: rebuild recovery

The test deliberately changed a stored driver aggregate, then rebuilt a city containing
5,100 trips from authoritative review versions. Comparison detected 57 mismatching live
scores. Candidate construction took 0.236 seconds, publication took 0.048 seconds, and
total recovery took 0.284 seconds—well below the 1,800-second requirement.

## Final verification

- 17 tests passed with real PostgreSQL concurrency enabled.
- Ruff passed.
- Alembic schema is at `0009 (head)`.
- All 34 independent PostgreSQL invariants passed after the failure tests.
- All 100 Redis generation IDs matched PostgreSQL.
- The final outbox has zero pending and zero failed events.

## Evidence

- `reports/iteration-018-load.json` and `.md`
- `reports/iteration-019-redis-outage.json` and `.md`
- `reports/iteration-019-worker-recovery.json` and `.md`
- `reports/iteration-020-rebuild.json` and `.md`
- Phase 1 through Phase 4 completion documents and their iteration reports

## Honest boundary

These are reproducible local measurements, not production capacity claims. The workload
does not emulate multiple regions, network partitions, managed-service failover, or the
original exercise's 100,000 global changes/second. It does demonstrate the intended
engineering story: build the simplest correct source of truth, scale synthetic data,
measure bottlenecks, introduce asynchronous derivation and caching, inject failures, and
prove reconstruction from durable records.
