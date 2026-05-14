from __future__ import annotations

import logging

from app.core.config import settings
from app.services.news.schemas import NewsArticle
from app.services.news.summarizer.rule_based import RuleBasedSummaryProvider

logger = logging.getLogger(__name__)


class ClaudeSummaryProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        fallback: RuleBasedSummaryProvider | None = None,
    ) -> None:
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.CLAUDE_MODEL
        self.fallback = fallback or RuleBasedSummaryProvider()

    def summarize_article(
        self,
        article: NewsArticle,
        context: dict | None = None,
    ) -> str:
        if not self.api_key:
            return self.fallback.summarize_article(article, context)

        try:
            from anthropic import Anthropic
        except Exception as exc:
            logger.warning("Anthropic SDK unavailable, using rule-based summary: %s", exc)
            return self.fallback.summarize_article(article, context)

        try:
            client = Anthropic(api_key=self.api_key, timeout=10.0)
            message = client.messages.create(
                model=self.model,
                max_tokens=220,
                temperature=0.2,
                system=(
                    "你是 IXAI 的投資風險助理。請用繁體中文輸出 80-150 字，"
                    "只說明新聞重點、對持倉可能影響、FCN KI/KO 風險與後續觀察重點。"
                    "不得提供買進、賣出、加碼、減碼、部位數量或價格目標建議。"
                    "不要使用 markdown。"
                ),
                messages=[
                    {
                        "role": "user",
                        "content": self._prompt(article, context or {}),
                    }
                ],
            )
            text = self._message_text(message)
            return self._sanitize(text) or self.fallback.summarize_article(article, context)
        except Exception as exc:
            logger.warning("Claude summary failed, using rule-based summary: %s", exc)
            return self.fallback.summarize_article(article, context)

    def _prompt(self, article: NewsArticle, context: dict) -> str:
        return (
            f"新聞標的：{article.symbol}\n"
            f"新聞標題：{article.title}\n"
            f"相關程度：{article.relevance_level} / {article.relevance_score}\n"
            f"影響方向：{article.impact}\n"
            f"投資組合曝險：{article.portfolio_exposure}\n"
            f"風險方向：{article.risk_direction}\n"
            f"注意等級：{article.attention_level}\n"
            f"是否 FCN underlying：{article.is_fcn_related}\n"
            f"相關 FCN：{', '.join(article.related_fcn_codes or [])}\n"
            f"既有風險提示：{article.portfolio_impact_summary or article.narrative or article.impact_reason}\n"
            "請輸出一段中文投資助理提醒，聚焦風險、影響與觀察，不提供交易指令。"
        )

    def _message_text(self, message) -> str:
        parts: list[str] = []
        for block in getattr(message, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return " ".join(parts).strip()

    def _sanitize(self, text: str, max_length: int = 150) -> str:
        normalized = str(text or "").strip()
        forbidden_replacements = {
            "建議買進": "建議觀察",
            "建議賣出": "建議留意",
            "買進": "觀察",
            "賣出": "留意",
            "加碼": "提高關注",
            "減碼": "控管風險",
        }
        for phrase, replacement in forbidden_replacements.items():
            normalized = normalized.replace(phrase, replacement)
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip("，。； ") + "。"
