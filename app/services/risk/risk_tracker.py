from __future__ import annotations

from typing import Any


RISK_LEVEL_SCORE = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}

_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def save_snapshot(portfolio_id, data):
    normalized_portfolio_id = _normalize_portfolio_id(portfolio_id)
    _SNAPSHOTS[normalized_portfolio_id] = _normalize_snapshot(data)


def compare_snapshot(portfolio_id, current_data):
    normalized_portfolio_id = _normalize_portfolio_id(portfolio_id)
    previous_data = _SNAPSHOTS.get(normalized_portfolio_id)

    if not previous_data:
        return {
            "risk_level_change": "SAME",
            "crypto_ratio_change": "SAME",
        }

    current_snapshot = _normalize_snapshot(current_data)

    return {
        "risk_level_change": _compare_risk_level(
            previous_data.get("risk_level"),
            current_snapshot.get("risk_level"),
        ),
        "crypto_ratio_change": _compare_number(
            previous_data.get("crypto_ratio"),
            current_snapshot.get("crypto_ratio"),
        ),
    }


def _normalize_portfolio_id(portfolio_id) -> str:
    if portfolio_id is None or str(portfolio_id).strip() == "":
        raise ValueError("portfolio_id is required")

    return str(portfolio_id).strip()


def _normalize_snapshot(data) -> dict[str, Any]:
    data = data or {}

    return {
        "risk_level": _normalize_risk_level(data.get("risk_level")),
        "crypto_ratio": _to_float(data.get("crypto_ratio")),
        "top_risk_asset": data.get("top_risk_asset"),
    }


def _normalize_risk_level(risk_level) -> str:
    normalized = str(risk_level or "LOW").upper().strip()
    if normalized in RISK_LEVEL_SCORE:
        return normalized
    return "LOW"


def _compare_risk_level(previous_level, current_level) -> str:
    previous_score = RISK_LEVEL_SCORE.get(_normalize_risk_level(previous_level), 1)
    current_score = RISK_LEVEL_SCORE.get(_normalize_risk_level(current_level), 1)

    return _compare_number(previous_score, current_score)


def _compare_number(previous_value, current_value) -> str:
    previous_number = _to_float(previous_value)
    current_number = _to_float(current_value)

    if current_number > previous_number:
        return "UP"

    if current_number < previous_number:
        return "DOWN"

    return "SAME"


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
