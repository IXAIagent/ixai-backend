from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Portfolio, StockPosition, User
from app.services.intelligence.timeline_intelligence_engine import TimelineIntelligenceEngine


class FakeStore:
    def __init__(self, history):
        self.history = history

    def get_recent_history(self, portfolio_id: str, limit: int = 200):
        return list(self.history)


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
        engine.dispose()


def _history_row(days_ago: int, regime: str, score: float, concentration: float, driver: str, volatility: str = "NORMAL"):
    generated_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "generated_at": generated_at.isoformat(),
        "regime": regime,
        "workspace_mode": regime,
        "concentration_score": concentration,
        "dominant_driver": driver,
        "volatility_state": volatility,
        "scores": {"total_score": score},
        "top_alerts": [{"title": driver}],
    }


def test_timeline_no_history_fallback():
    response = TimelineIntelligenceEngine(FakeStore([])).analyze("portfolio-empty")

    assert response.is_stale is True
    assert response.confidence < 45
    assert "歷史資料仍在累積" in response.message
    assert {window.window for window in response.windows} == {"7d", "30d", "90d"}


def test_timeline_windows_output():
    history = [
        _history_row(80, "DEFENSIVE", 20, 20, "cash buffer"),
        _history_row(20, "AI_MOMENTUM", 35, 35, "AI concentration"),
        _history_row(6, "AI_MOMENTUM", 50, 48, "AI concentration"),
        _history_row(1, "HIGH_VOLATILITY", 66, 62, "crypto volatility", "ELEVATED"),
    ]

    response = TimelineIntelligenceEngine(FakeStore(history)).analyze("portfolio-1")
    windows = {window.window: window for window in response.windows}

    assert response.is_stale is False
    assert windows["7d"].risk_score_trend == "RISK_RISING"
    assert windows["30d"].concentration_trend == "CONCENTRATION_RISING"
    assert windows["90d"].regime_evolution == "DEFENSIVE → HIGH_VOLATILITY"


def test_timeline_regime_evolution_and_concentration_trend():
    history = [
        _history_row(10, "RISK_ON", 30, 25, "AI concentration"),
        _history_row(1, "CRYPTO_SPECULATIVE", 45, 55, "crypto volatility"),
    ]

    response = TimelineIntelligenceEngine(FakeStore(history)).analyze("portfolio-2")

    assert response.regime_evolution == "RISK_ON → CRYPTO_SPECULATIVE"
    assert response.concentration_trend == "CONCENTRATION_RISING"
    assert "集中度" in response.timeline_summary


def test_timeline_compliance_filter_sanitizes_output():
    history = [
        _history_row(10, "DEFENSIVE", 30, 20, "buy target price"),
        _history_row(1, "HIGH_VOLATILITY", 50, 40, "sell stop loss", "ELEVATED"),
    ]

    response = TimelineIntelligenceEngine(FakeStore(history)).analyze("portfolio-3")
    text = " ".join([
        response.timeline_summary,
        *response.dominant_driver_history,
        *response.recurring_risks,
        *response.deteriorating_signals,
    ]).lower()

    assert "buy" not in text
    assert "sell" not in text
    assert "target price" not in text
    assert "stop loss" not in text


def test_timeline_endpoint_route_exists():
    from app.main import app

    assert "/api/v1/intelligence/timeline" in [route.path for route in app.routes]


def test_scheduler_skip_news_still_success(monkeypatch, db_session):
    from app.scheduler import intelligence_runner
    from app.services.intelligence.schemas import PortfolioSummaryV2AResponse

    suffix = uuid4().hex
    user = User(id=f"user-{suffix}", email=f"v2c-{suffix}@ixai.local", hashed_password="hash")
    portfolio = Portfolio(id=f"portfolio-{suffix}", user_id=user.id, name="V2C", base_currency="USD")
    db_session.add(user)
    db_session.add(portfolio)
    db_session.add(StockPosition(portfolio_id=portfolio.id, symbol="AAPL", quantity=1, avg_price=100))
    db_session.commit()

    class FakeService:
        def __init__(self, db, skip_news: bool = False):
            assert skip_news is True

        def get_portfolio_summary_v2a(self, portfolio_arg):
            assert portfolio_arg.id == portfolio.id
            return PortfolioSummaryV2AResponse(
                regime="BALANCED",
                dominant_risk="No dominant risk",
                concentration_score=10,
                drift_summary="Stable",
                generated_at=datetime.now(timezone.utc),
                is_stale=False,
            )

    monkeypatch.setattr(intelligence_runner, "PortfolioIntelligenceService", FakeService)
    monkeypatch.setattr(intelligence_runner.settings, "INTELLIGENCE_SCHEDULER_SKIP_NEWS", True)

    result = intelligence_runner.run_intelligence_scheduler_once(db=db_session)

    assert result["status"] == "success"
    assert result["success"] == 1


def test_yfinance_rate_limit_cooldown_not_crash(monkeypatch):
    from app.services.news.providers import yfinance_provider

    calls = {"count": 0}

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def news(self):
            calls["count"] += 1
            raise Exception("YFRateLimitError: Too Many Requests")

    yfinance_provider.YFinanceNewsProvider._cache.clear()
    yfinance_provider.YFinanceNewsProvider._cooldown.clear()
    monkeypatch.setattr(yfinance_provider.yf, "Ticker", FakeTicker)

    provider = yfinance_provider.YFinanceNewsProvider()
    assert provider.get_news("AAPL") == []
    assert provider.get_news("AAPL") == []
    assert calls["count"] == 1
