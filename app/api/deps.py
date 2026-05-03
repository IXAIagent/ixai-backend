from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import User, Portfolio

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

