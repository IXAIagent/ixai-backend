from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.models.models import (
    Alert,
    CryptoPosition,
    FCNPosition,
    Portfolio,
    StockPosition,
    User,
)


def now():
    return datetime.now(UTC)


def main():
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == "demo@yixuan.ai").first()
        if not user:
            user = User(
                id=uuid.uuid4().bytes,
                email="demo@yixuan.ai",
                name="Demo User",
            )
            db.add(user)
            db.flush()
            print("✅ user created")
        else:
            print("⚠️ user exists")

        portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
        if not portfolio:
            portfolio = Portfolio(
                id=uuid.uuid4().bytes,
                user_id=user.id,
                name="Demo Portfolio",
                base_currency="USD",
            )
            db.add(portfolio)
            db.flush()
            print("✅ portfolio created")
        else:
            print("⚠️ portfolio exists")

        db.add(
            StockPosition(
                id=uuid.uuid4().bytes,
                portfolio_id=portfolio.id,
                market="us",
                symbol="AAPL",
                company_name="Apple Inc.",
                currency="USD",
                quantity=100,
                avg_cost=140,
                current_price=210,
                current_value=21000,
                is_active=True,
            )
        )

        db.add(
            StockPosition(
                id=uuid.uuid4().bytes,
                portfolio_id=portfolio.id,
                market="us",
                symbol="TSLA",
                company_name="Tesla Inc.",
                currency="USD",
                quantity=50,
                avg_cost=160,
                current_price=250,
                current_value=12500,
                is_active=True,
            )
        )

        print("✅ stocks added")

        db.add(
            FCNPosition(
                id=uuid.uuid4().bytes,
                portfolio_id=portfolio.id,
                fcn_code="FCN219M",
                currency="USD",
                notional_amount=100000,
                worst_of_symbol="MDB",
                distance_to_ki_pct=5,
                risk_level="high",
                status="active",
            )
        )

        print("✅ fcn added")

        db.add(
            CryptoPosition(
                id=uuid.uuid4().bytes,
                portfolio_id=portfolio.id,
                asset_type="grid",
                symbol="BTC",
                exchange_name="Binance",
                quote_currency="USDT",
                currency="USD",
                quantity=0.03,
                current_price=78000,
                current_value=2340,
                leverage=8,
                status="active",
            )
        )

        print("✅ crypto added")

        db.add(
            Alert(
                id=uuid.uuid4().bytes,
                portfolio_id=portfolio.id,
                asset_class="fcn",
                asset_ref="FCN219M",
                title="FCN 接近 KI",
                message="風險偏高",
                severity="high",
                status="open",
                triggered_at=now(),
            )
        )

        print("✅ alert added")

        db.commit()

        print("\n🔥 SUCCESS")
        print(f"portfolio_id(bytes) = {portfolio.id}")
        print(f"portfolio_id(hex) = {portfolio.id.hex()}")

    except Exception as e:
        db.rollback()
        print("❌ ERROR:", e)
    finally:
        db.close()


if __name__ == "__main__":
    main()
