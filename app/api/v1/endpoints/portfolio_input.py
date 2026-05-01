from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, StockPosition, CryptoPosition, Portfolio


router = APIRouter(prefix="/portfolio", tags=["portfolio_input"])


# -----------------------
# Helper：每個 user 都有自己的 default portfolio
# -----------------------
def get_or_create_default_portfolio(
    db: Session,
    current_user: User,
) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id)
        .first()
    )

    if portfolio:
        return portfolio

    new_portfolio = Portfolio(
        name="User Portfolio",
        base_currency="USD",
        user_id=current_user.id,
    )

    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)

    return new_portfolio


# -----------------------
# 查詢自己的 Portfolio
# -----------------------
@router.get("/me")
def get_my_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = get_or_create_default_portfolio(db, current_user)

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "user_id": portfolio.user_id,
    }


# -----------------------
# 新增股票：只會加到目前登入者 portfolio
# -----------------------
@router.post("/stock")
def add_stock(
    symbol: str,
    quantity: float,
    avg_cost: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = get_or_create_default_portfolio(db, current_user)

    position = StockPosition(
        portfolio_id=portfolio.id,
        symbol=symbol.upper(),
        quantity=quantity,
        avg_price=avg_cost,
    )

    db.add(position)
    db.commit()
    db.refresh(position)

    return {
        "status": "success",
        "message": f"{symbol.upper()} 已加入",
        "portfolio_id": portfolio.id,
        "stock_id": position.id,
    }


# -----------------------
# 查詢自己的股票
# -----------------------
from app.services.market_data.service import MarketDataService
from app.services.risk.volatility import calculate_volatility


@router.get("/stocks")
def list_my_stocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = get_or_create_default_portfolio(db, current_user)

    stocks = (
        db.query(StockPosition)
        .filter(StockPosition.portfolio_id == portfolio.id)
        .all()
    )

    crypto_positions = (
        db.query(CryptoPosition)
        .filter(CryptoPosition.portfolio_id == portfolio.id)
        .all()
    )

    service = MarketDataService()

    result = []

    # 股票
    for s in stocks:
        symbol = str(s.symbol or "").upper().strip()

        try:
            current_price = service.get_price(symbol)
        except Exception:
            current_price = s.avg_price

        try:
            volatility = calculate_volatility(symbol)
        except Exception:
            volatility = None

        volatility_pct = round(volatility * 100, 2) if volatility is not None else None
        if volatility_pct is None:
            risk_tag = None
        elif volatility_pct < 25:
            risk_tag = "LOW"
        elif volatility_pct <= 60:
            risk_tag = "MEDIUM"
        else:
            risk_tag = "HIGH"

        value = float(s.quantity or 0) * float(current_price or 0)
        result.append({
            "symbol": symbol,
            "quantity": s.quantity,
            "avg_price": s.avg_price,
            "current_price": round(float(current_price or 0), 2),
            "volatility": volatility_pct,
            "risk_tag": risk_tag,
            "value": round(value, 2),
        })

    # Crypto
    for c in crypto_positions:
        symbol = str(c.symbol or "").upper().strip()

        try:
            current_price = service.get_price(symbol)
        except Exception:
            current_price = c.avg_price

        try:
            volatility = calculate_volatility(symbol)
        except Exception:
            volatility = None

        volatility_pct = round(volatility * 100, 2) if volatility is not None else None
        if volatility_pct is None:
            risk_tag = None
        elif volatility_pct < 25:
            risk_tag = "LOW"
        elif volatility_pct <= 60:
            risk_tag = "MEDIUM"
        else:
            risk_tag = "HIGH"

        value = float(c.quantity or 0) * float(current_price or 0)

        result.append({
            "symbol": symbol,
            "quantity": c.quantity,
            "avg_price": c.avg_price,
            "current_price": round(float(current_price or 0), 2),
            "volatility": volatility_pct,
            "risk_tag": risk_tag,
            "value": round(value, 2),
        })
    return result


# -----------------------
# 新增 Crypto：只會加到目前登入者 portfolio
# -----------------------
@router.post("/crypto")
def add_crypto(
    symbol: str,
    quantity: float,
    price: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = get_or_create_default_portfolio(db, current_user)

    position = CryptoPosition(
    portfolio_id=portfolio.id,
    symbol=symbol.upper(),
    quantity=quantity,
    avg_price=price,
)

    db.add(position)
    db.commit()
    db.refresh(position)

    return {
        "status": "success",
        "message": f"{symbol.upper()} 已加入",
        "portfolio_id": portfolio.id,
        "crypto_id": position.id,
    }


# -----------------------
# 查詢自己的 Crypto
# -----------------------
@router.get("/crypto")
def list_my_crypto(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = get_or_create_default_portfolio(db, current_user)

    crypto = (
        db.query(CryptoPosition)
        .filter(CryptoPosition.portfolio_id == portfolio.id)
        .all()
    )

    return crypto
