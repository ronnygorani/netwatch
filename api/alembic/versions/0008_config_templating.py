"""Config templates and scoped variables (global/site/device inheritance).

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_config_templates_name"), "config_templates", ["name"], unique=True)

    op.create_table(
        "config_variables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_ref", sa.String(length=64), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "scope_ref", name="uq_config_variables_scope"),
    )
    op.create_index(op.f("ix_config_variables_scope"), "config_variables", ["scope"], unique=False)

    # Changes may now carry a template name and the config rendered per device
    # at proposal time, so approvers approve exactly what will be pushed.
    op.add_column("changes", sa.Column("template_name", sa.String(length=64), nullable=True))
    op.add_column("changes", sa.Column("rendered", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("changes", "rendered")
    op.drop_column("changes", "template_name")
    op.drop_index(op.f("ix_config_variables_scope"), table_name="config_variables")
    op.drop_table("config_variables")
    op.drop_index(op.f("ix_config_templates_name"), table_name="config_templates")
    op.drop_table("config_templates")
