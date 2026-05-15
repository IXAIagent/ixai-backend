"""Intelligence Pack v2A snapshot metadata.

Adds nullable metadata columns used by Portfolio Intelligence Layer
snapshots. Existing snapshot JSON remains the source of detailed history;
these columns support quick filtering and drift summaries.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_intelligence_snapshot_v2a"
down_revision = "0002_persistence_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("intelligence_memory_snapshots", sa.Column("regime", sa.String(), nullable=True))
    op.add_column("intelligence_memory_snapshots", sa.Column("concentration_score", sa.Float(), nullable=True))
    op.add_column("intelligence_memory_snapshots", sa.Column("dominant_driver", sa.String(), nullable=True))
    op.add_column("intelligence_memory_snapshots", sa.Column("volatility_state", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("intelligence_memory_snapshots", "volatility_state")
    op.drop_column("intelligence_memory_snapshots", "dominant_driver")
    op.drop_column("intelligence_memory_snapshots", "concentration_score")
    op.drop_column("intelligence_memory_snapshots", "regime")
