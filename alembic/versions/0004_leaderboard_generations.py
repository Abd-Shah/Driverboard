"""Add immutable leaderboard generations.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "leaderboard_generations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_scores_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_leaderboard_generations_version"),
        sa.CheckConstraint(
            "status IN ('building', 'published', 'superseded')",
            name="ck_leaderboard_generations_status",
        ),
        sa.UniqueConstraint("city_id", "version", name="uq_leaderboard_generation_city_version"),
    )
    op.create_index("ix_leaderboard_generations_city_id", "leaderboard_generations", ["city_id"])
    op.create_index(
        "uq_leaderboard_generation_published_city",
        "leaderboard_generations",
        ["city_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "leaderboard_entries",
        sa.Column(
            "generation_id",
            uuid,
            sa.ForeignKey("leaderboard_generations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer, primary_key=True),
        sa.Column("driver_id", uuid, sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("rating_sum", sa.Integer, nullable=False),
        sa.Column("contributing_review_count", sa.Integer, nullable=False),
        sa.CheckConstraint("rank BETWEEN 1 AND 100", name="ck_leaderboard_entries_rank"),
        sa.CheckConstraint("rating_sum >= 0", name="ck_leaderboard_entries_rating_sum"),
        sa.CheckConstraint(
            "contributing_review_count >= 20",
            name="ck_leaderboard_entries_eligible_count",
        ),
        sa.UniqueConstraint(
            "generation_id", "driver_id", name="uq_leaderboard_entry_generation_driver"
        ),
    )


def downgrade() -> None:
    op.drop_table("leaderboard_entries")
    op.drop_table("leaderboard_generations")
