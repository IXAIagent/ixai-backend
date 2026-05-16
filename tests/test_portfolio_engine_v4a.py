"""Regression tests for v4A Portfolio Intelligence Engine."""
from __future__ import annotations

import re
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    CashPosition,
    CryptoPosition,
    FCNPosition,
    Portfolio,
    StockPosition,
    User,
)
from app.services.intelligence.engine_service import IntelligenceEngineService
from app.services.intelligence.engines.concentration_engine import ConcentrationEngine
from app.services.intelligence.engines.exposure_graph_engine import ExposureGraphEngine
from app.services.intelligence.engines.fcn_systemic_risk_engine import (
    FCNSystemicRiskEngine,
)
from app.services.intelligence.engines.intelligence_score_engine import (
    IntelligenceScoreEngine,
)
from app.services.intelligence.engines.portfolio_drift_engine import (
    PortfolioDriftEngine,
)
from app.services.intelligence.engines.risk_propagation_engine import (
    RiskPropagationEngine,
)
from app.services.intelligence.schemas import IntelligenceScore


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


def _make_user(db, email="v4a@example.com"):
    user = User(id=f"user-{uuid4().hex}", email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_portfolio(db, user_id, *, with_positions=True, with_repeated_fcn=False):
    pf = Portfolio(id=f"pf-{uuid4().hex}", user_id=user_id, name="P", base_currency="USD")
    db.add(pf)
    db.flush()
    if with_positions:
        db.add(StockPosition(portfolio_id=pf.id, symbol="NVDA", quantity=10, avg_price=400, current_price=420, current_value=4200))
        db.add(StockPosition(portfolio_id=pf.id, symbol="MSFT", quantity=5, avg_price=300, current_price=320, current_value=1600))
        db.add(CryptoPosition(portfolio_id=pf.id, symbol="BTCUSDT", asset_type="spot", quantity=0.1, avg_price=50000, current_value=5000))
        db.add(CashPosition(portfolio_id=pf.id, currency="USD", amount=2000))
        underlyings = '[{"symbol":"NVDA"},{"symbol":"TSM"}]'
        db.add(
            FCNPosition(
                portfolio_id=pf.id,
                fcn_code="FCN-001",
                notional_amount=3000,
                underlyings=underlyings,
                worst_of_symbol="NVDA",
                ki_level=0.7,
                distance_to_ki_pct=12.0,
                risk_level="medium",
            )
        )
        if with_repeated_fcn:
            db.add(
                FCNPosition(
                    portfolio_id=pf.id,
                    fcn_code="FCN-002",
                    notional_amount=3000,
                    underlyings=underlyings,
                    worst_of_symbol="TSM",
                    ki_level=0.7,
                    distance_to_ki_pct=4.0,  # critical KI
                    risk_level="high",
                )
            )
    db.commit()
    db.refresh(pf)
    return pf


# ---------------------------------------------------------------------------
# Engine output shape
# ---------------------------------------------------------------------------
def test_engine_summary_non_empty_for_populated_portfolio(db_session):
    user = _make_user(db_session)
    portfolio = _make_portfolio(db_session, user.id)

    summary = IntelligenceEngineService(db_session).portfolio_engine_summary(portfolio)

    assert summary.portfolio_id == portfolio.id
    assert len(summary.exposure_graph.nodes) > 0
    assert summary.concentration.concentration_score > 0
    assert summary.unified_score.risk_state in {"clear", "watch", "elevated", "critical"}
    assert summary.unified_score.confidence >= 0
    assert summary.is_stale is False


def test_engine_summary_empty_portfolio_does_not_crash(db_session):
    user = _make_user(db_session, "empty@example.com")
    portfolio = _make_portfolio(db_session, user.id, with_positions=False)

    summary = IntelligenceEngineService(db_session).portfolio_engine_summary(portfolio)

    assert summary.portfolio_id == portfolio.id
    assert summary.unified_score.risk_state in {"clear", "watch", "elevated", "critical"}


# ---------------------------------------------------------------------------
# FCN repeated underlying + concentration
# ---------------------------------------------------------------------------
def test_fcn_repeated_underlying_detection(db_session):
    user = _make_user(db_session, "repeat@example.com")
    portfolio = _make_portfolio(db_session, user.id, with_repeated_fcn=True)

    summary = IntelligenceEngineService(db_session).portfolio_engine_summary(portfolio)

    repeated_set = set(summary.exposure_graph.repeated_underlyings)
    assert "NVDA" in repeated_set or "TSM" in repeated_set
    assert summary.fcn_systemic_risk.risk_level in {"watch", "elevated", "critical"}


def test_concentration_risk_level_responds_to_inputs():
    engine = ConcentrationEngine()
    high_context = {
        "portfolio_payload": {
            "total_value": 10000,
            "cash_value": 0,
            "stock_positions": [{"symbol": "NVDA", "current_value": 9500}],
            "crypto_positions": [],
            "fcn_positions": [],
        },
        "fcn_analysis": [],
    }
    low_context = {
        "portfolio_payload": {
            "total_value": 10000,
            "cash_value": 3000,
            "stock_positions": [
                {"symbol": "AAPL", "current_value": 1500},
                {"symbol": "MSFT", "current_value": 1500},
            ],
            "crypto_positions": [],
            "fcn_positions": [],
        },
        "fcn_analysis": [],
    }
    high = engine.analyse(high_context)
    low = engine.analyse(low_context)
    assert high.concentration_score > low.concentration_score
    assert high.risk_level in {"elevated", "critical"}
    assert low.risk_level in {"clear", "watch"}


def test_exposure_graph_builds_themes_and_risk_factors():
    engine = ExposureGraphEngine()
    context = {
        "portfolio_payload": {
            "total_value": 10000,
            "stock_positions": [
                {"symbol": "NVDA", "current_value": 4000},
                {"symbol": "AAPL", "current_value": 1000},
            ],
            "crypto_positions": [{"symbol": "BTCUSDT", "current_value": 2000}],
            "fcn_positions": [],
        },
        "fcn_analysis": [
            {
                "fcn_code": "FCN-A",
                "underlyings": [{"symbol": "NVDA"}, {"symbol": "AMD"}],
            }
        ],
    }
    exposure = engine.analyse(context)
    labels = {node.label for node in exposure.nodes}
    edge_types = {edge.edge_type for edge in exposure.edges}
    assert "NVDA" in labels and "AI_CHIP" in labels
    assert "asset_in_theme" in edge_types and "fcn_underlying" in edge_types
    assert "AI_THEME_RISK" in labels


def test_drift_engine_handles_no_history():
    drift = PortfolioDriftEngine()
    summary = drift.analyse(
        portfolio_id="pf-none",
        current_concentration=ConcentrationEngine().analyse(
            {
                "portfolio_payload": {
                    "total_value": 1000,
                    "cash_value": 200,
                    "stock_positions": [{"symbol": "AAPL", "current_value": 800}],
                    "crypto_positions": [],
                    "fcn_positions": [],
                },
                "fcn_analysis": [],
            }
        ),
        current_regime="defensive",
        current_volatility_state="normal",
        current_fcn_pressure=0,
    )
    assert summary.history_window == 0
    assert summary.allocation_drift in {"UNCHANGED", "STABLE", "INCREASING", "DECREASING"}


def test_risk_propagation_handles_empty_inputs():
    engine = RiskPropagationEngine()
    summary = engine.analyse(
        exposure=ExposureGraphEngine().analyse(
            {"portfolio_payload": {"total_value": 0}, "fcn_analysis": []}
        ),
        concentration=ConcentrationEngine().analyse(
            {"portfolio_payload": {"total_value": 0}, "fcn_analysis": []}
        ),
        fcn_risk=FCNSystemicRiskEngine().analyse({"fcn_analysis": []}),
        drift=PortfolioDriftEngine().analyse(
            portfolio_id="x",
            current_concentration=ConcentrationEngine().analyse(
                {"portfolio_payload": {"total_value": 0}, "fcn_analysis": []}
            ),
            current_regime="defensive",
            current_volatility_state="normal",
            current_fcn_pressure=0,
        ),
    )
    assert FORBIDDEN.search(summary.summary) is None
    for chain in summary.chains:
        assert FORBIDDEN.search(chain.explanation) is None


def test_unified_score_aggregation_returns_valid_band():
    aggregator = IntelligenceScoreEngine()
    score = aggregator.aggregate(
        scores=IntelligenceScore(total_score=60, fcn_risk_score=70),
        exposure=ExposureGraphEngine().analyse(
            {
                "portfolio_payload": {
                    "total_value": 10000,
                    "stock_positions": [
                        {"symbol": "NVDA", "current_value": 4000},
                        {"symbol": "TSLA", "current_value": 2000},
                    ],
                    "crypto_positions": [],
                    "fcn_positions": [],
                },
                "fcn_analysis": [],
            }
        ),
        concentration=ConcentrationEngine().analyse(
            {
                "portfolio_payload": {
                    "total_value": 10000,
                    "cash_value": 0,
                    "stock_positions": [{"symbol": "NVDA", "current_value": 6000}],
                    "crypto_positions": [],
                    "fcn_positions": [],
                },
                "fcn_analysis": [],
            }
        ),
        fcn_risk=FCNSystemicRiskEngine().analyse({"fcn_analysis": []}),
        drift=PortfolioDriftEngine().analyse(
            portfolio_id="x",
            current_concentration=ConcentrationEngine().analyse(
                {"portfolio_payload": {"total_value": 0}, "fcn_analysis": []}
            ),
            current_regime="defensive",
            current_volatility_state="normal",
            current_fcn_pressure=0,
        ),
        volatility_score=40.0,
    )
    assert score.risk_state in {"clear", "watch", "elevated", "critical"}
    assert 0 <= score.total_intelligence_score <= 100


# ---------------------------------------------------------------------------
# Compliance: every free-text field stays clean
# ---------------------------------------------------------------------------
def test_no_forbidden_wording_in_engine_summary(db_session):
    user = _make_user(db_session, "compliance@example.com")
    portfolio = _make_portfolio(db_session, user.id, with_repeated_fcn=True)
    summary = IntelligenceEngineService(db_session).portfolio_engine_summary(portfolio)
    free_text_fields = [
        summary.drift.drift_summary,
        summary.risk_propagation.summary,
        *[chain.explanation for chain in summary.risk_propagation.chains],
        summary.concentration.top_concentration_label,
    ]
    for text in free_text_fields:
        assert FORBIDDEN.search(text or "") is None, text


# ---------------------------------------------------------------------------
# Permission contract via endpoint dependency
# ---------------------------------------------------------------------------
def test_engine_endpoint_uses_resolver_dependency(db_session):
    """The endpoint uses resolve_portfolio_for_user, so cross-user access
    must reuse the v3C permission helper. Smoke check the helper directly
    so the contract stays guarded here too."""
    from app.api.deps import user_can_access_portfolio

    owner = _make_user(db_session, "owner-v4a@example.com")
    other = _make_user(db_session, "other-v4a@example.com")
    portfolio = _make_portfolio(db_session, owner.id)
    assert user_can_access_portfolio(db_session, owner, portfolio) is True
    assert user_can_access_portfolio(db_session, other, portfolio) is False
