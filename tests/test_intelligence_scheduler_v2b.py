from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import IntelligenceRunLog, Portfolio, User


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


def _portfolio(db_session, name: str = "Scheduler") -> Portfolio:
    suffix = uuid4().hex
    user = User(
        id=f"user-{suffix}",
        email=f"scheduler-{suffix}@ixai.local",
        hashed_password="hash",
    )
    portfolio = Portfolio(
        id=f"portfolio-{suffix}",
        user_id=user.id,
        name=name,
        base_currency="USD",
    )
    db_session.add(user)
    db_session.add(portfolio)
    db_session.commit()
    return portfolio


def test_runner_no_portfolio_does_not_crash(db_session):
    from app.scheduler.intelligence_runner import run_intelligence_scheduler_once

    result = run_intelligence_scheduler_once(db=db_session)

    assert result["status"] == "skipped"
    assert result["processed"] == 0
    assert db_session.query(IntelligenceRunLog).count() == 0


def test_runner_success_writes_run_log(monkeypatch, db_session):
    from app.scheduler import intelligence_runner
    from app.services.intelligence.schemas import PortfolioSummaryV2AResponse

    portfolio = _portfolio(db_session)

    def _fake_summary(self, portfolio_arg):
        assert portfolio_arg.id == portfolio.id
        return PortfolioSummaryV2AResponse(
            regime="BALANCED",
            dominant_risk="No dominant risk",
            concentration_score=10,
            drift_summary="Stable",
            generated_at="2026-05-15T00:00:00Z",
            is_stale=False,
        )

    monkeypatch.setattr(
        intelligence_runner.PortfolioIntelligenceService,
        "get_portfolio_summary_v2a",
        _fake_summary,
    )

    result = intelligence_runner.run_intelligence_scheduler_once(db=db_session)
    run_log = db_session.query(IntelligenceRunLog).one()

    assert result["status"] == "success"
    assert result["success"] == 1
    assert run_log.portfolio_id == portfolio.id
    assert run_log.status == "success"
    assert run_log.finished_at is not None


def test_runner_failure_does_not_stop_other_portfolios(monkeypatch, db_session):
    from app.scheduler import intelligence_runner
    from app.services.intelligence.schemas import PortfolioSummaryV2AResponse

    first = _portfolio(db_session, "First")
    second = _portfolio(db_session, "Second")

    def _fake_summary(self, portfolio_arg):
        if portfolio_arg.id == first.id:
            raise RuntimeError("provider exploded")
        assert portfolio_arg.id == second.id
        return PortfolioSummaryV2AResponse(
            regime="BALANCED",
            dominant_risk="No dominant risk",
            concentration_score=10,
            drift_summary="Stable",
            generated_at="2026-05-15T00:00:00Z",
            is_stale=False,
        )

    monkeypatch.setattr(
        intelligence_runner.PortfolioIntelligenceService,
        "get_portfolio_summary_v2a",
        _fake_summary,
    )

    result = intelligence_runner.run_intelligence_scheduler_once(db=db_session)
    statuses = {
        item.portfolio_id: item.status
        for item in db_session.query(IntelligenceRunLog).order_by(IntelligenceRunLog.created_at.asc()).all()
    }

    assert result["status"] == "completed_with_errors"
    assert result["processed"] == 2
    assert result["success"] == 1
    assert result["failed"] == 1
    assert statuses[first.id] == "failed"
    assert statuses[second.id] == "success"


def test_admin_endpoint_production_forbidden(monkeypatch, db_session):
    from app.api.v1.endpoints import intelligence

    monkeypatch.setattr(intelligence, "is_development_env", lambda: False)

    with pytest.raises(HTTPException) as exc:
        intelligence.run_intelligence_scheduler_admin_once(db=db_session)

    assert exc.value.status_code == 403


def test_admin_endpoint_development_runs(monkeypatch, db_session):
    from app.api.v1.endpoints import intelligence

    monkeypatch.setattr(intelligence, "is_development_env", lambda: True)
    monkeypatch.setattr(
        intelligence,
        "run_intelligence_scheduler_once",
        lambda db, source: {"status": "success", "source": source, "processed": 0},
    )

    response = intelligence.run_intelligence_scheduler_admin_once(db=db_session)

    assert response["status"] == "success"
    assert response["source"] == "admin_endpoint"


def test_scheduler_migration_module_importable():
    import importlib

    migration = importlib.import_module("migrations.versions.0004_intelligence_scheduler_logs")

    assert migration.revision == "0004_intelligence_scheduler_logs"
