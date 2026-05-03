from datetime import datetime
from app.core.database import Base, engine, SessionLocal
from app.models.models import (
    User,
    Portfolio,
    StockPosition,
    FCNPosition,
    CryptoPosition,
    Alert,
)


def get_or_create_user(db):
    user = db.query(User).filter(User.email == "demo@ixai.local").first()
    if user:
        print("✅ user exists")
        return user

    user = User(
        email="demo@ixai.local",
        hashed_password="dev-password-not-for-production",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("✅ user created")
    return user


def get_or_create_portfolio(db, user):
    portfolio = (
        db.query(Portfolio)
        .filter(
            Portfolio.user_id == user.id,
            Portfolio.name == "IXAI Demo Portfolio",
        )
        .first()
    )

    if portfolio:
        print("✅ portfolio exists")
        return portfolio

    portfolio = Portfolio(
        name="IXAI Demo Portfolio",
        base_currency="USD",
        user_id=user.id,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    print("✅ portfolio created")
    return portfolio


def clear_demo_positions(db, portfolio):
    db.query(Alert).filter(Alert.portfolio_id == portfolio.id).delete()
    db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio.id).delete()
    db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio.id).delete()
    db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio.id).delete()
    db.commit()
    print("✅ old demo positions cleared")


def seed_stocks(db, portfolio):
    stocks = [
        {
            "symbol": "AAPL",
            "quantity": 100,
            "avg_price": 140.26,
            "current_price": 195.00,
        },
        {
            "symbol": "TSLA",
            "quantity": 50,
            "avg_price": 160.91,
            "current_price": 285.00,
        },
        {
            "symbol": "NVDA",
            "quantity": 10,
            "avg_price": 127.00,
            "current_price": 880.00,
        },
    ]

    for item in stocks:
        current_value = item["quantity"] * item["current_price"]
        db.add(
            StockPosition(
                portfolio_id=portfolio.id,
                symbol=item["symbol"],
                quantity=item["quantity"],
                avg_price=item["avg_price"],
                current_price=item["current_price"],
                current_value=current_value,
            )
        )

    db.commit()
    print("✅ stocks seeded")


def seed_fcns(db, portfolio):
    fcns = [
        {
            "name": "FCN219M",
            "fcn_code": "FCN219M",
            "notional": 30000,
            "notional_amount": 30000,
            "worst_of_symbol": "MDB",
            "distance_to_ki_pct": -8.5,
            "distance_to_ko_pct": 34.2,
            "risk_level": "high",
        },
        {
            "name": "FCN813M",
            "fcn_code": "FCN813M",
            "notional": 25000,
            "notional_amount": 25000,
            "worst_of_symbol": "TSLA",
            "distance_to_ki_pct": 18.4,
            "distance_to_ko_pct": 12.8,
            "risk_level": "medium",
        },
    ]

    for item in fcns:
        db.add(
            FCNPosition(
                portfolio_id=portfolio.id,
                name=item["name"],
                fcn_code=item["fcn_code"],
                notional=item["notional"],
                notional_amount=item["notional_amount"],
                worst_of_symbol=item["worst_of_symbol"],
                distance_to_ki_pct=item["distance_to_ki_pct"],
                distance_to_ko_pct=item["distance_to_ko_pct"],
                risk_level=item["risk_level"],
            )
        )

    db.commit()
    print("✅ fcns seeded")


def seed_crypto(db, portfolio):
    cryptos = [
        {
            "symbol": "BTCUSDT",
            "asset_type": "grid",
            "quantity": 0.033,
            "avg_price": 75345.40,
            "current_price": 97000.00,
            "leverage": 8,
            "grid_lower": 72000,
            "grid_upper": 82000,
        },
        {
            "symbol": "ETHUSDT",
            "asset_type": "grid",
            "quantity": 0.75,
            "avg_price": 2006.32,
            "current_price": 1850.00,
            "leverage": 10,
            "grid_lower": 1750,
            "grid_upper": 2450,
        },
    ]

    for item in cryptos:
        current_value = item["quantity"] * item["current_price"]
        db.add(
            CryptoPosition(
                portfolio_id=portfolio.id,
                symbol=item["symbol"],
                asset_type=item["asset_type"],
                quantity=item["quantity"],
                avg_price=item["avg_price"],
                current_price=item["current_price"],
                current_value=current_value,
                leverage=item["leverage"],
                grid_lower=item["grid_lower"],
                grid_upper=item["grid_upper"],
            )
        )

    db.commit()
    print("✅ crypto positions seeded")


def seed_alerts(db, portfolio):
    alerts = [
        {
            "asset_class": "FCN",
            "asset_ref": "FCN219M / MDB",
            "severity": "high",
            "level": "high",
            "title": "FCN KI 風險提醒",
            "message": "FCN219M 的 Worst-of 標的 MDB 已接近或跌破 KI 區域，需持續追蹤。",
            "status": "open",
        },
        {
            "asset_class": "CRYPTO",
            "asset_ref": "BTCUSDT Grid",
            "severity": "medium",
            "level": "medium",
            "title": "BTC Grid 區間提醒",
            "message": "BTCUSDT 已高於原設定 Grid 上緣，應檢查是否需要調整策略區間。",
            "status": "open",
        },
        {
            "asset_class": "PORTFOLIO",
            "asset_ref": "IXAI Demo Portfolio",
            "severity": "medium",
            "level": "medium",
            "title": "投資組合集中度提醒",
            "message": "股票、FCN 與 Crypto 同時暴露於高波動資產，需留意整體回撤風險。",
            "status": "open",
        },
    ]

    for item in alerts:
        db.add(
            Alert(
                portfolio_id=portfolio.id,
                asset_class=item["asset_class"],
                asset_ref=item["asset_ref"],
                severity=item["severity"],
                level=item["level"],
                title=item["title"],
                message=item["message"],
                status=item["status"],
                triggered_at=datetime.utcnow(),
            )
        )

    db.commit()
    print("✅ alerts seeded")


def main():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = get_or_create_user(db)
        portfolio = get_or_create_portfolio(db, user)

        clear_demo_positions(db, portfolio)

        seed_stocks(db, portfolio)
        seed_fcns(db, portfolio)
        seed_crypto(db, portfolio)
        seed_alerts(db, portfolio)

        print("")
        print("🎉 Demo seed completed")
        print(f"Portfolio ID: {portfolio.id}")
        print("")
        print("Test:")
        print("http://127.0.0.1:8000/api/v1/dashboard/dev-real-summary")

    except Exception as exc:
        db.rollback()
        print(f"❌ ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()