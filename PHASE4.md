# Phase 4 completion

Phase 4 introduces Redis as a disposable published-leaderboard cache and proves the system
on the roadmap's large synthetic dataset. PostgreSQL remains authoritative for reviews,
scores, generations, the outbox, retries, and rebuilds.

## Iterations

- Iteration 015 added cache-aside reads, PostgreSQL fallback, TTLs, metrics, Docker Redis,
  and a bulk-batched synthetic data generator.
- Iteration 016 connected durable generation publication to post-commit cache refresh and
  added cache warming and independent generation-identity auditing.
- Iteration 017 generated the full dataset, ran recovery and correctness checks, warmed
  all city keys, and compared PostgreSQL and Redis reads.

## Full-size result

The completion run used 100 cities, 10,000 drivers, 500,000 reviewed trips, and 10,000
unrated trips. The deterministic workflow, including a complete rebuild from source
records, completed in 359.324 seconds with cache refresh enabled. It recovered its injected worker failure, left zero
pending and failed events, and passed all 34 PostgreSQL invariants. All 100 Redis city
entries matched their currently published PostgreSQL generation.

## Read benchmark

The local comparison issued 5,000 reads with 20 client threads against the same database.
The Redis run was fully warmed and recorded a 100% hit rate. Results are evidence from this
machine, not a production-capacity claim.

| Metric | PostgreSQL | Redis |
| --- | ---: | ---: |
| Read p50 | 14.466 ms | 2.020 ms |
| Read p95 | 28.338 ms | 4.691 ms |
| Reads/second | 940.2 | 8,483.7 |

Redis improved read p95 by 83.4% and delivered 9.02 times the measured throughput.

## Reproduce

```bash
docker compose up -d db redis
alembic upgrade head
CACHE_ENABLED=true python -m tools.iteration.cli --name iteration-017 \
  --cities 100 --drivers 10000 --reviews 500000 --unrated-trips 10000
CACHE_ENABLED=true python -m tools.cache.cli
CACHE_ENABLED=true python -m tools.cache.audit
CACHE_ENABLED=false python -m tools.benchmark.concurrent \
  --reads 5000 --writes 0 --workers 20 \
  --output reports/iteration-017-postgres-read.json
CACHE_ENABLED=true python -m tools.benchmark.concurrent \
  --reads 5000 --writes 0 --workers 20 \
  --output reports/iteration-017-redis-read.json
python -m tools.benchmark.phase4_compare
RUN_POSTGRES_TESTS=1 pytest
```

The reports are `reports/iteration-015.*`, `reports/iteration-016.*`,
`reports/iteration-017.*`, and `reports/iteration-017-cache-comparison.*`.

## Completion boundary

Phase 4 now includes the large generator, Redis cache-aside reads, event-driven refresh,
fallback behavior, metrics, cache auditing, and measured justification. Broader sustained
load, injected service failures, lag experiments, rebuild timing against the 30-minute
target, and final performance analysis belong to Phase 5.
