from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.models import Portfolio, StockPosition, User
from app.services.fcn_schedule_service import build_fcn_schedule


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
      db = TestingSessionLocal()
      try:
          yield db
      finally:
          db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _user_with_portfolio(session_factory, label: str):
    db = session_factory()
    try:
        user = User(id=f"{label}-user", email=f"{label}@ixai.local", hashed_password="hash")
        portfolio = Portfolio(id=f"{label}-portfolio", user_id=user.id, name=f"{label} Portfolio", base_currency="USD")
        db.add_all([user, portfolio])
        db.commit()
        return user.id, portfolio.id
    finally:
        db.close()


def _auth(user_id: str):
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def test_user_can_delete_own_stock_position(client_db):
    client, session_factory = client_db
    user_id, portfolio_id = _user_with_portfolio(session_factory, "owner")
    db = session_factory()
    try:
        stock = StockPosition(portfolio_id=portfolio_id, symbol="AAPL", quantity=1, avg_price=100, current_price=100)
        db.add(stock)
        db.commit()
        stock_id = stock.id
    finally:
        db.close()

    response = client.delete(f"/api/v1/portfolio/stocks/{stock_id}", headers=_auth(user_id))

    assert response.status_code == 200
    db = session_factory()
    try:
        assert db.query(StockPosition).filter(StockPosition.id == stock_id).first() is None
    finally:
        db.close()


def test_user_cannot_delete_another_users_position(client_db):
    client, session_factory = client_db
    owner_id, portfolio_id = _user_with_portfolio(session_factory, "owner")
    outsider_id, _ = _user_with_portfolio(session_factory, "outsider")
    db = session_factory()
    try:
        stock = StockPosition(portfolio_id=portfolio_id, symbol="MSFT", quantity=1, avg_price=100, current_price=100)
        db.add(stock)
        db.commit()
        stock_id = stock.id
    finally:
        db.close()

    response = client.delete(f"/api/v1/portfolio/stocks/{stock_id}", headers=_auth(outsider_id))

    assert response.status_code == 404
    db = session_factory()
    try:
        assert db.query(StockPosition).filter(StockPosition.id == stock_id).first() is not None
    finally:
        db.close()
    assert owner_id == "owner-user"


def test_delete_missing_position_returns_404(client_db):
    client, session_factory = client_db
    user_id, _ = _user_with_portfolio(session_factory, "owner")

    response = client.delete("/api/v1/portfolio/stocks/missing-id", headers=_auth(user_id))

    assert response.status_code == 404


def test_fcn_schedule_generation_business_day_lag():
    rows = build_fcn_schedule(
        start_date=date(2026, 5, 16),
        tenor_months=3,
        frequency="monthly",
        payment_lag_days=3,
    )

    assert len(rows) == 3
    assert rows[0]["observation_date"] == date(2026, 6, 16)
    assert rows[0]["payment_date"].weekday() < 5


def test_add_fcn_generates_schedule(client_db):
    client, session_factory = client_db
    user_id, _ = _user_with_portfolio(session_factory, "owner")

    response = client.post(
        "/api/v1/portfolio/fcn",
        headers=_auth(user_id),
        json={
            "name": "FCN100",
            "notional_amount": 100000,
            "underlying_details": [{"symbol": "MDB"}],
            "issue_date": "2026-05-16",
            "tenor_months": 3,
            "coupon_frequency": "monthly",
            "coupon_payment_lag_days": 3,
            "strike_level": 80,
            "ki_level": 60,
            "ko_level": 100,
        },
    )

    assert response.status_code == 200
    fcn_id = response.json()["id"]
    schedule = client.get(f"/api/v1/portfolio/fcn/{fcn_id}/schedule", headers=_auth(user_id))

    assert schedule.status_code == 200
    assert len(schedule.json()) == 3
