# Engineering Decision Log

## ADR-001: PostgreSQL is authoritative

**Status:** Accepted — Iteration 001

Review history requires transactions, constraints, durable storage, and deterministic
rebuilds. PostgreSQL owns authoritative trips and review versions. Any score, cache, or
leaderboard added later remains derived.

## ADR-002: Preserve immutable review versions

**Status:** Accepted — Iteration 001

A correction appends a version instead of overwriting a rating. This makes changes
auditable and allows reconstruction. A database constraint permits only one current
version for a logical review.

## ADR-003: Auditing and iteration tooling ship with every iteration

**Status:** Accepted — Iteration 001

Every iteration must update independent invariant checks, execute a deterministic
workload, retain measurements, and produce machine- and human-readable reports. An
iteration is incomplete if its audit fails.

## ADR-004: Keep the first architecture synchronous

**Status:** Accepted — Iteration 001

FastAPI writes directly to PostgreSQL. Redis, brokers, and workers are deferred until a
measured bottleneck or reliability requirement justifies them.

## ADR-005: Use trip completion time for the rolling window

**Status:** Accepted — Iteration 001

The future 90-day score uses `trips.completed_at`, not review submission time. Correcting
an old trip must not make that trip newly eligible.

## ADR-006: One PUT command creates or replaces a trip rating

**Status:** Accepted — Iteration 002

The resource identity is the trip, so `PUT /trips/{trip_id}/review` represents both the
initial value and its latest replacement. A correction appends history instead of
changing the resource identity.

## ADR-007: Persist successful idempotency results

**Status:** Accepted — Iteration 002

Each write requires an idempotency key. PostgreSQL stores a canonical request hash,
status, and response. Identical retries replay the result without executing the mutation;
reusing a key with different content returns `409 Conflict`.

## ADR-008: Serialize keys and trips in PostgreSQL

**Status:** Accepted — Iteration 002

A transaction-scoped advisory lock serializes the same idempotency key, and a row lock on
the trip serializes competing review changes. This keeps the first implementation within
one transactional system instead of introducing a distributed lock service.

## ADR-009: Do not append a version for an unchanged rating

**Status:** Accepted — Iteration 002

A new request key that submits the already-current rating succeeds but reuses the current
version. This preserves the distinction between actual corrections and redundant client
commands while still durably recording the request result.

## ADR-010: Store exact score components instead of an average

**Status:** Accepted — Iteration 003

`driver_scores` persists integer rating sum and contributing-review count. Average rating
is derived when returned. This avoids floating-point drift and retains the exact values
needed for future ranking tie-breakers.

## ADR-011: Refresh affected scores synchronously

**Status:** Accepted — Iteration 003

An actual initial review or correction recalculates its driver's score in the same
PostgreSQL transaction. Phase 1 favors immediately consistent, easily audited behavior;
asynchronous processing remains deferred until measurements justify it.

## ADR-012: Rebuild a city at one explicit timestamp

**Status:** Accepted — Iteration 003

A city rebuild calculates all drivers using one shared `calculated_at` and an inclusive
90-day window based on trip completion time. Shared time makes the result deterministic
and prevents reviews near the boundary from being treated differently across drivers.

## ADR-013: Publish immutable leaderboard generations

**Status:** Accepted — Iteration 004

Leaderboard entries are never mutated in place. A new generation is fully populated
before it replaces the published generation, giving readers a consistent snapshot and
preserving prior rankings for inspection.

## ADR-014: Rank using exact ratios and deterministic tie-breakers

**Status:** Accepted — Iteration 004

PostgreSQL orders eligible drivers by the exact numeric ratio of rating sum to count,
then count descending, then stable driver ID ascending. Display rounding never influences
rank and every execution has deterministic ordering.

## ADR-015: Enforce one published generation in the database

**Status:** Accepted — Iteration 004

A partial unique index permits only one `published` generation per city. Publication
locks the city row, serializes version assignment, supersedes the old generation, and
publishes the completed replacement in one transaction.

## ADR-016: Publish synchronously during the correctness phase

**Status:** Accepted — Iteration 004

An actual review change currently recalculates its driver and publishes a city generation
before the review transaction commits. This is simple and immediately consistent at the
current scale. Later measurements may justify batching or asynchronous publication.

## ADR-017: Soft-delete rider reviews

**Status:** Accepted — Iteration 005

Deletion records `deleted_at` instead of removing the review or its versions. This keeps
the authoritative history rebuildable. A later rider submission clears deletion and
appends a version only when the rating itself changed.

## ADR-018: Preserve moderation as numbered decisions

**Status:** Accepted — Iteration 005

Every authorized exclude or restore command appends an immutable, sequential decision.
The review carries its current exclusion state for efficient contribution queries, and
the independent audit reconstructs that state from decision history.

## ADR-019: Record distinct moderation no-ops

**Status:** Accepted — Iteration 005

A new decision asking for the already-current state is retained with `changed_state=false`
for accountability. It does not refresh scores or publish a leaderboard. A retry using
the same idempotency key replays the original decision and creates no additional row.

## ADR-020: Trust upstream identity headers in the project API

**Status:** Accepted — Iteration 005

The current service accepts rider and moderator identities from required headers. They
model identities verified by an upstream gateway; authentication and role management are
outside this project's stated scope and are not simulated with a misleading local scheme.

## ADR-021: Isolate rebuild candidates from live derived state

**Status:** Accepted — Iteration 006

Rebuilds write separate candidate scores and a non-public candidate generation. Normal
readers continue using the existing published generation until an explicit operator
publication succeeds.

## ADR-022: Compare against a captured base generation

**Status:** Accepted — Iteration 006

Each rebuild records its base generation and a durable comparison summary covering entry,
rank, score, and live-score differences. This makes correction scope reviewable before
publication.

## ADR-023: Reject stale candidate publication

**Status:** Accepted — Iteration 006

Publication locks the city and confirms that the captured base is still published. If a
review change published another generation meanwhile, the candidate is rejected rather
than overwriting newer state.

## ADR-024: Make expiration a durable idempotent operation

**Status:** Accepted — Iteration 007

An expiration run is uniquely identified by city and effective timestamp. Retrying the
same run returns its durable result, preventing duplicate generation publication.

## ADR-025: Recalculate a city during expiration

**Status:** Accepted — Iteration 007

The correctness-first implementation recalculates every driver in the city at one shared
timestamp. This reliably handles delayed runs and multiple reviews crossing the boundary;
incremental scheduling can be introduced later if measurements justify it.

## ADR-026: Publish only when expiration changes aggregates

**Status:** Accepted — Iteration 007

All score timestamps advance on an expiration run, but a new leaderboard generation is
published only if a driver's sum, count, or eligibility changed. This avoids version
churn when advancing time does not change the visible ranking inputs.

## ADR-027: Keep PostgreSQL concurrency tests opt-in

**Status:** Accepted — Iteration 008

Fast unit and API-validation tests run without infrastructure. Real row-lock,
idempotency-conflict, and concurrent-correction tests are retained in the suite behind
`RUN_POSTGRES_TESTS=1` and are mandatory in the Phase 1 verification command.

## ADR-028: Use structured request telemetry without an external stack

**Status:** Accepted — Iteration 008

The API emits JSON request ID, method, path, status, and duration fields and returns the
request ID to callers. This establishes diagnosability without prematurely introducing a
metrics or tracing service.

## ADR-029: Declare the synchronous implementation Phase 1 complete

**Status:** Accepted — Iteration 008

The implementation now covers all correctness, audit, rebuild, expiration, and versioned
read requirements. Scaling infrastructure is explicitly deferred until larger workloads
identify a measured bottleneck.

## ADR-030: Scale city count before adding infrastructure

**Status:** Accepted — Iteration 009

Phase 2 first exercises five cities using the existing synchronous PostgreSQL design.
This validates city isolation and exposes database behavior before caching or workers can
hide query costs.

## ADR-031: Keep operational work city-scoped

**Status:** Accepted — Iteration 009

Rebuild, expiration, score replacement, and publication continue to lock and update one
city at a time. Independent cities can progress without sharing derived-state locks.

## ADR-032: Measure query plans before claiming index benefits

**Status:** Accepted — Iteration 010

The repository records PostgreSQL JSON execution plans and read percentiles before and
after Phase 2 indexes. We report the authoritative score query's measured 67.5% execution
time reduction and explicitly treat sub-millisecond service variation as noise.

## ADR-033: Add a composite trip-window access path

**Status:** Accepted — Iteration 010

Score calculation filters by city and driver equality followed by a completed-time range.
The matching composite index lets PostgreSQL perform one targeted scan instead of
combining separate indexes, which the captured plan verifies.

## ADR-034: Report local benchmark scope explicitly

**Status:** Accepted — Iteration 011

Phase 2 throughput and latency are labeled as local service/database results with dataset,
worker count, and hardware context. They are evidence for architectural evolution, not
claims about production capacity.

## ADR-035: Defer Redis and brokers after Phase 2

**Status:** Accepted — Iteration 011

The synchronous system sustained the final Phase 2 workload with an 18.328 ms leaderboard
read p95 and 110.603 ms correction p95. Phase 3 will add asynchronous processing to
measure its benefit; Phase 2 does not add infrastructure merely for appearance.

## ADR-036: Use a PostgreSQL transactional outbox

**Status:** Accepted — Iteration 012

Authoritative review mutations and derived-work events share one transaction. PostgreSQL
already provides the durability and locking required at this scale, so Phase 3 does not
introduce a broker before measuring the database-backed worker.

## ADR-037: Accept bounded eventual consistency for derived state

**Status:** Accepted — Iteration 012

Review writes return after durable acceptance. Scores and leaderboard generations converge
when the worker processes the event. Existing generation metadata tells readers how fresh
the published snapshot is.

## ADR-038: Batch by unique driver and city

**Status:** Accepted — Iteration 012

A worker batch recalculates each affected driver once and publishes once per affected
city, regardless of how many events targeted them. Iteration 012 reduced 67 events to 50
driver calculations and five city generations.

## ADR-039: Commit derived work and event completion atomically

**Status:** Accepted — Iteration 013

Score changes, generation publication, processed-event ledger insertion, and event
completion share one worker transaction. A crash rolls back the whole batch, allowing a
safe retry without partial publication.

## ADR-040: Use SKIP LOCKED for worker concurrency

**Status:** Accepted — Iteration 013

Workers use ordered `FOR UPDATE SKIP LOCKED` claims. Concurrent workers therefore process
disjoint batches without a centralized coordinator; a real two-worker PostgreSQL test
verifies that each event completes once.

## ADR-041: Bound retries with observable backoff

**Status:** Accepted — Iteration 013

Failures record an error and retry after 1, 2, 4, and 8 seconds. The fifth failure becomes
terminal and remains visible through metrics and audits. Iteration 013 injects a failure
and proves the event subsequently recovers.

## ADR-042: Retain the PostgreSQL outbox after measured comparison

**Status:** Accepted — Iteration 014

On the same local 10-city dataset and ten-client benchmark, asynchronous acceptance
reduced review-write p95 from 110.603 ms to 29.474 ms and increased measured throughput
from 131.6 to 490.1 writes/second. The result justifies separating authoritative writes
from disposable score and generation work while retaining one durable system.

## ADR-043: Measure convergence separately from acceptance latency

**Status:** Accepted — Iteration 014

An accepted review is durable before its ranking is visible. Benchmarks therefore report
API write latency and worker convergence independently. Iteration 014 drained 49 queued
events across ten city generations in 157.998 ms; generation timestamps and outbox
metrics expose this eventual-consistency boundary to readers and operators.

## ADR-044: Complete Phase 3 without a broker or cache

**Status:** Accepted — Iteration 014

The database-backed worker provides durable delivery, bounded retries, concurrent claims,
and rebuildability with fewer moving parts. Redis or a broker remains a future option if
queue-depth, contention, or multi-region measurements show that PostgreSQL is the limiting
component.

## ADR-045: Use Redis only for published leaderboard reads

**Status:** Accepted — Iteration 015

Redis stores complete versioned city leaderboard responses. Reviews, scores, generations,
and event delivery remain in PostgreSQL, so flushing Redis requires warming rather than
reconstruction and cannot lose accepted user data.

## ADR-046: Fall back to PostgreSQL on misses and cache failures

**Status:** Accepted — Iteration 015

The leaderboard read path treats Redis as optional. Misses and connection failures read
the published PostgreSQL generation and attempt a cache fill. A short connection timeout
prevents a cache outage from becoming a prolonged API outage.

## ADR-047: Refresh cache after durable generation publication

**Status:** Accepted — Iteration 016

Workers refresh affected city keys only after their PostgreSQL transaction commits.
Rebuild and expiration publication do the same. If refresh fails, PostgreSQL remains
correct and the 120-second TTL plus cache-aside reads provide recovery.

## ADR-048: Audit cache generation identity independently

**Status:** Accepted — Iteration 016

The cache audit compares each Redis generation ID with the currently published PostgreSQL
generation. This verifies cross-store convergence without treating cache contents as an
input to the existing 34 authoritative database checks.

## ADR-049: Retain Redis after the large-dataset measurement

**Status:** Accepted — Iteration 017

At 100 cities, 10,000 drivers, and 500,000 reviews, 5,000 reads with 20 clients measured
4.691 ms p95 and 8,483.7 reads/second through Redis versus 28.338 ms and 940.2 reads/second
through PostgreSQL. The 83.4% p95 improvement and 9.02x throughput justify the added
component for read-heavy leaderboard traffic.

## ADR-050: Validate mixed traffic with the worker running

**Status:** Accepted — Iteration 018

Read-only and isolated write benchmarks hide queue interaction. The final load runner
therefore executes leaderboard reads, real corrections, and worker batches concurrently,
then requires the outbox to converge to zero before reporting success.

## ADR-051: Treat backlog depth and convergence as first-class results

**Status:** Accepted — Iteration 018

The 21,000-operation run peaked at 751 pending events and drained all 1,000 new events.
Reporting the peak and final queue state complements request latency and prevents fast API
acceptance from hiding an unhealthy derived-state pipeline.

## ADR-052: Keep Redis failure non-fatal

**Status:** Accepted — Iteration 019

With Redis deliberately stopped, all 2,000 reads completed through PostgreSQL at 41.155 ms
p95 and 732.3 reads/second. This slower but correct mode is preferable to making a
disposable optimization part of the availability boundary.

## ADR-053: Preserve monotonic derived time

**Status:** Accepted — Iteration 020

Workers and rebuilds use the latest completed city expiration as a lower bound for score
calculation time. This prevents a delayed event or synthetic future-time expiration from
moving the 90-day window backward.

## ADR-054: Complete the project at measured recovery targets

**Status:** Accepted — Iteration 020

A forced 100-event worker failure recovered in 500.303 ms, and a corrupted 5,100-trip city
rebuilt in 0.284 seconds against the 30-minute target. Together with 34 clean database
audits, 100 matching Redis generations, and the full PostgreSQL test suite, these results
close the planned five-phase project.
