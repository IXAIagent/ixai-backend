from __future__ import annotations

from math import isfinite
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        return number if isfinite(number) else default
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        return number if isfinite(number) else None
    except Exception:
        return None


def _clamp_score(score: Any) -> int:
    return max(0, min(100, int(round(_safe_float(score)))))


def _risk_level(score: int) -> str:
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
        return 25
    return 0


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _asset_weight(value: float, total_value: float) -> float:
    if total_value <= 0:
        return 0.0
    return round(max(0.0, value / total_value), 4)


def _pct(value: float) -> int:
    return int(round(value * 100))


def _format_pct(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value * 100:.1f}%"


def _source(asset_class: str, score: int, weight: float, message: str) -> dict[str, Any]:
    return {
        "asset_class": asset_class,
        "score": _clamp_score(score),
        "weight": round(max(0.0, weight), 4),
        "message": message,
    }


def _position_value(position: Any) -> float:
    if not isinstance(position, dict):
        return 0.0

    current_value = _safe_optional_float(position.get("current_value"))
    if current_value is not None:
        return current_value

    quantity = _safe_float(position.get("quantity"))
    price = _safe_float(
        position.get("current_price")
        if position.get("current_price") is not None
        else position.get("avg_price")
    )
    return quantity * price


def _fcn_has_missing_price_data(item: dict[str, Any]) -> bool:
    prices = _as_list(item.get("prices"))
    if not prices:
        return True

    for price in prices:
        if not isinstance(price, dict):
            return True
        initial_price = _safe_optional_float(price.get("initial_price"))
        current_price = _safe_optional_float(price.get("current_price"))
        if initial_price is None or initial_price <= 0 or current_price is None or current_price <= 0:
            return True

    return False


def _fcn_risk(summary: dict[str, Any], total_value: float) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    fcn_analysis = [item for item in _as_list(summary.get("fcn_analysis")) if isinstance(item, dict)]
    fcn_value = _safe_float(summary.get("fcn_value"))
    warnings: list[str] = []

    if not fcn_analysis and fcn_value <= 0:
        return None, None, warnings

    if not fcn_analysis and fcn_value > 0:
        warnings.append(
            "FCN 初始價或即時價資料可能不完整，請確認 FCN underlyings 與 entry prices。"
        )

    best_score = 25 if fcn_value > 0 else 0
    best_message = "FCN 部位需持續追蹤 Worst-of 標的與 KI 距離。"
    top_detail: dict[str, Any] | None = None

    for item in fcn_analysis:
        fcn_code = str(item.get("fcn_code") or item.get("code") or item.get("name") or "FCN")
        worst_symbol = str(item.get("worst_symbol") or item.get("worst_of") or "-").upper()
        distance_to_ki = _safe_optional_float(item.get("distance_to_KI"))
        worst_performance = _safe_optional_float(item.get("worst_performance"))
        score = _score_from_level(item.get("risk_level"))
        message = f"FCN 風險主要來自 {worst_symbol} 的 KI 距離需持續追蹤"

        if distance_to_ki is not None:
            if distance_to_ki <= 0:
                score = max(score, 88)
                message = f"FCN 風險主要來自 {worst_symbol} 已跌破或觸及 KI"
            elif distance_to_ki <= 0.10:
                score = max(score, 84)
                message = f"FCN 風險主要來自 {worst_symbol} 距 KI 小於 10%"
            elif distance_to_ki <= 0.20:
                score = max(score, 60)
                message = f"FCN 風險主要來自 {worst_symbol} 距 KI 小於 20%"

        if (
            _fcn_has_missing_price_data(item)
            or (
                worst_performance == 0.0
                and (distance_to_ki is None or distance_to_ki < -1.0 or distance_to_ki > 1.5)
            )
        ):
            warnings.append(
                "FCN 初始價或即時價資料可能不完整，請確認 FCN underlyings 與 entry prices。"
            )

        if score > best_score:
            best_score = score
            best_message = message
            top_detail = {
                "fcn_code": fcn_code,
                "worst_symbol": worst_symbol,
                "distance_to_KI": distance_to_ki,
                "score": score,
            }

    if not top_detail and fcn_analysis:
        first = fcn_analysis[0]
        top_detail = {
            "fcn_code": str(first.get("fcn_code") or first.get("code") or first.get("name") or "FCN"),
            "worst_symbol": str(first.get("worst_symbol") or first.get("worst_of") or "-").upper(),
            "distance_to_KI": _safe_optional_float(first.get("distance_to_KI")),
            "score": best_score,
        }

    source = _source("FCN", best_score, _asset_weight(fcn_value, total_value), best_message)
    return source, top_detail, list(dict.fromkeys(warnings))


def _crypto_risk(summary: dict[str, Any], total_value: float) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    crypto_positions = [item for item in _as_list(summary.get("crypto_positions")) if isinstance(item, dict)]
    crypto_value = _safe_float(summary.get("crypto_value"))

    if not crypto_positions and crypto_value <= 0:
        return None, []

    crypto_ratio = crypto_value / total_value if total_value > 0 else 0.0
    score = 25 if crypto_value > 0 else 0
    messages: list[str] = []
    alerts: list[dict[str, Any]] = []

    if crypto_ratio > 0.35:
        score = max(score, 82)
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，高波動曝險偏高")
    elif crypto_ratio > 0.20:
        score = max(score, 58)
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，需要持續監控")
    elif crypto_value > 0:
        messages.append(f"Crypto 佔總資產約 {_pct(crypto_ratio)}%，目前比重可控")

    for position in crypto_positions:
        symbol = str(position.get("symbol") or "CRYPTO").upper()
        leverage = _safe_float(position.get("leverage"))
        current_price = _safe_optional_float(position.get("current_price"))
        grid_lower = _safe_optional_float(position.get("grid_lower"))
        grid_upper = _safe_optional_float(position.get("grid_upper"))

        if leverage > 5:
            score = min(100, max(score, 65) + 10)
            messages.append(f"{symbol} 槓桿約 {leverage:g}x，需留意波動放大")

        if (
            current_price is None
            or grid_lower is None
            or grid_upper is None
            or current_price <= 0
            or grid_lower <= 0
            or grid_upper <= 0
            or grid_lower >= grid_upper
        ):
            continue

        if current_price > grid_upper or current_price < grid_lower:
            score = max(score, 86)
            direction = "高於" if current_price > grid_upper else "低於"
            messages.append(f"{symbol} Grid 價格已{direction}策略區間")
            alerts.append({
                "title": f"{symbol} Grid 超出區間",
                "severity": "HIGH",
                "level": "HIGH",
                "asset_class": "Crypto",
                "asset_ref": symbol,
                "message": f"{symbol} 目前價格已{direction} Grid 區間，請檢視策略區間、槓桿與風險承受度。",
            })
            continue

        near_lower = current_price <= grid_lower * 1.05
        near_upper = current_price >= grid_upper * 0.95
        if near_lower or near_upper:
            score = max(score, 60)
            edge = "下緣" if near_lower else "上緣"
            messages.append(f"{symbol} Grid 價格接近策略區間{edge} 5% 內")

    message = "；".join(dict.fromkeys(messages)) if messages else "Crypto / Grid 部位需持續追蹤價格區間與槓桿。"
    return _source("Crypto", score, _asset_weight(crypto_value, total_value), message), alerts


def _stock_concentration_risk(summary: dict[str, Any], total_value: float) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    stock_positions = _as_list(summary.get("stocks")) or _as_list(summary.get("stock_positions"))
    stock_positions = [item for item in stock_positions if isinstance(item, dict)]
    stock_value = _safe_float(summary.get("stock_value"))

    if not stock_positions and stock_value <= 0:
        return None, None

    value_by_symbol: dict[str, float] = {}
    for position in stock_positions:
        symbol = str(position.get("symbol") or "STOCK").upper()
        value_by_symbol[symbol] = value_by_symbol.get(symbol, 0.0) + _position_value(position)

    top_symbol, top_value = max(value_by_symbol.items(), key=lambda item: item[1], default=("STOCK", 0.0))
    top_ratio = top_value / total_value if total_value > 0 else 0.0

    if top_ratio > 0.60:
        score = 82
        message = f"{top_symbol} 佔總資產約 {_pct(top_ratio)}%，單一股票集中度偏高"
    elif top_ratio > 0.40:
        score = 60
        message = f"{top_symbol} 佔總資產約 {_pct(top_ratio)}%，需檢視集中度"
    elif top_ratio > 0.25:
        score = 35
        message = f"{top_symbol} 佔總資產約 {_pct(top_ratio)}%，有集中度提醒"
    elif stock_value > 0:
        score = 20
        message = "股票部位目前未出現明顯單一集中度風險"
    else:
        return None, None

    detail = {"symbol": top_symbol, "ratio": top_ratio, "score": score}
    return _source("Stock", score, _asset_weight(stock_value, total_value), message), detail


def _cash_risk(summary: dict[str, Any], total_value: float) -> tuple[dict[str, Any] | None, float]:
    cash_value = _safe_float(summary.get("cash_value"))
    cash_ratio = cash_value / total_value if total_value > 0 else 0.0

    if total_value <= 0:
        return None, 0.0

    if cash_ratio < 0.05:
        return _source("Cash", 48, cash_ratio, "現金水位低於 5%，市場回撤緩衝偏低"), cash_ratio

    if cash_ratio < 0.10:
        return _source("Cash", 28, cash_ratio, "現金水位低於 10%，建議持續留意緩衝"), cash_ratio

    return None, cash_ratio


def _top_risk(
    sources: list[dict[str, Any]],
    fcn_detail: dict[str, Any] | None,
    stock_detail: dict[str, Any] | None,
) -> tuple[str, str]:
    if not sources:
        return "目前無明顯單一風險來源", "目前資料未顯示明顯單一風險來源，仍建議持續監控配置、FCN KI 與 Crypto 區間。"

    top_source = max(sources, key=lambda item: (_safe_float(item.get("score")), _safe_float(item.get("weight"))))
    asset_class = str(top_source.get("asset_class") or "")

    if asset_class == "FCN" and fcn_detail:
        code = str(fcn_detail.get("fcn_code") or "FCN")
        worst_symbol = str(fcn_detail.get("worst_symbol") or "-").upper()
        distance_to_ki = _safe_optional_float(fcn_detail.get("distance_to_KI"))
        return (
            f"FCN / {worst_symbol}",
            (
                f"fcn_code={code}，worst_symbol={worst_symbol}，"
                f"distance_to_KI={_format_pct(distance_to_ki)}。"
            ),
        )

    if asset_class == "Crypto":
        return "Crypto / Grid", str(top_source.get("message") or "Crypto / Grid 風險需持續追蹤。")

    if asset_class == "Stock" and stock_detail:
        symbol = str(stock_detail.get("symbol") or "STOCK").upper()
        ratio = _safe_float(stock_detail.get("ratio"))
        return "Stock Concentration", f"{symbol} 佔總資產約 {_pct(ratio)}%，需檢視單一股票集中度。"

    if asset_class == "Cash":
        return "Cash Buffer", str(top_source.get("message") or "現金水位偏低，需留意回撤緩衝。")

    return asset_class or "Portfolio", str(top_source.get("message") or "需持續追蹤主要風險來源。")


def _decision_cards(risk_level: str, sources: list[dict[str, Any]], top_risk: str) -> list[dict[str, str]]:
    source_by_class = {str(source.get("asset_class")): source for source in sources}
    cards: list[dict[str, str]] = []

    if risk_level == "high":
        overall_message = "目前風險偏高，建議優先檢視 FCN 與 Crypto 曝險。"
    elif risk_level == "medium":
        overall_message = f"目前風險中等，建議檢視主要來源：{top_risk}。"
    else:
        overall_message = "目前風險相對可控，建議持續追蹤配置與現金緩衝。"

    cards.append({
        "title": "整體配置",
        "level": risk_level,
        "message": overall_message,
        "action_label": "查看配置風險",
    })

    if "FCN" in source_by_class:
        fcn_source = source_by_class["FCN"]
        cards.append({
            "title": "FCN 監控",
            "level": _risk_level(_clamp_score(fcn_source.get("score"))),
            "message": str(fcn_source.get("message") or "FCN Worst-of 標的距 KI 需持續追蹤。"),
            "action_label": "查看 FCN 明細",
        })

    if "Crypto" in source_by_class:
        crypto_source = source_by_class["Crypto"]
        cards.append({
            "title": "Crypto / Grid",
            "level": _risk_level(_clamp_score(crypto_source.get("score"))),
            "message": "請確認 Grid 價格是否仍在策略區間內。",
            "action_label": "查看 Crypto 狀態",
        })

    if "Stock" in source_by_class and len(cards) < 3:
        stock_source = source_by_class["Stock"]
        cards.append({
            "title": "股票集中度",
            "level": _risk_level(_clamp_score(stock_source.get("score"))),
            "message": str(stock_source.get("message") or "請檢視單一股票集中度。"),
            "action_label": "查看股票集中度",
        })

    if "Cash" in source_by_class and len(cards) < 3:
        cash_source = source_by_class["Cash"]
        cards.append({
            "title": "現金緩衝",
            "level": _risk_level(_clamp_score(cash_source.get("score"))),
            "message": str(cash_source.get("message") or "請留意現金水位。"),
            "action_label": "查看現金水位",
        })

    return cards[:3]


def _ai_advice(risk_level: str, sources: list[dict[str, Any]]) -> str:
    source_names = {str(source.get("asset_class") or "") for source in sources}

    if risk_level == "high":
        focus: list[str] = []
        if "FCN" in source_names:
            focus.append("FCN Worst-of 標的")
        if "Crypto" in source_names:
            focus.append("Crypto 波動曝險")
        if "Stock" in source_names:
            focus.append("股票集中度")
        if "Cash" in source_names:
            focus.append("現金水位")

        focus_text = "、".join(focus) if focus else "主要風險來源"
        return (
            f"目前投資組合風險偏高，主要來自 {focus_text}。"
            "建議優先檢視 FCN 距 KI 狀態、Grid 是否仍在策略區間內，"
            "並確認現金水位是否足以承受市場回撤。"
        )

    if risk_level == "medium":
        return (
            "目前投資組合風險中等，建議定期檢視 FCN KI 距離、"
            "Crypto / Grid 區間、單一股票集中度與現金緩衝。"
        )

    return "目前投資組合風險相對可控，建議持續監控配置比例、FCN KI 距離、Crypto 區間與現金水位。"


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, float):
        return value if isfinite(value) else 0.0
    return value


def build_risk_engine_v3(summary: dict[str, Any]) -> dict[str, Any]:
    """Build a defensive, dashboard-friendly risk breakdown without trading instructions."""
    try:
        total_value = _safe_float(summary.get("total_value"))
        cash_value = _safe_float(summary.get("cash_value"))
        data_quality_warnings = [
            str(item)
            for item in _as_list(summary.get("data_quality_warnings"))
            if item
        ]

        sources: list[dict[str, Any]] = []
        generated_alerts: list[dict[str, Any]] = []

        fcn_source, fcn_detail, fcn_warnings = _fcn_risk(summary, total_value)
        if fcn_source:
            sources.append(fcn_source)
        data_quality_warnings.extend(fcn_warnings)

        crypto_source, crypto_alerts = _crypto_risk(summary, total_value)
        if crypto_source:
            sources.append(crypto_source)
        generated_alerts.extend(crypto_alerts)

        stock_source, stock_detail = _stock_concentration_risk(summary, total_value)
        if stock_source:
            sources.append(stock_source)

        cash_source, cash_ratio = _cash_risk(summary, total_value)
        if cash_source:
            sources.append(cash_source)

        base_score = max((_safe_float(source.get("score")) for source in sources), default=0.0)
        active_risk_count = sum(1 for source in sources if _safe_float(source.get("score")) >= 40)
        risk_score = _clamp_score(base_score + (10 if active_risk_count >= 2 else 0))
        risk_level = _risk_level(risk_score)
        top_risk, top_risk_reason = _top_risk(sources, fcn_detail, stock_detail)

        result = {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_sources": sources,
            "top_risk": top_risk,
            "top_risk_reason": top_risk_reason,
            "decision_cards": _decision_cards(risk_level, sources, top_risk),
            "ai_advice": _ai_advice(risk_level, sources),
            "data_quality_warnings": list(dict.fromkeys(data_quality_warnings)),
            "cash_value": cash_value,
            "cash_ratio": round(cash_ratio, 4),
            "generated_alerts": generated_alerts,
        }
    except Exception as exc:
        result = {
            "risk_score": 0,
            "risk_level": "low",
            "risk_sources": [],
            "top_risk": "目前無明顯單一風險來源",
            "top_risk_reason": "Risk Engine v3 計算時發生例外，已保留 dashboard 回傳避免中斷。",
            "decision_cards": [
                {
                    "title": "整體配置",
                    "level": "low",
                    "message": "風險資料暫時不完整，建議稍後重新整理並檢視資料品質。",
                    "action_label": "查看配置風險",
                }
            ],
            "ai_advice": "目前風險資料暫時不完整，建議先確認資料品質、FCN KI 距離、Crypto 區間與現金水位。",
            "data_quality_warnings": [f"Risk Engine v3 error: {exc}"],
            "cash_value": _safe_float(summary.get("cash_value")),
            "cash_ratio": 0.0,
            "generated_alerts": [],
        }

    return _sanitize_json(result)
