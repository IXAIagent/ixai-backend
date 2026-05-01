from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import Alert, Portfolio
from app.services.telegram_service import TelegramService


def build_daily_summary_text(db: Session, portfolio_id: bytes) -> str:
    portfolio = db.get(Portfolio, portfolio_id)
    portfolio_name = portfolio.name if portfolio else "Unknown Portfolio"

    open_alerts = (
        db.query(Alert)
        .filter(Alert.portfolio_id == portfolio_id, Alert.status == "open")
        .order_by(Alert.triggered_at.desc())
        .all()
    )

    closed_alerts = (
        db.query(Alert)
        .filter(Alert.portfolio_id == portfolio_id, Alert.status == "closed")
        .order_by(Alert.triggered_at.desc())
        .limit(10)
        .all()
    )

    high_count = sum(1 for a in open_alerts if (a.severity or "").lower() == "high")
    medium_count = sum(1 for a in open_alerts if (a.severity or "").lower() == "medium")
    low_count = sum(1 for a in open_alerts if (a.severity or "").lower() == "low")

    lines: list[str] = []
    lines.append("📊 <b>Daily Risk Report</b>")
    lines.append(f"組合: {portfolio_name}")
    lines.append("")
    lines.append(f"未解除風險共 {len(open_alerts)} 筆")
    lines.append(f"- HIGH: {high_count}")
    lines.append(f"- MEDIUM: {medium_count}")
    lines.append(f"- LOW: {low_count}")

    if open_alerts:
        lines.append("")
        lines.append("🚨 <b>目前未解除風險</b>")
        for a in open_alerts[:10]:
            sev = (a.severity or "").upper()
            lines.append(f"- [{sev}] {a.title}")
    else:
        lines.append("")
        lines.append("✅ 目前沒有未解除風險")

    if closed_alerts:
        lines.append("")
        lines.append("✅ <b>最近解除風險</b>")
        for a in closed_alerts[:5]:
            lines.append(f"- {a.title}")

    return "\n".join(lines)


def send_daily_summary(
    db: Session,
    portfolio_id: bytes,
    bot_token: str,
    chat_id: str,
) -> str:
    text = build_daily_summary_text(db, portfolio_id)
    tg = TelegramService(bot_token, chat_id)
    tg.send_message(text)
    return text