from __future__ import annotations

from typing import Any


CRYPTO_TARGET_RANGE_TEXT = "20–30%"
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


def generate_risk_explanation(
    summary: dict,
    portfolio_risk: dict,
    positions: list,
) -> dict:
    level = _normalize_level(
        _get_value(portfolio_risk, "risk_level")
        or _get_value(summary, "risk_level")
        or _get_value(summary, "overall_risk_level")
    )
    reasons: list[str] = []
    suggestions: list[str] = []

    crypto_ratio = _to_percent(_get_value(summary, "crypto_ratio"))
    if crypto_ratio >= 50:
        reasons.append(
            f"Crypto 佔比 {_format_percent(crypto_ratio)}%，高於建議區間 {CRYPTO_TARGET_RANGE_TEXT}"
        )
        _append_unique(
            suggestions,
            f"建議將 Crypto 佔比逐步降至 {CRYPTO_TARGET_RANGE_TEXT}",
        )

    normalized_positions = [_normalize_position(position) for position in positions]

    high_positions = [
        position for position in normalized_positions if position["risk_tag"] == "HIGH"
    ]
    for position in high_positions:
        reasons.append(_build_position_reason(position, "高風險資產"))

    if high_positions:
        _append_unique(suggestions, "建議優先檢視高波動資產")

    medium_positions = [
        position for position in normalized_positions if position["risk_tag"] == "MEDIUM"
    ]
    for position in medium_positions:
        reasons.append(_build_position_reason(position, "中高波動資產"))

    top_risk_asset = _get_value(portfolio_risk, "top_risk_asset")
    if top_risk_asset:
        reasons.append(f"主要風險來源為 {str(top_risk_asset).upper()}")
        _append_unique(suggestions, "避免單一資產過度集中")

    if not reasons:
        reasons.append("目前未偵測到明顯集中或高波動風險")

    if not suggestions:
        suggestions.append("建議持續追蹤資產配置與波動變化")
        suggestions.append("可增加低波動資產或現金部位")
    elif level in {"MEDIUM", "HIGH"}:
        _append_unique(suggestions, "可增加低波動資產或現金部位")

    return {
        "level": level,
        "reasons": reasons,
        "suggestions": suggestions,
        "summary_text": _build_summary_text(level, reasons, top_risk_asset),
    }


def _normalize_level(level: Any) -> str:
    normalized = str(level or "LOW").upper()
    if normalized in VALID_RISK_LEVELS:
        return normalized
    return "LOW"


def _normalize_position(position: Any) -> dict[str, Any]:
    symbol = _get_value(position, "symbol") or "UNKNOWN"
    risk_tag = _get_value(position, "risk_tag")
    volatility = _get_value(position, "volatility")

    return {
        "symbol": str(symbol).upper(),
        "risk_tag": str(risk_tag).upper() if risk_tag else None,
        "volatility": _to_percent(volatility) if volatility is not None else None,
    }


def _build_position_reason(position: dict[str, Any], label: str) -> str:
    symbol = position["symbol"]
    volatility = position["volatility"]

    if volatility is None:
        return f"{symbol} 屬於{label}"

    return f"{symbol} 波動率 {_format_percent(volatility)}%，屬於{label}"


def _build_summary_text(
    level: str,
    reasons: list[str],
    top_risk_asset: Any,
) -> str:
    if level == "HIGH":
        prefix = "整體風險偏高"
    elif level == "MEDIUM":
        prefix = "整體風險中等"
    else:
        prefix = "整體風險偏低"

    if top_risk_asset:
        return f"{prefix}，主要來自 {str(top_risk_asset).upper()}。"

    if reasons:
        return f"{prefix}，{reasons[0]}。"

    return f"{prefix}，目前配置未出現明顯集中風險。"


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


def _format_percent(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)
