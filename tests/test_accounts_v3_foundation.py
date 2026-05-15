from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import accounts
from app.api.v1.endpoints.dashboard import get_summary
from app.core.database import Base
from app.models.models import Account, AccountMembership, Portfolio, User
from app.services.accounts.account_service import AccountService


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


def _user(db_session, label: str = "user") -> User:
    suffix = uuid4().hex
    user = User(id=f"{label}-{suffix}", email=f"{label}-{suffix}@ixai.local", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    return user


def test_user_can_create_account(db_session):
    user = _user(db_session)

    account = AccountService(db_session).create_account(user, "Family Office", "family")
    membership = (
        db_session.query(AccountMembership)
        .filter(AccountMembership.account_id == account.id, AccountMembership.user_id == user.id)
        .one()
    )

    assert account.name == "Family Office"
    assert account.account_type == "family"
    assert membership.role == "owner"


def test_owner_can_read_account(db_session):
    user = _user(db_session)
    account = AccountService(db_session).create_account(user, "Personal", "individual")

    response = accounts.get_account(account.id, db=db_session, current_user=user)

    assert response["id"] == account.id
    assert response["name"] == "Personal"


def test_non_member_cannot_read_account(db_session):
    owner = _user(db_session, "owner")
    outsider = _user(db_session, "outsider")
    account = AccountService(db_session).create_account(owner, "Private", "individual")

    with pytest.raises(HTTPException) as exc:
        accounts.get_account(account.id, db=db_session, current_user=outsider)

    assert exc.value.status_code == 403


def test_viewer_cannot_create_portfolio(db_session):
    owner = _user(db_session, "owner")
    viewer = _user(db_session, "viewer")
    account = AccountService(db_session).create_account(owner, "Shared", "family")
    db_session.add(AccountMembership(account_id=account.id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        accounts.create_account_portfolio(
            account.id,
            accounts.PortfolioCreateRequest(name="Viewer Portfolio"),
            db=db_session,
            current_user=viewer,
        )

    assert exc.value.status_code == 403


def test_account_portfolios_list_normal(db_session):
    user = _user(db_session)
    account = AccountService(db_session).create_account(user, "Business", "business")
    created = accounts.create_account_portfolio(
        account.id,
        accounts.PortfolioCreateRequest(name="Core", base_currency="USD"),
        db=db_session,
        current_user=user,
    )

    response = accounts.list_account_portfolios(account.id, db=db_session, current_user=user)

    assert created["account_id"] == account.id
    assert response["items"][0]["name"] == "Core"


def test_existing_portfolio_path_not_broken(db_session):
    user = _user(db_session)
    portfolio = Portfolio(user_id=user.id, name="Legacy Portfolio", base_currency="USD")
    db_session.add(portfolio)
    db_session.commit()

    response = get_summary(portfolio=portfolio, db=db_session)

    assert "total_value" in response
    assert portfolio.account_id is None


def test_account_intelligence_summary_fail_soft(monkeypatch, db_session):
    user = _user(db_session)
    account = AccountService(db_session).create_account(user, "Intel", "individual")
    portfolio = Portfolio(user_id=user.id, account_id=account.id, name="Intel Portfolio", base_currency="USD")
    db_session.add(portfolio)
    db_session.commit()

    class BrokenService:
        def __init__(self, db, skip_news=False):
            pass

        def get_portfolio_summary_v2a(self, portfolio_arg):
            raise RuntimeError("boom")

    import app.services.accounts.account_service as account_service

    monkeypatch.setattr(account_service, "PortfolioIntelligenceService", BrokenService)
    response = accounts.get_account_intelligence_summary(account.id, db=db_session, current_user=user)

    assert response["is_stale"] is True
    assert response["items"][0]["portfolio_id"] == portfolio.id


def test_accounts_route_registered():
    from app.main import app

    assert "/api/v1/accounts" in [route.path for route in app.routes]
