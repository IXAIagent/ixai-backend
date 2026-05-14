from __future__ import annotations

from typing import Protocol

from app.services.news.schemas import NewsArticle


class SummaryProvider(Protocol):
    def summarize_article(
        self,
        article: NewsArticle,
        context: dict | None = None,
    ) -> str:
        ...
