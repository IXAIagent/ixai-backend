from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.models.models import Account, Entitlement, Subscription


PlanCode = Literal["free", "personal", "pro", "enterprise"]
SubscriptionStatus = Literal["active", "trialing", "past_due", "canceled", "expired"]

ENTITLEMENT_KEYS = (
    "daily_brief",
    "weekly_brief",
    "watchlist",
    "pro_preview",
    "portfolio",
    "fcn_monitoring",
    "risk_engine",
    "ai_copilot",
)

FREE_ENTITLEMENTS = {
    "daily_brief": True,
    "weekly_brief": True,
    "watchlist": True,
    "pro_preview": False,
    "portfolio": False,
    "fcn_monitoring": False,
    "risk_engine": False,
    "ai_copilot": False,
}


@dataclass(frozen=True)
class MembershipSnapshot:
    account_id: str
    plan_code: str
    status: str
    entitlements: dict[str, bool]


class MembershipService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_account_by_external_identity(
        self,
        provider: str | None,
        external_user_id: str | None,
    ) -> Account | None:
        provider = str(provider or "").strip().lower()
        external_user_id = str(external_user_id or "").strip()

        if not provider or not external_user_id:
            return None

        return (
            self.db.query(Account)
            .filter(
                Account.external_provider == provider,
                Account.external_user_id == external_user_id,
            )
            .first()
        )

    def get_account_membership(self, account_id: str) -> Subscription | None:
        return (
            self.db.query(Subscription)
            .filter(Subscription.account_id == str(account_id))
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def ensure_default_membership(self, account_id: str) -> MembershipSnapshot:
        subscription = self.get_account_membership(account_id)
        now = datetime.utcnow()

        if not subscription:
            subscription = Subscription(
                account_id=account_id,
                plan_code="free",
                status="active",
                provider="manual",
                created_at=now,
                updated_at=now,
            )
            self.db.add(subscription)
            self.db.flush()

        existing = {
            entitlement.key: entitlement
            for entitlement in self.db.query(Entitlement)
            .filter(Entitlement.account_id == str(account_id))
            .all()
        }

        for key, enabled in FREE_ENTITLEMENTS.items():
            if key in existing:
                continue

            self.db.add(
                Entitlement(
                    account_id=account_id,
                    key=key,
                    enabled=enabled,
                    source="plan",
                    created_at=now,
                    updated_at=now,
                )
            )

        self.db.commit()
        return self.snapshot(account_id)

    def get_entitlements(self, account_id: str) -> dict[str, bool]:
        rows = (
            self.db.query(Entitlement)
            .filter(Entitlement.account_id == str(account_id))
            .all()
        )
        entitlements = {key: False for key in ENTITLEMENT_KEYS}

        for row in rows:
            if row.key in entitlements:
                entitlements[row.key] = bool(row.enabled)

        return entitlements

    def has_entitlement(self, account_id: str, key: str) -> bool:
        if key not in ENTITLEMENT_KEYS:
            return False

        row = (
            self.db.query(Entitlement)
            .filter(Entitlement.account_id == str(account_id), Entitlement.key == key)
            .first()
        )

        if not row or not row.enabled:
            return False

        if row.expires_at and row.expires_at <= datetime.utcnow():
            return False

        return True

    def snapshot(self, account_id: str) -> MembershipSnapshot:
        subscription = self.get_account_membership(account_id)

        if not subscription:
            return MembershipSnapshot(
                account_id=str(account_id),
                plan_code="free",
                status="active",
                entitlements={key: False for key in ENTITLEMENT_KEYS},
            )

        return MembershipSnapshot(
            account_id=str(account_id),
            plan_code=subscription.plan_code,
            status=subscription.status,
            entitlements=self.get_entitlements(account_id),
        )
