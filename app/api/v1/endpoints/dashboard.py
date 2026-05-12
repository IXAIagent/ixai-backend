from math import isfinite
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from app.api.deps import get_current_user, get_owned_portfolio
from app.core.config import is_development_env
from app.core.database import get_db
from app.models.models import CryptoPosition, FCNPosition, Portfolio, StockPosition, User
from app.services.portfolio_service import build_allocation_payload, build_portfolio_summary
from app.services.push_state_service import should_send_push
from app.services.telegram_push_service import send_telegram_message
from app.services.action_service import calculate_stock_action
from app.services.fcn_monitor_service import FCNMonitorService
from app.services.market_data.service import MarketDataService
from app.services.normalization import get_asset_display_name
from app.services.resolver import resolve_asset
from app.services.risk_engine_v3 import build_risk_engine_v3
from app.services.risk.portfolio_risk import calculate_portfolio_risk
from app.services.risk.alert_engine import generate_risk_alert
from app.services.risk.explanation_engine import generate_risk_explanation
from app.services.risk.allocation_engine import generate_allocation_advice
from app.services.risk.risk_tracker import save_snapshot, compare_snapshot

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def require_development_route():
    if not is_development_env():
        raise HTTPException(status_code=404, detail="Not found")


def get_top_stock_risk(db: Session, portfolio_id: str, total_value: float):
    candidate_tables = ["stock", "stocks", "stock_position", "stock_positions"]
    inspector = inspect(db.get_bind())
    table_names = set(inspector.get_table_names())

    for table in candidate_tables:
        if table not in table_names:
            continue

        columns = inspector.get_columns(table)
        column_names = [str(c["name"]) for c in columns]

        if "symbol" not in column_names or "quantity" not in column_names or "portfolio_id" not in column_names:
            continue

        price_col = None
        for c in ["avg_cost", "avg_price", "current_price"]:
            if c in column_names:
                price_col = c
                break

        if not price_col:
            continue

        rows = db.execute(
            text(f"""
                SELECT symbol, quantity, {price_col} AS price
                FROM {table}
                WHERE portfolio_id = :pid
            """),
            {"pid": portfolio_id},
        ).fetchall()

        top_symbol = None
        top_ratio = 0

        for r in rows:
            value = float(r.quantity or 0) * float(r.price or 0)
            ratio = value / total_value if total_value > 0 else 0

            if ratio > top_ratio:
                top_ratio = ratio
                top_symbol = str(r.symbol).upper()

        if top_symbol:
            return {
                "symbol": top_symbol,
                "ratio": top_ratio,
                "text": f"{top_symbol} 佔比 {int(top_ratio * 100)}%",
            }

    return None


def build_ai_advice(top_risk, risk_asset_ratio: float, crypto_ratio: float):
    if top_risk:
        symbol = top_risk["symbol"]
        ratio_pct = int(top_risk["ratio"] * 100)

        if top_risk["ratio"] >= 0.6:
            return f"""
🔥 {symbol} 佔比 {ratio_pct}%

⚠ 高風險（集中度過高）
👉 建議檢視單一資產集中度與風險承受度（目前 {ratio_pct}%）

📊 分散建議：
- ETF（SPY / QQQ）
- 半導體（NVDA / AMD）
- 現金 / 債券

💡 風險提示：
- 避免單一資產過度集中
- 定期檢視配置比例
""".strip()

    if crypto_ratio >= 0.5:
        return f"""
🔥 Crypto 佔比 {int(crypto_ratio * 100)}%

⚠ 高風險（高波動資產過高）
👉 建議降低至 20~30%

📊 分散建議：
- 增加現金
- 降低槓桿
- 分散不同幣種

💡 風險提示：
- 留意波動放大風險
- 避免過度集中
""".strip()

    if crypto_ratio >= 0.3:
        return f"""
⚠ Crypto 佔比 {int(crypto_ratio * 100)}%

👉 波動資產偏高，建議控管風險

📊 建議：
- 保留現金
- 避免過度集中
""".strip()

    if risk_asset_ratio >= 0.4:
        return "風險資產占比偏高，建議增加現金 / 債券，降低回撤風險。"

    return "目前配置風險可控，建議持續監控市場變化與資產配置。"


def build_alerts_from_risk(risk_score: int, top_risk: str | None, ai_advice: str):
    if risk_score >= 80:
        return [{
            "title": "高風險警報",
            "severity": "HIGH",
            "message": f"{top_risk or '投資組合'} 風險分數 {risk_score}，建議立即檢視配置。",
            "advice": ai_advice,
        }]

    if risk_score >= 50:
        return [{
            "title": "中度風險提醒",
            "severity": "MEDIUM",
            "message": f"{top_risk or '投資組合'} 風險分數 {risk_score}，建議留意集中度。",
            "advice": ai_advice,
        }]

    return []


def build_portfolio_risk_positions(
    payload: dict,
    top_risk_obj,
    crypto_ratio: float,
) -> list[dict]:
    stock_value = float(payload.get("stock_value", 0) or 0)
    crypto_value = float(payload.get("crypto_value", 0) or 0)
    fcn_value = float(payload.get("fcn_value", 0) or 0)

    positions = []

    if stock_value > 0:
        top_stock_ratio = float((top_risk_obj or {}).get("ratio", 0) or 0)
        if top_stock_ratio > 0.5:
            stock_risk_tag = "HIGH"
        elif top_stock_ratio > 0.3:
            stock_risk_tag = "MEDIUM"
        else:
            stock_risk_tag = "LOW"

        positions.append({
            "symbol": (top_risk_obj or {}).get("symbol") or "STOCK",
            "value": stock_value,
            "risk_tag": stock_risk_tag,
        })

    if crypto_value > 0:
        if crypto_ratio >= 0.5:
            crypto_risk_tag = "HIGH"
        elif crypto_ratio >= 0.3:
            crypto_risk_tag = "MEDIUM"
        else:
            crypto_risk_tag = "LOW"

        positions.append({
            "symbol": "CRYPTO",
            "value": crypto_value,
            "risk_tag": crypto_risk_tag,
        })

    if fcn_value > 0:
        positions.append({
            "symbol": "FCN",
            "value": fcn_value,
            "risk_tag": "LOW",
        })

    return positions


def maybe_send_risk_push(
    portfolio_id: str,
    portfolio_name: str,
    level: str,
    risk_score: int,
    top_risk_text: str | None,
    ai_advice: str,
):
    if risk_score < 80:
        return

    top_risk_key = top_risk_text or "portfolio"

    if not should_send_push(portfolio_id, risk_score, top_risk_key):
        return

    message = f"""
🚨 IXAI Agent 風險提醒
Portfolio：{portfolio_name}
風險等級：{level}
Risk Score：{risk_score}
Top Risk：{top_risk_text or "投資組合"}

AI 建議
{ai_advice}
""".strip()

    send_telegram_message(message)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        return number if number == number else default
    except Exception:
        return default


def _safe_price(value: Any) -> float | None:
    number = _safe_float(value, default=0.0)
    if number > 0 and isfinite(number):
        return number
    return None


def _live_price(
    market_service: MarketDataService,
    symbol: str,
    asset_type: str,
) -> tuple[float | None, str]:
    try:
        result = market_service.get_price(symbol, asset_type=asset_type)
        price = _safe_price(getattr(result, "price", None))
        source = str(getattr(result, "source", None) or "manual")
        return price, source
    except Exception:
        return None, "manual"


def _serialize_fcn_position(fcn: FCNPosition) -> dict[str, Any]:
    code = getattr(fcn, "fcn_code", None) or getattr(fcn, "name", None) or "FCN"
    return {
        "id": getattr(fcn, "id", None),
        "name": getattr(fcn, "name", None) or code,
        "fcn_code": getattr(fcn, "fcn_code", None) or code,
        "code": code,
        "notional": getattr(fcn, "notional", None),
        "notional_amount": getattr(fcn, "notional_amount", None) or getattr(fcn, "notional", None),
        "worst_of_symbol": getattr(fcn, "worst_of_symbol", None) or "",
        "worst_of": getattr(fcn, "worst_of_symbol", None) or "",
        "distance_to_ki_pct": getattr(fcn, "distance_to_ki_pct", None),
        "distance_to_ko_pct": getattr(fcn, "distance_to_ko_pct", None),
        "risk_level": getattr(fcn, "risk_level", None) or "low",
    }


def _serialize_stock_position(
    stock: StockPosition,
    market_service: MarketDataService,
) -> dict[str, Any]:
    symbol = str(getattr(stock, "symbol", None) or "STOCK").upper()
    quantity = _safe_float(getattr(stock, "quantity", 0))
    live_price, price_source = _live_price(market_service, symbol, "stock")
    current_price = live_price or _safe_float(
        getattr(stock, "current_price", None) or getattr(stock, "avg_price", 0)
    )
    stored_value = getattr(stock, "current_value", None)
    current_value = quantity * current_price if current_price > 0 else stored_value
    if current_value is None:
        current_value = 0

    display_name = get_asset_display_name(symbol, "stock")
    if display_name == symbol:
        try:
            resolved = resolve_asset(symbol, "stock")
            resolved_display = resolved.get("display_name")
            if resolved_display and resolved.get("canonical_symbol"):
                display_name = f"{resolved_display} {resolved['canonical_symbol']}"
        except Exception:
            display_name = symbol

    return {
        "id": getattr(stock, "id", None),
        "symbol": symbol,
        "display_name": display_name,
        "quantity": getattr(stock, "quantity", None),
        "avg_price": getattr(stock, "avg_price", None),
        "current_price": current_price,
        "current_value": current_value,
        "price_source": price_source if live_price else "stored",
    }


def _serialize_crypto_position(
    crypto: CryptoPosition,
    market_service: MarketDataService,
) -> dict[str, Any]:
    symbol = str(getattr(crypto, "symbol", None) or "CRYPTO").upper()
    asset_type = getattr(crypto, "asset_type", None) or "crypto"
    quantity = _safe_float(getattr(crypto, "quantity", 0))
    live_price, price_source = _live_price(market_service, symbol, asset_type)
    current_price = live_price or _safe_float(getattr(crypto, "current_price", 0))
    stored_value = getattr(crypto, "current_value", None)
    current_value = quantity * current_price if current_price > 0 else stored_value
    if current_value is None:
        current_value = 0

    grid_lower = getattr(crypto, "grid_lower", None)
    grid_upper = getattr(crypto, "grid_upper", None)
    out_of_range = False
    if current_price > 0 and grid_lower is not None and grid_upper is not None:
        out_of_range = current_price < _safe_float(grid_lower) or current_price > _safe_float(grid_upper)

    return {
        "id": getattr(crypto, "id", None),
        "symbol": symbol,
        "display_name": get_asset_display_name(symbol, asset_type),
        "asset_type": asset_type,
        "quantity": getattr(crypto, "quantity", None),
        "avg_price": getattr(crypto, "avg_price", None),
        "current_price": current_price,
        "current_value": current_value,
        "price_source": price_source if live_price else "stored",
        "leverage": getattr(crypto, "leverage", None),
        "grid_lower": grid_lower,
        "grid_upper": grid_upper,
        "grid_out_of_range": out_of_range,
    }


def _merge_alerts(primary: list[dict[str, Any]], secondary: Any) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in [*primary, *(secondary if isinstance(secondary, list) else [])]:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("title") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        alerts.append(item)

    return alerts


def _ensure_price_source_summary(payload: dict[str, Any]) -> None:
    raw_summary = payload.get("price_source_summary")
    if not isinstance(raw_summary, dict):
        raw_summary = {}

    summary = dict(raw_summary)
    summary.update({
        "yahoo": int(_safe_float(raw_summary.get("yahoo"))),
        "binance": int(_safe_float(raw_summary.get("binance"))),
        "manual": int(_safe_float(raw_summary.get("manual"))),
    })
    payload["price_source_summary"] = summary


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, float):
        return value if isfinite(value) else 0.0
    return value


def _format_pct(value: Any) -> str:
    if value is None:
        return "unknown"
    number = _safe_float(value)
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def _position_value(position: dict[str, Any]) -> float:
    current_value = position.get("current_value")
    if current_value is not None:
        return _safe_float(current_value)

    quantity = _safe_float(position.get("quantity"))
    price = _safe_float(position.get("current_price") or position.get("avg_price"))
    return quantity * price


def build_rule_based_ai_summary(payload: dict[str, Any]) -> dict[str, Any]:
    total_value = _safe_float(payload.get("total_value"))
    stock_value = _safe_float(payload.get("stock_value"))
    cash_value = _safe_float(payload.get("cash_value"))
    crypto_value = _safe_float(payload.get("crypto_value"))
    fcn_value = _safe_float(payload.get("fcn_value"))
    fcn_count = int(_safe_float(payload.get("fcn_count")))

    if total_value <= 0:
        total_value = stock_value + cash_value + crypto_value + fcn_value

    stock_ratio = stock_value / total_value if total_value > 0 else 0
    cash_ratio = cash_value / total_value if total_value > 0 else 0
    crypto_ratio = crypto_value / total_value if total_value > 0 else 0

    stock_positions = [
        item for item in payload.get("stock_positions", [])
        if isinstance(item, dict)
    ]
    fcn_analysis = [
        item for item in payload.get("fcn_analysis", [])
        if isinstance(item, dict)
    ]
    crypto_positions = [
        item for item in payload.get("crypto_positions", [])
        if isinstance(item, dict)
    ]

    messages: list[str] = []
    rule_alerts: list[dict[str, Any]] = []
    risk_scores: list[int] = []
    top_risk = "目前無明顯單一風險來源"

    top_stock = None
    top_stock_ratio = 0.0
    for stock in stock_positions:
        ratio = _position_value(stock) / total_value if total_value > 0 else 0
        if ratio > top_stock_ratio:
            top_stock_ratio = ratio
            top_stock = stock

    if top_stock and top_stock_ratio > 0.5:
        symbol = str(top_stock.get("symbol") or "單一股票").upper()
        top_risk = f"{symbol} concentration"
        risk_scores.append(90)
        messages.append(
            f"{symbol} 佔投資組合 {_format_pct(top_stock_ratio)}，單一股票集中度偏高"
        )
        rule_alerts.append({
            "title": "單一股票集中度過高",
            "severity": "HIGH",
            "message": f"{symbol} 佔投資組合 {_format_pct(top_stock_ratio)}，建議降低單一資產曝險。",
        })
    elif stock_ratio >= 0.4:
        risk_scores.append(50)
        messages.append(f"股票部位約佔 {_format_pct(stock_ratio)}，需持續留意市場波動與產業集中度")

    if total_value > 0 and cash_ratio < 0.05:
        if top_risk == "目前無明顯單一風險來源":
            top_risk = "cash buffer low"
        risk_scores.append(75 if cash_value > 0 else 85)
        messages.append(
            f"現金水位僅 {_format_pct(cash_ratio)}，低於總資產 5%，流動性緩衝偏低"
        )
        rule_alerts.append({
            "title": "現金水位偏低",
            "severity": "HIGH" if cash_value <= 0 else "MEDIUM",
            "message": "現金水位低於總資產 5%，建議補足短期流動性緩衝。",
        })

    if fcn_analysis:
        fcn = next(
            (
                item for item in fcn_analysis
                if str(item.get("risk_level") or "").lower() in {"high", "medium"}
            ),
            fcn_analysis[0],
        )
        symbol = fcn.get("worst_symbol") or fcn.get("worst_of") or "worst-of"
        distance = fcn.get("distance_to_KI")
        if distance is None:
            distance = fcn.get("distance_to_ki_pct")
        fcn_risk = str(fcn.get("risk_level") or "unknown").lower()
        if fcn_risk == "high":
            risk_scores.append(90)
            if top_risk == "目前無明顯單一風險來源":
                top_risk = f"FCN {symbol} KI risk"
        elif fcn_risk == "medium":
            risk_scores.append(65)
            if top_risk == "目前無明顯單一風險來源":
                top_risk = f"FCN {symbol} monitoring"
        messages.append(
            f"FCN 共 {fcn_count or len(fcn_analysis)} 檔，名目本金約 {fcn_value:,.0f}；"
            f"目前 worst-of 為 {symbol}，距離 KI 約 {_format_pct(distance)}，風險等級 {fcn_risk}"
        )

    if crypto_positions or crypto_value > 0:
        crypto_notes: list[str] = []
        leveraged = [
            item for item in crypto_positions
            if _safe_float(item.get("leverage")) > 1
        ]
        grid_out = [
            item for item in crypto_positions
            if item.get("grid_out_of_range")
        ]
        if leveraged:
            symbols = ", ".join(str(item.get("symbol") or "CRYPTO").upper() for item in leveraged[:3])
            crypto_notes.append(f"{symbols} 有槓桿曝險")
            risk_scores.append(75)
            if top_risk == "目前無明顯單一風險來源":
                top_risk = "crypto leverage risk"
        if grid_out:
            symbols = ", ".join(str(item.get("symbol") or "GRID").upper() for item in grid_out[:3])
            crypto_notes.append(f"{symbols} 已超出 grid 區間")
            risk_scores.append(75)
            if top_risk == "目前無明顯單一風險來源":
                top_risk = "grid range risk"
        if not crypto_notes and crypto_ratio >= 0.3:
            crypto_notes.append(f"Crypto 佔比 {_format_pct(crypto_ratio)}，波動資產比重偏高")
            risk_scores.append(60)
        if crypto_notes:
            messages.append("Crypto / Grid 風險：" + "；".join(crypto_notes))

    existing_alerts = [
        item for item in payload.get("alerts", [])
        if isinstance(item, dict)
    ]
    if existing_alerts:
        messages.append(f"目前另有 {len(existing_alerts)} 則風險提醒，建議一併檢視")

    if not messages:
        messages.append(
            "目前投資組合未出現明顯單一風險來源，建議持續追蹤價格更新、FCN KI 距離與現金水位"
        )
        risk_scores.append(20)

    max_score = max(risk_scores or [20])
    if max_score >= 80:
        risk_level = "high"
    elif max_score >= 50:
        risk_level = "medium"
    else:
        risk_level = "low"

    if risk_level == "high":
        closing = "建議先處理最高風險來源，並補足現金緩衝，再逐步分散至不同產業或資產類別。"
    elif risk_level == "medium":
        closing = "建議設定調整優先順序，降低集中或槓桿曝險，並保留足夠現金以應對波動。"
    else:
        closing = "建議維持定期檢視，避免單一資產、FCN 或 Crypto 曝險在市場波動時快速放大。"

    return {
        "risk_level": risk_level,
        "top_risk": top_risk,
        "ai_advice": "；".join(messages) + "。" + closing,
        "alerts": rule_alerts,
    }


def apply_dashboard_v2_fields(db: Session, portfolio: Portfolio, payload: dict[str, Any]) -> dict[str, Any]:
    stocks = db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio.id).all()
    fcns = db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio.id).all()
    cryptos = db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio.id).all()
    market_service = MarketDataService()

    payload["stock_positions"] = [
        _serialize_stock_position(stock, market_service) for stock in stocks
    ]
    payload["stocks"] = payload["stock_positions"]
    payload["fcn_positions"] = [_serialize_fcn_position(fcn) for fcn in fcns]
    payload["crypto_positions"] = [
        _serialize_crypto_position(crypto, market_service) for crypto in cryptos
    ]
    payload["cash_value"] = _safe_float(payload.get("cash_value"))
    _ensure_price_source_summary(payload)

    fcn_analysis = []
    for fcn in fcns:
        result = FCNMonitorService.analyze_fcn(fcn)
        if result:
            fcn_analysis.append(result)
    payload["fcn_analysis"] = fcn_analysis

    risk_v3 = build_risk_engine_v3(payload)
    generated_alerts = risk_v3.pop("generated_alerts", [])
    existing_alerts = payload.get("latest_alerts") or payload.get("alerts") or []

    payload.update(risk_v3)
    merged_alerts = _merge_alerts(generated_alerts, existing_alerts)
    payload["alerts"] = merged_alerts
    payload["latest_alerts"] = merged_alerts

    ai_summary = build_rule_based_ai_summary(payload)
    payload["risk_level"] = ai_summary["risk_level"]
    payload["top_risk"] = ai_summary["top_risk"]
    payload["ai_advice"] = ai_summary["ai_advice"]
    merged_alerts = _merge_alerts(ai_summary["alerts"], payload["alerts"])
    payload["alerts"] = merged_alerts
    payload["latest_alerts"] = merged_alerts

    return _sanitize_payload(payload)



@router.get("/summary/{portfolio_id}")
def get_summary(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: Session = Depends(get_db),
):
    payload = build_portfolio_summary(db, portfolio.id)
    if not payload:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    total = payload.get("total_value", 0) or 0
    stock_value = payload.get("stock_value", 0) or 0
    crypto_value = payload.get("crypto_value", 0) or 0

    stock_ratio = stock_value / total if total > 0 else 0
    crypto_ratio = crypto_value / total if total > 0 else 0
    risk_asset_ratio = (stock_value + crypto_value) / total if total > 0 else 0

    if crypto_ratio >= 0.5:
        level = "HIGH"
        msg = "Crypto 佔比過高"
    elif risk_asset_ratio > 0.7:
        level = "HIGH"
        msg = "風險資產占比過高"
    elif crypto_ratio >= 0.3:
        level = "MEDIUM"
        msg = "Crypto 佔比偏高"
    elif risk_asset_ratio > 0.4:
        level = "MEDIUM"
        msg = "風險資產占比偏高"
    else:
        level = "LOW"
        msg = "資產配置正常"

    top_risk_obj = get_top_stock_risk(db, portfolio.id, total)
    top_risk_text = top_risk_obj["text"] if top_risk_obj else None

    if crypto_ratio >= 0.3 and not top_risk_text:
        top_risk_text = f"Crypto 佔比 {int(crypto_ratio * 100)}%"

    ai_advice = build_ai_advice(top_risk_obj, risk_asset_ratio, crypto_ratio)
    ai_advice = ai_advice or ""

    payload["stock_ratio"] = round(stock_ratio * 100, 2)
    payload["crypto_ratio"] = round(crypto_ratio * 100, 2)
    payload["risk_asset_ratio"] = round(risk_asset_ratio * 100, 2)

    risk_positions = build_portfolio_risk_positions(
        payload=payload,
        top_risk_obj=top_risk_obj,
        crypto_ratio=crypto_ratio,
    )
    risk_result = calculate_portfolio_risk(risk_positions)
    current_data = {
        "risk_level": risk_result["risk_level"],
        "crypto_ratio": crypto_ratio,
        "top_risk_asset": risk_result["top_risk_asset"],
    }
    changes = compare_snapshot(portfolio.id, current_data)
    save_snapshot(portfolio.id, current_data)

    alert_text = generate_risk_alert(risk_result, risk_positions)
    explanation = generate_risk_explanation(
        summary=payload,
        portfolio_risk=risk_result,
        positions=risk_positions,
    )
    allocation_advice = generate_allocation_advice(
        summary=payload,
        portfolio_risk=risk_result,
        risk_explanation=explanation,
    )

    # ===== 配置風險提示 =====
    action = calculate_stock_action(top_risk_obj, total)

    if action:
        ai_advice += f"""

📌 配置風險提示
👉 {action['symbol']} 可能存在集中度風險
👉 建議檢視整體配置與風險承受度
👉 避免單一資產過度集中
"""

    risk_score = max(
        int(risk_asset_ratio * 100),
        int(crypto_ratio * 120),
    )

    risk_alerts = build_alerts_from_risk(
        risk_score=risk_score,
        top_risk=top_risk_text,
        ai_advice=ai_advice,
    )

    maybe_send_risk_push(
        portfolio_id=portfolio.id,
        portfolio_name=payload.get("portfolio_name") or "User Portfolio",
        level=level,
        risk_score=risk_score,
        top_risk_text=top_risk_text,
        ai_advice=ai_advice,
    )

    payload.update({
        "risk_score": risk_score,
        "risk_level": level,
        "risk_message": msg,
        "top_risk": top_risk_text,
        "ai_advice": ai_advice,
        "alerts": risk_alerts,
        "latest_alerts": risk_alerts,
        "portfolio_risk": risk_result,
        "risk_alert": alert_text,
        "risk_alert_message": alert_text,
        "risk_explanation": explanation,
        "allocation_advice": allocation_advice,
        "risk_changes": changes,
        "stock_ratio": payload["stock_ratio"],
        "crypto_ratio": payload["crypto_ratio"],
        "risk_asset_ratio": payload["risk_asset_ratio"],
    })

    return apply_dashboard_v2_fields(db, portfolio, payload)


@router.get("/alerts/{portfolio_id}")
def get_alerts(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: Session = Depends(get_db),
):
    summary = get_summary(portfolio=portfolio, db=db)
    return summary.get("latest_alerts", [])


@router.post("/telegram/test")
def telegram_test(
    current_user: User = Depends(get_current_user),
):
    message = f"""
✅ IXAI Agent Telegram 測試成功
使用者：{current_user.email}
推播系統已連線。
""".strip()

    send_telegram_message(message)

    return {
        "status": "ok",
        "message": "Telegram test push sent",
    }


@router.get("/my-summary")
def get_my_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")

    return get_summary(portfolio=portfolio, db=db)


@router.get("/my-asset-allocation")
def get_my_asset_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")

    payload = build_allocation_payload(db, portfolio.id)
    if not payload:
        raise HTTPException(status_code=404, detail="Portfolio allocation not found")

    return _sanitize_payload(payload)


@router.get("/my-risk-overview")
def get_my_risk_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")

    payload = build_portfolio_summary(db, portfolio.id)
    if not payload:
        raise HTTPException(status_code=404, detail="Portfolio summary not found")

    summary = apply_dashboard_v2_fields(db, portfolio, payload)

    return _sanitize_payload({
        "portfolio_id": summary.get("portfolio_id"),
        "portfolio_name": summary.get("portfolio_name"),
        "risk_level": summary.get("risk_level"),
        "risk_score": summary.get("risk_score"),
        "top_risk": summary.get("top_risk"),
        "decision_cards": summary.get("decision_cards") or [],
        "alerts": summary.get("alerts") or [],
        "ai_advice": summary.get("ai_advice"),
    })


@router.get("/dev-summary")
def get_dev_summary():
    require_development_route()
    return {
        "status": "ok",
        "portfolio_name": "IXAI Demo Portfolio",
        "total_value": 125000,
        "risk_level": "MEDIUM",
        "risk_score": 62,
        "stock_value": 52000,
        "fcn_value": 48000,
        "crypto_value": 25000,
        "top_risk": "Crypto 佔比偏高",
        "ai_advice": "目前配置風險中等，建議持續監控 FCN KI 距離、Crypto 槓桿與單一資產集中度。",
        "alerts": [
            {
                "title": "風險提醒",
                "severity": "MEDIUM",
                "message": "Crypto 與 FCN 部位需要持續追蹤。"
            }
        ]
    }
@router.get("/dev-real-summary")
def get_dev_real_summary(db: Session = Depends(get_db)):
    require_development_route()
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.name == "IXAI Demo Portfolio")
        .order_by(Portfolio.created_at.desc())
        .first()
    )

    if not portfolio:
        portfolio = db.query(Portfolio).first()

    if not portfolio:
        return {
            "status": "empty",
            "message": "目前資料庫沒有 portfolio",
        }

    payload = build_portfolio_summary(db, portfolio.id)

    if not payload:
        raise HTTPException(status_code=404, detail="Portfolio summary not found")

    return apply_dashboard_v2_fields(db, portfolio, {
        "status": "ok",
        **payload,
    })
