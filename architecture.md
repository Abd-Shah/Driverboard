# Architecture

## Current state: Phase 5 complete (Iteration 020)

The application has FastAPI and worker processes backed by PostgreSQL, plus Redis as a
disposable leaderboard read cache. PostgreSQL remains authoritative and provides the
durable outbox; Redis can be emptied or unavailable without losing accepted work.

```text
HTTP client -> FastAPI review route -> transactional review service -> PostgreSQL
                         |                 |                            |- trips
                         |                 |- trip row lock             |- reviews
                         |                 |- idempotency key lock      |- review_versions
                         |                 `- immutable correction      `- idempotency_requests
                         `-> current review read

Iteration tool -> deterministic seed -> audit -> versioned report
Audit tool ---------------------------> independent SQL checks

Current review version -> durable outbox -> worker score calculation -> driver_scores
Authoritative history  -> city score rebuild -----------> driver_scores
driver_scores -> deterministic top 100 -> immutable generation -> atomic publication
delete/moderate -> contribution-state change -> outbox -> score refresh -> new generation
authoritative records -> candidate scores/generation -> compare -> publish or discard
periodic trigger -> expiration run -> advance score windows -> publish if changed
HTTP middleware -> request ID + structured latency/status log
review transaction -> authoritative rows + outbox event -> fast response
worker batch -> unique city/driver changes -> scores -> one generation per city
worker publication -> Redis city snapshot
leaderboard read -> Redis hit OR PostgreSQL fallback -> cache fill
```

## Components

- `src/driver_leaderboard`: application configuration, database session management,
  health and review APIs, transactional services, and persistence models.
- `tools/audit`: read-only invariant checks. Audit queries do not trust future service
  calculations.
- `tools/iteration`: deterministic dataset generation, audit execution, timing capture,
  and report generation.
- `alembic`: versioned database schema.
- `tools/rebuild`: deterministic reconstruction of disposable derived score state.

## Current data model

Cities contain drivers. Completed trips bind one rider, driver, and city. A review is a
stable identity for a trip and immutable review-version rows preserve corrections.

`review_versions.is_current` identifies the accepted version. A partial unique index
ensures at most one current version per review. Historical versions are never updated
into new ratings.

`idempotency_requests` stores the canonical request hash and original response. Requests
sharing a key are serialized with a PostgreSQL transaction-scoped advisory lock. An
identical replay returns the stored result; different content is rejected. Review changes
also lock the trip row, serializing initial submissions and corrections for the same trip.

## Review API

- `PUT /trips/{trip_id}/review` creates or corrects a rating. It requires
  `Idempotency-Key` and `X-Rider-ID` headers.
- `GET /trips/{trip_id}/review` returns the latest accepted version.

The write validates trip existence and rider ownership. A new rating creates version 1;
a correction appends the next version. Submitting the already-current rating under a new
key succeeds without creating meaningless history.

Rider deletion sets `reviews.deleted_at` without removing the review or any version.
Resubmitting a rating clears deletion; it appends a version only when the rating changed.
`GET /trips/{trip_id}/review` treats a deleted review as absent.

Moderation commands append numbered `moderation_decisions`. The review stores the latest
`moderation_excluded` state for contribution queries, while the audit reconstructs that
state independently from decision history. Repeated delivery with the same idempotency
key replays the original decision. A distinct decision that requests the already-current
state is recorded as a no-op and does not recalculate scores or publish a generation.

The current API uses `X-Rider-ID` and `X-Moderator-ID` as identities supplied by a trusted
upstream boundary. Authentication and role management are intentionally out of scope.

## Rolling driver scores

`driver_scores` stores `rating_sum` and `contributing_review_count` for every driver in a
city. The average is calculated from those exact integers when read; it is not stored as
a floating-point ranking value. A driver is eligible at 20 contributing reviews.

The window is inclusive and is based on `trips.completed_at`:

```text
calculated_at - 90 days <= completed_at <= calculated_at
```

An actual initial rating or correction recalculates the affected driver inside the same
database transaction. A city rebuild deletes that city's derived rows, independently
recalculates all of its drivers at one shared timestamp, and commits the replacement.
`GET /cities/{city_id}/drivers/{driver_id}/score` exposes the current derived score.

## Versioned city leaderboards

Every accepted rating change that alters a review recalculates the affected driver and
builds a new city generation in the same transaction. A generation begins as `building`.
Its top 100 entries are frozen, the prior published generation becomes `superseded`, and
the new generation becomes `published`. A partial unique index guarantees at most one
published generation per city.

Eligible drivers are ordered by:

1. Exact average (`rating_sum / contributing_review_count`) descending.
2. Contributing-review count descending.
3. Stable driver ID ascending.

Each entry snapshots the exact sum and count used to rank it. The response includes the
generation ID, monotonically increasing city version, generation and publication times,
latest source-score calculation time, rank, score, and review count. Readers fetch only
the published generation from `GET /cities/{city_id}/leaderboard`.

`tools.rebuild.leaderboard` creates and publishes a generation from current derived
scores. Historical generations are immutable and remain available for audit or later
comparison tooling.

## Staged rebuilds

`POST /admin/rebuilds` captures the current published generation, independently computes
candidate scores at one timestamp, builds a hidden candidate generation, and records a
comparison summary. Live scores and normal leaderboard reads are unchanged while the job
is `ready`.

Publication locks the city and requires the current published generation to equal the
candidate's recorded base generation. It then replaces live scores and promotes the
candidate atomically. A changed base causes `409 Conflict`; the candidate can be
discarded. Candidate and discarded generations are never returned by the reader API.

## Time-based expiration

`expiration_runs` durably records each `(city, effective_at)` execution. A run locks the
city, recalculates every driver at the supplied time, counts drivers whose exact aggregate
or eligibility changed, and publishes a generation only when that count is nonzero.
Retrying the same city and timestamp returns the original run.

The application exposes a manual API and CLI suitable for invocation by cron or another
scheduler. Scheduling infrastructure is deliberately external; correctness, recovery,
and idempotency live inside this service. A delayed run uses its actual effective time and
therefore catches every review already beyond the boundary.

## Reliability boundary

PostgreSQL is the durable source of truth. Reports, future score tables, and leaderboard
generations are disposable derived artifacts. The audit checks relational integrity,
exactly one current version, contiguous history, latest-version selection, and durable
idempotency-result references directly from authoritative tables. Score audits use
separate SQL to compare every stored sum, count, city, window, and eligibility value with
the review source records. Leaderboard audits independently reproduce the top-100 order,
check contiguous ranks and sequential generation versions, verify freshness, and require
exactly one published generation per city.
Moderation audits reconstruct current exclusion state and state transitions from the
immutable decision sequence. Score comparison SQL excludes both deleted and moderated
reviews independently of the application services.
Rebuild audits recompute candidate scores at the job timestamp, validate job/generation
state alignment, and ensure published rebuilds had successful comparisons.
Expiration audits confirm score timestamps cover the latest completed run and that a run
publishes exactly when aggregates changed.

## Beyond Phase 1

Phase 1 has no remaining functional gaps. Later phases may replace synchronous city-wide
work with measured caching, background processing, or event delivery while preserving the
same authoritative records and audits.

## Multi-city execution

Synthetic drivers are deterministically distributed across cities and every trip inherits
its driver's city. Score rebuilds, generation publication, staged recovery, and expiration
lock and mutate one city at a time. The audit requires one published generation per city
and independently validates each score and ranking against that city's authoritative rows.

## PostgreSQL access paths

Phase 2 includes an `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` benchmark for the
authoritative score aggregation. The composite
`trips(city_id, driver_id, completed_at)` index matches its equality/equality/range
predicate and replaced separate city/driver index scans. Partial eligible-score and
moderation-history indexes support their corresponding filtered and latest-decision paths.
Benchmark reports preserve planning time, execution time, selected indexes, and service
read percentiles.

## Phase 2 measured boundary

The final synchronous deployment was exercised with 10 cities, 500 drivers, and 15,500
trips. Ten concurrent clients measured city leaderboard reads and real review corrections.
PostgreSQL remains both source of truth and derived-state store. No cache or broker was
added because the measured workload is stable enough to establish a clear Phase 3
before/after comparison.

## Transactional outbox

Review, deletion, and moderation transactions append an `outbox_events` row only when
effective contribution changes. The authoritative mutation and event commit together, so
a worker outage cannot lose derived work. API responses no longer wait for score or
leaderboard calculation.

Workers claim pending rows with `FOR UPDATE SKIP LOCKED`, group repeated changes by city
and driver, recalculate each affected driver once, and publish one generation per affected
city. Completion state and a processed-event ledger commit in the same transaction as the
derived updates. Leaderboards are therefore eventually consistent and expose their
existing generation freshness while work is pending.

Failed batches roll back all derived changes and event state. A separate failure
transaction increments attempts, records the error, and schedules exponential backoff;
the fifth failed attempt becomes terminal. Multiple workers safely claim disjoint event
sets. Metrics expose queue depth, state counts, and oldest pending age.

## Redis leaderboard cache

Each city has one TTL-bound Redis JSON value containing the complete published generation
response. The worker refreshes affected keys only after the PostgreSQL transaction commits,
so Redis never makes an uncommitted generation visible. Rebuild and expiration publication
also refresh their city. Reads are cache-aside: a miss or Redis connection error reads the
published generation from PostgreSQL and attempts to refill the key.

Cache correctness does not depend on Redis durability. Generation IDs make cache content
comparable with PostgreSQL, and `tools.cache.audit` independently checks every populated
city. Process metrics expose hits, misses, writes, errors, and hit rate. A 120-second TTL
bounds stale data if a post-commit refresh cannot reach Redis.

## Validated failure behavior

- Redis unavailable: reads fall back to the published PostgreSQL generation; Redis is
  warmed again after recovery.
- Worker transaction failure: all derived changes roll back, the event batch is retried,
  and ledger/event completion commits with the successful generation.
- Derived score corruption: a city-scoped rebuild calculates isolated candidate scores,
  detects differences, and atomically publishes only after comparison.
- Synthetic future expiration: workers and rebuilds preserve monotonic score calculation
  time by using the latest completed expiration time as a lower bound.

Phase 5 also distinguishes active candidate verification from historical rebuild evidence.
Ready candidates are compared with current authoritative reviews; published historical
rebuilds retain their recorded successful comparison and are not expected to match review
corrections accepted later.
