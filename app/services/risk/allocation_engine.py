from __future__ import annotations

from typing import Any


TARGET_ALLOCATION = {
    "stock": "40–60%",
    "crypto": "20–30%",
    "fcn": "0–30%",
    "cash": "10–20%",
}

WARNING_TEXT = "此為風險管理與配置方向，不構成個別買賣建議。"


def generate_allocation_advice(
    summary: dict,
    portfolio_risk: dict,
    risk_explanation: dict,
) -> dict:
    actions: list[str] = []

    crypto_ratio = _to_percent(_get_value(summary, "crypto_ratio"))
    stock_ratio = _to_percent(_get_value(summary, "stock_ratio"))
    risk_level = str(_get_value(portfolio_risk, "risk_level") or "").upper()

    if crypto_ratio >= 50:
        _append_action(actions, "降低 Crypto 占比至 20–30% 區間")

    if stock_ratio >= 70:
        _append_action(
            actions,
            "檢視股票集中度，避免單一市場或單一個股過度集中",
        )

    if risk_level == "HIGH":
        _append_action(actions, "提高現金或低波動資產比例")

    for suggestion in _get_suggestions(risk_explanation):
        _append_action(actions, suggestion)

    if not actions:
        _append_action(actions, "維持定期檢視資產配置與波動變化")

    return {
        "title": "配置建議",
        "target_allocation": TARGET_ALLOCATION.copy(),
        "actions": actions,
        "warning": WARNING_TEXT,
    }


def _get_suggestions(risk_explanation: Any) -> list[str]:
    suggestions = _get_value(risk_explanation, "suggestions") or []
    if not isinstance(suggestions, list):
        return []

    return [str(suggestion).strip() for suggestion in suggestions if suggestion]


def _append_action(actions: list[str], action: str) -> None:
    normalized_action = str(action or "").strip()
    if not normalized_action:
        return

    if not _is_compliant_action(normalized_action):
        return

    if normalized_action not in actions:
        actions.append(normalized_action)


def _is_compliant_action(action: str) -> bool:
    if "立即" in action and ("買" in action or "賣" in action):
        return False

    if ("買" in action and "股" in action) or ("賣" in action and "股" in action):
        return False

    return True


def _get_value(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)


def _to_percent(value: Any) -> float:
    numeric_value = _to_float(value)
    if 0 < numeric_value <= 1:
        return numeric_value * 100
    return numeric_value


def _to_float(value: Any) -> float:
    if isinstance(value, str):
        value = value.replace("%", "").strip()

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
