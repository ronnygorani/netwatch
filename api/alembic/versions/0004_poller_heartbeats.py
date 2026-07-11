"""Poller heartbeats: one upserted row per collector for liveness tracking.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poller_heartbeats",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("devices_polled", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("cycle_seconds", sa.Float(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("poller_heartbeats")
