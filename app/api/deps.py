from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import Account, AccountMembership, Portfolio, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_owned_portfolio(
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Portfolio:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if portfolio.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return portfolio


def user_can_access_portfolio(
    db: Session, user: User, portfolio: Portfolio
) -> bool:
    """v3C: ownership OR account membership grants read access to a portfolio."""
    if portfolio.user_id == user.id:
        return True
    account_id = getattr(portfolio, "account_id", None)
    if not account_id:
        return False
    account = db.query(Account).filter(Account.id == account_id).first()
    if account and account.owner_user_id == user.id:
        return True
    membership = (
        db.query(AccountMembership)
        .filter(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == user.id,
        )
        .first()
    )
    return membership is not None


def resolve_portfolio_for_user(
    portfolio_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Portfolio:
    """v3C: resolve a portfolio from optional query param with permission check.

    Behaviour:
    - portfolio_id provided + user owns OR is member → return portfolio
    - portfolio_id provided + user has no access → 403
    - portfolio_id provided + not found → 404
    - portfolio_id missing → fall back to user's first owned portfolio (404 if none)
    """
    if portfolio_id:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        if not user_can_access_portfolio(db, current_user, portfolio):
            raise HTTPException(status_code=403, detail="Not authorized for this portfolio")
        return portfolio

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id)
        .order_by(Portfolio.created_at.asc())
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")
    return portfolio
