from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.integrations import SupabaseAccountLinkRequest, link_supabase_account
from app.api.v1.endpoints.membership import get_membership_me
from app.core.database import Base
from app.models.models import Entitlement, Subscription
from app.services.membership_service import MembershipService


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


def _link(db_session, external_user_id: str = "membership-user-1"):
    return link_supabase_account(
        SupabaseAccountLinkRequest(
            provider="supabase",
            external_user_id=external_user_id,
            email="membership@example.com",
            name="Membership Test",
        ),
        db=db_session,
    )


def test_default_linked_account_gets_free_membership(db_session):
    response = _link(db_session)
    snapshot = MembershipService(db_session).snapshot(response.backend_account_id)

    assert snapshot.plan_code == "free"
    assert snapshot.status == "active"
    assert snapshot.entitlements["daily_brief"] is True
    assert snapshot.entitlements["weekly_brief"] is True
    assert snapshot.entitlements["watchlist"] is True


def test_pro_entitlements_not_enabled_by_default(db_session):
    response = _link(db_session)
    entitlements = MembershipService(db_session).get_entitlements(response.backend_account_id)

    assert entitlements["pro_preview"] is False
    assert entitlements["portfolio"] is False
    assert entitlements["fcn_monitoring"] is False
    assert entitlements["risk_engine"] is False
    assert entitlements["ai_copilot"] is False


def test_ensure_default_membership_is_idempotent(db_session):
    response = _link(db_session)
    service = MembershipService(db_session)

    service.ensure_default_membership(response.backend_account_id)
    service.ensure_default_membership(response.backend_account_id)

    assert (
        db_session.query(Subscription)
        .filter(Subscription.account_id == response.backend_account_id)
        .count()
        == 1
    )
    assert (
        db_session.query(Entitlement)
        .filter(Entitlement.account_id == response.backend_account_id)
        .count()
        == 8
    )


def test_membership_endpoint_returns_expected_response(db_session):
    _link(db_session, "membership-user-2")
    response = get_membership_me(
        provider="supabase",
        external_user_id="membership-user-2",
        db=db_session,
    )

    assert response.plan_code == "free"
    assert response.status == "active"
    assert response.entitlements["daily_brief"] is True
    assert response.entitlements["portfolio"] is False
    assert response.entitlements["fcn_monitoring"] is False


def test_membership_endpoint_returns_not_linked(db_session):
    with pytest.raises(HTTPException) as exc:
        get_membership_me(provider="supabase", external_user_id="missing-user", db=db_session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "not_linked"


def test_membership_route_registered():
    from app.main import app

    assert "/api/v1/membership/me" in [route.path for route in app.routes]


def test_temporary_migration_status_route_registered():
    from app.main import app

    assert "/admin/migration-status" in [route.path for route in app.routes]


def test_temporary_membership_migration_route_registered():
    from app.main import app

    assert "/admin/run-membership-migration" in [route.path for route in app.routes]


def test_temporary_membership_migration_requires_configured_token(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.delenv("MIGRATION_BOOTSTRAP_TOKEN", raising=False)
    response = TestClient(app).post("/admin/run-membership-migration")

    assert response.status_code == 403
    assert response.json()["error"] == "migration_bootstrap_not_configured"


def test_temporary_membership_migration_rejects_wrong_token(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("MIGRATION_BOOTSTRAP_TOKEN", "correct-token")
    response = TestClient(app).post(
        "/admin/run-membership-migration",
        headers={"x-ixai-migration-token": "wrong-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == "migration_bootstrap_forbidden"
