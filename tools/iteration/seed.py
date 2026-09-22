import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from driver_leaderboard.models import (
    City,
    Driver,
    DriverScore,
    ExpirationRun,
    IdempotencyRequest,
    LeaderboardEntry,
    LeaderboardGeneration,
    ModerationDecision,
    OutboxEvent,
    ProcessedOutboxEvent,
    RebuildCandidateScore,
    RebuildJob,
    Review,
    ReviewVersion,
    Rider,
    Trip,
)


def reset_and_seed(
    session: Session,
    *,
    cities: int = 1,
    drivers: int,
    reviews: int,
    unrated_trips: int = 0,
    seed: int = 42,
) -> dict[str, int]:
    if cities < 1 or drivers < cities or reviews < 0 or unrated_trips < 0:
        raise ValueError(
            "cities must be positive, drivers must cover every city, and counts cannot be negative"
        )
    rng = random.Random(seed)
    for model in (
        IdempotencyRequest,
        ProcessedOutboxEvent,
        OutboxEvent,
        ExpirationRun,
        RebuildCandidateScore,
        RebuildJob,
        ModerationDecision,
        LeaderboardEntry,
        LeaderboardGeneration,
        DriverScore,
        ReviewVersion,
        Review,
        Trip,
        Rider,
        Driver,
        City,
    ):
        session.execute(delete(model))

    city_names = [
        "Vancouver",
        "Toronto",
        "Victoria",
        "Calgary",
        "Montreal",
        "Ottawa",
        "Edmonton",
        "Winnipeg",
        "Halifax",
        "Quebec City",
    ]
    city_rows = [
        City(id=uuid.uuid4(), name=city_names[i] if i < len(city_names) else f"City {i + 1}")
        for i in range(cities)
    ]
    driver_rows = [
        Driver(
            id=uuid.uuid4(),
            city_id=city_rows[(i - 1) % cities].id,
            stable_id=f"driver_{i:05d}",
        )
        for i in range(1, drivers + 1)
    ]
    session.add_all(city_rows)
    session.add_all(driver_rows)
    session.flush()

    now = datetime.now(UTC)
    weights = [1, 2, 8, 29, 60]
    trip_count = reviews + unrated_trips
    batch_size = 5_000
    for batch_start in range(1, trip_count + 1, batch_size):
        rider_rows: list[dict[str, object]] = []
        trip_rows: list[dict[str, object]] = []
        review_rows: list[dict[str, object]] = []
        version_rows: list[dict[str, object]] = []
        batch_end = min(batch_start + batch_size, trip_count + 1)
        for i in range(batch_start, batch_end):
            rider_id = uuid.uuid4()
            trip_id = uuid.uuid4()
            driver = driver_rows[(i - 1) % drivers]
            trip_age_days = 89 if i == 1 else 91 if i == 2 else rng.randrange(0, 120)
            rider_rows.append({"id": rider_id, "stable_id": f"rider_{i:06d}"})
            trip_rows.append(
                {
                    "id": trip_id,
                    "stable_id": f"trip_{i:06d}",
                    "driver_id": driver.id,
                    "rider_id": rider_id,
                    "city_id": driver.city_id,
                    "completed_at": now - timedelta(days=trip_age_days),
                }
            )
            if i <= reviews:
                review_id = uuid.uuid4()
                review_rows.append(
                    {
                        "id": review_id,
                        "trip_id": trip_id,
                        "moderation_excluded": False,
                    }
                )
                version_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "review_id": review_id,
                        "version": 1,
                        "rating": rng.choices([1, 2, 3, 4, 5], weights=weights)[0],
                        "is_current": True,
                    }
                )
        session.execute(insert(Rider), rider_rows)
        session.execute(insert(Trip), trip_rows)
        if review_rows:
            session.execute(insert(Review), review_rows)
            session.execute(insert(ReviewVersion), version_rows)
    session.commit()
    return {
        "cities": cities,
        "drivers": drivers,
        "trips": trip_count,
        "reviews": reviews,
        "unrated_trips": unrated_trips,
    }
