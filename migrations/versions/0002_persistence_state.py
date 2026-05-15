"""Persistence v1B: push_states + intelligence_memory_snapshots.

Replaces file-based state (`.ixai_push_state.json`,
`data/intelligence_memory/*.json`) with PostgreSQL-backed tables so state
survives Render restarts and is shared across workers.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_persistence_state"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_push_states_key", "push_states", ["key"], unique=True)
    op.create_index("ix_push_states_user_id", "push_states", ["user_id"], unique=False)

    op.create_table(
        "intelligence_memory_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("workspace_mode", sa.String(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("risk_drift", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_memory_snapshots_portfolio_id",
        "intelligence_memory_snapshots",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        "ix_intelligence_memory_snapshots_created_at",
        "intelligence_memory_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intelligence_memory_snapshots_created_at",
        table_name="intelligence_memory_snapshots",
    )
    op.drop_index(
        "ix_intelligence_memory_snapshots_portfolio_id",
        table_name="intelligence_memory_snapshots",
    )
    op.drop_table("intelligence_memory_snapshots")

    op.drop_index("ix_push_states_user_id", table_name="push_states")
    op.drop_index("ix_push_states_key", table_name="push_states")
    op.drop_table("push_states")
