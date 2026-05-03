from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.models import CryptoPosition, FCNPosition, StockPosition


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        return number if number == number else default
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        return number if number == number else None
    except Exception:
        return None


def _clamp_score(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _level_from_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _score_from_level(level: Any) -> int:
    normalized = str(level or "").strip().lower()
    if normalized in {"critical", "high"}:
        return 80
    if normalized == "medium":
        return 55
    if normalized == "low":
        return 20
    return 0


def _weight(value: float, total_value: float) -> float:
    if total_value <= 0:
        return 0.0
    return round(max(0.0, value / total_value), 4)


def _pct(value: float) -> int:
    return int(round(value * 100))


def _position_value(position: Any) -> float:
    current_value = _safe_optional_float(getattr(position, "current_value", None))
    if current_value is not None:
        return current_value

    quantity = _safe_float(getattr(position, "quantity", 0))
    price = _safe_float(
        getattr(position, "current_price", None)
        or getattr(position, "avg_price", None)
        or getattr(position, "avg_cost", None)
    )
    return quantity * price


def _fcn_value(fcn: FCNPosition) -> float:
    notional_amount = _safe_optional_float(getattr(fcn, "notional_amount", None))
    if notional_amount is not None:
        return notional_amount
    return _safe_float(getattr(fcn, "notional", 0))


def _risk_source(asset_class: str, score: int, weight: float, message: str) -> dict[str, Any]:
    return {
        "asset_class": asset_class,
        "score": _clamp_score(score),
        "weight": round(weight, 4),
        "message": message,
    }


def _decision_card(title: str, level: str, message: str, action_label: str) -> dict[str, str]:
    return {
        "title": title,
        "level": level,
        "message": message,
        "action_label": action_label,
    }


def _stock_source(stocks: list[StockPosition], total_value: float, stock_value: float) -> dict[str, Any] | None:
    if not stocks and stock_value <= 0:
        return None

    valued_positions = [(s, _position_value(s)) for s in stocks]
    top_stock, top_value = max(valued_positions, key=lambda item: item[1], default=(None, 0.0))
    top_symbol = str(getattr(top_stock, "symbol", "STOCK") or "STOCK").upper()
    top_ratio = top_value / total_value if total_value > 0 else 0.0
    stock_ratio = stock_value / total_value if total_value > 0 else 0.0

    if top_ratio >= 0.6:
        score = 82
        message = f"{top_symbol} 佔總資產約 {_pct(top_ratio)}%，單一股票集中度偏高。"
    elif top_ratio >= 0.4:
        score = 58
        message = f"{top_symbol} 佔總資產約 {_pct(top_ratio)}%，需要檢視集中度。"
    elif stock_ratio >= 0.55:
        score = 45
        message = f"股票資產佔總資產約 {_pct(stock_ratio)}%，整體股票曝險偏高。"
    elif stock_ratio >= 0.3:
        score = 32
        message = f"股票資產佔總資產約 {_pct(stock_ratio)}%，建議持續觀察集中度。"
    else:
        score = 20
        message = "股票部位目前未出現明顯集中度風險。"

    return _risk_source("Stock", score, _weight(stock_value, total_value), message)


def _crypto_source(
    cryptos: list[CryptoPosition],
    total_value: float,
    crypto_value: float,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not cryptos and crypto_value <= 0:
        return None, []

    crypto_ratio = crypto_value / total_value if total_value > 0 else 0.0
    score = 20 if crypto_value > 0 else 0
    messages: list[str] = []
    generated_alerts: list[dict[str, Any]] = []

    if crypto_ratio > 0.35:
        score = max(score, 78)
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，高波動資產曝險偏高")
    elif crypto_ratio > 0.2:
        score = max(score, 55)
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，需要監控波動曝險")
    elif crypto_value > 0:
        score = max(score, 24)
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，目前比重可控")

    max_leverage = max((_safe_float(c.leverage, 0) for c in cryptos), default=0.0)
    if max_leverage > 5:
        score = min(100, score + (18 if max_leverage >= 10 else 10))
        messages.append(f"最高槓桿約 {max_leverage:g}x")

    for c in cryptos:
        symbol = str(c.symbol or "CRYPTO").upper()
        current_price = _safe_float(c.current_price, 0)
        grid_lower = _safe_float(c.grid_lower, 0)
        grid_upper = _safe_float(c.grid_upper, 0)
        asset_type = str(c.asset_type or "").lower()

        if asset_type != "grid" or current_price <= 0 or grid_lower <= 0 or grid_upper <= 0:
            continue

        direction = ""
        if current_price > grid_upper:
            direction = "高於"
        elif current_price < grid_lower:
            direction = "低於"

        if direction:
            score = max(score, 82)
            messages.append(f"{symbol} Grid {direction}設定區間")
            generated_alerts.append({
                "title": f"{symbol} Grid 超出區間",
                "severity": "HIGH",
                "level": "HIGH",
                "asset_class": "Crypto",
                "asset_ref": symbol,
                "message": (
                    f"{symbol} 目前價格 {current_price:g} 已{direction} Grid "
                    f"{grid_lower:g}-{grid_upper:g} 區間，建議檢查區間設定、槓桿與回撤承受度。"
                ),
            })

    message = "；".join(messages) if messages else "Crypto / Grid 部位需持續追蹤槓桿與區間。"
    return _risk_source("Crypto", score, _weight(crypto_value, total_value), message), generated_alerts


def _fcn_source(fcns: list[FCNPosition], total_value: float, fcn_value: float) -> dict[str, Any] | None:
    if not fcns and fcn_value <= 0:
        return None

    best_score = 20 if fcn_value > 0 else 0
    best_message = "FCN 部位需持續追蹤 Worst-of 標的與 KI / KO 距離。"

    for f in fcns:
        code = str(getattr(f, "fcn_code", None) or getattr(f, "name", None) or "FCN")
        worst = str(getattr(f, "worst_of_symbol", None) or "-").upper()
        distance_to_ki = _safe_optional_float(getattr(f, "distance_to_ki_pct", None))
        level_score = _score_from_level(getattr(f, "risk_level", None))
        distance_score = 0
        message = f"{code} Worst-of {worst} 需持續追蹤 KI 距離。"

        if distance_to_ki is not None:
            if distance_to_ki <= 0:
                distance_score = 88
                message = f"FCN 風險主要來自 {worst} 已觸及或低於 KI 參考區。"
            elif distance_to_ki <= 10:
                distance_score = 82
                message = f"FCN 風險主要來自 {worst} 距 KI 約 {distance_to_ki:.1f}%，距離過近。"
            elif distance_to_ki <= 20:
                distance_score = 58
                message = f"FCN 風險主要來自 {worst} 距 KI 約 {distance_to_ki:.1f}%，需要監控。"

        score = max(level_score, distance_score, 20)
        if score > best_score:
            best_score = score
            best_message = message

    return _risk_source("FCN", best_score, _weight(fcn_value, total_value), best_message)


def _fcn_position_score(fcn: FCNPosition) -> int:
    distance_to_ki = _safe_optional_float(getattr(fcn, "distance_to_ki_pct", None))
    distance_score = 0

    if distance_to_ki is not None:
        if distance_to_ki <= 0:
            distance_score = 88
        elif distance_to_ki <= 10:
            distance_score = 82
        elif distance_to_ki <= 20:
            distance_score = 58

    return max(_score_from_level(getattr(fcn, "risk_level", None)), distance_score, 20)


def _portfolio_score(sources: list[dict[str, Any]]) -> int:
    if not sources:
        return 0

    weighted_score = sum(
        _safe_float(source.get("score")) * _safe_float(source.get("weight"))
        for source in sources
    )
    top_source = max(sources, key=lambda source: (_safe_float(source.get("score")), _safe_float(source.get("weight"))))
    top_score = _safe_float(top_source.get("score"))
    top_weight = _safe_float(top_source.get("weight"))
    material_floor = top_score if top_weight >= 0.25 else top_score * 0.75

    return _clamp_score(max(weighted_score, material_floor))


def _top_risk(sources: list[dict[str, Any]], fcns: list[FCNPosition]) -> str:
    if not sources:
        return "目前無明顯單一風險來源"

    top_source = max(sources, key=lambda source: (_safe_float(source.get("score")), _safe_float(source.get("weight"))))
    asset_class = str(top_source.get("asset_class") or "")

    if asset_class == "FCN":
        riskiest_fcn = max(
            fcns,
            key=_fcn_position_score,
            default=None,
        )
        if riskiest_fcn:
            code = getattr(riskiest_fcn, "fcn_code", None) or getattr(riskiest_fcn, "name", None) or "FCN"
            worst = getattr(riskiest_fcn, "worst_of_symbol", None) or "-"
            return f"{code} Worst-of {str(worst).upper()}"

    return str(top_source.get("message") or asset_class or "Portfolio")


def _ai_advice(risk_level: str, top_risk: str) -> str:
    if risk_level == "high":
        return (
            "目前風險偏高，建議優先檢視 FCN Worst-of 標的與 Crypto 槓桿曝險，"
            "並確認現金水位是否足以承受回撤。"
        )

    if risk_level == "medium":
        return (
            f"目前風險中等，主要需追蹤 {top_risk}。建議定期檢視配置比例、"
            "FCN KI 距離與 Grid 區間是否仍符合原先風險承受度。"
        )

    return "目前風險相對可控，建議持續監控資產集中度、FCN KI 距離與 Crypto 波動。"


def _decision_cards(
    risk_level: str,
    sources: list[dict[str, Any]],
    top_risk: str,
) -> list[dict[str, str]]:
    cards = [
        _decision_card(
            "整體配置",
            risk_level,
            f"目前主要風險來源為 {top_risk}，建議先檢視多資產曝險與現金緩衝。",
            "查看配置風險",
        )
    ]

    source_by_class = {str(source.get("asset_class")): source for source in sources}

    if "FCN" in source_by_class:
        source = source_by_class["FCN"]
        cards.append(_decision_card(
            "FCN 監控",
            _level_from_score(_clamp_score(_safe_float(source.get("score")))),
            str(source.get("message") or "持續追蹤 Worst-of 標的與 KI / KO 距離。"),
            "檢視 FCN 風險",
        ))

    if "Crypto" in source_by_class:
        source = source_by_class["Crypto"]
        cards.append(_decision_card(
            "Crypto / Grid",
            _level_from_score(_clamp_score(_safe_float(source.get("score")))),
            str(source.get("message") or "持續追蹤 Grid 區間與槓桿曝險。"),
            "檢查 Grid 區間",
        ))

    if "Stock" in source_by_class:
        source = source_by_class["Stock"]
        cards.append(_decision_card(
            "股票集中度",
            _level_from_score(_clamp_score(_safe_float(source.get("score")))),
            str(source.get("message") or "檢視單一股票集中度。"),
            "檢視集中度",
        ))

    return cards[:3]


def calculate_portfolio_risk_v2(
    db: Session,
    portfolio_id: str,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stocks = db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio_id).all()
    cryptos = db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio_id).all()
    fcns = db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio_id).all()

    raw_stock_value = sum(_position_value(s) for s in stocks)
    raw_crypto_value = sum(_position_value(c) for c in cryptos)
    raw_fcn_value = sum(_fcn_value(f) for f in fcns)

    stock_value = _safe_float((summary or {}).get("stock_value"), raw_stock_value)
    crypto_value = _safe_float((summary or {}).get("crypto_value"), raw_crypto_value)
    fcn_value = _safe_float((summary or {}).get("fcn_value"), raw_fcn_value)
    total_value = _safe_float(
        (summary or {}).get("total_value"),
        stock_value + crypto_value + fcn_value,
    )

    sources: list[dict[str, Any]] = []
    generated_alerts: list[dict[str, Any]] = []

    stock_source = _stock_source(stocks, total_value, stock_value)
    if stock_source:
        sources.append(stock_source)

    fcn_source = _fcn_source(fcns, total_value, fcn_value)
    if fcn_source:
        sources.append(fcn_source)

    crypto_source, crypto_alerts = _crypto_source(cryptos, total_value, crypto_value)
    if crypto_source:
        sources.append(crypto_source)
    generated_alerts.extend(crypto_alerts)

    risk_score = _portfolio_score(sources)
    risk_level = _level_from_score(risk_score)
    top_risk = _top_risk(sources, fcns)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_sources": sources,
        "top_risk": top_risk,
        "ai_advice": _ai_advice(risk_level, top_risk),
        "decision_cards": _decision_cards(risk_level, sources, top_risk),
        "generated_alerts": generated_alerts,
    }
