"""Add durable expiration runs.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "expiration_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("affected_drivers", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "published_generation_id",
            uuid,
            sa.ForeignKey("leaderboard_generations.id"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_expiration_runs_status",
        ),
        sa.UniqueConstraint("city_id", "effective_at", name="uq_expiration_city_effective_at"),
    )
    op.create_index("ix_expiration_runs_city_id", "expiration_runs", ["city_id"])


def downgrade() -> None:
    op.drop_table("expiration_runs")
