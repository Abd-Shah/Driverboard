import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from driver_leaderboard.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class City(TimestampMixin, Base):
    __tablename__ = "cities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Driver(TimestampMixin, Base):
    __tablename__ = "drivers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    stable_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Rider(TimestampMixin, Base):
    __tablename__ = "riders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stable_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"
    __table_args__ = (
        Index("ix_trips_city_driver_completed", "city_id", "driver_id", "completed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stable_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    rider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("riders.id"), index=True)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), unique=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderation_excluded: Mapped[bool] = mapped_column(nullable=False, default=False)
    versions: Mapped[list["ReviewVersion"]] = relationship(back_populates="review")


class ReviewVersion(TimestampMixin, Base):
    __tablename__ = "review_versions"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_versions_rating"),
        CheckConstraint("version >= 1", name="ck_review_versions_version"),
        UniqueConstraint("review_id", "version", name="uq_review_versions_review_version"),
        Index(
            "uq_review_versions_current",
            "review_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)
    review: Mapped[Review] = relationship(back_populates="versions")


class IdempotencyRequest(TimestampMixin, Base):
    __tablename__ = "idempotency_requests"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ModerationDecision(TimestampMixin, Base):
    __tablename__ = "moderation_decisions"
    __table_args__ = (
        CheckConstraint("action IN ('exclude', 'restore')", name="ck_moderation_action"),
        CheckConstraint("decision_number >= 1", name="ck_moderation_decision_number"),
        UniqueConstraint(
            "review_id", "decision_number", name="uq_moderation_review_decision_number"
        ),
        Index("ix_moderation_review_decision_desc", "review_id", "decision_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id"), index=True)
    decision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    moderator_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_state: Mapped[bool] = mapped_column(nullable=False)


class DriverScore(Base):
    __tablename__ = "driver_scores"
    __table_args__ = (
        CheckConstraint("rating_sum >= 0", name="ck_driver_scores_rating_sum"),
        CheckConstraint(
            "contributing_review_count >= 0",
            name="ck_driver_scores_contributing_review_count",
        ),
        Index(
            "ix_driver_scores_city_eligible_count",
            "city_id",
            "contributing_review_count",
            "driver_id",
            postgresql_where=text("eligible"),
        ),
    )
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), primary_key=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    contributing_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible: Mapped[bool] = mapped_column(nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeaderboardGeneration(TimestampMixin, Base):
    __tablename__ = "leaderboard_generations"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_leaderboard_generations_version"),
        CheckConstraint(
            "status IN ('building', 'candidate', 'published', 'superseded', 'discarded')",
            name="ck_leaderboard_generations_status",
        ),
        UniqueConstraint("city_id", "version", name="uq_leaderboard_generation_city_version"),
        Index(
            "uq_leaderboard_generation_published_city",
            "city_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_scores_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        CheckConstraint("rank BETWEEN 1 AND 100", name="ck_leaderboard_entries_rank"),
        CheckConstraint("rating_sum >= 0", name="ck_leaderboard_entries_rating_sum"),
        CheckConstraint(
            "contributing_review_count >= 20",
            name="ck_leaderboard_entries_eligible_count",
        ),
        UniqueConstraint(
            "generation_id", "driver_id", name="uq_leaderboard_entry_generation_driver"
        ),
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leaderboard_generations.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    contributing_review_count: Mapped[int] = mapped_column(Integer, nullable=False)


class RebuildJob(TimestampMixin, Base):
    __tablename__ = "rebuild_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'ready', 'published', 'discarded', 'failed')",
            name="ck_rebuild_jobs_status",
        ),
        Index(
            "uq_rebuild_jobs_active_city",
            "city_id",
            unique=True,
            postgresql_where=text("status IN ('running', 'ready')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    base_generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leaderboard_generations.id"), nullable=False
    )
    candidate_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leaderboard_generations.id"), nullable=True
    )
    comparison_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RebuildCandidateScore(Base):
    __tablename__ = "rebuild_candidate_scores"
    __table_args__ = (
        CheckConstraint("rating_sum >= 0", name="ck_candidate_scores_rating_sum"),
        CheckConstraint(
            "contributing_review_count >= 0",
            name="ck_candidate_scores_review_count",
        ),
    )
    rebuild_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rebuild_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    contributing_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible: Mapped[bool] = mapped_column(nullable=False)


class ExpirationRun(TimestampMixin, Base):
    __tablename__ = "expiration_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_expiration_runs_status",
        ),
        UniqueConstraint("city_id", "effective_at", name="uq_expiration_city_effective_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    affected_drivers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leaderboard_generations.id"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutboxEvent(TimestampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_outbox_events_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        Index(
            "ix_outbox_pending_delivery",
            "next_attempt_at",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ProcessedOutboxEvent(Base):
    __tablename__ = "processed_outbox_events"
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE"), primary_key=True
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
