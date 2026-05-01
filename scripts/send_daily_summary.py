from __future__ import annotations

from app.core.database import SessionLocal
from app.models.models import Portfolio
from app.services.daily_summary_service import send_daily_summary


BOT_TOKEN = "7656803416:AAFiLzhtBhgQAyxjRFjjziwVD5V4tQx5o1U"
CHAT_ID = "8761817352"


def main():
    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            print("找不到 portfolio，請先建立資料。")
            return

        text = send_daily_summary(
            db=db,
            portfolio_id=portfolio.id,
            bot_token=BOT_TOKEN,
            chat_id=CHAT_ID,
        )

        print("=== DAILY SUMMARY SENT ===")
        print(text)

    finally:
        db.close()


if __name__ == "__main__":
    main()
