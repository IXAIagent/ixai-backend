from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Account, Portfolio, User
from app.services.accounts.account_service import AccountService


router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    name: str
    account_type: str = "individual"


class PortfolioCreateRequest(BaseModel):
    name: str
    base_currency: str = "USD"


def serialize_account(account: Account) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "name": account.name,
        "owner_user_id": str(account.owner_user_id),
        "account_type": account.account_type,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def serialize_portfolio(portfolio: Portfolio) -> dict[str, Any]:
    return {
        "id": str(portfolio.id),
        "name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "user_id": str(portfolio.user_id),
        "account_id": str(portfolio.account_id) if portfolio.account_id else None,
        "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None,
    }


@router.get("")
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = AccountService(db).list_accounts(current_user)
    return {"items": [serialize_account(account) for account in accounts]}


@router.post("")
def create_account(
    payload: AccountCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = AccountService(db).create_account(
        current_user,
        name=payload.name,
        account_type=payload.account_type,
    )
    return serialize_account(account)


@router.get("/{account_id}")
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = AccountService(db).get_account(current_user, account_id)
    return serialize_account(account)


@router.get("/{account_id}/portfolios")
def list_account_portfolios(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolios = AccountService(db).list_portfolios(current_user, account_id)
    return {"items": [serialize_portfolio(portfolio) for portfolio in portfolios]}


@router.post("/{account_id}/portfolios")
def create_account_portfolio(
    account_id: str,
    payload: PortfolioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = AccountService(db).create_portfolio(
        current_user,
        account_id=account_id,
        name=payload.name,
        base_currency=payload.base_currency,
    )
    return serialize_portfolio(portfolio)


@router.get("/{account_id}/intelligence/summary")
def get_account_intelligence_summary(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AccountService(db).account_intelligence_summary(current_user, account_id)
