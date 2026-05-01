from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.models import Alert, CryptoPosition, FCNPosition, Portfolio, StockPosition

from app.services.market_data.service import MarketDataService


def get_portfolio(db: Session, portfolio_id: str) -> Portfolio | None:
    return db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()


def get_portfolio_positions(db: Session, portfolio_id: str) -> dict[str, list[Any]]:
    return {
        "stocks": db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio_id).all(),
        "cryptos": db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio_id).all(),
        "fcns": db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio_id).all(),
    }


def get_portfolio_alerts(db: Session, portfolio_id: str) -> list[Alert]:
    query = db.query(Alert).filter(Alert.portfolio_id == portfolio_id)
    if hasattr(Alert, "triggered_at"):
        query = query.order_by(Alert.triggered_at.desc())
    return query.all()


def _value_from_position(position: Any, market_data_service: MarketDataService):
    quantity = float(getattr(position, "quantity", 0) or 0)

    symbol = str(getattr(position, "symbol", "") or "").upper().strip()
    position_type = position.__class__.__name__

    if position_type in {"StockPosition", "CryptoPosition"} and symbol:
        try:
            price = market_data_service.get_price(symbol)
            return quantity * float(price)
        except Exception:
            pass

    price = (
        getattr(position, "current_price", None)
        or getattr(position, "avg_price", None)
        or 0
    )

    return quantity * float(price or 0)


def calculate_portfolio_values(stocks, cryptos, fcns) -> dict[str, float]:
    market_data_service = MarketDataService()
    stock_value = float(sum(_value_from_position(s, market_data_service) for s in stocks))
    crypto_value = float(sum(_value_from_position(c, market_data_service) for c in cryptos))

    fcn_value = 0.0
    for f in fcns:
        notional_amount = getattr(f, "notional_amount", None)
        notional = getattr(f, "notional", None)
        fcn_value += float((notional_amount if notional_amount is not None else notional) or 0)

    total_value = stock_value + crypto_value + fcn_value
    return {
        "stock_value": stock_value,
        "crypto_value": crypto_value,
        "fcn_value": fcn_value,
        "total_value": total_value,
    }


def calculate_risk_level(alerts: list[Alert]) -> str:
    open_alerts = [a for a in alerts if (getattr(a, "status", None) or "open") == "open"]
    severities = [((getattr(a, "severity", None) or getattr(a, "level", None) or "").lower()) for a in open_alerts]
    if "critical" in severities or "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def serialize_alert(a: Alert) -> dict[str, Any]:
    severity = getattr(a, "severity", None) or getattr(a, "level", None) or ""
    triggered_at = getattr(a, "triggered_at", None)
    return {
        "id": getattr(a, "id", None),
        "severity": severity,
        "level": severity,
        "title": getattr(a, "title", None) or "",
        "message": getattr(a, "message", None) or "",
        "asset_class": getattr(a, "asset_class", None) or "",
        "asset_ref": getattr(a, "asset_ref", None) or "",
        "status": getattr(a, "status", None) or "open",
        "triggered_at": triggered_at.isoformat() if triggered_at else None,
    }


def build_alert_summary(alerts: list[Alert], limit: int = 5) -> list[dict[str, Any]]:
    open_alerts = [a for a in alerts if (getattr(a, "status", None) or "open") == "open"]
    return [serialize_alert(a) for a in open_alerts[:limit]]


def build_fcn_summary(fcns: list[FCNPosition], limit: int = 5) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for f in fcns[:limit]:
        result.append({
            "id": getattr(f, "id", None),
            "code": getattr(f, "fcn_code", None) or getattr(f, "name", None) or "FCN",
            "worst_of": getattr(f, "worst_of_symbol", None) or "",
            "distance_to_ki_pct": getattr(f, "distance_to_ki_pct", None),
            "distance_to_ko_pct": getattr(f, "distance_to_ko_pct", None),
            "risk_level": getattr(f, "risk_level", None) or "low",
        })
    return result


def build_portfolio_summary(db: Session, portfolio_id: str) -> dict[str, Any] | None:
    portfolio = get_portfolio(db, portfolio_id)
    if not portfolio:
        return None

    positions = get_portfolio_positions(db, portfolio_id)
    stocks = positions["stocks"]
    cryptos = positions["cryptos"]
    fcns = positions["fcns"]
    alerts = get_portfolio_alerts(db, portfolio_id)
    values = calculate_portfolio_values(stocks, cryptos, fcns)
    risk_level = calculate_risk_level(alerts)

    return {
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "total_value": values["total_value"],
        "stock_value": values["stock_value"],
        "crypto_value": values["crypto_value"],
        "fcn_value": values["fcn_value"],
        "stock_count": len(stocks),
        "crypto_count": len(cryptos),
        "fcn_count": len(fcns),
        "risk_level": risk_level,
        "overall_risk_level": risk_level,
        "alerts": build_alert_summary(alerts),
        "latest_alerts": build_alert_summary(alerts),
        "fcn_summary": build_fcn_summary(fcns),
    }


def build_allocation_payload(db: Session, portfolio_id: str) -> dict[str, Any] | None:
    summary = build_portfolio_summary(db, portfolio_id)
    if not summary:
        return None
    total = summary["total_value"] or 0

    def pct(value: float) -> float:
        return round((value / total) * 100, 2) if total > 0 else 0.0

    return {
        "portfolio_id": summary["portfolio_id"],
        "portfolio_name": summary["portfolio_name"],
        "total_value": total,
        "items": [
            {"asset_class": "stock", "value": summary["stock_value"], "percentage": pct(summary["stock_value"])},
            {"asset_class": "crypto", "value": summary["crypto_value"], "percentage": pct(summary["crypto_value"])},
            {"asset_class": "fcn", "value": summary["fcn_value"], "percentage": pct(summary["fcn_value"])},
        ],
    }


def build_alerts_payload(db: Session, portfolio_id: str) -> dict[str, Any] | None:
    portfolio = get_portfolio(db, portfolio_id)
    if not portfolio:
        return None

    alerts = get_portfolio_alerts(db, portfolio_id)
    open_alerts = [a for a in alerts if (getattr(a, "status", None) or "open") == "open"]
    closed_alerts = [a for a in alerts if (getattr(a, "status", None) or "open") == "closed"][:20]

    return {
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "open_alerts": [serialize_alert(a) for a in open_alerts],
        "closed_alerts": [serialize_alert(a) for a in closed_alerts],
        "open_count": len(open_alerts),
        "closed_count": len(closed_alerts),
    }
