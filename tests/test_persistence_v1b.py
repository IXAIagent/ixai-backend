"""Regression tests for Engineering Hardening Pack v1B.

Covers:
- PushState: write/read round-trip, cooldown logic, fail-soft on DB error.
- IntelligenceMemoryStore: append/read round-trip, recent-N ordering,
  trim past max_snapshots, fail-soft on DB error.
- Model import sanity (new tables present in metadata).
"""
from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base


@pytest.fixture()
def isolated_session_factory(tmp_path):
    """Spin up a throwaway sqlite DB with the full schema applied."""
    db_path = tmp_path / "v1b.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# push_state_service
# ---------------------------------------------------------------------------
def test_push_state_first_call_returns_true(monkeypatch, isolated_session_factory):
    import app.services.push_state_service as pss

    monkeypatch.setattr(pss, "SessionLocal", isolated_session_factory)

    assert pss.should_send_push("portfolio-1", 80, "FCN risk") is True


def test_push_state_dedupe_within_cooldown(monkeypatch, isolated_session_factory):
    import app.services.push_state_service as pss

    monkeypatch.setattr(pss, "SessionLocal", isolated_session_factory)

    # First call → push
    assert pss.should_send_push("portfolio-2", 80, "FCN risk") is True
    # Same payload immediately again → suppressed
    assert pss.should_send_push("portfolio-2", 80, "FCN risk") is False


def test_push_state_score_change_triggers_push(monkeypatch, isolated_session_factory):
    import app.services.push_state_service as pss

    monkeypatch.setattr(pss, "SessionLocal", isolated_session_factory)

    assert pss.should_send_push("portfolio-3", 50, "Stock concentration") is True
    # Score jump >=10 → must push again
    assert pss.should_send_push("portfolio-3", 65, "Stock concentration") is True


def test_push_state_top_risk_change_triggers_push(
    monkeypatch, isolated_session_factory
):
    import app.services.push_state_service as pss

    monkeypatch.setattr(pss, "SessionLocal", isolated_session_factory)

    assert pss.should_send_push("portfolio-4", 50, "FCN risk") is True
    # Different top_risk → push again even at same score
    assert pss.should_send_push("portfolio-4", 50, "Crypto leverage") is True


def test_push_state_cooldown_expiry_triggers_push(
    monkeypatch, isolated_session_factory
):
    import app.services.push_state_service as pss
    from app.models.models import PushState

    monkeypatch.setattr(pss, "SessionLocal", isolated_session_factory)

    assert pss.should_send_push("portfolio-5", 50, "FCN risk") is True

    # Backdate the stored timestamp past the cooldown window.
    db = isolated_session_factory()
    try:
        record = db.query(PushState).filter(PushState.key == "portfolio-5").first()
        assert record is not None
        record.value = (
            '{"risk_score": 50, "top_risk": "FCN risk", '
            f'"timestamp": {int(time.time()) - pss.COOLDOWN_SECONDS - 60}}}'.replace("}}", "}")
        )
        db.commit()
    finally:
        db.close()

    assert pss.should_send_push("portfolio-5", 50, "FCN risk") is True


def test_push_state_fail_soft_when_session_broken(monkeypatch):
    import app.services.push_state_service as pss

    class _BoomSession:
        def query(self, *args, **kwargs):
            raise RuntimeError("simulated db outage")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(pss, "SessionLocal", lambda: _BoomSession())

    # Must not raise; must return True (fail-open).
    assert pss.should_send_push("portfolio-6", 80, "FCN risk") is True


# ---------------------------------------------------------------------------
# IntelligenceMemoryStore
# ---------------------------------------------------------------------------
def _make_score(total: float = 50.0):
    from app.services.intelligence.schemas import IntelligenceScore

    return IntelligenceScore(total_score=total)


def _make_workspace(mode: str = "BALANCED", drift: str = "Stable"):
    from app.services.intelligence.schemas import WorkspaceDecision

    return WorkspaceDecision(workspace_mode=mode, risk_drift=drift)


def _make_narrative():
    from app.services.intelligence.schemas import IntelligenceNarrative

    return IntelligenceNarrative(
        market_narrative="Markets steady",
        portfolio_narrative="Portfolio diversified",
        risk_narrative="No major risks",
        fcn_narrative="FCN stable",
        what_changed_today="Nothing material",
    )


def test_intelligence_memory_append_and_read(
    monkeypatch, isolated_session_factory
):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)

    store = pm.IntelligenceMemoryStore()
    store.append_snapshot(
        "portfolio-A",
        _make_score(total=42),
        _make_workspace(mode="FCN_RISK", drift="Increasing"),
        _make_narrative(),
        [],
    )

    history = store.get_recent_history("portfolio-A", limit=5)
    assert len(history) == 1
    item = history[0]
    assert item["workspace_mode"] == "FCN_RISK"
    assert item["risk_drift"] == "Increasing"
    assert item["scores"]["total_score"] == 42


def test_intelligence_memory_recent_ordering_oldest_first(
    monkeypatch, isolated_session_factory
):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)

    store = pm.IntelligenceMemoryStore()
    for i, total in enumerate([10, 20, 30]):
        store.append_snapshot(
            "portfolio-B",
            _make_score(total=float(total)),
            _make_workspace(),
            _make_narrative(),
            [],
        )
        # Ensure created_at ordering is deterministic on fast hardware.
        time.sleep(0.01)

    history = store.get_recent_history("portfolio-B", limit=10)
    assert len(history) == 3
    totals = [item["scores"]["total_score"] for item in history]
    # Oldest first within the recent-N window.
    assert totals == [10, 20, 30]


def test_intelligence_memory_trim_to_max_snapshots(
    monkeypatch, isolated_session_factory
):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)

    store = pm.IntelligenceMemoryStore(max_snapshots=2)
    for total in [10, 20, 30]:
        store.append_snapshot(
            "portfolio-C",
            _make_score(total=float(total)),
            _make_workspace(),
            _make_narrative(),
            [],
        )
        time.sleep(0.01)

    history = store.get_recent_history("portfolio-C", limit=10)
    assert len(history) == 2
    totals = [item["scores"]["total_score"] for item in history]
    # Oldest dropped; the most recent two retained.
    assert totals == [20, 30]


def test_intelligence_memory_compare_historical_drift_no_history(
    monkeypatch, isolated_session_factory
):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)

    store = pm.IntelligenceMemoryStore()
    msg = store.compare_historical_drift("portfolio-empty", _make_score(total=50))
    assert "第一筆" in msg


def test_intelligence_memory_compare_historical_drift_rising(
    monkeypatch, isolated_session_factory
):
    import app.services.intelligence.persistent_memory as pm

    monkeypatch.setattr(pm, "SessionLocal", isolated_session_factory)

    store = pm.IntelligenceMemoryStore()
    store.append_snapshot(
        "portfolio-D",
        _make_score(total=30),
        _make_workspace(),
        _make_narrative(),
        [],
    )
    msg = store.compare_historical_drift("portfolio-D", _make_score(total=80))
    assert "上升" in msg


def test_intelligence_memory_fail_soft_on_append(monkeypatch):
    import app.services.intelligence.persistent_memory as pm

    class _BoomSession:
        def add(self, *a, **kw):
            raise RuntimeError("simulated db outage")

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def query(self, *a, **kw):
            raise RuntimeError("simulated db outage")

    monkeypatch.setattr(pm, "SessionLocal", lambda: _BoomSession())

    store = pm.IntelligenceMemoryStore()
    # Must not raise.
    store.append_snapshot(
        "portfolio-broken",
        _make_score(),
        _make_workspace(),
        _make_narrative(),
        [],
    )


def test_intelligence_memory_fail_soft_on_read(monkeypatch):
    import app.services.intelligence.persistent_memory as pm

    class _BoomSession:
        def query(self, *a, **kw):
            raise RuntimeError("simulated db outage")

        def close(self):
            pass

    monkeypatch.setattr(pm, "SessionLocal", lambda: _BoomSession())

    store = pm.IntelligenceMemoryStore()
    # Must return [] not raise.
    assert store.get_recent_history("portfolio-broken", limit=5) == []


# ---------------------------------------------------------------------------
# model import sanity
# ---------------------------------------------------------------------------
def test_new_tables_registered_in_metadata():
    # Trigger model import explicitly.
    from app.models import models  # noqa: F401

    assert "push_states" in Base.metadata.tables
    assert "intelligence_memory_snapshots" in Base.metadata.tables

    push_table = Base.metadata.tables["push_states"]
    assert {"id", "user_id", "key", "value", "created_at", "updated_at"}.issubset(
        set(push_table.columns.keys())
    )

    snap_table = Base.metadata.tables["intelligence_memory_snapshots"]
    assert {
        "id",
        "portfolio_id",
        "snapshot",
        "workspace_mode",
        "total_score",
        "risk_drift",
        "created_at",
    }.issubset(set(snap_table.columns.keys()))
