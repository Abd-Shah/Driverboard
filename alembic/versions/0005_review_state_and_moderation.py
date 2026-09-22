"""Add review deletion state and moderation history.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "reviews",
        sa.Column(
            "moderation_excluded", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
    )
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "moderation_decisions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("review_id", uuid, sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("decision_number", sa.Integer, nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("moderator_id", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("changed_state", sa.Boolean, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("action IN ('exclude', 'restore')", name="ck_moderation_action"),
        sa.CheckConstraint("decision_number >= 1", name="ck_moderation_decision_number"),
        sa.UniqueConstraint(
            "review_id", "decision_number", name="uq_moderation_review_decision_number"
        ),
    )
    op.create_index("ix_moderation_decisions_review_id", "moderation_decisions", ["review_id"])


def downgrade() -> None:
    op.drop_table("moderation_decisions")
    op.drop_column("reviews", "moderation_excluded")
    op.drop_column("reviews", "deleted_at")
