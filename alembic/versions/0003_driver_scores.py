"""Add derived rolling driver scores.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "driver_scores",
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), primary_key=True),
        sa.Column("driver_id", uuid, sa.ForeignKey("drivers.id"), primary_key=True),
        sa.Column("rating_sum", sa.Integer, nullable=False),
        sa.Column("contributing_review_count", sa.Integer, nullable=False),
        sa.Column("eligible", sa.Boolean, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating_sum >= 0", name="ck_driver_scores_rating_sum"),
        sa.CheckConstraint(
            "contributing_review_count >= 0",
            name="ck_driver_scores_contributing_review_count",
        ),
    )


def downgrade() -> None:
    op.drop_table("driver_scores")
