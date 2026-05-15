from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import CashPosition, Portfolio, StockPosition, User
from app.services.intelligence.drift_engine_v2 import DriftDetectionV2Engine
from app.services.intelligence.explainability_engine import ExplainabilityEngine
from app.services.intelligence.exposure_engine import ExposureIntelligenceEngine
from app.services.intelligence.regime_engine import PortfolioRegimeEngine
from app.services.intelligence.schemas import (
    IntelligenceNarrative,
    IntelligenceScore,
    PortfolioSummaryV2AResponse,
    WorkspaceDecision,
)
from app.services.news.schemas import NewsArticle


@pytest.fixture()
def isolated_session_factory(tmp_path):
    db_path = tmp_path / "v2a.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(isolated_session_factory):
    db = isolated_session_factory()
    try:
        yield db
    finally:
        db.close()


def test_regime_detection_ai_momentum():
    payload = {
        "total_value": 100000,
        "crypto_value": 0,
    }
    exposure = {"ai_theme_concentration": 42, "high_beta_concentration": 20}
    regime = PortfolioRegimeEngine().detect(
        payload,
        IntelligenceScore(ai_momentum_score=62, total_score=45),
        [NewsArticle(symbol="NVDA", title="AI demand strong", impact="positive")],
        [],
        exposure,
    )
    assert regime == "AI_MOMENTUM"


def test_exposure_intelligence_concentration_score():
    payload = {
        "total_value": 100000,
        "stock_positions": [
            {"symbol": "NVDA", "current_value": 45000},
            {"symbol": "AAPL", "current_value": 10000},
        ],
        "crypto_positions": [{"symbol": "BTC", "current_value": 15000}],
        "fcn_positions": [{"fcn_code": "FCN1", "notional_amount": 20000}],
    }
    result = ExposureIntelligenceEngine().analyze(payload, [{"worst_symbol": "NVDA"}])
    assert result["single_stock_exposure"] == 45
    assert result["ai_theme_concentration"] >= 55
    assert result["concentration_score"] > 50
    assert "NVDA" in result["top_correlated_symbols"]


def test_drift_detection_v2_regime_shift():
    drift = DriftDetectionV2Engine().detect(
        "CRYPTO_SPECULATIVE",
        {"concentration_score": 55, "crypto_concentration": 20, "thematic_exposure_summary": "crypto 20%"},
        "crypto volatility increasing",
        [{"regime": "AI_MOMENTUM", "concentration_score": 30, "volatility_state": "NORMAL"}],
    )
    assert drift["regime_drift"] == "AI_MOMENTUM → CRYPTO_SPECULATIVE"
    assert drift["exposure_drift"] == "INCREASING"
    assert "漂移" in drift["drift_summary"]


def test_explainability_no_trading_instruction():
    explanation = ExplainabilityEngine().explain(
        "HIGH_VOLATILITY",
        {"concentration_score": 60, "fcn_correlated_exposure": 25, "top_correlated_symbols": ["MDB"]},
        {"exposure_drift": "INCREASING", "drift_summary": "risk rising", "volatility_drift": "NORMAL → HIGH_VOL"},
        [NewsArticle(symbol="MDB", title="MDB downgrade", impact="negative", is_fcn_related=True)],
        [{"worst_symbol": "MDB"}],
    )
    text = " ".join(explanation.model_dump().values()).lower()
    assert "buy" not in text
    assert "sell" not in text
    assert explanation.dominant_driver


def test_portfolio_summary_endpoint_contract(monkeypatch, db_session):
    from app.api.v1.endpoints import intelligence

    suffix = uuid4().hex
    user = User(id=f"user-{suffix}", email=f"v2a-{suffix}@ixai.local", hashed_password="hash")
    portfolio = Portfolio(id=f"portfolio-{suffix}", user_id=user.id, name="V2A", base_currency="USD")
    db_session.add(user)
    db_session.add(portfolio)
    db_session.add(StockPosition(portfolio_id=portfolio.id, symbol="NVDA", quantity=1, avg_price=100, current_value=100))
    db_session.add(CashPosition(portfolio_id=portfolio.id, currency="USD", amount=1000))
    db_session.commit()

    def _fake_summary(self, portfolio_arg):
        assert portfolio_arg.id == portfolio.id
        return PortfolioSummaryV2AResponse(
            regime="AI_MOMENTUM",
            dominant_risk="AI concentration",
            concentration_score=50,
            drift_summary="stable",
            top_alerts=["NVDA alert"],
            intelligence_confidence=75,
            generated_at="2026-05-15T00:00:00Z",
        )

    monkeypatch.setattr(intelligence.PortfolioIntelligenceService, "get_portfolio_summary_v2a", _fake_summary)
    response = intelligence.get_portfolio_summary_v2a(db=db_session, current_user=user)
    assert response.regime == "AI_MOMENTUM"
    assert response.concentration_score == 50
    assert response.explainability is not None


def test_portfolio_summary_fail_soft(monkeypatch, db_session):
    from app.services.intelligence.service import PortfolioIntelligenceService

    suffix = uuid4().hex
    user = User(id=f"user-{suffix}", email=f"soft-{suffix}@ixai.local", hashed_password="hash")
    portfolio = Portfolio(id=f"portfolio-{suffix}", user_id=user.id, name="Soft", base_currency="USD")
    db_session.add(user)
    db_session.add(portfolio)
    db_session.commit()

    service = PortfolioIntelligenceService(db_session)
    monkeypatch.setattr(service, "_analysis_context", lambda portfolio_arg: (_ for _ in ()).throw(RuntimeError("boom")))
    response = service.get_portfolio_summary_v2a(portfolio)
    assert response.is_stale is True


def test_snapshot_persistence_v2a_metadata(monkeypatch, isolated_session_factory):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)
    store = pm.IntelligenceMemoryStore()
    store.append_snapshot(
        "portfolio-v2a",
        IntelligenceScore(total_score=66),
        WorkspaceDecision(workspace_mode="AI_MOMENTUM", risk_drift="Increasing"),
        IntelligenceNarrative(risk_narrative="risk rising"),
        [],
        metadata={
            "regime": "AI_MOMENTUM",
            "concentration_score": 72,
            "dominant_driver": "AI concentration",
            "volatility_state": "ELEVATED",
        },
    )
    history = store.get_recent_history("portfolio-v2a", limit=1)
    assert history[0]["regime"] == "AI_MOMENTUM"
    assert history[0]["concentration_score"] == 72
