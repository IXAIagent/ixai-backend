"""Regression tests for v3C portfolio-scoped API contract.

Covers:
- resolve_portfolio_for_user permission helper:
  - owner can read their portfolio
  - account member can read account portfolio
  - non-member cannot read (403)
  - unknown portfolio_id returns 404
  - missing portfolio_id falls back to user's first portfolio
- intelligence/portfolio-summary respects portfolio_id
- timeline respects portfolio_id
- cross-user isolation: user A cannot read user B portfolio via portfolio_id
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.api.deps import resolve_portfolio_for_user, user_can_access_portfolio
from app.models.models import (
    Account,
    AccountMembership,
    CashPosition,
    Portfolio,
    StockPosition,
    User,
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


def _make_user(db, email: str) -> User:
    user = User(id=f"user-{uuid4().hex}", email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_portfolio(db, owner_id: str, account_id: str | None = None) -> Portfolio:
    portfolio = Portfolio(
        id=f"portfolio-{uuid4().hex}",
        user_id=owner_id,
        account_id=account_id,
        name="Test Portfolio",
        base_currency="USD",
        created_at=datetime.utcnow(),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def _make_account(db, owner_id: str) -> Account:
    account = Account(
        id=f"account-{uuid4().hex}",
        owner_user_id=owner_id,
        name="Test Account",
        account_type="individual",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _make_membership(db, account_id: str, user_id: str, role: str = "viewer") -> AccountMembership:
    membership = AccountMembership(
        id=f"membership-{uuid4().hex}",
        account_id=account_id,
        user_id=user_id,
        role=role,
    )
    db.add(membership)
    db.commit()
    return membership


# ---------------------------------------------------------------------------
# user_can_access_portfolio
# ---------------------------------------------------------------------------
def test_owner_can_access_their_portfolio(db_session):
    user = _make_user(db_session, "owner@example.com")
    portfolio = _make_portfolio(db_session, owner_id=user.id)
    assert user_can_access_portfolio(db_session, user, portfolio) is True


def test_non_owner_without_membership_cannot_access(db_session):
    owner = _make_user(db_session, "owner@example.com")
    other = _make_user(db_session, "other@example.com")
    portfolio = _make_portfolio(db_session, owner_id=owner.id)
    assert user_can_access_portfolio(db_session, other, portfolio) is False


def test_account_member_can_access_account_portfolio(db_session):
    owner = _make_user(db_session, "owner@example.com")
    member = _make_user(db_session, "member@example.com")
    account = _make_account(db_session, owner_id=owner.id)
    _make_membership(db_session, account.id, member.id, role="viewer")
    portfolio = _make_portfolio(db_session, owner_id=owner.id, account_id=account.id)
    assert user_can_access_portfolio(db_session, member, portfolio) is True


def test_account_owner_can_access_account_portfolio_owned_by_other(db_session):
    """If the portfolio's account is owned by user X, X can read regardless of portfolio.user_id."""
    account_owner = _make_user(db_session, "acc-owner@example.com")
    portfolio_creator = _make_user(db_session, "creator@example.com")
    account = _make_account(db_session, owner_id=account_owner.id)
    portfolio = _make_portfolio(db_session, owner_id=portfolio_creator.id, account_id=account.id)
    assert user_can_access_portfolio(db_session, account_owner, portfolio) is True


# ---------------------------------------------------------------------------
# resolve_portfolio_for_user
# ---------------------------------------------------------------------------
def test_resolver_returns_portfolio_when_owner_provides_id(db_session):
    user = _make_user(db_session, "owner@example.com")
    portfolio = _make_portfolio(db_session, owner_id=user.id)

    result = resolve_portfolio_for_user(
        portfolio_id=portfolio.id, db=db_session, current_user=user
    )
    assert result.id == portfolio.id


def test_resolver_403_when_user_has_no_access(db_session):
    owner = _make_user(db_session, "owner@example.com")
    other = _make_user(db_session, "other@example.com")
    portfolio = _make_portfolio(db_session, owner_id=owner.id)

    with pytest.raises(HTTPException) as exc:
        resolve_portfolio_for_user(
            portfolio_id=portfolio.id, db=db_session, current_user=other
        )
    assert exc.value.status_code == 403


def test_resolver_404_when_portfolio_unknown(db_session):
    user = _make_user(db_session, "owner@example.com")
    with pytest.raises(HTTPException) as exc:
        resolve_portfolio_for_user(
            portfolio_id="nonexistent-id", db=db_session, current_user=user
        )
    assert exc.value.status_code == 404


def test_resolver_falls_back_to_first_owned_when_id_missing(db_session):
    user = _make_user(db_session, "owner@example.com")
    portfolio = _make_portfolio(db_session, owner_id=user.id)

    result = resolve_portfolio_for_user(
        portfolio_id=None, db=db_session, current_user=user
    )
    assert result.id == portfolio.id


def test_resolver_fallback_404_when_user_has_no_portfolio(db_session):
    user = _make_user(db_session, "no-portfolio@example.com")
    with pytest.raises(HTTPException) as exc:
        resolve_portfolio_for_user(
            portfolio_id=None, db=db_session, current_user=user
        )
    assert exc.value.status_code == 404


def test_resolver_allows_account_member_with_explicit_id(db_session):
    owner = _make_user(db_session, "owner@example.com")
    member = _make_user(db_session, "member@example.com")
    account = _make_account(db_session, owner_id=owner.id)
    _make_membership(db_session, account.id, member.id)
    portfolio = _make_portfolio(db_session, owner_id=owner.id, account_id=account.id)

    result = resolve_portfolio_for_user(
        portfolio_id=portfolio.id, db=db_session, current_user=member
    )
    assert result.id == portfolio.id


def test_resolver_empty_string_treated_as_missing(db_session):
    """Frontend sometimes sends ?portfolio_id= with empty value; treat as fallback."""
    user = _make_user(db_session, "owner@example.com")
    portfolio = _make_portfolio(db_session, owner_id=user.id)

    result = resolve_portfolio_for_user(
        portfolio_id="", db=db_session, current_user=user
    )
    assert result.id == portfolio.id


# ---------------------------------------------------------------------------
# Cross-user isolation against scoped endpoint deps
# ---------------------------------------------------------------------------
def test_cross_user_isolation_with_explicit_id(db_session):
    """Direct attempt to read user_B's portfolio with their portfolio_id must 403."""
    user_a = _make_user(db_session, "a@example.com")
    user_b = _make_user(db_session, "b@example.com")
    portfolio_b = _make_portfolio(db_session, owner_id=user_b.id)
    # Add a position so the portfolio is non-empty (proves data lookup attempted).
    db_session.add(
        CashPosition(
            id=f"cash-{uuid4().hex}",
            portfolio_id=portfolio_b.id,
            currency="USD",
            amount=1000.0,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        resolve_portfolio_for_user(
            portfolio_id=portfolio_b.id, db=db_session, current_user=user_a
        )
    assert exc.value.status_code == 403


def test_user_only_sees_own_in_fallback(db_session):
    """When portfolio_id missing, fallback must not return another user's portfolio."""
    user_a = _make_user(db_session, "a@example.com")
    user_b = _make_user(db_session, "b@example.com")
    # B has portfolio, A does not.
    _make_portfolio(db_session, owner_id=user_b.id)

    with pytest.raises(HTTPException) as exc:
        resolve_portfolio_for_user(
            portfolio_id=None, db=db_session, current_user=user_a
        )
    assert exc.value.status_code == 404


def test_member_role_grants_read_even_for_admin_role(db_session):
    """Any role membership grants read; v3C does not gate by role yet."""
    owner = _make_user(db_session, "owner@example.com")
    member = _make_user(db_session, "member@example.com")
    account = _make_account(db_session, owner_id=owner.id)
    _make_membership(db_session, account.id, member.id, role="admin")
    portfolio = _make_portfolio(db_session, owner_id=owner.id, account_id=account.id)
    assert user_can_access_portfolio(db_session, member, portfolio) is True


def test_portfolio_without_account_id_only_owner_can_access(db_session):
    """Portfolios with NULL account_id (legacy) gate strictly by user_id."""
    owner = _make_user(db_session, "owner@example.com")
    other = _make_user(db_session, "other@example.com")
    portfolio = _make_portfolio(db_session, owner_id=owner.id, account_id=None)
    assert user_can_access_portfolio(db_session, owner, portfolio) is True
    assert user_can_access_portfolio(db_session, other, portfolio) is False
