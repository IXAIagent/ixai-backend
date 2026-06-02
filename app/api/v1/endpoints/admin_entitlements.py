from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.membership_service import (
    MANUAL_ENTITLEMENT_KEYS,
    MembershipService,
)


router = APIRouter(prefix="/admin/entitlements", tags=["admin-entitlements"])


class ManualEntitlementRequest(BaseModel):
    account_id: str | None = None
    provider: Literal["supabase"] | None = None
    external_user_id: str | None = None
    plan_code: Literal["free", "personal", "pro", "enterprise"] = "free"
    entitlements: dict[str, bool] = Field(default_factory=dict)

    @field_validator("account_id", "external_user_id", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None:
            return value
        return str(value).strip()

    @model_validator(mode="after")
    def require_account_or_external_identity(self):
        if self.account_id:
            return self

        if self.provider and self.external_user_id:
            return self

        raise ValueError("account_id or provider/external_user_id is required")

    @field_validator("entitlements")
    @classmethod
    def validate_entitlement_keys(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown_keys = sorted(set(value) - set(MANUAL_ENTITLEMENT_KEYS))

        if unknown_keys:
            raise ValueError("invalid entitlement key")

        return value


class ManualEntitlementResponse(BaseModel):
    ok: bool
    account_id: str
    plan_code: str
    entitlements: dict[str, bool]


def require_internal_admin_token(x_ixai_admin_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("IXAI_ADMIN_INTERNAL_TOKEN", "").strip()

    if not expected or not x_ixai_admin_token or x_ixai_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_entitlement_endpoint_disabled_or_forbidden",
        )


@router.post("/manual", response_model=ManualEntitlementResponse)
def apply_manual_entitlements(
    payload: ManualEntitlementRequest,
    _: None = Depends(require_internal_admin_token),
    db: Session = Depends(get_db),
) -> ManualEntitlementResponse:
    """Internal-only manual entitlement override for Pro connection testing.

    This endpoint is not a billing system and does not grant paid access through
    Stripe. It is protected by IXAI_ADMIN_INTERNAL_TOKEN and exists only for
    controlled internal verification of membership / entitlement-gated UI.
    """
    service = MembershipService(db)
    account = service.find_account_by_id(payload.account_id)

    if not account:
        account = service.find_account_by_external_identity(
            payload.provider,
            payload.external_user_id,
        )

    if not account:
        raise HTTPException(status_code=404, detail="account_not_found")

    snapshot = service.apply_manual_entitlements(
        account_id=str(account.id),
        entitlements=payload.entitlements,
        plan_code=payload.plan_code,
    )

    return ManualEntitlementResponse(
        account_id=snapshot.account_id,
        entitlements=snapshot.entitlements,
        ok=True,
        plan_code=snapshot.plan_code,
    )
