from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user
from app.models.models import User, Portfolio

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db)):
    email = None
    password = None

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
    else:
        email = request.query_params.get("email")
        password = request.query_params.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="缺少 email 或 password")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    portfolio = Portfolio(
        name="User Portfolio",
        base_currency="USD",
        user_id=user.id,
    )
    db.add(portfolio)
    db.commit()

    token = create_access_token(str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    username = None
    password = None

    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        username = form.get("username") or form.get("email")
        password = form.get("password")
    elif "application/json" in content_type:
        data = await request.json()
        username = data.get("username") or data.get("email")
        password = data.get("password")
    else:
        username = request.query_params.get("username") or request.query_params.get("email")
        password = request.query_params.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="缺少帳號或密碼")

    user = db.query(User).filter(User.email == username).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    token = create_access_token(str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }
