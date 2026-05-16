"""Add FCN coupon schedule table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_fcn_coupon_sched"
down_revision = "0007_prefs_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fcn_coupon_schedules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("fcn_position_id", sa.String(), nullable=False),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column("observation_start_date", sa.Date(), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["fcn_position_id"], ["fcn_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fcn_coupon_schedules_fcn_position_id",
        "fcn_coupon_schedules",
        ["fcn_position_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fcn_coupon_schedules_fcn_position_id", table_name="fcn_coupon_schedules")
    op.drop_table("fcn_coupon_schedules")
