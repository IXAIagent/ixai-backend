from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.news.schemas import NewsArticle


class RelevanceEngine:
    EVENT_KEYWORDS = {
        "earnings",
        "revenue",
        "guidance",
        "forecast",
        "profit",
        "loss",
        "downgrade",
        "upgrade",
        "lawsuit",
        "investigation",
        "ai",
        "chip",
        "semiconductor",
    }
    POSITIVE_KEYWORDS = {
        "beat",
        "growth",
        "upgrade",
        "raises",
        "strong",
        "profit",
        "expansion",
        "demand",
        "record",
        "bullish",
    }
    NEGATIVE_KEYWORDS = {
        "miss",
        "loss",
        "downgrade",
        "cuts",
        "weak",
        "lawsuit",
        "investigation",
        "delay",
        "decline",
        "bearish",
        "warning",
    }

    def analyze(self, article: NewsArticle, context: dict[str, Any]) -> NewsArticle:
        try:
            symbol = str(article.symbol or "").upper()
            title = str(article.title or "")
            normalized_title = title.lower()
            score = 0.0

            if symbol in context.get("stock_symbols", set()) or symbol in context.get("crypto_symbols", set()):
                score += 3

            if symbol in context.get("fcn_underlying_symbols", set()):
                score += 2

            if symbol in context.get("worst_of_symbols", set()):
                score += 2

            if any(keyword in normalized_title for keyword in self.EVENT_KEYWORDS):
                score += 2

            if self._is_recent(article.published_at):
                score += 1

            impact = self._impact(normalized_title)
            is_fcn_related = symbol in context.get("fcn_underlying_symbols", set())
            related_fcn_codes = sorted(context.get("fcn_codes_by_symbol", {}).get(symbol, set()))

            article.relevance_score = score
            article.relevance_level = self._level(score)
            article.impact = impact
            article.is_fcn_related = is_fcn_related
            article.related_fcn_codes = related_fcn_codes
            article.impact_reason = self._impact_reason(impact, is_fcn_related)
            return article
        except Exception:
            return article

    def _level(self, score: float) -> str:
        if score >= 6:
            return "HIGH"
        if score >= 3:
            return "MEDIUM"
        return "LOW"

    def _impact(self, normalized_title: str) -> str:
        positive = sum(1 for keyword in self.POSITIVE_KEYWORDS if keyword in normalized_title)
        negative = sum(1 for keyword in self.NEGATIVE_KEYWORDS if keyword in normalized_title)
        if positive > negative:
            return "positive"
        if negative > positive:
            return "negative"
        return "neutral"

    def _impact_reason(self, impact: str, is_fcn_related: bool) -> str:
        if impact == "positive":
            reason = "此新聞可能對相關持倉形成正面情緒或基本面支持。"
        elif impact == "negative":
            reason = "此新聞可能對相關持倉形成負面情緒或風險壓力。"
        else:
            reason = "此新聞目前偏資訊性，需搭配價格與後續消息觀察。"

        if is_fcn_related:
            reason += "此標的亦屬於 FCN underlying，需留意 KI/KO 風險變化。"
        return reason

    def _is_recent(self, published_at: str | None) -> bool:
        if not published_at:
            return False
        try:
            normalized = published_at.replace("Z", "+00:00")
            published = datetime.fromisoformat(normalized)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - published).total_seconds() <= 86400
        except Exception:
            return False
