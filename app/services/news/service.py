from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import CryptoPosition, FCNPosition, Portfolio, StockPosition
from app.services.fcn_monitor_service import FCNMonitorService
from app.services.market_data.base import utc_now_iso
from app.services.news.impact_engine import PortfolioImpactEngine
from app.services.news.priority_engine import PortfolioPriorityEngine
from app.services.news.providers.yfinance_provider import YFinanceNewsProvider
from app.services.news.relevance_engine import RelevanceEngine
from app.services.news.schemas import NewsArticle, PortfolioNewsResponse, PortfolioPriorityResponse
from app.services.normalization import get_crypto_yahoo_fallback_symbol, normalize_crypto_symbol

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(
        self,
        db: Session,
        provider: YFinanceNewsProvider | None = None,
        relevance_engine: RelevanceEngine | None = None,
        impact_engine: PortfolioImpactEngine | None = None,
        priority_engine: PortfolioPriorityEngine | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or YFinanceNewsProvider()
        self.relevance_engine = relevance_engine or RelevanceEngine()
        self.impact_engine = impact_engine or PortfolioImpactEngine()
        self.priority_engine = priority_engine or PortfolioPriorityEngine()

    def get_portfolio_news(self, portfolio: Portfolio) -> PortfolioNewsResponse:
        context = self._build_portfolio_context(portfolio)
        symbols = list(context["symbols"])
        articles: list[NewsArticle] = []
        seen_links: set[str] = set()
        per_symbol_count: dict[str, int] = {}
        max_total = max(1, int(settings.NEWS_MAX_TOTAL_ARTICLES or 20))
        per_symbol = max(1, int(settings.NEWS_MAX_ARTICLES_PER_SYMBOL or 5))

        for symbol in symbols:
            try:
                for article in self.provider.get_news(symbol, limit=per_symbol):
                    key = article.link or f"{article.symbol}:{article.title}"
                    if key in seen_links:
                        continue
                    seen_links.add(key)
                    article.symbol = str(article.symbol or symbol).strip().upper()
                    article = self.relevance_engine.analyze(article, context)
                    impact = self.impact_engine.analyze(article, context)
                    article.portfolio_exposure = impact["portfolio_exposure"]
                    article.risk_direction = impact["risk_direction"]
                    article.attention_level = impact["attention_level"]
                    article.portfolio_impact_summary = impact["portfolio_impact_summary"]
                    article.narrative = self._generate_narrative(article)
                    articles.append(article)
            except Exception as exc:
                logger.warning("Portfolio news failed for %s: %s", symbol, exc)

        articles = self._rank_and_limit_articles(articles, max_total, per_symbol_count)
        articles = self.priority_engine.enrich_articles(articles)

        return PortfolioNewsResponse(
            portfolio_id=str(portfolio.id),
            portfolio_name=str(portfolio.name),
            articles=articles,
            summary=f"Found {len(articles)} recent articles related to your portfolio.",
            fetched_at=utc_now_iso(),
            is_stale=False,
        )

    def get_portfolio_priority(self, portfolio: Portfolio) -> PortfolioPriorityResponse:
        try:
            articles = self.get_portfolio_news(portfolio).articles
            return self.priority_engine.build_priority_response(articles)
        except Exception:
            return self.priority_engine.build_priority_response([])

    def _build_portfolio_context(self, portfolio: Portfolio) -> dict:
        stock_context = self._stock_context(portfolio.id)
        crypto_context = self._crypto_context(portfolio.id)
        fcn_context = self._fcn_context(portfolio.id)
        total_value = (
            stock_context["total_value"]
            + crypto_context["total_value"]
            + fcn_context["total_value"]
        )
        symbols = list(dict.fromkeys([
            *stock_context["symbols"],
            *crypto_context["symbols"],
            *fcn_context["fcn_underlying_symbols"],
        ]))
        exposure_ratio_by_symbol = self._exposure_ratios(
            total_value,
            stock_context["value_by_symbol"],
            crypto_context["value_by_symbol"],
            fcn_context["value_by_symbol"],
        )
        return {
            "symbols": symbols,
            "stock_symbols": stock_context["symbols"],
            "crypto_symbols": crypto_context["symbols"],
            "fcn_underlying_symbols": fcn_context["fcn_underlying_symbols"],
            "fcn_codes_by_symbol": fcn_context["fcn_codes_by_symbol"],
            "worst_of_symbols": fcn_context["worst_of_symbols"],
            "crypto_leverage_by_symbol": crypto_context["leverage_by_symbol"],
            "exposure_ratio_by_symbol": exposure_ratio_by_symbol,
        }

    def _stock_context(self, portfolio_id: str) -> dict:
        stocks = self.db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio_id).all()
        symbols: set[str] = set()
        value_by_symbol: dict[str, float] = {}
        total_value = 0.0
        for stock in stocks:
            symbol = str(stock.symbol or "").strip().upper()
            if not symbol:
                continue
            value = self._position_value(stock)
            symbols.add(symbol)
            value_by_symbol[symbol] = value_by_symbol.get(symbol, 0) + value
            total_value += value
        return {"symbols": symbols, "value_by_symbol": value_by_symbol, "total_value": total_value}

    def _stock_symbols(self, portfolio_id: str) -> list[str]:
        return list(self._stock_context(portfolio_id)["symbols"])

    def _crypto_context(self, portfolio_id: str) -> dict:
        cryptos = self.db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio_id).all()
        symbols: set[str] = set()
        value_by_symbol: dict[str, float] = {}
        leverage_by_symbol: dict[str, float] = {}
        total_value = 0.0
        for crypto in cryptos:
            raw_symbol = str(crypto.symbol or "").strip().upper()
            if not raw_symbol:
                continue
            normalized = normalize_crypto_symbol(raw_symbol)
            yahoo_symbol = get_crypto_yahoo_fallback_symbol(normalized)
            if yahoo_symbol:
                value = self._position_value(crypto)
                symbols.add(yahoo_symbol)
                value_by_symbol[yahoo_symbol] = value_by_symbol.get(yahoo_symbol, 0) + value
                leverage_by_symbol[yahoo_symbol] = max(
                    leverage_by_symbol.get(yahoo_symbol, 0),
                    self._safe_float(getattr(crypto, "leverage", 0)),
                )
                total_value += value
        return {
            "symbols": symbols,
            "value_by_symbol": value_by_symbol,
            "leverage_by_symbol": leverage_by_symbol,
            "total_value": total_value,
        }

    def _crypto_symbols(self, portfolio_id: str) -> list[str]:
        return list(self._crypto_context(portfolio_id)["symbols"])

    def _fcn_context(self, portfolio_id: str) -> dict:
        fcns = self.db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio_id).all()
        monitor = FCNMonitorService()
        symbols: set[str] = set()
        fcn_codes_by_symbol: dict[str, set[str]] = {}
        worst_of_symbols: set[str] = set()
        value_by_symbol: dict[str, float] = {}
        total_value = 0.0
        for fcn in fcns:
            fcn_code = str(getattr(fcn, "fcn_code", None) or getattr(fcn, "name", None) or "FCN").strip()
            notional = self._fcn_notional(fcn)
            try:
                underlyings = monitor.parse_underlyings(fcn)
                parsed_symbols = [
                    str(item.get("symbol") or "").strip().upper()
                    for item in underlyings
                    if str(item.get("symbol") or "").strip()
                ]
            except Exception:
                parsed_symbols = self._parse_fcn_underlyings_text(getattr(fcn, "underlyings", None))

            for symbol in parsed_symbols:
                symbols.add(symbol)
                fcn_codes_by_symbol.setdefault(symbol, set()).add(fcn_code)
                if parsed_symbols:
                    value_by_symbol[symbol] = value_by_symbol.get(symbol, 0) + (notional / len(parsed_symbols))

            worst_symbol = str(getattr(fcn, "worst_of_symbol", None) or "").strip().upper()
            if worst_symbol:
                worst_of_symbols.add(worst_symbol)
                symbols.add(worst_symbol)
                fcn_codes_by_symbol.setdefault(worst_symbol, set()).add(fcn_code)
                value_by_symbol[worst_symbol] = max(value_by_symbol.get(worst_symbol, 0), notional)
            total_value += notional

        return {
            "fcn_underlying_symbols": symbols,
            "fcn_codes_by_symbol": fcn_codes_by_symbol,
            "worst_of_symbols": worst_of_symbols,
            "value_by_symbol": value_by_symbol,
            "total_value": total_value,
        }

    def _exposure_ratios(self, total_value: float, *value_maps: dict[str, float]) -> dict[str, float]:
        if total_value <= 0:
            return {}
        ratios: dict[str, float] = {}
        for value_map in value_maps:
            for symbol, value in value_map.items():
                ratios[symbol] = ratios.get(symbol, 0) + (float(value or 0) / total_value)
        return ratios

    def _position_value(self, position) -> float:
        quantity = self._safe_float(getattr(position, "quantity", 0))
        price = (
            self._safe_float(getattr(position, "current_price", 0))
            or self._safe_float(getattr(position, "avg_price", 0))
        )
        return quantity * price

    def _fcn_notional(self, fcn: FCNPosition) -> float:
        notional_amount = getattr(fcn, "notional_amount", None)
        notional = getattr(fcn, "notional", None)
        return self._safe_float(notional_amount if notional_amount is not None else notional)

    def _safe_float(self, value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _rank_and_limit_articles(
        self,
        articles: list[NewsArticle],
        max_total: int,
        per_symbol_count: dict[str, int],
    ) -> list[NewsArticle]:
        ranked = sorted(
            articles,
            key=lambda article: (
                float(article.relevance_score or 0),
                str(article.published_at or ""),
            ),
            reverse=True,
        )
        selected: list[NewsArticle] = []
        for article in ranked:
            symbol = str(article.symbol or "").upper()
            if per_symbol_count.get(symbol, 0) >= 2:
                continue
            per_symbol_count[symbol] = per_symbol_count.get(symbol, 0) + 1
            selected.append(article)
            if len(selected) >= max_total:
                break
        return selected

    def _generate_narrative(self, article: NewsArticle) -> str:
        try:
            relevance = str(article.relevance_level or "LOW").upper()
            impact = str(article.impact or "neutral").lower()

            if relevance == "HIGH" and impact == "negative":
                parts = ["此新聞可能增加相關持倉短期波動與風險壓力，需留意價格變化。"]
            elif relevance == "HIGH" and impact == "positive":
                parts = ["此新聞可能對相關持倉形成正面情緒與基本面支撐。"]
            elif relevance == "MEDIUM":
                parts = ["此新聞可能影響市場對該標的的短期看法，建議持續觀察。"]
            else:
                parts = ["此新聞目前偏資訊性，對持倉影響有限。"]

            if article.is_fcn_related:
                parts.append("此標的同時屬於 FCN underlying，需特別留意 KI/KO 風險變化。")

            if relevance == "HIGH" and impact == "negative":
                parts.append("若後續出現連續負面消息，可能提高投資組合風險。")
            elif relevance == "HIGH" and impact == "positive":
                parts.append("若市場情緒延續，可能有助於改善持倉表現。")

            return self._trim_narrative("".join(parts))
        except Exception:
            return ""

    def _trim_narrative(self, text: str, max_length: int = 120) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip("，。； ") + "。"

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
