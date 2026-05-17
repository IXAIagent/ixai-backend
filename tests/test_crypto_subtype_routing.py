from __future__ import annotations

from app.services.crypto_subtypes import get_crypto_base_type, get_crypto_strategy_parts
from app.services.market_data.service import MarketDataService
from app.services.risk_engine_v3 import _crypto_risk


def test_crypto_subtype_parser_base_types():
    cases = {
        None: "spot",
        "": "spot",
        "spot": "spot",
        "grid:long": "grid",
        "grid:neutral": "grid",
        "dual:put": "dual",
        "dual:call": "dual",
        "stablecoin_earn:30:5.5": "stablecoin_earn",
        "unknown:x:y": "unknown",
    }

    for raw, expected in cases.items():
        assert get_crypto_base_type(raw) == expected


def test_crypto_subtype_parser_strategy_parts():
    assert get_crypto_strategy_parts("stablecoin_earn:30:5.5") == [
        "stablecoin_earn",
        "30",
        "5.5",
    ]
    assert get_crypto_strategy_parts(" grid:long ") == ["grid", "long"]


def test_market_data_routes_colon_encoded_subtypes_as_crypto():
    service = MarketDataService()

    assert service.detect_symbol_type("BTC", "grid:long") == "crypto"
    assert service.detect_symbol_type("BTC", "spot") == "crypto"
    assert service.detect_symbol_type("ETH", "dual:call") == "crypto"
    assert service.detect_symbol_type("USDT", "stablecoin_earn:30:5.5") == "crypto"
    assert service.detect_symbol_type("AAPL", None) == "stock"


def test_grid_long_enters_grid_range_risk_branch():
    source, alerts = _crypto_risk(
        {
            "crypto_positions": [
                {
                    "symbol": "BTCUSDT",
                    "asset_type": "grid:long",
                    "quantity": 1,
                    "current_price": 120,
                    "current_value": 120,
                    "grid_lower": 80,
                    "grid_upper": 100,
                }
            ],
            "crypto_value": 120,
        },
        total_value=120,
    )

    assert source is not None
    assert source["score"] >= 86
    assert alerts
    assert alerts[0]["asset_ref"] == "BTCUSDT"


def test_grid_neutral_enters_grid_range_risk_branch():
    source, alerts = _crypto_risk(
        {
            "crypto_positions": [
                {
                    "symbol": "ETHUSDT",
                    "asset_type": "grid:neutral",
                    "quantity": 1,
                    "current_price": 70,
                    "current_value": 70,
                    "grid_lower": 80,
                    "grid_upper": 100,
                }
            ],
            "crypto_value": 70,
        },
        total_value=70,
    )

    assert source is not None
    assert source["score"] >= 86
    assert alerts
    assert alerts[0]["asset_ref"] == "ETHUSDT"


def test_dual_and_stablecoin_earn_are_not_treated_as_generic_spot():
    source, alerts = _crypto_risk(
        {
            "crypto_positions": [
                {
                    "symbol": "BTCUSDT",
                    "asset_type": "dual:put",
                    "current_value": 100,
                },
                {
                    "symbol": "USDT",
                    "asset_type": "stablecoin_earn:30:5.5",
                    "current_value": 100,
                },
            ],
            "crypto_value": 200,
        },
        total_value=1000,
    )

    assert source is not None
    assert "Dual Investment" in source["message"]
    assert "Stablecoin Earn" in source["message"]
    assert alerts == []
