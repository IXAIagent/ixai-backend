from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import Account, AccountMembership, User


WRITE_ROLES = {"owner", "admin"}
READ_ROLES = {"owner", "admin", "viewer"}


def get_membership(db: Session, account_id: str, user: User) -> AccountMembership | None:
    return (
        db.query(AccountMembership)
        .filter(
            AccountMembership.account_id == str(account_id),
            AccountMembership.user_id == user.id,
        )
        .first()
    )


def require_account_access(db: Session, account_id: str, user: User) -> tuple[Account, AccountMembership]:
    account = db.query(Account).filter(Account.id == str(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    membership = get_membership(db, str(account.id), user)
    if not membership or membership.role not in READ_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized for this account")

    return account, membership


def require_account_write_access(db: Session, account_id: str, user: User) -> tuple[Account, AccountMembership]:
    account, membership = require_account_access(db, account_id, user)
    if membership.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Account write access required")
    return account, membership
