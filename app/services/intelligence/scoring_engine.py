from __future__ import annotations

from typing import Any

from app.services.intelligence.schemas import IntelligenceScore
from app.services.news.schemas import NewsArticle


AI_CHIP_SYMBOLS = {"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB", "AMD"}
CRYPTO_SYMBOLS = {"BTC", "BTCUSDT", "BTC-USD", "ETH", "ETHUSDT", "ETH-USD"}
MACRO_KEYWORDS = {"cpi", "fomc", "rates", "rate", "inflation", "usd", "vix", "recession", "fed"}


class IntelligenceScoringEngine:
    def score(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
        alerts: list[Any],
    ) -> IntelligenceScore:
        try:
            impact = self._impact_score(articles)
            relevance = self._portfolio_relevance_score(articles)
            fcn = self._fcn_risk_score(portfolio_payload, articles, fcn_analysis)
            ai = self._ai_momentum_score(portfolio_payload, articles)
            crypto = self._crypto_vol_score(portfolio_payload, articles)
            macro = self._macro_risk_score(articles, alerts)
            total = self._clamp(
                impact * 0.2
                + relevance * 0.2
                + fcn * 0.2
                + ai * 0.15
                + crypto * 0.15
                + macro * 0.1
            )
            return IntelligenceScore(
                impact_score=impact,
                portfolio_relevance_score=relevance,
                fcn_risk_score=fcn,
                ai_momentum_score=ai,
                crypto_vol_score=crypto,
                macro_risk_score=macro,
                total_score=total,
            )
        except Exception:
            return IntelligenceScore()

    def _impact_score(self, articles: list[NewsArticle]) -> float:
        if not articles:
            return 0
        values = []
        for article in articles:
            priority = self._float(article.priority_score)
            attention = str(article.attention_level or "").upper()
            impact = str(article.impact or "").lower()
            score = min(priority * 4, 70)
            if attention == "CRITICAL":
                score += 25
            elif attention == "HIGH":
                score += 15
            elif attention == "MEDIUM":
                score += 8
            if impact == "negative":
                score += 10
            elif impact == "positive":
                score += 6
            values.append(self._clamp(score))
        return self._clamp(sum(values[:8]) / max(1, min(len(values), 8)))

    def _portfolio_relevance_score(self, articles: list[NewsArticle]) -> float:
        if not articles:
            return 0
        total = 0.0
        for article in articles:
            score = self._float(article.relevance_score) * 10
            if article.is_fcn_related:
                score += 15
            if str(article.relevance_level or "").upper() == "HIGH":
                score += 20
            total += self._clamp(score)
        return self._clamp(total / max(1, len(articles)))

    def _fcn_risk_score(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
    ) -> float:
        score = 0.0
        fcn_value = self._float(portfolio_payload.get("fcn_value"))
        total_value = self._float(portfolio_payload.get("total_value"))
        if total_value > 0:
            score += min((fcn_value / total_value) * 100, 40)
        for fcn in fcn_analysis:
            risk = str(fcn.get("risk_level") or "").lower()
            ki = self._pct(fcn.get("distance_to_KI") or fcn.get("distance_to_ki") or fcn.get("distance_to_ki_pct"))
            if risk == "high":
                score += 30
            elif risk == "medium":
                score += 15
            if ki is not None:
                if ki < 5:
                    score += 30
                elif ki < 15:
                    score += 15
        if any(article.is_fcn_related for article in articles):
            score += 15
        return self._clamp(score)

    def _ai_momentum_score(self, portfolio_payload: dict[str, Any], articles: list[NewsArticle]) -> float:
        score = 0.0
        stock_positions = portfolio_payload.get("stock_positions") or []
        total_value = self._float(portfolio_payload.get("total_value"))
        ai_value = 0.0
        for position in stock_positions:
            symbol = str(position.get("symbol") or "").upper()
            if symbol in AI_CHIP_SYMBOLS:
                ai_value += self._float(position.get("current_value"))
        if total_value > 0:
            score += min((ai_value / total_value) * 100, 45)
        for article in articles:
            symbol = str(article.symbol or "").upper()
            title = str(article.title or "").lower()
            if symbol in AI_CHIP_SYMBOLS or "ai" in title or "chip" in title or "semiconductor" in title:
                score += 12
                if str(article.impact or "").lower() == "positive":
                    score += 8
        return self._clamp(score)

    def _crypto_vol_score(self, portfolio_payload: dict[str, Any], articles: list[NewsArticle]) -> float:
        score = 0.0
        crypto_positions = portfolio_payload.get("crypto_positions") or []
        total_value = self._float(portfolio_payload.get("total_value"))
        crypto_value = sum(self._float(position.get("current_value")) for position in crypto_positions)
        if total_value > 0:
            score += min((crypto_value / total_value) * 120, 45)
        if any(self._float(position.get("leverage")) > 1 for position in crypto_positions):
            score += 20
        for article in articles:
            symbol = str(article.symbol or "").upper()
            title = str(article.title or "").lower()
            if symbol in CRYPTO_SYMBOLS or "crypto" in title or "bitcoin" in title or "ethereum" in title:
                score += 10
                if str(article.impact or "").lower() == "negative" or "volatility" in title:
                    score += 10
        return self._clamp(score)

    def _macro_risk_score(self, articles: list[NewsArticle], alerts: list[Any]) -> float:
        score = min(len(alerts) * 8, 30)
        for article in articles:
            title = str(article.title or "").lower()
            if any(keyword in title for keyword in MACRO_KEYWORDS):
                score += 15
                if str(article.impact or "").lower() == "negative":
                    score += 8
        return self._clamp(score)

    def _pct(self, value: Any) -> float | None:
        number = self._float(value, None)
        if number is None:
            return None
        return abs(number) * 100 if abs(number) <= 1 else number

    def _float(self, value: Any, fallback: float | None = 0.0) -> float | None:
        try:
            if value is None or value == "":
                return fallback
            number = float(value)
            return number if number == number else fallback
        except (TypeError, ValueError):
            return fallback

    def _clamp(self, value: float) -> float:
        return round(max(0.0, min(100.0, float(value or 0))), 2)
