"""Add transactional outbox and processed-event ledger.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "outbox_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("driver_id", uuid, sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_outbox_events_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
    )
    op.create_index("ix_outbox_events_city_id", "outbox_events", ["city_id"])
    op.create_index("ix_outbox_events_driver_id", "outbox_events", ["driver_id"])
    op.create_index(
        "ix_outbox_pending_delivery",
        "outbox_events",
        ["next_attempt_at", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "processed_outbox_events",
        sa.Column(
            "event_id",
            uuid,
            sa.ForeignKey("outbox_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processed_outbox_events")
    op.drop_table("outbox_events")
