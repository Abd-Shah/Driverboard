"""Add measured Phase 2 query indexes.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_trips_city_driver_completed",
        "trips",
        ["city_id", "driver_id", "completed_at"],
    )
    op.create_index(
        "ix_driver_scores_city_eligible_count",
        "driver_scores",
        ["city_id", "contributing_review_count", "driver_id"],
        postgresql_where=sa.text("eligible"),
    )
    op.create_index(
        "ix_moderation_review_decision_desc",
        "moderation_decisions",
        ["review_id", "decision_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_moderation_review_decision_desc", table_name="moderation_decisions")
    op.drop_index("ix_driver_scores_city_eligible_count", table_name="driver_scores")
    op.drop_index("ix_trips_city_driver_completed", table_name="trips")
