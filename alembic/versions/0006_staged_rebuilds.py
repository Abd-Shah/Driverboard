"""Add staged rebuild jobs and candidate scores.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_leaderboard_generations_status", "leaderboard_generations", type_="check"
    )
    op.create_check_constraint(
        "ck_leaderboard_generations_status",
        "leaderboard_generations",
        "status IN ('building', 'candidate', 'published', 'superseded', 'discarded')",
    )
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "rebuild_jobs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "base_generation_id",
            uuid,
            sa.ForeignKey("leaderboard_generations.id"),
            nullable=False,
        ),
        sa.Column(
            "candidate_generation_id",
            uuid,
            sa.ForeignKey("leaderboard_generations.id"),
            nullable=True,
        ),
        sa.Column("comparison_summary", postgresql.JSONB, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'ready', 'published', 'discarded', 'failed')",
            name="ck_rebuild_jobs_status",
        ),
    )
    op.create_index("ix_rebuild_jobs_city_id", "rebuild_jobs", ["city_id"])
    op.create_index(
        "uq_rebuild_jobs_active_city",
        "rebuild_jobs",
        ["city_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'ready')"),
    )
    op.create_table(
        "rebuild_candidate_scores",
        sa.Column(
            "rebuild_id",
            uuid,
            sa.ForeignKey("rebuild_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("driver_id", uuid, sa.ForeignKey("drivers.id"), primary_key=True),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("rating_sum", sa.Integer, nullable=False),
        sa.Column("contributing_review_count", sa.Integer, nullable=False),
        sa.Column("eligible", sa.Boolean, nullable=False),
        sa.CheckConstraint("rating_sum >= 0", name="ck_candidate_scores_rating_sum"),
        sa.CheckConstraint(
            "contributing_review_count >= 0", name="ck_candidate_scores_review_count"
        ),
    )


def downgrade() -> None:
    op.drop_table("rebuild_candidate_scores")
    op.drop_table("rebuild_jobs")
    op.drop_constraint(
        "ck_leaderboard_generations_status", "leaderboard_generations", type_="check"
    )
    op.create_check_constraint(
        "ck_leaderboard_generations_status",
        "leaderboard_generations",
        "status IN ('building', 'published', 'superseded')",
    )
