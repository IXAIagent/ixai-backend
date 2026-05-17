from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.models import CryptoPosition, FCNPosition, StockPosition
from app.services.alert_service import build_alert_key, close_resolved_alerts, ensure_open_alert
from app.services.crypto_subtypes import get_crypto_base_type


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def check_fcn_risks(db: Session, portfolio_id: str, active_keys: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    created: list[dict[str, str]] = []
    fcns = db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio_id).all()

    for fcn in fcns:
        code = fcn.fcn_code or fcn.name or "FCN"
        worst = fcn.worst_of_symbol or "-"
        distance_to_ki = _safe_float(fcn.distance_to_ki_pct, 999)
        distance_to_ko = _safe_float(fcn.distance_to_ko_pct, 999)

        if distance_to_ki < 3:
            title = f"{code} 接近 KI 區域"
            message = f"Worst-of {worst} 距 KI 僅約 {distance_to_ki:.1f}%，已進入高風險區。"
            severity = "high"
        elif distance_to_ki < 8:
            title = f"{code} KI 風險升高"
            message = f"Worst-of {worst} 距 KI 約 {distance_to_ki:.1f}%，請留意風險。"
            severity = "medium"
        else:
            title = None

        if title:
            key = build_alert_key("fcn", code, title)
            active_keys.add(key)
            _, created_new = ensure_open_alert(db, portfolio_id, "fcn", code, severity, title, message)
            if created_new:
                created.append({"type": "fcn", "title": title, "severity": severity})

        if distance_to_ko < 5:
            title = f"{code} 接近 KO 條件"
            message = f"{code} 距 KO 約 {distance_to_ko:.1f}%，請留意是否可能提前出場。"
            severity = "low"
            key = build_alert_key("fcn", code, title)
            active_keys.add(key)
            _, created_new = ensure_open_alert(db, portfolio_id, "fcn", code, severity, title, message)
            if created_new:
                created.append({"type": "fcn", "title": title, "severity": severity})

    return created


def check_crypto_risks(db: Session, portfolio_id: str, active_keys: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    created: list[dict[str, str]] = []
    cryptos = db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio_id).all()

    for c in cryptos:
        symbol = c.symbol or "CRYPTO"
        asset_type = get_crypto_base_type(c.asset_type)
        leverage = _safe_float(c.leverage, 0)
        current_price = _safe_float(c.current_price, 0)
        grid_upper = _safe_float(c.grid_upper, 0)
        grid_lower = _safe_float(c.grid_lower, 0)

        title = None
        severity = "low"
        message = ""

        if asset_type == "grid" and grid_upper > 0 and grid_lower > 0 and current_price > 0:
            grid_range = grid_upper - grid_lower
            if grid_range > 0:
                position_pct = ((current_price - grid_lower) / grid_range) * 100
                if current_price > grid_upper:
                    title = f"{symbol} Grid 突破上緣"
                    message = f"{symbol} 已高於 grid 上緣，建議檢查是否重新建立區間。"
                    severity = "high"
                elif current_price < grid_lower:
                    title = f"{symbol} Grid 跌破下緣"
                    message = f"{symbol} 已低於 grid 下緣，請留意是否接近止損或需重設區間。"
                    severity = "high"
                elif position_pct >= 95:
                    title = f"{symbol} Grid 接近區間上緣"
                    message = f"{symbol} 位於區間約 {position_pct:.1f}% 處，已非常接近上緣。"
                    severity = "medium"
                elif position_pct <= 5:
                    title = f"{symbol} Grid 接近區間下緣"
                    message = f"{symbol} 位於區間約 {position_pct:.1f}% 處，已非常接近下緣。"
                    severity = "medium"

        if leverage >= 10:
            title = f"{symbol} 槓桿偏高"
            message = f"{symbol} 目前槓桿約 {leverage:.1f}x，風險偏高。"
            severity = "high"
        elif leverage >= 5 and not title:
            title = f"{symbol} 槓桿需留意"
            message = f"{symbol} 目前槓桿約 {leverage:.1f}x，請控管風險。"
            severity = "medium"

        if title:
            key = build_alert_key("crypto", symbol, title)
            active_keys.add(key)
            _, created_new = ensure_open_alert(db, portfolio_id, "crypto", symbol, severity, title, message)
            if created_new:
                created.append({"type": "crypto", "title": title, "severity": severity})

    return created


def check_stock_risks(db: Session, portfolio_id: str, active_keys: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    created: list[dict[str, str]] = []
    stocks = db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio_id).all()
    total_value = sum(_safe_float(s.current_value, 0) for s in stocks) or 1

    for s in stocks:
        symbol = s.symbol or "STOCK"
        current_price = _safe_float(s.current_price, 0)
        avg_cost = _safe_float(s.avg_price, 0)
        current_value = _safe_float(s.current_value, 0)

        title = None
        severity = "low"
        message = ""

        if avg_cost > 0 and current_price > 0:
            drawdown_pct = ((current_price - avg_cost) / avg_cost) * 100
            if drawdown_pct <= -20:
                title = f"{symbol} 深度跌破成本"
                message = f"{symbol} 相對成本已下跌約 {abs(drawdown_pct):.1f}%，請高度留意。"
                severity = "high"
            elif drawdown_pct <= -10:
                title = f"{symbol} 跌破成本"
                message = f"{symbol} 相對成本已下跌約 {abs(drawdown_pct):.1f}%，請留意風險。"
                severity = "medium"

        concentration_pct = (current_value / total_value) * 100 if current_value > 0 else 0
        if concentration_pct >= 40:
            title = f"{symbol} 集中度偏高"
            message = f"{symbol} 佔股票資產約 {concentration_pct:.1f}%，單一標的集中度偏高。"
            severity = "medium"

        if title:
            key = build_alert_key("stock", symbol, title)
            active_keys.add(key)
            _, created_new = ensure_open_alert(db, portfolio_id, "stock", symbol, severity, title, message)
            if created_new:
                created.append({"type": "stock", "title": title, "severity": severity})

    return created


def run_risk_check(db: Session, portfolio_id: str) -> dict[str, Any]:
    active_keys: set[tuple[str, str, str]] = set()
    created: list[dict[str, str]] = []
    created.extend(check_fcn_risks(db, portfolio_id, active_keys))
    created.extend(check_crypto_risks(db, portfolio_id, active_keys))
    created.extend(check_stock_risks(db, portfolio_id, active_keys))
    closed = close_resolved_alerts(db, portfolio_id, active_keys)
    db.commit()
    return {"created": created, "closed_count": len(closed)}
