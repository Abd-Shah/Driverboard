# Driver Review Leaderboard

An incremental backend project for correct, auditable driver ratings and deterministic
city leaderboards. PostgreSQL review records are authoritative; scores and rankings are
derived and rebuildable.

## Current state: Phase 5 complete (Iteration 020)

The service supports idempotent review changes and deletion, moderation exclusion and
restoration, rolling 90-day scores, and immutable versioned top-100 city leaderboards.
Scores and rankings refresh only when contribution state actually changes.

```bash
cp .env.example .env
docker compose up -d db redis
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn driver_leaderboard.main:app --reload
```

Run the independent audit or a complete deterministic experiment:

```bash
python -m tools.audit.cli
python -m tools.iteration.cli \
  --name iteration-014 \
  --cities 10 \
  --drivers 500 \
  --reviews 15000 \
  --unrated-trips 500
```

The iteration command resets development data, seeds a deterministic dataset, runs the
review submission/correction workload, audits the result, and writes JSON and Markdown
reports under `reports/`.

Review commands use `PUT /trips/{trip_id}/review` with `Idempotency-Key` and
`X-Rider-ID` headers. The current accepted version is available from
`GET /trips/{trip_id}/review`.

Delete a rider review with `DELETE /trips/{trip_id}/review` using `Idempotency-Key` and
`X-Rider-ID`. Exclude or restore a review with
`POST /reviews/{review_id}/moderation-decisions` using `Idempotency-Key` and
`X-Moderator-ID`. The moderator header represents an identity already authenticated by a
trusted gateway; production authentication is outside the current project scope.

Operators can build an isolated candidate with `POST /admin/rebuilds`, inspect it with
`GET /admin/rebuilds/{id}`, then explicitly publish or discard it. Candidate scores and
rankings never replace live state until publication, and publication rejects candidates
whose base generation has become stale.

Advance a city's rolling window with `POST /admin/expiration-runs` or:

```bash
python -m tools.expiration.cli --city-id <city-uuid>
```

Expiration runs are durable and idempotent for a `(city, effective_at)` pair. They
recalculate city scores and publish only when at least one driver's aggregate changes.

Run the read-only completion demonstration with `python -m tools.phase1_demo`. See
`PHASE1.md` for the full verification and demonstration workflow.

Iteration 009 extends the same system across multiple cities. Use `--cities` with the
iteration runner; drivers, trips, rebuilds, expirations, scores, and published generations
remain city-isolated.

Iteration 010 adds PostgreSQL query-plan and latency tooling plus measured indexes. Run
`python -m tools.benchmark.postgres`; the retained trip index reduced the authoritative
score-query execution time by 67.5% in the recorded five-city dataset.

The final Phase 2 workload covers 10 cities, 500 drivers, and 15,500 trips. Its concurrent
local benchmark sustained 1,077.7 leaderboard reads/second and 131.6 review
corrections/second with 18.328 ms and 110.603 ms p95 latency respectively. See
`PHASE2.md` for environment, caveats, commands, and all Phase 2 reports.

Iteration 012 introduces a PostgreSQL transactional outbox. Review commands now commit
authoritative state and a durable event, while `python -m tools.worker.cli --drain`
recalculates scores and publishes batched city generations in the background.

Iteration 013 adds exponential retry handling, an injected-failure recovery exercise,
two-worker `SKIP LOCKED` integration coverage, and `/admin/outbox/metrics` for pending,
processing, completed, failed, and oldest-event-age visibility.

Iteration 014 completes Phase 3 with the same 10-city, 500-driver, 15,500-trip workload
used for the Phase 2 baseline. Asynchronous review acceptance measured 29.474 ms p95 and
490.1 writes/second, a 73.4% p95 improvement and 272.4% throughput improvement over the
local Phase 2 run. The worker drained 49 benchmark events and published ten city
generations in 157.998 ms. See `PHASE3.md` for commands, caveats, and report locations.

Phase 4 adds a Redis read-through leaderboard cache without changing the source-of-truth
boundary. Workers refresh affected city keys after durable publication; misses and Redis
outages fall back to PostgreSQL. The 100-city, 10,000-driver, 500,000-review completion
run passed all 34 database audits and all 100 cached generations matched PostgreSQL.
At that dataset, Redis reduced measured read p95 from 28.338 ms to 4.691 ms and increased
throughput from 940.2 to 8,483.7 reads/second. See `PHASE4.md`.

Phase 5 validates the completed architecture under mixed traffic and controlled failures.
A 21,000-operation run sustained 3,131.4 combined operations/second while a live worker
drained a 751-event peak backlog to zero. Redis outage fallback served every request,
a forced 100-event worker failure recovered in 500.303 ms, and a deliberately corrupted
5,100-trip city rebuilt and published in 0.284 seconds against the 30-minute target. See
`PHASE5.md` for the final evidence and limitations.

Read a derived score from `GET /cities/{city_id}/drivers/{driver_id}/score`. Rebuild all
scores for one city with:

```bash
python -m tools.rebuild.scores --city-id <city-uuid>
```

Fetch the currently published generation from `GET /cities/{city_id}/leaderboard`.
Build and atomically publish a new generation with:

```bash
python -m tools.rebuild.leaderboard --city-id <city-uuid>
```

## Development checks

```bash
pytest
ruff check .
```
