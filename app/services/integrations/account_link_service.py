from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.models import Account, AccountMembership, User


DEFAULT_PRO_ACCESS_STATUS = "connected"


@dataclass(frozen=True)
class AccountLinkInput:
    provider: str
    external_user_id: str
    email: str
    name: str | None = None


@dataclass(frozen=True)
class AccountLinkResult:
    backend_account_id: str
    backend_user_id: str
    pro_access_status: str
    created: bool


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _display_name(payload: AccountLinkInput) -> str:
    name = _clean(payload.name)
    if name:
        return name

    local_part = payload.email.split("@", 1)[0].strip()
    if local_part:
        return f"{local_part} IXAI Account"

    return "IXAI App Account"


def _supabase_shadow_password_hash() -> str:
    """Create an unusable legacy password hash for Supabase-linked backend users.

    Supabase remains the source identity. This backend user exists only so
    existing ownership and membership models can attach to an account without
    enabling password login.
    """
    return get_password_hash(f"supabase-linked:{uuid4().hex}")


class SupabaseAccountLinkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def link_account(self, payload: AccountLinkInput) -> AccountLinkResult:
        provider = _clean(payload.provider).lower()
        external_user_id = _clean(payload.external_user_id)
        email = _clean(payload.email).lower()

        existing = (
            self.db.query(Account)
            .filter(
                Account.external_provider == provider,
                Account.external_user_id == external_user_id,
            )
            .first()
        )

        if existing:
            return AccountLinkResult(
                backend_account_id=str(existing.id),
                backend_user_id=str(existing.owner_user_id),
                pro_access_status=existing.pro_access_status or DEFAULT_PRO_ACCESS_STATUS,
                created=False,
            )

        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                hashed_password=_supabase_shadow_password_hash(),
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()

        account = Account(
            name=_display_name(payload),
            owner_user_id=user.id,
            account_type="individual",
            external_provider=provider,
            external_user_id=external_user_id,
            external_email=email,
            pro_access_status=DEFAULT_PRO_ACCESS_STATUS,
        )
        self.db.add(account)
        self.db.flush()
        self.db.add(AccountMembership(account_id=account.id, user_id=user.id, role="owner"))
        self.db.commit()
        self.db.refresh(account)

        return AccountLinkResult(
            backend_account_id=str(account.id),
            backend_user_id=str(user.id),
            pro_access_status=account.pro_access_status or DEFAULT_PRO_ACCESS_STATUS,
            created=True,
        )
