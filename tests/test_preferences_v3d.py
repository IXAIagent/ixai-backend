"""Regression tests for v3D UserPreference foundation."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.preferences import (
    UserPreferenceUpdate,
    get_preferences,
    update_preferences,
)
from app.core.database import Base
from app.models.models import User, UserPreference


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


def _make_user(db, email):
    user = User(id=f"user-{uuid4().hex}", email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_get_lazy_creates_preferences_row(db_session):
    user = _make_user(db_session, "a@example.com")
    result = get_preferences(db=db_session, current_user=user)
    assert result.locale == "zh-TW"
    assert result.default_landing_page == "dashboard"
    assert result.compact_mode is True

    # The row must now exist in DB.
    row = db_session.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    assert row is not None


def test_update_persists_supported_values(db_session):
    user = _make_user(db_session, "b@example.com")
    payload = UserPreferenceUpdate(
        locale="en",
        default_landing_page="intelligence",
        compact_mode=False,
        terminal_mode=False,
        show_advanced_intelligence=True,
        alert_mode="dailyBrief",
        notification_telegram=True,
        notification_email=False,
        risk_interpretation_mode="conservative",
        active_account_id="acc-1",
        active_portfolio_id="pf-1",
    )
    result = update_preferences(payload=payload, db=db_session, current_user=user)
    assert result.locale == "en"
    assert result.default_landing_page == "intelligence"
    assert result.compact_mode is False
    assert result.terminal_mode is False
    assert result.show_advanced_intelligence is True
    assert result.alert_mode == "dailyBrief"
    assert result.notification_telegram is True
    assert result.risk_interpretation_mode == "conservative"
    assert result.active_account_id == "acc-1"
    assert result.active_portfolio_id == "pf-1"


def test_update_rejects_invalid_enum_values_silently(db_session):
    """Unsupported enum values are ignored, defaults preserved (fail-soft)."""
    user = _make_user(db_session, "c@example.com")
    update_preferences(
        payload=UserPreferenceUpdate(locale="klingon", alert_mode="rocket"),
        db=db_session,
        current_user=user,
    )
    result = get_preferences(db=db_session, current_user=user)
    assert result.locale == "zh-TW"
    assert result.alert_mode == "criticalOnly"


def test_partial_update_does_not_overwrite_other_fields(db_session):
    user = _make_user(db_session, "d@example.com")
    update_preferences(
        payload=UserPreferenceUpdate(locale="en"),
        db=db_session,
        current_user=user,
    )
    update_preferences(
        payload=UserPreferenceUpdate(compact_mode=False),
        db=db_session,
        current_user=user,
    )
    result = get_preferences(db=db_session, current_user=user)
    assert result.locale == "en"
    assert result.compact_mode is False
    # other fields still defaults
    assert result.alert_mode == "criticalOnly"
    assert result.terminal_mode is True


def test_user_a_cannot_read_user_b_preferences(db_session):
    user_a = _make_user(db_session, "a@example.com")
    user_b = _make_user(db_session, "b@example.com")

    update_preferences(
        payload=UserPreferenceUpdate(locale="en"),
        db=db_session,
        current_user=user_b,
    )
    # User A retrieves — must get THEIR own defaults, never B's row.
    result_a = get_preferences(db=db_session, current_user=user_a)
    assert result_a.locale == "zh-TW"  # not "en"
    result_b = get_preferences(db=db_session, current_user=user_b)
    assert result_b.locale == "en"


def test_active_portfolio_id_can_be_cleared_with_empty_string(db_session):
    user = _make_user(db_session, "clear@example.com")
    update_preferences(
        payload=UserPreferenceUpdate(active_portfolio_id="pf-1"),
        db=db_session,
        current_user=user,
    )
    update_preferences(
        payload=UserPreferenceUpdate(active_portfolio_id=""),
        db=db_session,
        current_user=user,
    )
    result = get_preferences(db=db_session, current_user=user)
    assert result.active_portfolio_id is None


def test_audit_log_event_is_callable_and_does_not_raise():
    from app.services.audit_service import log_event

    # Stub must accept canonical events without raising.
    log_event("portfolio_created", user_id="u-1", metadata={"portfolio_id": "pf-1"})
    log_event("intelligence_viewed", user_id="u-1", metadata={"endpoint": "/portfolio-summary"})
    # Unknown event still must not raise.
    log_event("not_in_supported_list", user_id="u-1")
    # Sensitive keys must not leak; pass and verify no exception only.
    log_event("portfolio_switched", user_id="u-1", metadata={"password": "x", "api_key": "y"})
