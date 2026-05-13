from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.dashboard import get_my_risk_overview, get_summary
from app.core.database import Base
from app.models.models import CashPosition, Portfolio, StockPosition, User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def minimal_portfolio(db_session):
    suffix = uuid4().hex
    user = User(
        id=f"user-{suffix}",
        email=f"contract-{suffix}@ixai.local",
        hashed_password="test-password-hash",
    )
    portfolio = Portfolio(
        id=f"portfolio-{suffix}",
        user_id=user.id,
        name="Contract Smoke Portfolio",
        base_currency="USD",
    )
    stock = StockPosition(
        id=f"stock-{suffix}",
        portfolio_id=portfolio.id,
        symbol="AAPL",
        quantity=10,
        avg_price=180,
        current_price=180,
        current_value=1800,
    )
    cash = CashPosition(
        id=f"cash-{suffix}",
        portfolio_id=portfolio.id,
        currency="USD",
        amount=2700,
    )

    db_session.add(user)
    db_session.add(portfolio)
    db_session.add(stock)
    db_session.add(cash)
    db_session.commit()

    return user, portfolio


def test_dashboard_summary_contract(db_session, minimal_portfolio):
    _, portfolio = minimal_portfolio

    response = get_summary(portfolio=portfolio, db=db_session)

    for field in [
        "total_value",
        "stock_ratio",
        "crypto_ratio",
        "risk_level",
        "ai_advice",
        "alerts",
    ]:
        assert field in response

    assert isinstance(response["alerts"], list)
    assert isinstance(response["ai_advice"], str)


def test_dashboard_risk_overview_contract(db_session, minimal_portfolio):
    user, _ = minimal_portfolio

    response = get_my_risk_overview(db=db_session, current_user=user)

    for field in [
        "risk_score",
        "risk_level",
        "top_risk",
        "decision_cards",
        "alerts",
        "ai_advice",
    ]:
        assert field in response

    assert isinstance(response["risk_score"], int | float)
    assert isinstance(response["decision_cards"], list)
    assert isinstance(response["alerts"], list)
    assert isinstance(response["ai_advice"], str)
