from app.services.market_data.yahoo_provider import YahooProvider


def get_stock_price(symbol: str):
    try:
        provider = YahooProvider()
        return provider.get_price(symbol)
    except Exception:
        return None


def calculate_stock_action(top_risk_obj, total_value):
    if not top_risk_obj:
        return None

    symbol = top_risk_obj["symbol"]
    ratio = top_risk_obj["ratio"]

    target_ratio = 0.3

    if ratio <= target_ratio:
        return None

    reduce_ratio = ratio - target_ratio
    reduce_value = total_value * reduce_ratio

    price = get_stock_price(symbol)

    if not price or price <= 0:
        return None

    shares_to_sell = int(reduce_value / price)

    return {
        "symbol": symbol,
        "sell_shares": shares_to_sell,
        "target_ratio": int(target_ratio * 100),
        "current_ratio": int(ratio * 100),
        "price": round(price, 2),
        "reduce_value": round(reduce_value, 2),
    }
