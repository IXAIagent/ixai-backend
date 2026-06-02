from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.integrations import SupabaseAccountLinkRequest, link_supabase_account
from app.core.database import Base, get_db
from app.main import app


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
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
    client = TestClient(app)
    return client, engine


def _link_user(external_user_id: str = "manual-entitlement-user"):
    db = next(app.dependency_overrides[get_db]())
    try:
        return link_supabase_account(
            SupabaseAccountLinkRequest(
                provider="supabase",
                external_user_id=external_user_id,
                email="manual-entitlement@example.com",
                name="Manual Entitlement",
            ),
            db=db,
        )
    finally:
        db.close()


def test_manual_entitlement_endpoint_requires_token(monkeypatch):
    client, engine = _client_with_db()
    monkeypatch.setenv("IXAI_ADMIN_INTERNAL_TOKEN", "test-token")

    try:
        response = client.post(
            "/api/v1/admin/entitlements/manual",
            json={
                "provider": "supabase",
                "external_user_id": "missing-user",
                "plan_code": "pro",
                "entitlements": {"portfolio": True},
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_manual_entitlement_endpoint_rejects_wrong_token(monkeypatch):
    client, engine = _client_with_db()
    monkeypatch.setenv("IXAI_ADMIN_INTERNAL_TOKEN", "test-token")

    try:
        response = client.post(
            "/api/v1/admin/entitlements/manual",
            headers={"X-IXAI-ADMIN-TOKEN": "wrong-token"},
            json={
                "provider": "supabase",
                "external_user_id": "missing-user",
                "plan_code": "pro",
                "entitlements": {"portfolio": True},
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_manual_pro_entitlement_updates_membership_and_entitlements(monkeypatch):
    client, engine = _client_with_db()
    monkeypatch.setenv("IXAI_ADMIN_INTERNAL_TOKEN", "test-token")
    _link_user("manual-entitlement-user")

    try:
        response = client.post(
            "/api/v1/admin/entitlements/manual",
            headers={"X-IXAI-ADMIN-TOKEN": "test-token"},
            json={
                "provider": "supabase",
                "external_user_id": "manual-entitlement-user",
                "plan_code": "pro",
                "entitlements": {
                    "ai_copilot": False,
                    "fcn_monitoring": True,
                    "portfolio": True,
                    "risk_engine": True,
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["plan_code"] == "pro"
        assert payload["entitlements"]["portfolio"] is True
        assert payload["entitlements"]["fcn_monitoring"] is True
        assert payload["entitlements"]["risk_engine"] is True
        assert payload["entitlements"]["ai_copilot"] is False

        membership = client.get(
            "/api/v1/membership/me",
            params={"provider": "supabase", "external_user_id": "manual-entitlement-user"},
        ).json()
        entitlements = client.get(
            "/api/v1/entitlements/me",
            params={"provider": "supabase", "external_user_id": "manual-entitlement-user"},
        ).json()

        assert membership["plan_code"] == "pro"
        assert membership["entitlements"]["portfolio"] is True
        assert entitlements["plan"] == "pro"
        assert entitlements["entitlements"]["risk_engine"] is True
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
