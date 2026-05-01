from __future__ import annotations

import time
from datetime import datetime

import schedule

from app.core.database import SessionLocal
from app.models.models import Portfolio
from app.services.daily_summary_service import send_daily_summary


BOT_TOKEN = "7656803416:AAFiLzhtBhgQAyxjRFjjziwVD5V4tQx5o1U"
CHAT_ID = "8761817352"

# 每天推播時間，可自行改
DAILY_SUMMARY_TIME = "13:16"


def job():
    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            print("找不到 portfolio，略過本次 Daily Summary。")
            return

        text = send_daily_summary(
            db=db,
            portfolio_id=portfolio.id,
            bot_token=BOT_TOKEN,
            chat_id=CHAT_ID,
        )

        print("=== DAILY SUMMARY SENT ===")
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(text)

    except Exception as e:
        print("Daily Summary 排程執行失敗:", e)
    finally:
        db.close()


def main():
    print(f"Daily Summary scheduler started. Send time = {DAILY_SUMMARY_TIME}")
    schedule.every().day.at(DAILY_SUMMARY_TIME).do(job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
