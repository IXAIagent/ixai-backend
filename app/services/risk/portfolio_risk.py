from __future__ import annotations

from typing import Any


HIGH_RISK_THRESHOLD = 0.5
MEDIUM_RISK_THRESHOLD = 0.6


def calculate_portfolio_risk(positions: list) -> dict:
    normalized_positions = [_normalize_position(position) for position in positions]
    total_value = sum(position["value"] for position in normalized_positions)

    if total_value <= 0:
        return {
            "total_value": 0.0,
            "risk_level": "LOW",
            "top_risk_asset": None,
        }

    high_weight = 0.0
    medium_weight = 0.0
    top_risk_asset = None
    top_risk_value = 0.0

    for position in normalized_positions:
        value = position["value"]
        weight = value / total_value
        risk_tag = position["risk_tag"]

        if risk_tag == "HIGH":
            high_weight += weight
        elif risk_tag == "MEDIUM":
            medium_weight += weight

        if risk_tag in {"HIGH", "MEDIUM"} and value > top_risk_value:
            top_risk_asset = position["symbol"]
            top_risk_value = value

    if high_weight > HIGH_RISK_THRESHOLD:
        risk_level = "HIGH"
    elif medium_weight > MEDIUM_RISK_THRESHOLD:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "total_value": total_value,
        "risk_level": risk_level,
        "top_risk_asset": top_risk_asset,
    }


def _normalize_position(position: Any) -> dict[str, Any]:
    value = 0.0
    if isinstance(position, dict):
        raw_value = position.get("value", 0)
        symbol = position.get("symbol")
        risk_tag = position.get("risk_tag")
    else:
        raw_value = getattr(position, "value", 0)
        symbol = getattr(position, "symbol", None)
        risk_tag = getattr(position, "risk_tag", None)

    try:
        value = float(raw_value or 0)
    except (TypeError, ValueError):
        value = 0.0

    return {
        "symbol": symbol,
        "value": value,
        "risk_tag": str(risk_tag).upper() if risk_tag else None,
    }
