from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.integrations.account_link_service import (
    AccountLinkInput,
    SupabaseAccountLinkService,
)


router = APIRouter(prefix="/integrations", tags=["integrations"])


class SupabaseAccountLinkRequest(BaseModel):
    provider: Literal["supabase"]
    external_user_id: str = Field(min_length=1)
    email: str = Field(min_length=3)
    name: str | None = None

    @field_validator("external_user_id", "email", "name", mode="before")
    @classmethod
    def strip_strings(cls, value):
        if value is None:
            return value
        return str(value).strip()

    @field_validator("email")
    @classmethod
    def require_email_shape(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("valid email is required")
        return value.lower()


class SupabaseAccountLinkResponse(BaseModel):
    backend_account_id: str
    backend_user_id: str
    pro_access_status: Literal["connected", "preview", "active", "expired", "revoked"]
    created: bool


@router.post("/supabase/account-link", response_model=SupabaseAccountLinkResponse)
def link_supabase_account(
    payload: SupabaseAccountLinkRequest,
    db: Session = Depends(get_db),
) -> SupabaseAccountLinkResponse:
    """Create or find the backend account linked to a Supabase App user.

    TODO(v1.53+): Production callers must be authenticated with a trusted
    server-to-server mechanism such as a shared internal token, mTLS, or a
    signed request from the IXAI App Next server. This endpoint must not be
    treated as a public browser API.
    """
    result = SupabaseAccountLinkService(db).link_account(
        AccountLinkInput(
            provider=payload.provider,
            external_user_id=payload.external_user_id,
            email=payload.email,
            name=payload.name,
        )
    )

    return SupabaseAccountLinkResponse(
        backend_account_id=result.backend_account_id,
        backend_user_id=result.backend_user_id,
        pro_access_status=result.pro_access_status,
        created=result.created,
    )
