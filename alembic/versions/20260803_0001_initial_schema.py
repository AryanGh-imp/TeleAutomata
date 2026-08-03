"""initial execution history schema

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

revision = "20260803_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_name", sa.String(length=120), nullable=False),
        sa.Column("account", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operations_execution_id", "operations", ["execution_id"])
    op.create_index("ix_operations_status", "operations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_operations_status", table_name="operations")
    op.drop_index("ix_operations_execution_id", table_name="operations")
    op.drop_table("operations")
    op.drop_table("executions")
