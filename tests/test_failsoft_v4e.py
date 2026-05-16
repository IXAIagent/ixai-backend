"""v4E: engine orchestrator fail-soft / degraded status tests."""
from __future__ import annotations

import re
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.cache import analysis_context_cache, engine_summary_cache
from app.core.database import Base
from app.models.models import CashPosition, Portfolio, StockPosition, User
from app.services.intelligence.engine_service import IntelligenceEngineService


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
    # ensure isolation: clear process-wide cache between tests
    analysis_context_cache.clear()
    engine_summary_cache.clear()


def _make_user(db, email="failsoft@example.com"):
    user = User(id=f"user-{uuid4().hex}", email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_portfolio(db, user_id):
    pf = Portfolio(id=f"pf-{uuid4().hex}", user_id=user_id, name="P", base_currency="USD")
    db.add(pf)
    db.flush()
    db.add(StockPosition(portfolio_id=pf.id, symbol="NVDA", quantity=5, avg_price=400, current_value=2000))
    db.add(CashPosition(portfolio_id=pf.id, currency="USD", amount=1000))
    db.commit()
    db.refresh(pf)
    return pf


# ---------------------------------------------------------------------------
# Healthy path
# ---------------------------------------------------------------------------
def test_engine_summary_status_healthy_for_normal_portfolio(db_session):
    user = _make_user(db_session)
    portfolio = _make_portfolio(db_session, user.id)
    summary = IntelligenceEngineService(db_session).portfolio_engine_summary(portfolio)
    assert summary.status == "healthy"
    assert summary.failed_engines == []
    assert summary.stale_reason == ""
    assert summary.degraded_reason == ""
    assert summary.locale in {"en", "zh-TW"}


# ---------------------------------------------------------------------------
# Single engine failure → partial
# ---------------------------------------------------------------------------
def test_single_engine_failure_marks_partial(db_session, monkeypatch):
    user = _make_user(db_session, "partial@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)

    def boom(_context):
        raise RuntimeError("simulated drift fail")

    monkeypatch.setattr(service.drift, "analyse", boom)

    summary = service.portfolio_engine_summary(portfolio)
    assert summary.status == "partial"
    assert "drift" in summary.failed_engines
    assert summary.is_stale is False  # partial keeps response usable
    assert summary.degraded_reason.startswith("engine_failed:")


# ---------------------------------------------------------------------------
# Multi engine failure → degraded
# ---------------------------------------------------------------------------
def test_multiple_engine_failures_mark_degraded(db_session, monkeypatch):
    user = _make_user(db_session, "degraded@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated")

    monkeypatch.setattr(service.drift, "analyse", boom)
    monkeypatch.setattr(service.risk_propagation, "analyse", boom)
    monkeypatch.setattr(service.score_aggregator, "aggregate", boom)

    summary = service.portfolio_engine_summary(portfolio)
    assert summary.status == "degraded"
    assert len(summary.failed_engines) >= 2
    assert summary.is_stale is True
    assert summary.stale_reason == "multiple_engines_failed"
    # No forbidden wording anywhere even when degraded
    for text in (
        summary.degraded_reason,
        summary.stale_reason,
        summary.risk_propagation.summary,
    ):
        assert FORBIDDEN.search(text or "") is None


# ---------------------------------------------------------------------------
# Context unavailable → unavailable status
# ---------------------------------------------------------------------------
def test_context_unavailable_returns_unavailable(db_session, monkeypatch):
    user = _make_user(db_session, "unavail@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)

    def boom(_portfolio):
        raise RuntimeError("simulated context fail")

    monkeypatch.setattr(service.intelligence, "_analysis_context", boom)

    summary = service.portfolio_engine_summary(portfolio)
    assert summary.status == "unavailable"
    assert summary.is_stale is True
    assert summary.stale_reason == "analysis_context_unavailable"
    assert "analysis_context" in summary.failed_engines


# ---------------------------------------------------------------------------
# Cache hit short-circuits subsequent build
# ---------------------------------------------------------------------------
def test_engine_summary_cache_hits_on_repeat(db_session, monkeypatch):
    user = _make_user(db_session, "cache@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)

    call_count = {"context": 0}
    original = service.intelligence._analysis_context

    def counting_context(p):
        call_count["context"] += 1
        return original(p)

    monkeypatch.setattr(service.intelligence, "_analysis_context", counting_context)

    first = service.portfolio_engine_summary(portfolio)
    second = service.portfolio_engine_summary(portfolio)
    assert first.portfolio_id == second.portfolio_id
    # Either the summary cache or the context cache short-circuited; in any
    # case the underlying context loader runs at most once.
    assert call_count["context"] <= 1


# ---------------------------------------------------------------------------
# Locale propagation
# ---------------------------------------------------------------------------
def test_engine_summary_respects_locale(db_session):
    user = _make_user(db_session, "locale@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)
    en = service.portfolio_engine_summary(portfolio, locale="en")
    # zh-TW shares cache namespace with locale label
    zh = service.portfolio_engine_summary(portfolio, locale="zh-TW")
    assert en.locale == "en"
    assert zh.locale == "zh-TW"


def test_market_engine_respects_locale(db_session):
    user = _make_user(db_session, "marketloc@example.com")
    portfolio = _make_portfolio(db_session, user.id)
    service = IntelligenceEngineService(db_session)
    summary = service.market_engine_summary(portfolio, locale="zh-TW")
    assert summary.locale == "zh-TW"
    assert summary.status in {"healthy", "partial", "degraded", "unavailable"}
