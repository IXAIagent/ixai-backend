from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.membership_service import ENTITLEMENT_KEYS, MembershipService


router = APIRouter(prefix="/membership", tags=["membership"])


class MembershipResponse(BaseModel):
    account_id: str
    plan_code: str
    status: str
    entitlements: dict[str, bool]


@router.get("/me", response_model=MembershipResponse)
def get_membership_me(
    account_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    external_user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    """Return membership and entitlement state for an already-linked account.

    TODO(v1.55+): This endpoint is intended for the IXAI App Next API proxy.
    Production callers should be protected by a trusted server-to-server
    mechanism before Portfolio / FCN data is exposed.
    """
    service = MembershipService(db)
    snapshot = service.snapshot_for_identity(
        account_id=account_id,
        provider=provider,
        external_user_id=external_user_id,
    )

    if not snapshot:
        raise HTTPException(status_code=404, detail="not_linked")

    entitlements = {key: bool(snapshot.entitlements.get(key, False)) for key in ENTITLEMENT_KEYS}

    return MembershipResponse(
        account_id=snapshot.account_id,
        plan_code=snapshot.plan_code,
        status=snapshot.status,
        entitlements=entitlements,
    )
