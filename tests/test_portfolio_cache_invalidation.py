from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.portfolio_input import StockInput
from app.core.cache import analysis_context_cache, engine_summary_cache
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.models import Portfolio, StockPosition, User
from app.services.intelligence.schemas import PortfolioEngineSummaryResponse
from app.services.intelligence.service import PortfolioIntelligenceService
from app.services.market_data.base import utc_now_iso
from app.services.news.schemas import PortfolioNewsResponse
from app.services.news.service import NewsService


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
    analysis_context_cache.clear()
    engine_summary_cache.clear()
    try:
        yield TestClient(app), TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        analysis_context_cache.clear()
        engine_summary_cache.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _user_with_portfolio(session_factory, label: str):
    db = session_factory()
    try:
        user = User(id=f"{label}-user", email=f"{label}@ixai.local", hashed_password="hash")
        portfolio = Portfolio(
            id=f"{label}-portfolio",
            user_id=user.id,
            name=f"{label} Portfolio",
            base_currency="USD",
        )
        db.add_all([user, portfolio])
        db.commit()
        return user.id, portfolio.id
    finally:
        db.close()


def _auth(user_id: str):
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def test_create_position_invalidates_only_affected_portfolio_cache(client_db):
    client, session_factory = client_db
    user_id, portfolio_id = _user_with_portfolio(session_factory, "owner")
    _, other_portfolio_id = _user_with_portfolio(session_factory, "other")
    analysis_context_cache.set(("analysis_context", portfolio_id), {"stale": True})
    analysis_context_cache.set(("analysis_context", other_portfolio_id), {"stale": True})
    engine_summary_cache.set(
        ("engine", "portfolio", portfolio_id, "en"),
        PortfolioEngineSummaryResponse(generated_at=utc_now_iso()),
    )
    engine_summary_cache.set(
        ("engine", "portfolio", other_portfolio_id, "en"),
        PortfolioEngineSummaryResponse(generated_at=utc_now_iso()),
    )

    response = client.post(
        "/api/v1/portfolio/stock",
        headers=_auth(user_id),
        json={"symbol": "AAPL", "quantity": 2, "avg_price": 100, "current_price": 110},
    )

    assert response.status_code == 200
    assert analysis_context_cache.get(("analysis_context", portfolio_id)) is None
    assert engine_summary_cache.get(("engine", "portfolio", portfolio_id, "en")) is None
    assert analysis_context_cache.get(("analysis_context", other_portfolio_id)) == {"stale": True}
    assert engine_summary_cache.get(("engine", "portfolio", other_portfolio_id, "en")) is not None


def test_delete_position_invalidates_portfolio_cache(client_db):
    client, session_factory = client_db
    user_id, portfolio_id = _user_with_portfolio(session_factory, "owner")
    db = session_factory()
    try:
        stock = StockPosition(
            portfolio_id=portfolio_id,
            symbol="MSFT",
            quantity=1,
            avg_price=100,
            current_price=100,
        )
        db.add(stock)
        db.commit()
        stock_id = stock.id
    finally:
        db.close()

    analysis_context_cache.set(("analysis_context", portfolio_id), {"stale": True})
    engine_summary_cache.set(
        ("engine", "market", portfolio_id, "zh-TW"),
        PortfolioEngineSummaryResponse(generated_at=utc_now_iso()),
    )

    response = client.delete(f"/api/v1/portfolio/stocks/{stock_id}", headers=_auth(user_id))

    assert response.status_code == 200
    assert analysis_context_cache.get(("analysis_context", portfolio_id)) is None
    assert engine_summary_cache.get(("engine", "market", portfolio_id, "zh-TW")) is None


def test_subsequent_analysis_context_reflects_position_after_write(client_db, monkeypatch):
    client, session_factory = client_db
    user_id, portfolio_id = _user_with_portfolio(session_factory, "owner")
    analysis_context_cache.set(
        ("analysis_context", portfolio_id),
        {"portfolio_payload": {"stock_positions": []}},
    )

    def fake_news(self, portfolio):
        return PortfolioNewsResponse(
            portfolio_id=str(portfolio.id),
            portfolio_name=str(portfolio.name),
            articles=[],
            summary="test",
            fetched_at=utc_now_iso(),
            is_stale=False,
        )

    monkeypatch.setattr(NewsService, "get_portfolio_news", fake_news)

    response = client.post(
        "/api/v1/portfolio/stock",
        headers=_auth(user_id),
        json={"symbol": "AAPL", "quantity": 3, "avg_price": 100, "current_price": 120},
    )
    assert response.status_code == 200

    db = session_factory()
    try:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        context = PortfolioIntelligenceService(db)._analysis_context(portfolio)
    finally:
        db.close()

    stock_positions = context["portfolio_payload"]["stock_positions"]
    assert len(stock_positions) == 1
    assert stock_positions[0]["symbol"] == "AAPL"
    assert stock_positions[0]["quantity"] == 3
