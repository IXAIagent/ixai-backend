from __future__ import annotations

import os

from app.core.database import SessionLocal
from app.models.models import Portfolio
from app.services.daily_summary_service import send_daily_summary


def get_telegram_config():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print(
            "Missing Telegram configuration. Please set TELEGRAM_BOT_TOKEN "
            "and TELEGRAM_CHAT_ID before running this script."
        )
        return None, None

    return bot_token, chat_id


def main():
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return

    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            print("找不到 portfolio，請先建立資料。")
            return

        text = send_daily_summary(
            db=db,
            portfolio_id=portfolio.id,
            bot_token=bot_token,
            chat_id=chat_id,
        )

        print("=== DAILY SUMMARY SENT ===")
        print(text)

    finally:
        db.close()


if __name__ == "__main__":
    main()
