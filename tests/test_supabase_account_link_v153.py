from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.integrations import (
    SupabaseAccountLinkRequest,
    link_supabase_account,
)
from app.core.database import Base
from app.models.models import Account, AccountMembership, User


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


def _payload(external_user_id: str = "supabase-user-1"):
    return SupabaseAccountLinkRequest(
        provider="supabase",
        external_user_id=external_user_id,
        email="member@example.com",
        name="IXAI Member",
    )


def test_new_supabase_user_creates_account_link(db_session):
    response = link_supabase_account(_payload(), db=db_session)

    account = db_session.query(Account).filter(Account.id == response.backend_account_id).one()
    user = db_session.query(User).filter(User.id == response.backend_user_id).one()
    membership = (
        db_session.query(AccountMembership)
        .filter(
            AccountMembership.account_id == account.id,
            AccountMembership.user_id == user.id,
        )
        .one()
    )

    assert response.created is True
    assert response.pro_access_status == "connected"
    assert account.external_provider == "supabase"
    assert account.external_user_id == "supabase-user-1"
    assert account.external_email == "member@example.com"
    assert account.pro_access_status == "connected"
    assert user.email == "member@example.com"
    assert membership.role == "owner"


def test_same_supabase_user_returns_existing_link(db_session):
    first = link_supabase_account(_payload(), db=db_session)
    second = link_supabase_account(_payload(), db=db_session)

    assert first.created is True
    assert second.created is False
    assert second.backend_account_id == first.backend_account_id
    assert second.backend_user_id == first.backend_user_id
    assert db_session.query(Account).count() == 1


def test_invalid_provider_rejected():
    with pytest.raises(ValidationError):
        SupabaseAccountLinkRequest(
            provider="google",
            external_user_id="external-1",
            email="member@example.com",
        )


def test_missing_external_user_id_rejected():
    with pytest.raises(ValidationError):
        SupabaseAccountLinkRequest(
            provider="supabase",
            external_user_id="",
            email="member@example.com",
        )


def test_pro_access_status_default_is_connected_not_active(db_session):
    response = link_supabase_account(_payload("supabase-user-2"), db=db_session)

    assert response.pro_access_status == "connected"
    assert response.pro_access_status != "active"


def test_integrations_route_registered():
    from app.main import app

    assert "/api/v1/integrations/supabase/account-link" in [
        route.path for route in app.routes
    ]
