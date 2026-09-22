# Phase 3 completion

Phase 3 moves score and leaderboard calculation off the review request while preserving
PostgreSQL as the durable source of truth. Review, deletion, and moderation transactions
atomically append outbox events. Workers safely claim events, coalesce repeated driver
changes, and publish at most one generation per affected city in each batch.

## Iterations

- Iteration 012 added the transactional outbox, worker, batching, and processing ledger.
- Iteration 013 added bounded exponential retries, failure recovery, concurrent
  `SKIP LOCKED` claims, queue metrics, and expanded audits.
- Iteration 014 repeated the Phase 2 dataset and benchmark, captured the before/after
  result, and completed Phase 3 documentation and verification.

## Final dataset and correctness run

The deterministic completion run used 10 cities, 500 drivers, 15,000 reviewed trips, and
500 unrated trips. It processed 517 events as 510 driver recalculations and 60 batched city
generations across the full workload, recovered an injected failure, left no pending or
failed events, and passed all 34 independent audit checks.

## Measured local result

Both Phase 2 and Phase 3 used 1,000 leaderboard reads, 50 real review corrections, and ten
client threads against the same local PostgreSQL dataset. These figures demonstrate the
architectural difference on this machine; they are not production capacity claims.

| Metric | Phase 2 synchronous | Phase 3 asynchronous |
| --- | ---: | ---: |
| Review write p95 | 110.603 ms | 29.474 ms |
| Review writes/second | 131.6 | 490.1 |
| Leaderboard read p95 | 18.328 ms | 9.578 ms |
| Leaderboard reads/second | 1,077.7 | 1,441.6 |

Write p95 improved by 73.4%, and measured write throughput improved by 272.4%. After the
write run, the worker processed 49 queued events, published ten city generations, and
emptied the queue in 157.998 ms.

## Reproduce

```bash
alembic upgrade head
python -m tools.iteration.cli --name iteration-014 \
  --cities 10 --drivers 500 --reviews 15000 --unrated-trips 500
python -m tools.benchmark.concurrent --reads 1000 --writes 50 --workers 10 \
  --drain-worker --output reports/iteration-014-load.json
python -m tools.benchmark.phase3_compare
RUN_POSTGRES_TESTS=1 pytest
python -m tools.audit.cli
python -m tools.phase3_demo
```

The durable evidence is in `reports/iteration-014.json`,
`reports/iteration-014-load.json`, and `reports/iteration-014-comparison.json`, with
matching Markdown reports. The benchmark mutates reviews, so rerun the deterministic
iteration afterward when a clean demonstration database is desired.

## Completion boundary

Phase 3 now provides durable asynchronous derivation, retry safety, concurrent-worker
coordination, observability, reproducible measurements, and independent reconstruction
audits. A broker, cache, partitioning strategy, and production-scale load environment are
deliberately deferred to later phases and should be introduced only with new measurements.
