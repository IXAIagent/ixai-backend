from __future__ import annotations

from app.core.database import SessionLocal
from app.models.models import Alert, CryptoPosition, FCNPosition, Portfolio, StockPosition, User


def fmt_money(v: float | None, currency: str = "USD") -> str:
    if v is None:
        v = 0.0
    return f"{currency} {v:,.2f}"


def show_dashboard() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            print("目前資料庫沒有 user，請先跑 test_insert_assets.py")
            return

        portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
        if not portfolio:
            print("目前資料庫沒有 portfolio，請先建立投資組合資料")
            return

        stocks = db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio.id).all()
        cryptos = db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio.id).all()
        fcns = db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio.id).all()
        alerts = (
            db.query(Alert)
            .filter(Alert.portfolio_id == portfolio.id)
            .order_by(Alert.triggered_at.desc())
            .all()
        )

        stock_value = sum((s.current_value or 0.0) for s in stocks)
        crypto_value = sum((c.current_value or 0.0) for c in cryptos)
        fcn_value = sum((f.notional_amount or 0.0) for f in fcns)
        total_value = stock_value + crypto_value + fcn_value

        print("=" * 60)
        print("一玄AI 投資 Dashboard")
        print("=" * 60)
        print(f"User: {user.name or user.email}")
        print(f"Portfolio: {portfolio.name}")
        print(f"Base Currency: {portfolio.base_currency}")
        print("-" * 60)
        print(f"總資產: {fmt_money(total_value, portfolio.base_currency)}")
        print(f"股票資產: {fmt_money(stock_value, portfolio.base_currency)}")
        print(f"Crypto 資產: {fmt_money(crypto_value, portfolio.base_currency)}")
        print(f"FCN 名目金額: {fmt_money(fcn_value, portfolio.base_currency)}")
        print("-" * 60)

        print("\n[股票部位]")
        if not stocks:
            print("- 無資料")
        else:
            for s in stocks:
                print(
                    f"- {s.symbol} | {s.company_name or '-'} | "
                    f"現值 {fmt_money(s.current_value, s.currency)} | "
                    f"未實現 {fmt_money(s.unrealized_pnl, s.currency)}"
                )

        print("\n[Crypto 部位]")
        if not cryptos:
            print("- 無資料")
        else:
            for c in cryptos:
                extra = ""
                if c.asset_type == "grid":
                    extra = f" | Grid {c.grid_lower}-{c.grid_upper}"
                print(
                    f"- {c.symbol} ({c.asset_type}) | "
                    f"現值 {fmt_money(c.current_value, c.currency)} | "
                    f"未實現 {fmt_money(c.unrealized_pnl, c.currency)}{extra}"
                )

        print("\n[FCN 部位]")
        if not fcns:
            print("- 無資料")
        else:
            for f in fcns:
                print(
                    f"- {f.fcn_code} | Worst-of: {f.worst_of_symbol or '-'} | "
                    f"距 KI: {f.distance_to_ki_pct if f.distance_to_ki_pct is not None else '-'}% | "
                    f"Risk: {f.risk_level or '-'}"
                )

        print("\n[Alerts]")
        if not alerts:
            print("- 無警示")
        else:
            for a in alerts[:10]:
                print(f"- [{a.severity.upper()}] {a.title} | {a.message or ''}")

        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    show_dashboard()
