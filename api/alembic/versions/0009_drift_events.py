"""Config drift events.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drift_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_backup_id", sa.Integer(), nullable=True),
        sa.Column("current_backup_id", sa.Integer(), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("current_hash", sa.String(length=64), nullable=False),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("change_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_backup_id"], ["config_backups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_backup_id"], ["config_backups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["change_id"], ["changes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drift_events_device_id"), "drift_events", ["device_id"])
    op.create_index(op.f("ix_drift_events_detected_at"), "drift_events", ["detected_at"])
    op.create_index(op.f("ix_drift_events_classification"), "drift_events", ["classification"])
    op.create_index(op.f("ix_drift_events_status"), "drift_events", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_drift_events_status"), table_name="drift_events")
    op.drop_index(op.f("ix_drift_events_classification"), table_name="drift_events")
    op.drop_index(op.f("ix_drift_events_detected_at"), table_name="drift_events")
    op.drop_index(op.f("ix_drift_events_device_id"), table_name="drift_events")
    op.drop_table("drift_events")
