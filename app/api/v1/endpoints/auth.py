import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
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

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMITS = {
    "login": 5,
    "register": 3,
}
_rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"

    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def check_rate_limit(request: Request, route_key: str) -> None:
    limit = RATE_LIMITS.get(route_key)
    if not limit:
        return

    try:
        now = time.monotonic()
        bucket_key = f"{route_key}:{_client_ip(request)}"

        with _rate_limit_lock:
            hits = _rate_limit_hits[bucket_key]
            while hits and now - hits[0] >= RATE_LIMIT_WINDOW_SECONDS:
                hits.popleft()

            if len(hits) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Please wait and try again.",
                )

            hits.append(now)
    except HTTPException:
        raise
    except Exception:
        return


@router.post("/register")
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "register")
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
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "login")
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
