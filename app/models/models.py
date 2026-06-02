from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    owned_accounts = relationship("Account", back_populates="owner_user", cascade="all, delete-orphan")
    account_memberships = relationship("AccountMembership", back_populates="user", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    owner_user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    account_type = Column(String, default="individual", nullable=False)
    external_provider = Column(String, nullable=True)
    external_user_id = Column(String, nullable=True)
    external_email = Column(String, nullable=True)
    pro_access_status = Column(String, default="connected", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner_user = relationship("User", back_populates="owned_accounts")
    memberships = relationship("AccountMembership", back_populates="account", cascade="all, delete-orphan")
    portfolios = relationship("Portfolio", back_populates="account")


class AccountMembership(Base):
    __tablename__ = "account_memberships"

    id = Column(String, primary_key=True, default=generate_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String, default="viewer", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="memberships")
    user = relationship("User", back_populates="account_memberships")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    base_currency = Column(String, default="USD", nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    account_id = Column(String, ForeignKey("accounts.id"), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="portfolios")
    account = relationship("Account", back_populates="portfolios")
    stocks = relationship("StockPosition", back_populates="portfolio", cascade="all, delete-orphan")
    fcn_positions = relationship("FCNPosition", back_populates="portfolio", cascade="all, delete-orphan")
    crypto_positions = relationship("CryptoPosition", back_populates="portfolio", cascade="all, delete-orphan")
    cash_positions = relationship("CashPosition", back_populates="portfolio", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="portfolio", cascade="all, delete-orphan")
    import_batches = relationship("ImportBatch", back_populates="portfolio", cascade="all, delete-orphan")


class StockPosition(Base):
    __tablename__ = "stock_positions"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    quantity = Column(Float, nullable=False, default=0)
    avg_price = Column(Float, nullable=False, default=0)
    current_price = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="stocks")

    @property
    def avg_cost(self) -> float:
        return self.avg_price or 0

    @avg_cost.setter
    def avg_cost(self, value: float) -> None:
        self.avg_price = value


class FCNPosition(Base):
    __tablename__ = "fcn_positions"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    name = Column(String, nullable=True)
    fcn_code = Column(String, index=True, nullable=True)
    issuer = Column(String, nullable=True)
    notional = Column(Float, nullable=True)
    notional_amount = Column(Float, nullable=True)
    underlyings = Column(Text, nullable=True)
    tenor_months = Column(Integer, nullable=True)
    issue_date = Column(Date, nullable=True)
    maturity_date = Column(Date, nullable=True)
    settlement_currency = Column(String, nullable=True)
    coupon_frequency = Column(String, nullable=True)
    next_observation_date = Column(Date, nullable=True)
    next_coupon_date = Column(Date, nullable=True)
    observation_dates_json = Column(Text, nullable=True)
    coupon_dates_json = Column(Text, nullable=True)
    worst_of_symbol = Column(String, nullable=True)
    ki_level = Column(Float, nullable=True)
    ko_level = Column(Float, nullable=True)
    strike_level = Column(Float, nullable=True)
    coupon_rate = Column(Float, nullable=True)
    distance_to_ki_pct = Column(Float, nullable=True)
    distance_to_ko_pct = Column(Float, nullable=True)
    risk_level = Column(String, default="low", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="fcn_positions")
    coupon_schedules = relationship("FCNCouponSchedule", back_populates="fcn_position", cascade="all, delete-orphan")


class FCNCouponSchedule(Base):
    __tablename__ = "fcn_coupon_schedules"

    id = Column(String, primary_key=True, default=generate_uuid)
    fcn_position_id = Column(String, ForeignKey("fcn_positions.id"), index=True, nullable=False)
    period_index = Column(Integer, nullable=False)
    observation_start_date = Column(Date, nullable=True)
    observation_date = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=False)
    status = Column(String, default="scheduled", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    fcn_position = relationship("FCNPosition", back_populates="coupon_schedules")


class CryptoPosition(Base):
    __tablename__ = "crypto_positions"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    asset_type = Column(String, default="spot", nullable=False)  # spot / grid / dual
    quantity = Column(Float, nullable=False, default=0)
    avg_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    leverage = Column(Float, nullable=True)
    grid_lower = Column(Float, nullable=True)
    grid_upper = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="crypto_positions")


class CashPosition(Base):
    __tablename__ = "cash_positions"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    amount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="cash_positions")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    asset_class = Column(String, nullable=True)
    asset_ref = Column(String, nullable=True)
    severity = Column(String, nullable=True)  # low / medium / high / critical
    level = Column(String, nullable=True)  # backward-compatible alias
    title = Column(String, nullable=True)
    message = Column(String, nullable=False)
    status = Column(String, default="open", nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="alerts")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=False)
    import_type = Column(String, default="portfolio_csv", nullable=False)
    file_name = Column(String, nullable=True)
    imported = Column(Integer, default=0, nullable=False)
    updated = Column(Integer, default=0, nullable=False)
    skipped = Column(Integer, default=0, nullable=False)
    errors_count = Column(Integer, default=0, nullable=False)
    status = Column(String, default="completed", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    portfolio = relationship("Portfolio", back_populates="import_batches")
    rows = relationship("ImportRow", back_populates="batch", cascade="all, delete-orphan")


class ImportRow(Base):
    __tablename__ = "import_rows"

    id = Column(String, primary_key=True, default=generate_uuid)
    batch_id = Column(String, ForeignKey("import_batches.id"), index=True, nullable=False)
    row_number = Column(Integer, index=True, nullable=False)
    asset_type = Column(String, nullable=True)
    input_symbol = Column(String, nullable=True)
    canonical_symbol = Column(String, nullable=True)
    action = Column(String, nullable=True)
    status = Column(String, index=True, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    batch = relationship("ImportBatch", back_populates="rows")


class PushState(Base):
    __tablename__ = "push_states"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class IntelligenceMemorySnapshot(Base):
    __tablename__ = "intelligence_memory_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, index=True, nullable=False)
    snapshot = Column(Text, nullable=False)
    workspace_mode = Column(String, nullable=True)
    total_score = Column(Float, nullable=True)
    risk_drift = Column(String, nullable=True)
    regime = Column(String, nullable=True)
    concentration_score = Column(Float, nullable=True)
    dominant_driver = Column(String, nullable=True)
    volatility_state = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class IntelligenceRunLog(Base):
    __tablename__ = "intelligence_run_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id"), index=True, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, index=True, nullable=False)
    error = Column(Text, nullable=True)
    source = Column(String, default="scheduler", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class UserPreference(Base):
    """v3D: per-user preferences synced with frontend localStorage."""

    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    locale = Column(String, default="zh-TW", nullable=False)
    default_landing_page = Column(String, default="dashboard", nullable=False)
    compact_mode = Column(Boolean, default=True, nullable=False)
    terminal_mode = Column(Boolean, default=True, nullable=False)
    show_advanced_intelligence = Column(Boolean, default=False, nullable=False)
    alert_mode = Column(String, default="criticalOnly", nullable=False)
    notification_telegram = Column(Boolean, default=False, nullable=False)
    notification_email = Column(Boolean, default=False, nullable=False)
    risk_interpretation_mode = Column(String, default="balanced", nullable=False)
    active_account_id = Column(String, nullable=True)
    active_portfolio_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
