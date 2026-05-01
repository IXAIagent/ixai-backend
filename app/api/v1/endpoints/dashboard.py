from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_current_user, get_owned_portfolio
from app.core.database import get_db
from app.models.models import Portfolio, User
from app.services.portfolio_service import build_portfolio_summary
from app.services.push_state_service import should_send_push
from app.services.telegram_push_service import send_telegram_message
from app.services.action_service import calculate_stock_action
from app.services.risk.portfolio_risk import calculate_portfolio_risk
from app.services.risk.alert_engine import generate_risk_alert
from app.services.risk.explanation_engine import generate_risk_explanation
from app.services.risk.allocation_engine import generate_allocation_advice
from app.services.risk.risk_tracker import save_snapshot, compare_snapshot

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_top_stock_risk(db: Session, portfolio_id: str, total_value: float):
    candidate_tables = ["stock", "stocks", "stock_position", "stock_positions"]

    for table in candidate_tables:
        exists = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table},
        ).fetchone()

        if not exists:
            continue

        columns = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
        column_names = [c[1] for c in columns]

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

    return payload


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
