from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.models import User, Portfolio

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            is_active=True,
        )

        db.add(user)
        db.flush()

        portfolio = Portfolio(
            name="IXAI Portfolio",
            base_currency="USD",
            user_id=user.id,
        )
        db.add(portfolio)

        db.commit()
        db.refresh(user)

        return {
            "status": "ok",
            "message": "User registered",
            "email": user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("REGISTER ERROR:", str(e))
        raise


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user.id})

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }
