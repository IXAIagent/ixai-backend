import os

import requests


def send_telegram_message(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })


class TelegramService:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            resp = requests.post(url, json=payload, timeout=8)
            print("Telegram response:", resp.status_code, resp.text)
        except Exception as e:
            print("Telegram 發送失敗:", e)

    def send_risk_alert(self, title: str, alert_type: str, severity: str):
        severity = (severity or "").lower()

        icon = "⚠️"
        if severity == "high":
            icon = "🚨"
        elif severity == "medium":
            icon = "🟠"
        elif severity == "low":
            icon = "🟡"

        text = (
            f"{icon} <b>Risk Alert</b>\n"
            f"等級: <b>{severity.upper()}</b>\n"
            f"類型: {alert_type}\n"
            f"事件: {title}"
        )
        self.send_message(text)

    def send_risk_cleared(self, title: str, asset_class: str, asset_ref: str):
        text = (
            f"✅ <b>Risk Cleared</b>\n"
            f"類型: {asset_class}\n"
            f"標的: {asset_ref}\n"
            f"事件: {title}"
        )
        self.send_message(text)

    def send_summary(self, lines: list[str], title: str = "風險彙總"):
        if not lines:
            return

        body = "\n".join(lines)
        text = f"📋 <b>{title}</b>\n{body}"
        self.send_message(text)
