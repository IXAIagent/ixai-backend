"""Add Supabase external account link fields.

v1.53 foundation only. Account linking does not grant paid Pro access,
Portfolio access, FCN access, or legacy JWT login.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_supabase_account_link"
down_revision = "0008_fcn_coupon_sched"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("external_provider", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("external_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("external_email", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "pro_access_status",
                sa.String(),
                nullable=True,
                server_default="connected",
            )
        )

    op.create_index(
        "ix_accounts_external_identity",
        "accounts",
        ["external_provider", "external_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_external_identity", table_name="accounts")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("pro_access_status")
        batch_op.drop_column("external_email")
        batch_op.drop_column("external_user_id")
        batch_op.drop_column("external_provider")
