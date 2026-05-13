from typing import Any


class RiskPositionAnalyzer:
    @staticmethod
    def analyze(
        payload: dict,
        top_risk_obj: Any,
        crypto_ratio: float,
    ) -> list[dict]:
        stock_value = float(payload.get("stock_value", 0) or 0)
        crypto_value = float(payload.get("crypto_value", 0) or 0)
        fcn_value = float(payload.get("fcn_value", 0) or 0)

        positions = []

        if stock_value > 0:
            top_stock_ratio = float((top_risk_obj or {}).get("ratio", 0) or 0)
            if top_stock_ratio > 0.5:
                stock_risk_tag = "HIGH"
            elif top_stock_ratio > 0.3:
                stock_risk_tag = "MEDIUM"
            else:
                stock_risk_tag = "LOW"

            positions.append({
                "symbol": (top_risk_obj or {}).get("symbol") or "STOCK",
                "value": stock_value,
                "risk_tag": stock_risk_tag,
            })

        if crypto_value > 0:
            if crypto_ratio >= 0.5:
                crypto_risk_tag = "HIGH"
            elif crypto_ratio >= 0.3:
                crypto_risk_tag = "MEDIUM"
            else:
                crypto_risk_tag = "LOW"

            positions.append({
                "symbol": "CRYPTO",
                "value": crypto_value,
                "risk_tag": crypto_risk_tag,
            })

        if fcn_value > 0:
            positions.append({
                "symbol": "FCN",
                "value": fcn_value,
                "risk_tag": "LOW",
            })

        return positions
