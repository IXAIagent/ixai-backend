"""Composite index for intelligence memory timeline reads."""

from __future__ import annotations

from alembic import op


revision = "0005_intelligence_memory_composite_index"
down_revision = "0004_intelligence_scheduler_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_intelligence_memory_snapshots_portfolio_created",
        "intelligence_memory_snapshots",
        ["portfolio_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intelligence_memory_snapshots_portfolio_created",
        table_name="intelligence_memory_snapshots",
    )
