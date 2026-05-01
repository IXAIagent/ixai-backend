from datetime import date, datetime

from app.core.database import Base, SessionLocal, engine
from app.models.models import (
    Alert,
    CryptoPosition,
    FCNPosition,
    FCNUnderlying,
    Portfolio,
    StockPosition,
    User,
)


Base.metadata.create_all(bind=engine)


def main() -> None:
    db = SessionLocal()

    try:
        # 建立 demo user
        user = User(
            email="demo@example.com",
            name="Demo User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # 建立 demo portfolio
        portfolio = Portfolio(
            user_id=user.id,
            name="Demo Portfolio",
            base_currency="USD",
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

        # 建立 demo 股票部位
        stocks = [
            StockPosition(
                portfolio_id=portfolio.id,
                market="US",
                symbol="AAPL",
                company_name="Apple Inc.",
                currency="USD",
                quantity=80,
                avg_cost=165.0,
                current_price=192.0,
                current_value=15360.0,
                unrealized_pnl=2160.0,
                weight_pct=18.0,
            ),
            StockPosition(
                portfolio_id=portfolio.id,
                market="US",
                symbol="MSFT",
                company_name="Microsoft Corp.",
                currency="USD",
                quantity=35,
                avg_cost=380.0,
                current_price=410.0,
                current_value=14350.0,
                unrealized_pnl=1050.0,
                weight_pct=16.8,
            ),
            StockPosition(
                portfolio_id=portfolio.id,
                market="TW",
                symbol="2330",
                company_name="TSMC",
                currency="TWD",
                quantity=120,
                avg_cost=860.0,
                current_price=910.0,
                current_value=109200.0,
                unrealized_pnl=6000.0,
                weight_pct=12.5,
            ),
        ]
        db.add_all(stocks)
        db.commit()

        # 建立 demo crypto 部位
        cryptos = [
            CryptoPosition(
                portfolio_id=portfolio.id,
                asset_type="spot",
                symbol="BTC",
                exchange_name="Binance",
                quote_currency="USDT",
                currency="USD",
                quantity=0.25,
                avg_cost=68500.0,
                current_price=71200.0,
                current_value=17800.0,
                unrealized_pnl=675.0,
                leverage=1.0,
                margin_amount=0.0,
                status="active",
            ),
            CryptoPosition(
                portfolio_id=portfolio.id,
                asset_type="grid",
                symbol="ETH",
                exchange_name="Binance",
                quote_currency="USDT",
                currency="USD",
                quantity=1.8,
                avg_cost=2100.0,
                current_price=2250.0,
                current_value=4050.0,
                unrealized_pnl=270.0,
                leverage=5.0,
                margin_amount=800.0,
                grid_lower=1800.0,
                grid_upper=2400.0,
                grid_count=40,
                status="active",
            ),
        ]
        db.add_all(cryptos)
        db.commit()

        # 建立 demo FCN 主表
        fcn = FCNPosition(
            portfolio_id=portfolio.id,
            fcn_code="FCN_DEMO_001",
            issuer="Demo Bank",
            currency="USD",
            notional_amount=100000.0,
            ko_level=100.0,
            ki_level=65.0,
            strike_level=95.0,
            coupon_rate=1.45,
            issue_date=date(2026, 1, 15),
            maturity_date=date(2027, 1, 15),
            next_coupon_date=date(2026, 5, 15),
            worst_of_symbol="NVDA",
            worst_of_price=720.0,
            distance_to_ki_pct=8.2,
            distance_to_ko_pct=24.5,
            risk_level="high",
            status="active",
        )
        db.add(fcn)
        db.commit()
        db.refresh(fcn)

        # 建立 demo FCN underlyings
        underlyings = [
            FCNUnderlying(
                fcn_position_id=fcn.id,
                symbol="NVDA",
                name="NVIDIA",
                initial_price=820.0,
                current_price=720.0,
                performance_pct=-12.2,
                is_worst_of=True,
            ),
            FCNUnderlying(
                fcn_position_id=fcn.id,
                symbol="AMZN",
                name="Amazon",
                initial_price=185.0,
                current_price=178.0,
                performance_pct=-3.8,
                is_worst_of=False,
            ),
            FCNUnderlying(
                fcn_position_id=fcn.id,
                symbol="GOOGL",
                name="Alphabet",
                initial_price=172.0,
                current_price=169.0,
                performance_pct=-1.7,
                is_worst_of=False,
            ),
        ]
        db.add_all(underlyings)
        db.commit()

        # 建立 demo alerts
        alerts = [
            Alert(
                portfolio_id=portfolio.id,
                asset_class="fcn",
                asset_ref="FCN_DEMO_001",
                severity="high",
                title="FCN 接近 KI 區域",
                message="Worst-of 距 KI 約 8.2%，請留意波動風險。",
                status="open",
                triggered_at=datetime.utcnow(),
            ),
            Alert(
                portfolio_id=portfolio.id,
                asset_class="crypto",
                asset_ref="ETH Grid",
                severity="medium",
                title="ETH Grid 接近區間上緣",
                message="ETH 已接近上緣，建議檢查是否需要調整區間。",
                status="open",
                triggered_at=datetime.utcnow(),
            ),
            Alert(
                portfolio_id=portfolio.id,
                asset_class="stock",
                asset_ref="AAPL",
                severity="low",
                title="AAPL 持倉占比偏高",
                message="單一持股占比接近 20%，請留意集中度。",
                status="open",
                triggered_at=datetime.utcnow(),
            ),
        ]
        db.add_all(alerts)
        db.commit()

        print("Insert OK: demo assets inserted successfully")

    finally:
        db.close()


if __name__ == "__main__":
    main()


