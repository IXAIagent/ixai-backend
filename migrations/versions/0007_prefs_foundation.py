"""v3D: per-user preferences foundation.

Adds the `user_preferences` table used by the frontend to sync localStorage
settings (locale, landing page, compact/terminal mode, alert mode, active
account/portfolio) with the backend so they survive across devices.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_prefs_foundation"
down_revision = "0006_accounts_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False, server_default="zh-TW"),
        sa.Column(
            "default_landing_page", sa.String(), nullable=False, server_default="dashboard"
        ),
        sa.Column("compact_mode", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("terminal_mode", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "show_advanced_intelligence",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("alert_mode", sa.String(), nullable=False, server_default="criticalOnly"),
        sa.Column(
            "notification_telegram",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "notification_email", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "risk_interpretation_mode",
            sa.String(),
            nullable=False,
            server_default="balanced",
        ),
        sa.Column("active_account_id", sa.String(), nullable=True),
        sa.Column("active_portfolio_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
