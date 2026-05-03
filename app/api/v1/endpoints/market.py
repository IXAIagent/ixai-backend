from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.portfolio_input import (
    get_bearer_token,
    get_dev_portfolio,
    get_or_create_user_portfolio,
)
from app.core.database import get_db
from app.services.market_data.service import MarketDataService
from app.services.portfolio_service import get_portfolio_positions

router = APIRouter()
market_data_service = MarketDataService()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default

        return number
    except Exception:
        return default


def _clean_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _price_is_usable(value: Any) -> bool:
    if value is None:
        return False

    try:
        number = float(value)
    except Exception:
        return False

    return not (math.isnan(number) or math.isinf(number))


def _source_name(price_result: Any) -> str:
    source = str(getattr(price_result, "source", "") or "").strip().lower()
    return source or "unknown"


def _source_summary_payload(source_summary: Counter[str]) -> dict[str, int]:
    payload = {
        "yahoo": source_summary.get("yahoo", 0),
        "binance": source_summary.get("binance", 0),
        "manual": source_summary.get("manual", 0),
    }

    for source, count in source_summary.items():
        if source not in payload:
            payload[source] = count

    return payload


def update_position_price(position: Any, price_result: Any) -> bool:
    price = getattr(price_result, "price", None)
    if not _price_is_usable(price):
        return False

    price_value = float(price)
    quantity = _safe_float(getattr(position, "quantity", None), default=0.0)

    if hasattr(position, "current_price"):
        setattr(position, "current_price", price_value)

    if hasattr(position, "current_value"):
        setattr(position, "current_value", quantity * price_value)

    return True


def _get_refresh_portfolio(request: Request, db: Session):
    token = get_bearer_token(request)
    if token:
        user = get_current_user(token=token, db=db)
        return get_or_create_user_portfolio(db, user), "user", None

    return get_dev_portfolio(db), "demo", None


def _extract_fcn_symbols(fcn: Any) -> list[str]:
    raw_values: list[Any] = []
    for attr in (
        "underlying_symbol",
        "underlying_symbols",
        "underlyings",
        "worst_of_symbol",
        "worst_of",
        "symbol",
    ):
        value = getattr(fcn, attr, None)
        if value:
            raw_values.append(value)

    symbols: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        if isinstance(value, (list, tuple, set)):
            parts = value
        else:
            parts = re.split(r"[,/|;\s]+", str(value))

        for part in parts:
            symbol = _clean_symbol(part)
            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)

    return symbols


@router.get("/price/{symbol}")
def get_market_price(
    symbol: str,
    asset_type: str | None = Query(default=None),
):
    result = market_data_service.get_price(symbol, asset_type=asset_type)
    return result.to_dict()


@router.post("/refresh-prices")
def refresh_prices(request: Request, db: Session = Depends(get_db)):
    updated_symbols: list[str] = []
    failed_symbols: list[str] = []
    fcn_preview: list[dict[str, Any]] = []
    source_summary: Counter[str] = Counter()
    errors: list[str] = []
    portfolio_source = "unknown"

    try:
        portfolio, portfolio_source, portfolio_error = _get_refresh_portfolio(
            request,
            db,
        )
        if portfolio_error:
            errors.append(portfolio_error)

        if not portfolio:
            return {
                "status": "ok",
                "updated_count": 0,
                "failed_symbols": [],
                "price_source_summary": _source_summary_payload(source_summary),
                "fcn_preview": [],
                "fallback": True,
                "portfolio_source": "demo",
                "error": "No portfolio found",
            }

        positions = get_portfolio_positions(db, portfolio.id)

        for position in [*positions.get("stocks", []), *positions.get("cryptos", [])]:
            symbol = _clean_symbol(getattr(position, "symbol", None))
            if not symbol:
                continue

            try:
                asset_type = getattr(position, "asset_type", None)
                price_result = market_data_service.get_price(symbol, asset_type=asset_type)
                source_summary[_source_name(price_result)] += 1

                if update_position_price(position, price_result):
                    updated_symbols.append(symbol)
                else:
                    failed_symbols.append(symbol)
            except Exception as exc:
                failed_symbols.append(symbol)
                errors.append(f"{symbol}: {exc}")

        for fcn in positions.get("fcns", []):
            for symbol in _extract_fcn_symbols(fcn):
                try:
                    price_result = market_data_service.get_price(symbol, asset_type="stock")
                    source_summary[_source_name(price_result)] += 1
                    price = getattr(price_result, "price", None)

                    if not _price_is_usable(price):
                        failed_symbols.append(symbol)
                        price = None

                    fcn_preview.append(
                        {
                            "symbol": symbol,
                            "price": price,
                            "source": getattr(price_result, "source", None),
                        }
                    )
                except Exception as exc:
                    failed_symbols.append(symbol)
                    errors.append(f"{symbol}: {exc}")
                    fcn_preview.append(
                        {
                            "symbol": symbol,
                            "price": None,
                            "source": "manual",
                        }
                    )

        db.commit()
    except Exception as exc:
        db.rollback()
        errors.append(str(exc))

    return {
        "status": "ok",
        "updated_count": len(updated_symbols),
        "failed_symbols": sorted(set(failed_symbols)),
        "price_source_summary": _source_summary_payload(source_summary),
        "fcn_preview": fcn_preview,
        "fallback": portfolio_source != "user",
        "portfolio_source": portfolio_source,
        "updated_symbols": updated_symbols,
        "error": "; ".join(errors) if errors else None,
    }
