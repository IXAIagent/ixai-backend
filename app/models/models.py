from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String
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


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    base_currency = Column(String, default="USD", nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="portfolios")
    stocks = relationship("StockPosition", back_populates="portfolio", cascade="all, delete-orphan")
    fcn_positions = relationship("FCNPosition", back_populates="portfolio", cascade="all, delete-orphan")
    crypto_positions = relationship("CryptoPosition", back_populates="portfolio", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="portfolio", cascade="all, delete-orphan")


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
    notional = Column(Float, nullable=True)
    notional_amount = Column(Float, nullable=True)
    worst_of_symbol = Column(String, nullable=True)
    distance_to_ki_pct = Column(Float, nullable=True)
    distance_to_ko_pct = Column(Float, nullable=True)
    risk_level = Column(String, default="low", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="fcn_positions")


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
