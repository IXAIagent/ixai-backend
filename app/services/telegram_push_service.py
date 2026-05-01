from __future__ import annotations

from html import escape
from typing import Any

import requests

from app.core.config import settings


def is_telegram_configured() -> bool:
    return bool(settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def send_telegram_message(message: str) -> dict[str, Any]:
    """Send a Telegram message using Bot API.

    Returns a status dict instead of raising, so dashboard APIs do not crash
    when Telegram is not configured or the network fails.
    """
    if not is_telegram_configured():
        return {"ok": False, "status": "not_configured"}

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
        if response.ok:
            return {"ok": True, "status": "sent"}
        return {
            "ok": False,
            "status": "telegram_error",
            "code": response.status_code,
            "body": response.text[:300],
        }
    except Exception as exc:
        return {"ok": False, "status": "send_failed", "error": str(exc)}


def build_risk_alert_message(
    *,
    portfolio_name: str,
    risk_level: str,
    risk_score: int,
    top_risk: str | None,
    ai_advice: str | None,
) -> str:
    icon = "🚨" if str(risk_level).upper() == "HIGH" else "🟠"
    title = escape(portfolio_name or "IXAI Portfolio")
    top = escape(top_risk or "投資組合")
    advice = escape(ai_advice or "請檢視資產配置。")

    return (
        f"{icon} <b>IXAI Agent 風險提醒</b>\n"
        f"Portfolio：<b>{title}</b>\n"
        f"風險等級：<b>{escape(str(risk_level).upper())}</b>\n"
        f"Risk Score：<b>{risk_score}</b>\n"
        f"Top Risk：<b>{top}</b>\n\n"
        f"<b>AI 建議</b>\n{advice}"
    )
