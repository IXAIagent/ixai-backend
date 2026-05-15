"""Composite index for intelligence memory timeline reads."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_intel_mem_idx"
down_revision = "0004_intelligence_scheduler_logs"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_intelligence_memory_snapshots_portfolio_created"
TABLE_NAME = "intelligence_memory_snapshots"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {
        item.get("name")
        for item in inspector.get_indexes(TABLE_NAME)
    }
    if INDEX_NAME in existing_indexes:
        return

    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["portfolio_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {
        item.get("name")
        for item in inspector.get_indexes(TABLE_NAME)
    }
    if INDEX_NAME not in existing_indexes:
        return

    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
