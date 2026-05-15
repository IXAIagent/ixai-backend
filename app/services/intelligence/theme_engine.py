from __future__ import annotations

from collections import Counter

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import IntelligenceCorrelation, LongMemorySummary, ThemeEvolution
from app.services.news.schemas import NewsArticle


class ThemeEvolutionEngine:
    def evolve(
        self,
        enrichment: dict[str, dict],
        articles: list[NewsArticle],
        correlations: list[IntelligenceCorrelation],
        memory: LongMemorySummary,
    ) -> ThemeEvolution:
        try:
            counts: Counter[str] = Counter()
            for item in enrichment.values():
                for theme in item.get("themes", []):
                    counts[str(theme)] += 2
                for tag in item.get("fcn_tags", []):
                    counts[f"FCN_{tag}"] += 2
                for tag in item.get("macro_tags", []):
                    counts[str(tag)] += 1
            for article in articles:
                title = str(article.title or "").lower()
                if "rotation" in title:
                    counts["AI_ROTATION"] += 2
                if article.is_fcn_related:
                    counts["FCN_STRESS_BUILDING"] += 2
            for item in correlations:
                if item.correlation_type == "CRYPTO_VOLATILITY":
                    counts["CRYPTO_DELEVERAGING"] += 1
                if item.correlation_type == "MACRO_RATES":
                    counts["RATE_PRESSURE"] += 2
            for theme in memory.recurring_risk_themes:
                counts[theme] += 1

            dominant = [theme for theme, _ in counts.most_common(4)]
            emerging = [
                theme
                for theme in dominant
                if theme not in set(memory.recurring_risk_themes)
            ][:3]
            weakening = [
                theme
                for theme in memory.recurring_risk_themes
                if theme not in dominant
            ][:3]
            confidence = min(100.0, 35.0 + sum(counts.values()) * 5)
            summary = self._summary(dominant, emerging, weakening)
            return ThemeEvolution(
                dominant_themes=dominant,
                emerging_themes=emerging,
                weakening_themes=weakening,
                theme_confidence=round(confidence, 2),
                narrative_summary=compliance_filter.sanitize_text(summary),
            )
        except Exception:
            return ThemeEvolution(narrative_summary="目前主題演變資料不足，維持例行觀察。")

    def _summary(self, dominant: list[str], emerging: list[str], weakening: list[str]) -> str:
        if dominant:
            text = f"目前主導主題為 {'、'.join(dominant[:3])}。"
        else:
            text = "目前尚未偵測到明確主導主題。"
        if emerging:
            text += f" 新興主題包含 {'、'.join(emerging[:2])}。"
        if weakening:
            text += f" 轉弱主題包含 {'、'.join(weakening[:2])}。"
        return text
