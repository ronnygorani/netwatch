"""Indexes for the hot query paths.

devices.site serves the ?site= filter; the composite (device_id, collected_at)
serves latest-per-device aggregation and per-device history ordering.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_devices_site", "devices", ["site"], unique=False)
    op.create_index(
        "ix_metrics_device_id_collected_at",
        "metrics",
        ["device_id", "collected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_metrics_device_id_collected_at", table_name="metrics")
    op.drop_index("ix_devices_site", table_name="devices")
