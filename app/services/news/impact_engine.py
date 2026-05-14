from __future__ import annotations

from typing import Any

from app.services.news.schemas import NewsArticle


class PortfolioImpactEngine:
    RISK_INCREASE_KEYWORDS = {
        "lawsuit",
        "downgrade",
        "warning",
        "weak",
        "miss",
    }
    RISK_DECREASE_KEYWORDS = {
        "upgrade",
        "beat",
        "strong",
        "raises",
    }

    def analyze(self, article: NewsArticle, portfolio_context: dict[str, Any]) -> dict[str, str]:
        try:
            exposure = self._portfolio_exposure(article, portfolio_context)
            risk_direction = self._risk_direction(article)
            attention_level = self._attention_level(article, exposure, risk_direction, portfolio_context)
            summary = self._summary(article, exposure, risk_direction, portfolio_context)
            return {
                "portfolio_exposure": exposure,
                "risk_direction": risk_direction,
                "attention_level": attention_level,
                "portfolio_impact_summary": self._trim(summary),
            }
        except Exception:
            return {
                "portfolio_exposure": "LOW",
                "risk_direction": "NEUTRAL",
                "attention_level": "LOW",
                "portfolio_impact_summary": "",
            }

    def _portfolio_exposure(self, article: NewsArticle, context: dict[str, Any]) -> str:
        symbol = self._symbol(article)
        exposure_ratio = float(context.get("exposure_ratio_by_symbol", {}).get(symbol, 0) or 0)
        leverage = float(context.get("crypto_leverage_by_symbol", {}).get(symbol, 0) or 0)
        is_crypto = symbol in context.get("crypto_symbols", set())
        is_fcn_underlying = symbol in context.get("fcn_underlying_symbols", set())
        is_worst_of = symbol in context.get("worst_of_symbols", set())

        if exposure_ratio > 0.15 or is_worst_of or (is_crypto and leverage > 5):
            return "HIGH"
        if exposure_ratio > 0.05 or is_fcn_underlying or is_crypto:
            return "MEDIUM"
        return "LOW"

    def _risk_direction(self, article: NewsArticle) -> str:
        title = str(article.title or "").lower()
        impact = str(article.impact or "neutral").lower()
        if impact == "negative" or any(keyword in title for keyword in self.RISK_INCREASE_KEYWORDS):
            return "INCREASE"
        if impact == "positive" or any(keyword in title for keyword in self.RISK_DECREASE_KEYWORDS):
            return "DECREASE"
        return "NEUTRAL"

    def _attention_level(
        self,
        article: NewsArticle,
        exposure: str,
        risk_direction: str,
        context: dict[str, Any],
    ) -> str:
        symbol = self._symbol(article)
        relevance = str(article.relevance_level or "LOW").upper()
        is_worst_of = symbol in context.get("worst_of_symbols", set())

        if exposure == "HIGH" and risk_direction == "INCREASE" and is_worst_of:
            return "CRITICAL"
        if exposure == "HIGH" or relevance == "HIGH":
            return "HIGH"
        if exposure == "MEDIUM" or relevance == "MEDIUM":
            return "MEDIUM"
        return "LOW"

    def _summary(
        self,
        article: NewsArticle,
        exposure: str,
        risk_direction: str,
        context: dict[str, Any],
    ) -> str:
        symbol = self._symbol(article)
        is_worst_of = symbol in context.get("worst_of_symbols", set())

        if is_worst_of:
            return "此新聞涉及 FCN worst-of 標的，若市場波動擴大，可能提高 KI 風險。"
        if risk_direction == "INCREASE":
            return "此消息可能提高短期波動與市場風險情緒，建議留意後續財報與指引。"
        if risk_direction == "DECREASE":
            return "此消息有助於改善市場情緒，短期可能支撐持倉表現。"
        if exposure == "HIGH":
            return "此新聞涉及高曝險持倉，建議持續觀察價格反應與後續消息。"
        return "此新聞目前偏資訊性，對投資組合影響有限，建議納入後續觀察。"

    def _symbol(self, article: NewsArticle) -> str:
        return str(article.symbol or "").strip().upper()

    def _trim(self, text: str, max_length: int = 120) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip("，。； ") + "。"
