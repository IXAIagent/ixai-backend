from __future__ import annotations

from app.core.database import SessionLocal
from app.models.models import Portfolio
from app.services.risk_engine import run_risk_check


def main():
    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            print("找不到 portfolio，請先建立資料。")
            return

        result = run_risk_check(db, portfolio.id)

        print("=== RISK CHECK COMPLETE ===")
        print(f"portfolio_id: {result['portfolio_id']}")
        print(f"created_count: {result['created_count']}")

        for item in result["created_alerts"]:
            print(f"- [{item['type']}] {item['title']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()