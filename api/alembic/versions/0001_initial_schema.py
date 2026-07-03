"""Initial schema: devices and metrics tables.

Captures the schema exactly as `Base.metadata.create_all()` used to build it,
so existing databases can adopt Alembic with `alembic stamp head` and fresh
databases get an identical result from `alembic upgrade head`.

Revision ID: 0001
Revises:
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("site", sa.String(length=64), nullable=False),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip_address"),
    )
    op.create_index(op.f("ix_devices_id"), "devices", ["id"], unique=False)

    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metrics_id"), "metrics", ["id"], unique=False)
    op.create_index(op.f("ix_metrics_device_id"), "metrics", ["device_id"], unique=False)
    op.create_index(op.f("ix_metrics_collected_at"), "metrics", ["collected_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_metrics_collected_at"), table_name="metrics")
    op.drop_index(op.f("ix_metrics_device_id"), table_name="metrics")
    op.drop_index(op.f("ix_metrics_id"), table_name="metrics")
    op.drop_table("metrics")
    op.drop_index(op.f("ix_devices_id"), table_name="devices")
    op.drop_table("devices")
