"""Regression tests for v4B Market Intelligence Engine."""
from __future__ import annotations

import re
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import CashPosition, Portfolio, StockPosition, User
from app.services.intelligence.engine_service import IntelligenceEngineService
from app.services.intelligence.engines.macro_news_risk_engine import MacroNewsRiskEngine
from app.services.intelligence.engines.market_regime_engine import MarketRegimeEngine
from app.services.intelligence.engines.portfolio_market_impact_engine import (
    PortfolioMarketImpactEngine,
)
from app.services.intelligence.engines.volatility_state_engine import (
    VolatilityStateEngine,
)
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    FCNSystemicRiskSummary,
    IntelligenceScore,
)
from app.services.news.schemas import NewsArticle


FORBIDDEN = re.compile(
    r"\b(buy|sell|add position|reduce position|target price|stop loss)\b|"
    r"買進|賣出|加碼|減碼|目標價|停損",
    re.IGNORECASE,
)


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


def _make_user(db, email="v4b@example.com"):
    user = User(id=f"user-{uuid4().hex}", email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_portfolio(db, user_id):
    pf = Portfolio(id=f"pf-{uuid4().hex}", user_id=user_id, name="P", base_currency="USD")
    db.add(pf)
    db.flush()
    db.add(StockPosition(portfolio_id=pf.id, symbol="MSFT", quantity=5, avg_price=300, current_value=1500))
    db.add(CashPosition(portfolio_id=pf.id, currency="USD", amount=500))
    db.commit()
    db.refresh(pf)
    return pf


# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------
def test_market_regime_data_limited_when_no_news():
    engine = MarketRegimeEngine()
    summary = engine.analyse({"scores": None, "articles": [], "fcn_analysis": []})
    assert summary.regime == "data_limited"
    assert FORBIDDEN.search(summary.narrative) is None


def test_market_regime_classifies_with_signals():
    engine = MarketRegimeEngine()
    summary = engine.analyse(
        {
            "scores": IntelligenceScore(
                ai_momentum_score=70, crypto_vol_score=20, fcn_risk_score=20, total_score=60
            ),
            "articles": [NewsArticle(symbol="NVDA", title="AI demand strong", impact="positive")],
            "fcn_analysis": [],
        }
    )
    assert summary.regime in MarketRegimeEngine.SUPPORTED
    assert FORBIDDEN.search(summary.narrative) is None


def test_market_regime_defensive_on_close_ki():
    engine = MarketRegimeEngine()
    summary = engine.analyse(
        {
            "scores": IntelligenceScore(fcn_risk_score=70, total_score=60),
            "articles": [NewsArticle(symbol="X", title="Headline", impact="neutral")],
            "fcn_analysis": [{"distance_to_KI": 0.04}],  # 4%
        }
    )
    assert summary.regime == "defensive"


# ---------------------------------------------------------------------------
# Volatility state
# ---------------------------------------------------------------------------
def test_volatility_data_limited_without_scores():
    engine = VolatilityStateEngine()
    summary = engine.analyse({"scores": None})
    assert summary.data_limited is True
    assert summary.overall_state == "data_limited"


def test_volatility_high_when_crypto_score_high():
    engine = VolatilityStateEngine()
    summary = engine.analyse(
        {
            "scores": IntelligenceScore(crypto_vol_score=80, ai_momentum_score=40),
            "fcn_analysis": [],
        }
    )
    assert summary.crypto_volatility_state == "high"
    assert summary.overall_state in {"elevated", "high"}


# ---------------------------------------------------------------------------
# Macro news
# ---------------------------------------------------------------------------
def test_macro_news_empty_articles_fail_soft():
    engine = MacroNewsRiskEngine()
    summary = engine.analyse({"articles": []})
    assert FORBIDDEN.search(summary.narrative) is None
    assert all(getattr(summary, field) == 0 for field in (
        "rates_pressure",
        "ai_pressure",
        "crypto_pressure",
        "geopolitics_pressure",
        "earnings_pressure",
        "macro_stress",
    ))


def test_macro_news_detects_themes():
    engine = MacroNewsRiskEngine()
    articles = [
        NewsArticle(symbol="X", title="Fed signals higher rates", impact="negative"),
        NewsArticle(symbol="NVDA", title="AI chip demand surges", impact="positive"),
        NewsArticle(symbol="BTC", title="Bitcoin crashes 10%", impact="negative"),
    ]
    summary = engine.analyse({"articles": articles})
    assert summary.rates_pressure > 0
    assert summary.ai_pressure > 0
    assert summary.crypto_pressure > 0
    theme_names = {theme.theme for theme in summary.top_themes}
    assert theme_names & {"rates", "ai", "crypto"}
    for theme in summary.top_themes:
        for headline in theme.sample_headlines:
            assert FORBIDDEN.search(headline) is None


# ---------------------------------------------------------------------------
# Portfolio market impact
# ---------------------------------------------------------------------------
def test_portfolio_market_impact_returns_safe_text():
    engine = PortfolioMarketImpactEngine()
    context = {
        "portfolio_payload": {
            "total_value": 10000,
            "fcn_value": 3000,
            "crypto_value": 1500,
            "stock_value": 4000,
            "cash_value": 1500,
        }
    }
    from app.services.intelligence.engines.market_regime_engine import MarketRegimeEngine
    regime = MarketRegimeEngine().analyse(
        {
            "scores": IntelligenceScore(fcn_risk_score=70, total_score=60),
            "articles": [NewsArticle(symbol="X", title="x", impact="negative")],
            "fcn_analysis": [{"distance_to_KI": 0.06}],
        }
    )
    impact = engine.analyse(
        context=context,
        concentration=ConcentrationSummary(risk_level="elevated", concentration_score=60, theme_pct=30),
        fcn_risk=FCNSystemicRiskSummary(risk_level="elevated", repeated_underlyings=["NVDA"], nearest_ki_pct=8),
        regime=regime,
        volatility=VolatilityStateEngine().analyse(
            {"scores": IntelligenceScore(crypto_vol_score=70), "fcn_analysis": []}
        ),
        macro=MacroNewsRiskEngine().analyse(
            {"articles": [NewsArticle(symbol="X", title="Fed hikes rates", impact="negative")]}
        ),
    )
    for field in (
        impact.fcn_impact,
        impact.crypto_impact,
        impact.equity_impact,
        impact.cash_buffer_interpretation,
    ):
        assert FORBIDDEN.search(field) is None
    assert impact.overall_impact_level in {"clear", "watch", "elevated", "critical"}


# ---------------------------------------------------------------------------
# End-to-end via service
# ---------------------------------------------------------------------------
def test_market_engine_summary_end_to_end(db_session):
    user = _make_user(db_session)
    portfolio = _make_portfolio(db_session, user.id)
    summary = IntelligenceEngineService(db_session).market_engine_summary(portfolio)
    assert summary.portfolio_id == portfolio.id
    assert summary.regime.regime in MarketRegimeEngine.SUPPORTED
    assert summary.volatility.overall_state in {
        "low",
        "normal",
        "elevated",
        "high",
        "data_limited",
    }
    for text in (
        summary.regime.narrative,
        summary.macro_news.narrative,
        summary.portfolio_impact.fcn_impact,
        summary.portfolio_impact.crypto_impact,
        summary.portfolio_impact.equity_impact,
        summary.portfolio_impact.cash_buffer_interpretation,
    ):
        assert FORBIDDEN.search(text or "") is None
