from __future__ import annotations

from typing import Any


RISK_LEVEL_MESSAGES = {
    "LOW": "目前未偵測到明顯集中風險",
    "MEDIUM": "需留意高波動資產占比與單一資產集中度",
    "HIGH": "整體風險偏高，建議優先檢視高波動資產占比",
}

RISK_LEVEL_SUGGESTIONS = {
    "LOW": "建議持續追蹤波動與配置變化",
    "MEDIUM": "建議檢視高波動資產占比，避免風險過度集中",
    "HIGH": "建議重新評估風險承受度，並檢視整體配置是否過度集中",
}


def generate_risk_alert(risk_result: dict, positions: list) -> str:
    risk_level = _normalize_risk_level(risk_result.get("risk_level"))
    total_value = _to_float(risk_result.get("total_value"))
    top_risk_asset = risk_result.get("top_risk_asset") or _find_top_risk_asset(
        positions
    )

    level_message = RISK_LEVEL_MESSAGES[risk_level]
    suggestion = RISK_LEVEL_SUGGESTIONS[risk_level]

    if top_risk_asset:
        source_text = f"主要風險來自 {top_risk_asset}"
    elif total_value > 0:
        source_text = "主要風險來源尚不明確"
    else:
        source_text = "尚無足夠部位資料可判斷主要風險來源"

    return f"Portfolio Risk: {risk_level}｜{level_message}｜{source_text}，{suggestion}"


def _normalize_risk_level(risk_level: Any) -> str:
    normalized = str(risk_level or "LOW").upper()
    if normalized in RISK_LEVEL_MESSAGES:
        return normalized
    return "LOW"


def _find_top_risk_asset(positions: list) -> str | None:
    top_symbol = None
    top_value = 0.0

    for position in positions:
        risk_tag = _get_position_value(position, "risk_tag")
        normalized_risk_tag = str(risk_tag or "").upper()
        if normalized_risk_tag not in {"HIGH", "MEDIUM"}:
            continue

        value = _to_float(_get_position_value(position, "value"))
        if value > top_value:
            top_symbol = _get_position_value(position, "symbol")
            top_value = value

    return str(top_symbol).upper() if top_symbol else None


def _get_position_value(position: Any, key: str) -> Any:
    if isinstance(position, dict):
        return position.get(key)
    return getattr(position, key, None)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
