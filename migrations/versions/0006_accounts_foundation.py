"""Accounts foundation for multi-portfolio v3."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_accounts_foundation"
down_revision = "0005_intel_mem_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"], unique=False)

    op.create_table(
        "account_memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_memberships_account_id", "account_memberships", ["account_id"], unique=False)
    op.create_index("ix_account_memberships_user_id", "account_memberships", ["user_id"], unique=False)

    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.String(), nullable=True))
        batch_op.create_foreign_key("fk_portfolios_account_id_accounts", "accounts", ["account_id"], ["id"])
    op.create_index("ix_portfolios_account_id", "portfolios", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_portfolios_account_id", table_name="portfolios")
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.drop_constraint("fk_portfolios_account_id_accounts", type_="foreignkey")
        batch_op.drop_column("account_id")

    op.drop_index("ix_account_memberships_user_id", table_name="account_memberships")
    op.drop_index("ix_account_memberships_account_id", table_name="account_memberships")
    op.drop_table("account_memberships")

    op.drop_index("ix_accounts_owner_user_id", table_name="accounts")
    op.drop_table("accounts")
