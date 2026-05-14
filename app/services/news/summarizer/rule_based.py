from __future__ import annotations

from app.services.news.schemas import NewsArticle


class RuleBasedSummaryProvider:
    def summarize_article(
        self,
        article: NewsArticle,
        context: dict | None = None,
    ) -> str:
        try:
            summary = (
                article.narrative
                or article.portfolio_impact_summary
                or article.impact_reason
                or "此新聞目前偏資訊性，建議搭配價格變化與後續消息持續觀察。"
            )
            return self._trim(summary)
        except Exception:
            return ""

    def _trim(self, text: str, max_length: int = 120) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip("，。； ") + "。"
