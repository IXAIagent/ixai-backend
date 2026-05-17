from __future__ import annotations

from app.services.risk_engine_v3 import build_risk_engine_v3


def test_canonical_risk_engine_handles_stock_fcn_and_crypto_classes():
    result = build_risk_engine_v3(
        {
            "total_value": 10_000,
            "stock_value": 4_500,
            "cash_value": 500,
            "crypto_value": 2_000,
            "fcn_value": 3_000,
            "stocks": [
                {
                    "symbol": "NVDA",
                    "quantity": 10,
                    "current_price": 450,
                    "current_value": 4_500,
                }
            ],
            "crypto_positions": [
                {
                    "symbol": "BTCUSDT",
                    "asset_type": "grid:long",
                    "current_price": 120,
                    "current_value": 1_200,
                    "grid_lower": 80,
                    "grid_upper": 100,
                },
                {
                    "symbol": "ETHUSDT",
                    "asset_type": "dual:put",
                    "current_value": 500,
                },
                {
                    "symbol": "USDT",
                    "asset_type": "stablecoin_earn:30:5.5",
                    "current_value": 300,
                },
            ],
            "fcn_analysis": [
                {
                    "fcn_code": "FCN100",
                    "worst_symbol": "MDB",
                    "distance_to_KI": 0.04,
                    "risk_level": "high",
                    "prices": [
                        {
                            "symbol": "MDB",
                            "initial_price": 100,
                            "current_price": 72,
                        }
                    ],
                }
            ],
        }
    )

    source_classes = {
        source["asset_class"]
        for source in result["risk_sources"]
    }

    assert {"Stock", "FCN", "Crypto", "Cash"}.issubset(source_classes)
    assert result["risk_score"] >= 80
    assert result["risk_level"] == "high"
    assert any(alert["asset_ref"] == "BTCUSDT" for alert in result["generated_alerts"])


def test_canonical_risk_engine_preserves_crypto_subtype_messages():
    result = build_risk_engine_v3(
        {
            "total_value": 1_000,
            "crypto_value": 300,
            "crypto_positions": [
                {
                    "symbol": "BTCUSDT",
                    "asset_type": "dual:call",
                    "current_value": 150,
                },
                {
                    "symbol": "USDC",
                    "asset_type": "stablecoin_earn:90:4.8",
                    "current_value": 150,
                },
            ],
        }
    )

    crypto_source = next(
        source for source in result["risk_sources"]
        if source["asset_class"] == "Crypto"
    )

    assert "Dual Investment" in crypto_source["message"]
    assert "Stablecoin Earn" in crypto_source["message"]
