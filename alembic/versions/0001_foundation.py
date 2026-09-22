"""Create authoritative foundation tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    now = sa.text("CURRENT_TIMESTAMP")
    op.create_table(
        "cities",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "drivers",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_drivers_city_id", "drivers", ["city_id"])
    op.create_table(
        "riders",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("stable_id", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "trips",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("stable_id", sa.String(64), nullable=False, unique=True),
        sa.Column("driver_id", uuid, sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("rider_id", uuid, sa.ForeignKey("riders.id"), nullable=False),
        sa.Column("city_id", uuid, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    for column in ("driver_id", "rider_id", "city_id", "completed_at"):
        op.create_index(f"ix_trips_{column}", "trips", [column])
    op.create_table(
        "reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("trip_id", uuid, sa.ForeignKey("trips.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "review_versions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("review_id", uuid, sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_versions_rating"),
        sa.CheckConstraint("version >= 1", name="ck_review_versions_version"),
        sa.UniqueConstraint("review_id", "version", name="uq_review_versions_review_version"),
    )
    op.create_index("ix_review_versions_review_id", "review_versions", ["review_id"])
    op.create_index(
        "uq_review_versions_current",
        "review_versions",
        ["review_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_table("review_versions")
    op.drop_table("reviews")
    op.drop_table("trips")
    op.drop_table("riders")
    op.drop_table("drivers")
    op.drop_table("cities")
