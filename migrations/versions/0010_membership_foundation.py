"""Membership and entitlement foundation.

v1.55 foundation only. Linked accounts default to Free membership and
non-Pro entitlements; paid Pro, Portfolio, FCN, Stripe, and billing workflows
remain disabled.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_membership_foundation"
down_revision = "0009_supabase_account_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("plan_code", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("provider", sa.String(), nullable=False, server_default="manual"),
        sa.Column("provider_customer_id", sa.String(), nullable=True),
        sa.Column("provider_subscription_id", sa.String(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_account_id", "subscriptions", ["account_id"], unique=False)
    op.create_index("ix_subscriptions_plan_code", "subscriptions", ["plan_code"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)

    op.create_table(
        "entitlements",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(), nullable=False, server_default="plan"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entitlements_account_id", "entitlements", ["account_id"], unique=False)
    op.create_index("ix_entitlements_key", "entitlements", ["key"], unique=False)
    op.create_index(
        "ix_entitlements_account_key",
        "entitlements",
        ["account_id", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_entitlements_account_key", table_name="entitlements")
    op.drop_index("ix_entitlements_key", table_name="entitlements")
    op.drop_index("ix_entitlements_account_id", table_name="entitlements")
    op.drop_table("entitlements")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_code", table_name="subscriptions")
    op.drop_index("ix_subscriptions_account_id", table_name="subscriptions")
    op.drop_table("subscriptions")
