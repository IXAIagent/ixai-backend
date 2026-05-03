from __future__ import annotations

import os
import time
from datetime import datetime

from app.core.database import SessionLocal
from app.models.models import Portfolio
from app.services.daily_summary_service import send_daily_summary


# 每天推播時間，可自行改
DAILY_SUMMARY_TIME = "13:16"


def get_telegram_config():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print(
            "Missing Telegram configuration. Please set TELEGRAM_BOT_TOKEN "
            "and TELEGRAM_CHAT_ID before running the scheduler."
        )
        return None, None

    return bot_token, chat_id


def job():
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return

    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            print("找不到 portfolio，略過本次 Daily Summary。")
            return

        text = send_daily_summary(
            db=db,
            portfolio_id=portfolio.id,
            bot_token=bot_token,
            chat_id=chat_id,
        )

        print("=== DAILY SUMMARY SENT ===")
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(text)

    except Exception as e:
        print("Daily Summary 排程執行失敗:", e)
    finally:
        db.close()


def main():
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return

    import schedule

    print(f"Daily Summary scheduler started. Send time = {DAILY_SUMMARY_TIME}")
    schedule.every().day.at(DAILY_SUMMARY_TIME).do(job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
