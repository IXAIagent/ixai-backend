from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

try:
    from cachetools import TTLCache
except ImportError:  # pragma: no cover - used only before dependencies are installed.
    from app.services.market_data.service import TTLCache

import yfinance as yf

from app.core.config import settings
from app.services.news.schemas import NewsArticle

logger = logging.getLogger(__name__)


class YFinanceNewsProvider:
    source = "yfinance"
    _cache = TTLCache(maxsize=200, ttl=settings.NEWS_CACHE_TTL)

    def get_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return []

        max_limit = max(1, int(settings.NEWS_MAX_ARTICLES_PER_SYMBOL or 5))
        safe_limit = min(max(1, int(limit or max_limit)), max_limit)
        cache_key = (normalized_symbol, safe_limit)

        if cache_key in self._cache:
            return list(self._cache[cache_key])

        try:
            raw_news = yf.Ticker(normalized_symbol).news or []
            articles = [
                self._to_article(normalized_symbol, item)
                for item in raw_news[:safe_limit]
            ]
            articles = [article for article in articles if article is not None]
            self._cache[cache_key] = articles
            return articles
        except Exception:
            logger.exception(
                "news provider failure",
                extra={
                    "provider": "yfinance",
                    "operation": "news_lookup",
                    "symbol": normalized_symbol,
                },
            )
            return []

    def _to_article(self, symbol: str, item: Any) -> NewsArticle | None:
        if not isinstance(item, dict):
            return None

        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        title = self._first_text(item, content, ("title", "headline"))
        if not title:
            return None

        publisher = self._first_text(item, content, ("publisher", "provider", "source"))
        link = self._extract_link(item, content)
        published_at = self._extract_published_at(item, content)
        related_tickers = self._extract_related_tickers(item, content)

        return NewsArticle(
            symbol=symbol,
            title=title,
            publisher=publisher,
            link=link,
            published_at=published_at,
            related_tickers=related_tickers,
            source=self.source,
        )

    def _first_text(self, item: dict[str, Any], content: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for source in (item, content):
            for key in keys:
                value = source.get(key)
                if isinstance(value, dict):
                    value = value.get("displayName") or value.get("name")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_link(self, item: dict[str, Any], content: dict[str, Any]) -> str | None:
        for source in (item, content):
            for key in ("link", "url", "canonicalUrl", "clickThroughUrl"):
                value = source.get(key)
                if isinstance(value, dict):
                    value = value.get("url")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_published_at(self, item: dict[str, Any], content: dict[str, Any]) -> str | None:
        for source in (item, content):
            for key in ("providerPublishTime", "pubDate", "displayTime", "published_at"):
                value = source.get(key)
                if isinstance(value, (int, float)):
                    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_related_tickers(self, item: dict[str, Any], content: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for source in (item, content):
            raw = source.get("relatedTickers") or source.get("related_tickers") or source.get("symbols")
            if isinstance(raw, list):
                values.extend(str(value).strip().upper() for value in raw if str(value).strip())
        return list(dict.fromkeys(values))
