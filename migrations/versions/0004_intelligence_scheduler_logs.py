"""Intelligence scheduler run logs.

Adds per-portfolio scheduler run logs for Render Cron style intelligence
generation. The scheduler writes snapshots through the existing persistent
memory path and records success/failure per portfolio here.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_intelligence_scheduler_logs"
down_revision = "0003_intelligence_snapshot_v2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_run_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intelligence_run_logs_portfolio_id", "intelligence_run_logs", ["portfolio_id"], unique=False)
    op.create_index("ix_intelligence_run_logs_status", "intelligence_run_logs", ["status"], unique=False)
    op.create_index("ix_intelligence_run_logs_created_at", "intelligence_run_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_intelligence_run_logs_created_at", table_name="intelligence_run_logs")
    op.drop_index("ix_intelligence_run_logs_status", table_name="intelligence_run_logs")
    op.drop_index("ix_intelligence_run_logs_portfolio_id", table_name="intelligence_run_logs")
    op.drop_table("intelligence_run_logs")
