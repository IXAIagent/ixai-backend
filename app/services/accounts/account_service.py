from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import Account, AccountMembership, Portfolio, User
from app.services.accounts.access_control import require_account_access, require_account_write_access
from app.services.intelligence.service import PortfolioIntelligenceService


class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_accounts(self, user: User) -> list[Account]:
        return (
            self.db.query(Account)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .filter(AccountMembership.user_id == user.id)
            .order_by(Account.created_at.asc())
            .all()
        )

    def create_account(self, user: User, name: str, account_type: str = "individual") -> Account:
        clean_name = str(name or "").strip() or "Personal Account"
        clean_type = str(account_type or "individual").strip().lower()
        if clean_type not in {"individual", "family", "business"}:
            clean_type = "individual"

        account = Account(name=clean_name, owner_user_id=user.id, account_type=clean_type)
        self.db.add(account)
        self.db.flush()
        self.db.add(AccountMembership(account_id=account.id, user_id=user.id, role="owner"))
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_account(self, user: User, account_id: str) -> Account:
        account, _ = require_account_access(self.db, account_id, user)
        return account

    def list_portfolios(self, user: User, account_id: str) -> list[Portfolio]:
        require_account_access(self.db, account_id, user)
        return (
            self.db.query(Portfolio)
            .filter(Portfolio.account_id == str(account_id))
            .order_by(Portfolio.created_at.asc())
            .all()
        )

    def create_portfolio(
        self,
        user: User,
        account_id: str,
        name: str,
        base_currency: str = "USD",
    ) -> Portfolio:
        require_account_write_access(self.db, account_id, user)
        portfolio = Portfolio(
            name=str(name or "").strip() or "New Portfolio",
            base_currency=str(base_currency or "USD").strip().upper() or "USD",
            user_id=user.id,
            account_id=str(account_id),
        )
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio

    def account_intelligence_summary(self, user: User, account_id: str) -> dict[str, Any]:
        try:
            account = self.get_account(user, account_id)
            portfolios = self.list_portfolios(user, account_id)
            summaries: list[dict[str, Any]] = []
            service = PortfolioIntelligenceService(self.db, skip_news=True)
            for portfolio in portfolios:
                try:
                    summary = service.get_portfolio_summary_v2a(portfolio)
                    summaries.append({
                        "portfolio_id": str(portfolio.id),
                        "portfolio_name": str(portfolio.name),
                        "regime": summary.regime,
                        "dominant_risk": summary.dominant_risk,
                        "concentration_score": summary.concentration_score,
                        "drift_summary": summary.drift_summary,
                        "intelligence_confidence": summary.intelligence_confidence,
                        "is_stale": summary.is_stale,
                    })
                except Exception as exc:
                    summaries.append({
                        "portfolio_id": str(portfolio.id),
                        "portfolio_name": str(portfolio.name),
                        "is_stale": True,
                        "error": str(exc)[:200],
                    })

            return {
                "account_id": str(account.id),
                "account_name": str(account.name),
                "portfolio_count": len(portfolios),
                "items": summaries,
                "is_stale": any(bool(item.get("is_stale")) for item in summaries),
            }
        except HTTPException:
            raise
        except Exception as exc:
            return {
                "account_id": str(account_id),
                "items": [],
                "is_stale": True,
                "error": str(exc)[:200],
            }
