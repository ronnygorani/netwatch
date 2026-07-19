"""Link cached devices to their Nautobot source-of-truth records.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("nautobot_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_devices_nautobot_id"), "devices", ["nautobot_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_nautobot_id"), table_name="devices")
    op.drop_column("devices", "nautobot_id")
