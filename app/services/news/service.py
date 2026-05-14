from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import CryptoPosition, FCNPosition, Portfolio, StockPosition
from app.services.fcn_monitor_service import FCNMonitorService
from app.services.market_data.base import utc_now_iso
from app.services.news.providers.yfinance_provider import YFinanceNewsProvider
from app.services.news.schemas import NewsArticle, PortfolioNewsResponse
from app.services.normalization import get_crypto_yahoo_fallback_symbol, normalize_crypto_symbol

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(
        self,
        db: Session,
        provider: YFinanceNewsProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or YFinanceNewsProvider()

    def get_portfolio_news(self, portfolio: Portfolio) -> PortfolioNewsResponse:
        symbols = self._collect_portfolio_symbols(portfolio)
        articles: list[NewsArticle] = []
        seen_links: set[str] = set()
        max_total = max(1, int(settings.NEWS_MAX_TOTAL_ARTICLES or 20))
        per_symbol = max(1, int(settings.NEWS_MAX_ARTICLES_PER_SYMBOL or 5))

        for symbol in symbols:
            if len(articles) >= max_total:
                break
            try:
                for article in self.provider.get_news(symbol, limit=per_symbol):
                    key = article.link or f"{article.symbol}:{article.title}"
                    if key in seen_links:
                        continue
                    seen_links.add(key)
                    articles.append(article)
                    if len(articles) >= max_total:
                        break
            except Exception as exc:
                logger.warning("Portfolio news failed for %s: %s", symbol, exc)

        return PortfolioNewsResponse(
            portfolio_id=str(portfolio.id),
            portfolio_name=str(portfolio.name),
            articles=articles,
            summary=f"Found {len(articles)} recent articles related to your portfolio.",
            fetched_at=utc_now_iso(),
            is_stale=False,
        )

    def _collect_portfolio_symbols(self, portfolio: Portfolio) -> list[str]:
        symbols: list[str] = []
        symbols.extend(self._stock_symbols(portfolio.id))
        symbols.extend(self._crypto_symbols(portfolio.id))
        symbols.extend(self._fcn_symbols(portfolio.id))
        return list(dict.fromkeys(symbol for symbol in symbols if symbol))

    def _stock_symbols(self, portfolio_id: str) -> list[str]:
        stocks = self.db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio_id).all()
        return [str(stock.symbol or "").strip().upper() for stock in stocks if str(stock.symbol or "").strip()]

    def _crypto_symbols(self, portfolio_id: str) -> list[str]:
        cryptos = self.db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio_id).all()
        symbols: list[str] = []
        for crypto in cryptos:
            raw_symbol = str(crypto.symbol or "").strip().upper()
            if not raw_symbol:
                continue
            normalized = normalize_crypto_symbol(raw_symbol)
            yahoo_symbol = get_crypto_yahoo_fallback_symbol(normalized)
            if yahoo_symbol:
                symbols.append(yahoo_symbol)
        return symbols

    def _fcn_symbols(self, portfolio_id: str) -> list[str]:
        fcns = self.db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio_id).all()
        monitor = FCNMonitorService()
        symbols: list[str] = []
        for fcn in fcns:
            try:
                underlyings = monitor.parse_underlyings(fcn)
                symbols.extend(str(item.get("symbol") or "").strip().upper() for item in underlyings)
            except Exception:
                symbols.extend(self._parse_fcn_underlyings_text(getattr(fcn, "underlyings", None)))
        return symbols

    def _parse_fcn_underlyings_text(self, raw_value) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            records = raw_value
        else:
            text = str(raw_value).strip()
            if not text:
                return []
            try:
                records = json.loads(text)
            except json.JSONDecodeError:
                return [symbol.upper() for symbol in re.split(r"[,;/\s]+", text) if symbol.strip()]

        symbols: list[str] = []
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    value = record.get("symbol")
                else:
                    value = record
                if str(value or "").strip():
                    symbols.append(str(value).strip().upper())
        return symbols
