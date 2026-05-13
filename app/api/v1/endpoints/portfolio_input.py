import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import is_development_env
from app.core.database import get_db
from app.core.security import decode_access_token, get_password_hash
from app.models.models import CashPosition, CryptoPosition, FCNPosition, Portfolio, StockPosition, User
from app.services.normalization import normalize_stock_symbol

router = APIRouter()


class StockInput(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    current_price: float


class StockUpdateInput(BaseModel):
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None


class CryptoInput(BaseModel):
    symbol: str
    asset_type: Optional[str] = "crypto"
    quantity: float
    avg_price: Optional[float] = None
    current_price: float
    leverage: Optional[float] = None
    grid_lower: Optional[float] = None
    grid_upper: Optional[float] = None


class CryptoUpdateInput(BaseModel):
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    leverage: Optional[float] = None
    grid_lower: Optional[float] = None
    grid_upper: Optional[float] = None


class CashInput(BaseModel):
    currency: Optional[str] = "USD"
    amount: float


class CashUpdateInput(BaseModel):
    amount: Optional[float] = None


class FCNInput(BaseModel):
    name: Optional[str] = None
    fcn_code: Optional[str] = None
    issuer: Optional[str] = None
    notional_amount: Optional[float] = None
    underlyings: Optional[str] = None
    underlying_details: Optional[list[dict]] = None
    tenor_months: Optional[int] = None
    issue_date: Optional[date] = None
    maturity_date: Optional[date] = None
    settlement_currency: Optional[str] = None
    coupon_frequency: Optional[str] = None
    next_observation_date: Optional[date] = None
    next_coupon_date: Optional[date] = None
    observation_dates_json: Optional[str] = None
    coupon_dates_json: Optional[str] = None
    worst_of_symbol: Optional[str] = None
    initial_price: Optional[float] = None
    current_price: Optional[float] = None
    ki_level: Optional[float] = None
    ko_level: Optional[float] = None
    strike_level: Optional[float] = None
    coupon_rate: Optional[float] = None
    risk_level: Optional[str] = None


def get_dev_portfolio(db: Session):
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.name == "IXAI Demo Portfolio")
        .order_by(Portfolio.created_at.desc())
        .first()
    )

    if portfolio:
        return portfolio

    portfolio = db.query(Portfolio).first()
    if portfolio:
        return portfolio

    user = db.query(User).filter(User.email == "demo@ixai.local").first()
    if not user:
        user = User(email="demo@ixai.local", hashed_password=get_password_hash("demo"))
        db.add(user)
        db.commit()
        db.refresh(user)

    portfolio = Portfolio(
        name="IXAI Demo Portfolio",
        base_currency="USD",
        user_id=user.id,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    return portfolio


def get_bearer_token(request: Request):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def get_request_user(request: Request, db: Session):
    token = get_bearer_token(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_or_create_user_portfolio(db: Session, user: User):
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at.asc())
        .first()
    )

    if portfolio:
        return portfolio

    portfolio = Portfolio(
        name="IXAI Portfolio",
        base_currency="USD",
        user_id=user.id,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    return portfolio


def get_request_portfolio(request: Request, db: Session):
    user = get_request_user(request, db)
    if user:
        return get_or_create_user_portfolio(db, user)

    if is_development_env():
        return get_dev_portfolio(db)

    raise HTTPException(status_code=401, detail="Authentication required")


def get_write_portfolio(request: Request, db: Session):
    user = get_request_user(request, db)
    if user:
        return get_or_create_user_portfolio(db, user)

    if is_development_env():
        return get_dev_portfolio(db)

    raise HTTPException(status_code=401, detail="Authentication required")


def _clean_text(value: Optional[str], fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _clean_symbol(value: Optional[str], fallback: str = "") -> str:
    return _clean_text(value, fallback).upper()


def _distance_to_barrier_pct(
    initial_price: Optional[float],
    current_price: Optional[float],
    level_pct: Optional[float],
    direction: str,
) -> Optional[float]:
    if initial_price is None or current_price is None or level_pct is None:
        return None

    if initial_price <= 0 or current_price <= 0:
        return None

    barrier_price = initial_price * (level_pct / 100)
    if direction == "down":
        return ((current_price - barrier_price) / current_price) * 100

    return ((barrier_price - current_price) / current_price) * 100


def _fcn_risk_level(payload: FCNInput, distance_to_ki_pct: Optional[float]) -> str:
    risk_level = _clean_text(payload.risk_level).lower()
    if risk_level in {"low", "medium", "high"}:
        return risk_level

    if distance_to_ki_pct is None:
        return "low"

    if distance_to_ki_pct <= 10:
        return "high"

    if distance_to_ki_pct <= 20:
        return "medium"

    return "low"


def _fcn_underlyings_value(payload: FCNInput) -> Optional[str]:
    if payload.underlying_details is not None:
        return json.dumps(payload.underlying_details, ensure_ascii=False, separators=(",", ":"))

    underlyings = _clean_text(payload.underlyings)
    return underlyings or None


def _set_fcn_field_if_present(fcn: FCNPosition, field_name: str, value):
    if value is not None and hasattr(type(fcn), field_name):
        setattr(fcn, field_name, value)


def _calculate_current_value(quantity: Optional[float], current_price: Optional[float]) -> Optional[float]:
    if quantity is None or current_price is None:
        return None
    return quantity * current_price


@router.post("/stock")
def add_stock(payload: StockInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    stock = StockPosition(
        portfolio_id=portfolio.id,
        symbol=normalize_stock_symbol(payload.symbol),
        quantity=payload.quantity,
        avg_price=payload.avg_price,
        current_price=payload.current_price,
        current_value=payload.quantity * payload.current_price,
    )

    db.add(stock)
    db.commit()
    db.refresh(stock)

    return {"status": "ok", "message": "Stock added", "id": stock.id}


@router.get("/stocks")
def list_stocks(request: Request, db: Session = Depends(get_db)):
    portfolio = get_request_portfolio(request, db)
    if not portfolio:
        return []

    return portfolio.stocks


@router.patch("/stock/{stock_id}")
def update_stock(stock_id: str, payload: StockUpdateInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    stock = (
        db.query(StockPosition)
        .filter(
            StockPosition.id == stock_id,
            StockPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    if payload.quantity is not None:
        stock.quantity = payload.quantity
    if payload.avg_price is not None:
        stock.avg_price = payload.avg_price
    if payload.current_price is not None:
        stock.current_price = payload.current_price

    stock.current_value = _calculate_current_value(stock.quantity, stock.current_price)
    db.commit()
    db.refresh(stock)

    return {"status": "ok", "message": "Stock updated", "id": stock.id}


@router.delete("/stock/{stock_id}")
def delete_stock(stock_id: str, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    stock = (
        db.query(StockPosition)
        .filter(
            StockPosition.id == stock_id,
            StockPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    db.delete(stock)
    db.commit()

    return {"status": "ok", "message": "Stock deleted"}


@router.post("/crypto")
def add_crypto(payload: CryptoInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    crypto = CryptoPosition(
        portfolio_id=portfolio.id,
        symbol=payload.symbol.upper().strip(),
        asset_type=_clean_text(payload.asset_type, "crypto").lower(),
        quantity=payload.quantity,
        avg_price=payload.avg_price,
        current_price=payload.current_price,
        current_value=payload.quantity * payload.current_price,
        leverage=payload.leverage,
        grid_lower=payload.grid_lower,
        grid_upper=payload.grid_upper,
    )

    db.add(crypto)
    db.commit()
    db.refresh(crypto)

    return {"status": "ok", "message": "Crypto added", "id": crypto.id}


@router.get("/crypto")
def list_crypto(request: Request, db: Session = Depends(get_db)):
    portfolio = get_request_portfolio(request, db)
    if not portfolio:
        return []

    return portfolio.crypto_positions


@router.patch("/crypto/{crypto_id}")
def update_crypto(crypto_id: str, payload: CryptoUpdateInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    crypto = (
        db.query(CryptoPosition)
        .filter(
            CryptoPosition.id == crypto_id,
            CryptoPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not crypto:
        raise HTTPException(status_code=404, detail="Crypto position not found")

    if payload.quantity is not None:
        crypto.quantity = payload.quantity
    if payload.avg_price is not None:
        crypto.avg_price = payload.avg_price
    if payload.current_price is not None:
        crypto.current_price = payload.current_price
    if payload.leverage is not None:
        crypto.leverage = payload.leverage
    if payload.grid_lower is not None:
        crypto.grid_lower = payload.grid_lower
    if payload.grid_upper is not None:
        crypto.grid_upper = payload.grid_upper

    crypto.current_value = _calculate_current_value(crypto.quantity, crypto.current_price)
    db.commit()
    db.refresh(crypto)

    return {"status": "ok", "message": "Crypto updated", "id": crypto.id}


@router.delete("/crypto/{crypto_id}")
def delete_crypto(crypto_id: str, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    crypto = (
        db.query(CryptoPosition)
        .filter(
            CryptoPosition.id == crypto_id,
            CryptoPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not crypto:
        raise HTTPException(status_code=404, detail="Crypto position not found")

    db.delete(crypto)
    db.commit()

    return {"status": "ok", "message": "Crypto deleted"}


@router.post("/cash")
def upsert_cash(payload: CashInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="Cash amount must be positive")

    currency = _clean_symbol(payload.currency, portfolio.base_currency or "USD")
    cash = (
        db.query(CashPosition)
        .filter(
            CashPosition.portfolio_id == portfolio.id,
            CashPosition.currency == currency,
        )
        .first()
    )

    if cash:
        cash.amount = payload.amount
    else:
        cash = CashPosition(
            portfolio_id=portfolio.id,
            currency=currency,
            amount=payload.amount,
        )
        db.add(cash)

    db.commit()
    db.refresh(cash)

    return {"status": "ok", "message": "Cash updated", "id": cash.id}


@router.get("/cash")
def list_cash(request: Request, db: Session = Depends(get_db)):
    portfolio = get_request_portfolio(request, db)
    if not portfolio:
        return []

    return portfolio.cash_positions


@router.patch("/cash/{cash_id}")
def update_cash(cash_id: str, payload: CashUpdateInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    cash = (
        db.query(CashPosition)
        .filter(
            CashPosition.id == cash_id,
            CashPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not cash:
        raise HTTPException(status_code=404, detail="Cash position not found")

    if payload.amount is not None:
        if payload.amount < 0:
            raise HTTPException(status_code=400, detail="Cash amount must be positive")
        cash.amount = payload.amount

    db.commit()
    db.refresh(cash)

    return {"status": "ok", "message": "Cash updated", "id": cash.id}


@router.delete("/cash/{cash_id}")
def delete_cash(cash_id: str, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    cash = (
        db.query(CashPosition)
        .filter(
            CashPosition.id == cash_id,
            CashPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not cash:
        raise HTTPException(status_code=404, detail="Cash position not found")

    db.delete(cash)
    db.commit()

    return {"status": "ok", "message": "Cash deleted"}


@router.post("/fcn")
def add_fcn(payload: FCNInput, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    distance_to_ki_pct = _distance_to_barrier_pct(
        payload.initial_price,
        payload.current_price,
        payload.ki_level,
        "down",
    )
    distance_to_ko_pct = _distance_to_barrier_pct(
        payload.initial_price,
        payload.current_price,
        payload.ko_level,
        "up",
    )
    code = _clean_text(payload.fcn_code, _clean_text(payload.name, "FCN"))
    underlyings = _fcn_underlyings_value(payload)

    fcn = FCNPosition(
        portfolio_id=portfolio.id,
        name=_clean_text(payload.name, code),
        fcn_code=code,
        issuer=_clean_text(payload.issuer) or None,
        notional=payload.notional_amount,
        notional_amount=payload.notional_amount,
        underlyings=underlyings,
        tenor_months=payload.tenor_months,
        issue_date=payload.issue_date,
        maturity_date=payload.maturity_date,
        settlement_currency=_clean_symbol(payload.settlement_currency, "USD"),
        coupon_frequency=_clean_text(payload.coupon_frequency) or None,
        next_observation_date=payload.next_observation_date,
        next_coupon_date=payload.next_coupon_date,
        observation_dates_json=_clean_text(payload.observation_dates_json) or None,
        coupon_dates_json=_clean_text(payload.coupon_dates_json) or None,
        worst_of_symbol=_clean_symbol(payload.worst_of_symbol),
        ki_level=payload.ki_level,
        ko_level=payload.ko_level,
        strike_level=payload.strike_level,
        coupon_rate=payload.coupon_rate,
        distance_to_ki_pct=distance_to_ki_pct,
        distance_to_ko_pct=distance_to_ko_pct,
        risk_level=_fcn_risk_level(payload, distance_to_ki_pct),
    )
    _set_fcn_field_if_present(fcn, "underlyings", underlyings)
    _set_fcn_field_if_present(fcn, "initial_price", payload.initial_price)
    _set_fcn_field_if_present(fcn, "current_price", payload.current_price)
    _set_fcn_field_if_present(fcn, "ki_level", payload.ki_level)
    _set_fcn_field_if_present(fcn, "ko_level", payload.ko_level)
    _set_fcn_field_if_present(fcn, "strike_level", payload.strike_level)
    _set_fcn_field_if_present(fcn, "coupon_rate", payload.coupon_rate)

    db.add(fcn)
    db.commit()
    db.refresh(fcn)

    return {"status": "ok", "message": "FCN added", "id": fcn.id}


@router.get("/fcns")
def list_fcns(request: Request, db: Session = Depends(get_db)):
    portfolio = get_request_portfolio(request, db)
    if not portfolio:
        return []

    return portfolio.fcn_positions


@router.delete("/fcn/{fcn_id}")
def delete_fcn(fcn_id: str, request: Request, db: Session = Depends(get_db)):
    portfolio = get_write_portfolio(request, db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    fcn = (
        db.query(FCNPosition)
        .filter(
            FCNPosition.id == fcn_id,
            FCNPosition.portfolio_id == portfolio.id,
        )
        .first()
    )

    if not fcn:
        raise HTTPException(status_code=404, detail="FCN position not found")

    db.delete(fcn)
    db.commit()

    return {"status": "ok", "message": "FCN deleted"}
