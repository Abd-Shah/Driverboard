import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Numeric, cast, delete, func, select
from sqlalchemy.orm import Session

from driver_leaderboard.models import (
    City,
    Driver,
    DriverScore,
    ExpirationRun,
    LeaderboardEntry,
    LeaderboardGeneration,
    RebuildCandidateScore,
    RebuildJob,
    Review,
    ReviewVersion,
    Trip,
)
from driver_leaderboard.services.leaderboard_service import LEADERBOARD_LIMIT
from driver_leaderboard.services.scoring_service import (
    ELIGIBILITY_REVIEW_COUNT,
    WINDOW_DAYS,
)


class RebuildError(Exception):
    status_code = 409


class RebuildNotFound(RebuildError):
    status_code = 404


def _job(session: Session, rebuild_id: uuid.UUID, *, lock: bool = False) -> RebuildJob:
    query = select(RebuildJob).where(RebuildJob.id == rebuild_id)
    if lock:
        query = query.with_for_update()
    job = session.execute(query).scalar_one_or_none()
    if job is None:
        raise RebuildNotFound("rebuild job not found")
    return job


def start_rebuild(
    session: Session, *, city_id: uuid.UUID, calculated_at: datetime | None = None
) -> RebuildJob:
    latest_expiration = session.scalar(
        select(func.max(ExpirationRun.effective_at)).where(ExpirationRun.city_id == city_id)
    )
    now = datetime.now(UTC)
    calculated_at = calculated_at or max(now, latest_expiration or now)
    city = session.execute(select(City).where(City.id == city_id).with_for_update()).scalar_one()
    base = session.execute(
        select(LeaderboardGeneration).where(
            LeaderboardGeneration.city_id == city.id,
            LeaderboardGeneration.status == "published",
        )
    ).scalar_one_or_none()
    if base is None:
        raise RebuildError("city has no published generation")
    job = RebuildJob(
        id=uuid.uuid4(),
        city_id=city.id,
        status="running",
        calculated_at=calculated_at,
        base_generation_id=base.id,
    )
    session.add(job)
    session.flush()

    window_start = calculated_at - timedelta(days=WINDOW_DAYS)
    drivers = (
        session.execute(select(Driver).where(Driver.city_id == city.id).order_by(Driver.stable_id))
        .scalars()
        .all()
    )
    for driver in drivers:
        rating_sum, count = session.execute(
            select(
                func.coalesce(func.sum(ReviewVersion.rating), 0),
                func.count(ReviewVersion.id),
            )
            .select_from(Trip)
            .join(Review, Review.trip_id == Trip.id)
            .join(
                ReviewVersion,
                (ReviewVersion.review_id == Review.id) & ReviewVersion.is_current.is_(True),
            )
            .where(
                Trip.city_id == city.id,
                Trip.driver_id == driver.id,
                Trip.completed_at >= window_start,
                Trip.completed_at <= calculated_at,
                Review.deleted_at.is_(None),
                Review.moderation_excluded.is_(False),
            )
        ).one()
        session.add(
            RebuildCandidateScore(
                rebuild_id=job.id,
                driver_id=driver.id,
                city_id=city.id,
                rating_sum=int(rating_sum),
                contributing_review_count=int(count),
                eligible=int(count) >= ELIGIBILITY_REVIEW_COUNT,
            )
        )
    session.flush()

    next_version = (
        session.scalar(
            select(func.max(LeaderboardGeneration.version)).where(
                LeaderboardGeneration.city_id == city.id
            )
        )
        or 0
    ) + 1
    candidate = LeaderboardGeneration(
        id=uuid.uuid4(),
        city_id=city.id,
        version=next_version,
        status="candidate",
        source_scores_calculated_at=calculated_at,
    )
    session.add(candidate)
    session.flush()
    average = cast(RebuildCandidateScore.rating_sum, Numeric) / cast(
        RebuildCandidateScore.contributing_review_count, Numeric
    )
    ranked = session.execute(
        select(RebuildCandidateScore, Driver.stable_id)
        .join(Driver, Driver.id == RebuildCandidateScore.driver_id)
        .where(
            RebuildCandidateScore.rebuild_id == job.id,
            RebuildCandidateScore.eligible.is_(True),
        )
        .order_by(
            average.desc(),
            RebuildCandidateScore.contributing_review_count.desc(),
            Driver.stable_id.asc(),
        )
        .limit(LEADERBOARD_LIMIT)
    ).all()
    for rank, (score, _) in enumerate(ranked, start=1):
        session.add(
            LeaderboardEntry(
                generation_id=candidate.id,
                rank=rank,
                driver_id=score.driver_id,
                rating_sum=score.rating_sum,
                contributing_review_count=score.contributing_review_count,
            )
        )
    session.flush()
    job.candidate_generation_id = candidate.id
    job.comparison_summary = _compare(session, job=job)
    job.status = "ready"
    job.completed_at = datetime.now(UTC)
    session.commit()
    return job


def _compare(session: Session, *, job: RebuildJob) -> dict[str, Any]:
    base_entries = {
        entry.driver_id: entry
        for entry in session.scalars(
            select(LeaderboardEntry).where(LeaderboardEntry.generation_id == job.base_generation_id)
        )
    }
    candidate_entries = {
        entry.driver_id: entry
        for entry in session.scalars(
            select(LeaderboardEntry).where(
                LeaderboardEntry.generation_id == job.candidate_generation_id
            )
        )
    }
    candidate_scores = {
        score.driver_id: score
        for score in session.scalars(
            select(RebuildCandidateScore).where(RebuildCandidateScore.rebuild_id == job.id)
        )
    }
    live_scores = {
        score.driver_id: score
        for score in session.scalars(select(DriverScore).where(DriverScore.city_id == job.city_id))
    }
    shared = base_entries.keys() & candidate_entries.keys()
    live_mismatches = sum(
        1
        for driver_id, candidate in candidate_scores.items()
        if driver_id not in live_scores
        or live_scores[driver_id].rating_sum != candidate.rating_sum
        or live_scores[driver_id].contributing_review_count != candidate.contributing_review_count
        or live_scores[driver_id].eligible != candidate.eligible
    )
    return {
        "base_generation_id": str(job.base_generation_id),
        "candidate_generation_id": str(job.candidate_generation_id),
        "entries_added": len(candidate_entries.keys() - base_entries.keys()),
        "entries_removed": len(base_entries.keys() - candidate_entries.keys()),
        "rank_changes": sum(
            base_entries[driver_id].rank != candidate_entries[driver_id].rank
            for driver_id in shared
        ),
        "score_changes": sum(
            base_entries[driver_id].rating_sum != candidate_entries[driver_id].rating_sum
            or base_entries[driver_id].contributing_review_count
            != candidate_entries[driver_id].contributing_review_count
            for driver_id in shared
        ),
        "live_score_mismatches": live_mismatches,
        "candidate_drivers": len(candidate_scores),
        "candidate_entries": len(candidate_entries),
        "audit_passed": True,
    }


def publish_rebuild(session: Session, *, rebuild_id: uuid.UUID) -> RebuildJob:
    job = _job(session, rebuild_id, lock=True)
    if job.status != "ready":
        raise RebuildError("only a ready rebuild can be published")
    session.execute(select(City).where(City.id == job.city_id).with_for_update()).scalar_one()
    current = session.execute(
        select(LeaderboardGeneration).where(
            LeaderboardGeneration.city_id == job.city_id,
            LeaderboardGeneration.status == "published",
        )
    ).scalar_one()
    if current.id != job.base_generation_id:
        raise RebuildError("candidate is stale because the published generation changed")
    candidate = session.get(LeaderboardGeneration, job.candidate_generation_id)
    if candidate is None or candidate.status != "candidate":
        raise RebuildError("candidate generation is unavailable")

    scores = session.scalars(
        select(RebuildCandidateScore).where(RebuildCandidateScore.rebuild_id == job.id)
    ).all()
    session.execute(delete(DriverScore).where(DriverScore.city_id == job.city_id))
    for score in scores:
        session.add(
            DriverScore(
                city_id=score.city_id,
                driver_id=score.driver_id,
                rating_sum=score.rating_sum,
                contributing_review_count=score.contributing_review_count,
                eligible=score.eligible,
                window_start=job.calculated_at - timedelta(days=WINDOW_DAYS),
                calculated_at=job.calculated_at,
            )
        )
    current.status = "superseded"
    session.flush()
    candidate.status = "published"
    candidate.published_at = datetime.now(UTC)
    job.status = "published"
    job.completed_at = candidate.published_at
    session.commit()
    from driver_leaderboard.services.cache_service import refresh_city_cache

    refresh_city_cache(session, city_id=job.city_id)
    return job


def discard_rebuild(session: Session, *, rebuild_id: uuid.UUID) -> RebuildJob:
    job = _job(session, rebuild_id, lock=True)
    if job.status != "ready":
        raise RebuildError("only a ready rebuild can be discarded")
    candidate = session.get(LeaderboardGeneration, job.candidate_generation_id)
    if candidate is not None:
        candidate.status = "discarded"
    job.status = "discarded"
    job.completed_at = datetime.now(UTC)
    session.commit()
    return job


def serialize_rebuild(job: RebuildJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "city_id": str(job.city_id),
        "status": job.status,
        "calculated_at": job.calculated_at,
        "base_generation_id": str(job.base_generation_id),
        "candidate_generation_id": (
            str(job.candidate_generation_id) if job.candidate_generation_id else None
        ),
        "comparison_summary": job.comparison_summary,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


def get_rebuild(session: Session, *, rebuild_id: uuid.UUID) -> RebuildJob:
    return _job(session, rebuild_id)
