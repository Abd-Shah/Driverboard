# Driverboard

Driverboard is an auditable backend for collecting driver ratings and publishing
deterministic top-100 leaderboards for each city. It supports rating corrections,
deletion and moderation, rolling 90-day scores, retry-safe background processing,
versioned leaderboard snapshots, Redis caching, and complete reconstruction from durable
review history.

The project was developed in five measured phases: correctness, database optimization,
asynchronous processing, Redis caching, and failure/recovery validation.

## What it does

- Accepts one current 1–5 rating for each eligible completed trip.
- Preserves immutable review versions when a rider corrects a rating.
- Uses idempotency keys so retries cannot apply the same change twice.
- Excludes deleted, moderated, and older-than-90-day reviews from driver scores.
- Requires 20 contributing reviews before a driver becomes leaderboard-eligible.
- Publishes immutable top-100 city generations ordered by average, review count, and
  stable driver ID.
- Processes score and ranking changes through a durable PostgreSQL transactional outbox.
- Serves leaderboard snapshots from Redis with automatic PostgreSQL fallback.
- Rebuilds and compares derived scores from authoritative reviews before publication.
- Independently audits database and cache consistency.

## Architecture

```text
Rider / Operator
       |
       v
    FastAPI
       |
       +---- authoritative mutation + outbox event ----> PostgreSQL
       |                                                    |
       |                                                    v
       |                                             background worker
       |                                                    |
       |                                      scores + versioned generation
       |                                                    |
       +---- leaderboard read ----> Redis <-----------------+
                  |                cache
                  +---- miss/error ----> PostgreSQL fallback

Audit tool ----> independently reconstructs expected state from PostgreSQL
```

PostgreSQL is the source of truth. Driver scores, leaderboard generations, and Redis
entries are derived data and can be reconstructed from trips, review versions, deletion
state, and moderation history.

## Technology

- Python 3.11 and FastAPI
- PostgreSQL 16, SQLAlchemy, and Alembic
- Redis 7
- Docker Compose
- Pytest and Ruff

## Quick start

### 1. Create the environment

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 2. Start PostgreSQL and Redis

```bash
docker compose up -d db redis
docker compose ps
```

Both containers should report `healthy`.

### 3. Apply migrations

```bash
alembic upgrade head
alembic current
```

The current schema is `0009 (head)`.

### 4. Generate a demonstration dataset

This command resets development data, creates three cities and 60 drivers, exercises
review correction, deletion, moderation, worker retry, expiration, and rebuild flows, and
then runs the independent database audit.

```bash
CACHE_ENABLED=true python -m tools.iteration.cli \
  --name local-demo \
  --cities 3 \
  --drivers 60 \
  --reviews 1800 \
  --unrated-trips 60
```

The command should finish with `audit=PASS`.

Warm and verify Redis:

```bash
CACHE_ENABLED=true python -m tools.cache.cli
CACHE_ENABLED=true python -m tools.cache.audit
```

The cache audit should report `"passed": true`.

### 5. Start the API

```bash
CACHE_ENABLED=true uvicorn driver_leaderboard.main:app --reload --port 8001
```

Open [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs) to use the Swagger UI.
Port 8001 is used here to avoid conflicts with services commonly bound to port 8000.

## Try the API

Start with:

```text
GET /health
GET /admin/outbox/metrics
GET /admin/cache/metrics
```

Get a city ID from PostgreSQL:

```bash
docker compose exec db psql -U leaderboard -d leaderboard \
  -c "SELECT id, name FROM cities ORDER BY name;"
```

Use a returned UUID with:

```text
GET /cities/{city_id}/leaderboard
```

The response includes the generation ID and version, publication and source-score
timestamps, rank, stable driver ID, average rating, and contributing-review count.

### Submit or correct a rating

Find a trip and its rider:

```bash
docker compose exec db psql -U leaderboard -d leaderboard -c "
SELECT t.id AS trip_id, t.rider_id, rv.rating
FROM trips t
JOIN reviews r ON r.trip_id = t.id
JOIN review_versions rv ON rv.review_id = r.id AND rv.is_current
ORDER BY t.stable_id
LIMIT 1;
"
```

In Swagger, execute `PUT /trips/{trip_id}/review` with:

```text
Idempotency-Key: any unique value
X-Rider-ID: the trip's rider UUID
```

```json
{
  "rating": 5
}
```

The request durably accepts the new review version and creates an outbox event. Process
pending derived work with:

```bash
CACHE_ENABLED=true python -m tools.worker.cli --drain
```

The worker recalculates the affected driver, publishes a new city generation, refreshes
Redis, and marks the event complete.

## Testing and auditing

Run the fast test suite and linter:

```bash
pytest
ruff check .
```

After generating a dataset, run the real PostgreSQL concurrency tests:

```bash
RUN_POSTGRES_TESTS=1 pytest
```

Run the independent database and cache audits:

```bash
python -m tools.audit.cli
CACHE_ENABLED=true python -m tools.cache.audit
```

Tests verify known scenarios such as corrections, retries, and concurrent workers. The
database audit separately evaluates 34 whole-system invariants, including review-version
integrity, exact score reconstruction, deterministic ranking, moderation state, rebuild
state, expiration, and outbox processing. The cache audit compares every Redis generation
ID with the currently published PostgreSQL generation.

For a compact final-state summary, run:

```bash
CACHE_ENABLED=true python -m tools.phase5_demo
```

## Measured results

The final local dataset contained 100 cities, 10,000 drivers, and 500,000+ synthetic
reviews. These are reproducible local-machine measurements, not production capacity
claims.

| Measurement | Result |
| --- | ---: |
| Redis leaderboard throughput | 8,483.7 reads/second |
| Redis leaderboard latency | 4.691 ms p95 |
| Read-throughput improvement | 9.02x |
| Read-latency improvement | 83.4% |
| Asynchronous review-write latency | 29.474 ms p95 |
| Review-write latency improvement | 73.4% |
| Mixed workload throughput | 3,131.4 operations/second |
| Peak backlog drained to zero | 751 events |
| Forced 100-event worker recovery | 500.303 ms |
| Corrupted 5,100-trip city rebuild | 0.284 seconds |

Selected benchmark and recovery evidence is stored in `reports/`, while the current
system design and failure behavior are documented in `architecture.md`.

## Repository guide

```text
src/driver_leaderboard/   API, models, services, and schemas
alembic/                  Database migrations
tools/audit/              Independent invariant checks
tools/iteration/          Deterministic data generation and experiment runner
tools/benchmark/          PostgreSQL, cache, load, failure, and rebuild benchmarks
tools/worker/             Transactional-outbox worker CLI
tests/                    Unit, integration, concurrency, and audit tests
reports/                  Selected measured evidence
```

See `architecture.md` for detailed data flows and failure behavior.

## Scope

This project focuses on driver-rating correctness and leaderboard derivation. Dispatch,
trip matching, payments, free-text review serving, fraud-model design, and production
authentication are intentionally out of scope.
