from sqlalchemy.orm import Session


class PortfolioSummaryService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_asset_ratios(self, payload: dict) -> dict:
        total = payload.get("total_value", 0) or 0
        stock_value = payload.get("stock_value", 0) or 0
        crypto_value = payload.get("crypto_value", 0) or 0

        stock_ratio = stock_value / total if total > 0 else 0
        crypto_ratio = crypto_value / total if total > 0 else 0
        risk_asset_ratio = (stock_value + crypto_value) / total if total > 0 else 0

        return {
            "stock_ratio": stock_ratio,
            "crypto_ratio": crypto_ratio,
            "risk_asset_ratio": risk_asset_ratio,
            "stock_ratio_pct": round(stock_ratio * 100, 2),
            "crypto_ratio_pct": round(crypto_ratio * 100, 2),
            "risk_asset_ratio_pct": round(risk_asset_ratio * 100, 2),
        }

    def determine_risk_level(
        self,
        stock_ratio: float,
        crypto_ratio: float,
        top_risk_asset_ratio: float,
    ) -> dict:
        if crypto_ratio >= 0.5:
            level = "HIGH"
            message = "Crypto 佔比過高"
        elif top_risk_asset_ratio > 0.7:
            level = "HIGH"
            message = "風險資產占比過高"
        elif crypto_ratio >= 0.3:
            level = "MEDIUM"
            message = "Crypto 佔比偏高"
        elif top_risk_asset_ratio > 0.4:
            level = "MEDIUM"
            message = "風險資產占比偏高"
        else:
            level = "LOW"
            message = "資產配置正常"

        return {
            "risk_level": level,
            "risk_message": message,
            "stock_ratio": stock_ratio,
            "crypto_ratio": crypto_ratio,
            "top_risk_asset_ratio": top_risk_asset_ratio,
        }

    def calculate_risk_score(
        self,
        risk_level: str,
        risk_asset_ratio: float | None = None,
        crypto_ratio: float | None = None,
    ) -> int:
        if risk_asset_ratio is not None and crypto_ratio is not None:
            return max(
                int(risk_asset_ratio * 100),
                int(crypto_ratio * 120),
            )

        normalized_level = str(risk_level or "").upper()
        if normalized_level == "HIGH":
            return 80
        if normalized_level == "MEDIUM":
            return 50
        return 20
