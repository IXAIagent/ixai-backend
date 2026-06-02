from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.membership_service import ENTITLEMENT_KEYS, MembershipService


router = APIRouter(prefix="/entitlements", tags=["entitlements"])


class EntitlementsResponse(BaseModel):
    plan: str
    entitlements: dict[str, bool]


@router.get("/me", response_model=EntitlementsResponse)
def get_entitlements_me(
    provider: str | None = Query(default=None),
    external_user_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EntitlementsResponse:
    """Return the feature-gate entitlement map for an already-linked account."""
    snapshot = MembershipService(db).snapshot_for_identity(
        account_id=account_id,
        provider=provider,
        external_user_id=external_user_id,
    )

    if not snapshot:
        raise HTTPException(status_code=404, detail="not_linked")

    return EntitlementsResponse(
        plan=snapshot.plan_code,
        entitlements={
            key: bool(snapshot.entitlements.get(key, False)) for key in ENTITLEMENT_KEYS
        },
    )
