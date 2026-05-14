from __future__ import annotations

from datetime import datetime, timezone

from app.services.market_data.base import utc_now_iso
from app.services.news.schemas import NewsArticle, PortfolioPriorityResponse


class PortfolioPriorityEngine:
    def enrich_articles(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        try:
            for article in articles:
                score = self._score(article)
                article.priority_score = score
                article.priority_level = self._priority_level(score)
                article.alert_summary = self._alert_summary(article)
            return articles
        except Exception:
            return articles

    def build_priority_response(
        self,
        articles: list[NewsArticle],
    ) -> PortfolioPriorityResponse:
        try:
            enriched = self.enrich_articles(articles)
            top_alerts = [
                article
                for article in sorted(
                    enriched,
                    key=lambda item: (
                        int(getattr(item, "priority_score", 0) or 0),
                        str(getattr(item, "published_at", "") or ""),
                    ),
                    reverse=True,
                )
                if str(getattr(article, "priority_level", "LOW") or "LOW").upper()
                in {"CRITICAL", "HIGH", "MEDIUM"}
            ][:5]
            return PortfolioPriorityResponse(
                top_alerts=top_alerts,
                critical_count=sum(
                    1
                    for article in top_alerts
                    if str(article.priority_level or "").upper() == "CRITICAL"
                ),
                high_count=sum(
                    1
                    for article in top_alerts
                    if str(article.priority_level or "").upper() == "HIGH"
                ),
                generated_at=utc_now_iso(),
                is_stale=False,
            )
        except Exception:
            return PortfolioPriorityResponse(
                top_alerts=[],
                critical_count=0,
                high_count=0,
                generated_at=utc_now_iso(),
                is_stale=False,
            )

    def _score(self, article: NewsArticle) -> int:
        score = int(float(getattr(article, "relevance_score", 0) or 0) * 2)

        if getattr(article, "is_fcn_related", False):
            score += 2
        if str(getattr(article, "attention_level", "") or "").upper() == "CRITICAL":
            score += 5
        if str(getattr(article, "risk_direction", "") or "").upper() == "INCREASE":
            score += 3
        if str(getattr(article, "impact", "") or "").lower() == "negative":
            score += 2

        age_hours = self._age_hours(getattr(article, "published_at", None))
        if age_hours is not None:
            if age_hours <= 6:
                score += 2
            elif age_hours <= 24:
                score += 1

        relevance = str(getattr(article, "relevance_level", "") or "").upper()
        if relevance == "HIGH":
            score += 2
        elif relevance == "MEDIUM":
            score += 1

        return score

    def _priority_level(self, score: int) -> str:
        if score >= 18:
            return "CRITICAL"
        if score >= 12:
            return "HIGH"
        if score >= 7:
            return "MEDIUM"
        return "LOW"

    def _alert_summary(self, article: NewsArticle) -> str:
        level = str(getattr(article, "priority_level", "LOW") or "LOW").upper()
        if level == "CRITICAL":
            summary = "此事件對目前投資組合具有較高優先級，可能需要立即留意後續價格與風險變化。"
        elif level == "HIGH":
            summary = "此事件與持倉或 FCN 標的高度相關，建議優先追蹤後續消息。"
        elif level == "MEDIUM":
            summary = "此事件可能影響相關標的短期情緒，建議持續觀察。"
        else:
            summary = "此事件目前優先級較低，可納入例行觀察。"

        if getattr(article, "is_fcn_related", False):
            summary += "其中包含 FCN underlying，需留意 KI/KO 風險。"

        return self._trim(summary)

    def _age_hours(self, published_at: str | None) -> float | None:
        if not published_at:
            return None
        try:
            normalized = published_at.replace("Z", "+00:00")
            published = datetime.fromisoformat(normalized)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - published).total_seconds() / 3600
        except Exception:
            return None

    def _trim(self, text: str, max_length: int = 120) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip("，。； ") + "。"
