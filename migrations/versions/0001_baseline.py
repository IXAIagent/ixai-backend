"""Baseline schema for IXAI.

Existing Render PostgreSQL databases should not run this baseline upgrade.
After confirming the existing schema matches the current SQLAlchemy models, run:

    alembic stamp head

New empty databases should use:

    alembic upgrade head
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_currency", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"], unique=False)

    op.create_table(
        "stock_positions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_positions_portfolio_id", "stock_positions", ["portfolio_id"], unique=False)
    op.create_index("ix_stock_positions_symbol", "stock_positions", ["symbol"], unique=False)

    op.create_table(
        "fcn_positions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("fcn_code", sa.String(), nullable=True),
        sa.Column("issuer", sa.String(), nullable=True),
        sa.Column("notional", sa.Float(), nullable=True),
        sa.Column("notional_amount", sa.Float(), nullable=True),
        sa.Column("underlyings", sa.Text(), nullable=True),
        sa.Column("tenor_months", sa.Integer(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("settlement_currency", sa.String(), nullable=True),
        sa.Column("coupon_frequency", sa.String(), nullable=True),
        sa.Column("next_observation_date", sa.Date(), nullable=True),
        sa.Column("next_coupon_date", sa.Date(), nullable=True),
        sa.Column("observation_dates_json", sa.Text(), nullable=True),
        sa.Column("coupon_dates_json", sa.Text(), nullable=True),
        sa.Column("worst_of_symbol", sa.String(), nullable=True),
        sa.Column("ki_level", sa.Float(), nullable=True),
        sa.Column("ko_level", sa.Float(), nullable=True),
        sa.Column("strike_level", sa.Float(), nullable=True),
        sa.Column("coupon_rate", sa.Float(), nullable=True),
        sa.Column("distance_to_ki_pct", sa.Float(), nullable=True),
        sa.Column("distance_to_ko_pct", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fcn_positions_fcn_code", "fcn_positions", ["fcn_code"], unique=False)
    op.create_index("ix_fcn_positions_portfolio_id", "fcn_positions", ["portfolio_id"], unique=False)

    op.create_table(
        "crypto_positions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("asset_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=True),
        sa.Column("grid_lower", sa.Float(), nullable=True),
        sa.Column("grid_upper", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crypto_positions_portfolio_id", "crypto_positions", ["portfolio_id"], unique=False)
    op.create_index("ix_crypto_positions_symbol", "crypto_positions", ["symbol"], unique=False)

    op.create_table(
        "cash_positions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cash_positions_portfolio_id", "cash_positions", ["portfolio_id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("asset_class", sa.String(), nullable=True),
        sa.Column("asset_ref", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("level", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_portfolio_id", "alerts", ["portfolio_id"], unique=False)

    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("import_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errors_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"], unique=False)
    op.create_index("ix_import_batches_portfolio_id", "import_batches", ["portfolio_id"], unique=False)
    op.create_index("ix_import_batches_user_id", "import_batches", ["user_id"], unique=False)

    op.create_table(
        "import_rows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(), nullable=True),
        sa.Column("input_symbol", sa.String(), nullable=True),
        sa.Column("canonical_symbol", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_rows_batch_id", "import_rows", ["batch_id"], unique=False)
    op.create_index("ix_import_rows_row_number", "import_rows", ["row_number"], unique=False)
    op.create_index("ix_import_rows_status", "import_rows", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_rows_status", table_name="import_rows")
    op.drop_index("ix_import_rows_row_number", table_name="import_rows")
    op.drop_index("ix_import_rows_batch_id", table_name="import_rows")
    op.drop_table("import_rows")

    op.drop_index("ix_import_batches_user_id", table_name="import_batches")
    op.drop_index("ix_import_batches_portfolio_id", table_name="import_batches")
    op.drop_index("ix_import_batches_created_at", table_name="import_batches")
    op.drop_table("import_batches")

    op.drop_index("ix_alerts_portfolio_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_cash_positions_portfolio_id", table_name="cash_positions")
    op.drop_table("cash_positions")

    op.drop_index("ix_crypto_positions_symbol", table_name="crypto_positions")
    op.drop_index("ix_crypto_positions_portfolio_id", table_name="crypto_positions")
    op.drop_table("crypto_positions")

    op.drop_index("ix_fcn_positions_portfolio_id", table_name="fcn_positions")
    op.drop_index("ix_fcn_positions_fcn_code", table_name="fcn_positions")
    op.drop_table("fcn_positions")

    op.drop_index("ix_stock_positions_symbol", table_name="stock_positions")
    op.drop_index("ix_stock_positions_portfolio_id", table_name="stock_positions")
    op.drop_table("stock_positions")

    op.drop_index("ix_portfolios_user_id", table_name="portfolios")
    op.drop_table("portfolios")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
