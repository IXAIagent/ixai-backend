from __future__ import annotations

from typing import Any

from app.services.intelligence.schemas import IntelligenceCorrelation
from app.services.news.schemas import NewsArticle


AI_CHIP_SYMBOLS = {"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB", "AMD"}
CRYPTO_SYMBOLS = {"BTC", "BTCUSDT", "BTC-USD", "ETH", "ETHUSDT", "ETH-USD"}


class IntelligenceCorrelationEngine:
    def correlate(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
    ) -> list[IntelligenceCorrelation]:
        try:
            correlations: list[IntelligenceCorrelation] = []
            correlations.extend(self._fcn_linkages(articles, fcn_analysis))
            correlations.extend(self._ai_chip_linkages(portfolio_payload, articles))
            correlations.extend(self._crypto_linkages(portfolio_payload, articles))
            correlations.extend(self._macro_linkages(articles))
            correlations.extend(self._concentration_linkages(portfolio_payload, articles))
            unique: dict[str, IntelligenceCorrelation] = {}
            for item in correlations:
                key = f"{item.source_symbol}:{item.correlation_type}:{','.join(item.related_symbols)}"
                unique.setdefault(key, item)
            return list(unique.values())[:8]
        except Exception:
            return []

    def _fcn_linkages(
        self,
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
    ) -> list[IntelligenceCorrelation]:
        rows: list[IntelligenceCorrelation] = []
        worst_symbols = {
            str(item.get("worst_symbol") or item.get("worst_of") or "").upper()
            for item in fcn_analysis
            if item.get("worst_symbol") or item.get("worst_of")
        }
        for article in articles:
            symbol = str(article.symbol or "").upper()
            if not (article.is_fcn_related or symbol in worst_symbols):
                continue
            related = list(article.related_fcn_codes or [])
            rows.append(
                IntelligenceCorrelation(
                    source_symbol=symbol or "FCN",
                    related_symbols=related,
                    correlation_type="FCN_UNDERLYING",
                    explanation=f"{symbol or '此標的'} 與 FCN underlying 相關，需觀察 KI/KO 距離與 worst-of 變化。",
                    risk_direction=str(article.risk_direction or "NEUTRAL").upper(),
                )
            )
        return rows

    def _ai_chip_linkages(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
    ) -> list[IntelligenceCorrelation]:
        held = {
            str(position.get("symbol") or "").upper()
            for position in portfolio_payload.get("stock_positions", [])
            if str(position.get("symbol") or "").upper() in AI_CHIP_SYMBOLS
        }
        rows: list[IntelligenceCorrelation] = []
        for article in articles:
            symbol = str(article.symbol or "").upper()
            title = str(article.title or "").lower()
            if symbol in AI_CHIP_SYMBOLS or "ai" in title or "chip" in title or "semiconductor" in title:
                rows.append(
                    IntelligenceCorrelation(
                        source_symbol=symbol or "AI",
                        related_symbols=sorted(held)[:5],
                        correlation_type="AI_CHIP",
                        explanation="此事件與 AI/半導體曝險相關，可能影響組合中的成長與科技持倉情緒。",
                        risk_direction=str(article.risk_direction or "NEUTRAL").upper(),
                    )
                )
        return rows

    def _crypto_linkages(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
    ) -> list[IntelligenceCorrelation]:
        crypto_symbols = [str(item.get("symbol") or "").upper() for item in portfolio_payload.get("crypto_positions", [])]
        rows: list[IntelligenceCorrelation] = []
        for article in articles:
            symbol = str(article.symbol or "").upper()
            title = str(article.title or "").lower()
            if symbol in CRYPTO_SYMBOLS or "crypto" in title or "bitcoin" in title or "ethereum" in title:
                rows.append(
                    IntelligenceCorrelation(
                        source_symbol=symbol or "CRYPTO",
                        related_symbols=crypto_symbols[:5],
                        correlation_type="CRYPTO_VOLATILITY",
                        explanation="此事件與 crypto 曝險或波動相關，可能放大短期淨值波動。",
                        risk_direction=str(article.risk_direction or "NEUTRAL").upper(),
                    )
                )
        return rows

    def _macro_linkages(self, articles: list[NewsArticle]) -> list[IntelligenceCorrelation]:
        rows: list[IntelligenceCorrelation] = []
        for article in articles:
            title = str(article.title or "").lower()
            if any(term in title for term in ("cpi", "fomc", "rates", "inflation", "usd", "vix", "recession")):
                rows.append(
                    IntelligenceCorrelation(
                        source_symbol=str(article.symbol or "MACRO").upper(),
                        related_symbols=[],
                        correlation_type="MACRO_RATES",
                        explanation="此事件屬於宏觀或利率風險，可能影響風險資產估值與美元流動性。",
                        risk_direction=str(article.risk_direction or "NEUTRAL").upper(),
                    )
                )
        return rows

    def _concentration_linkages(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
    ) -> list[IntelligenceCorrelation]:
        total = self._float(portfolio_payload.get("total_value"))
        if total <= 0:
            return []
        rows: list[IntelligenceCorrelation] = []
        values = {
            str(position.get("symbol") or "").upper(): self._float(position.get("current_value"))
            for position in portfolio_payload.get("stock_positions", [])
        }
        for symbol, value in values.items():
            if value / total < 0.15:
                continue
            if any(str(article.symbol or "").upper() == symbol for article in articles):
                rows.append(
                    IntelligenceCorrelation(
                        source_symbol=symbol,
                        related_symbols=[symbol],
                        correlation_type="SINGLE_NAME_CONCENTRATION",
                        explanation=f"{symbol} 屬於較高單一標的曝險，相關新聞可能更直接影響組合波動。",
                        risk_direction="NEUTRAL",
                    )
                )
        return rows

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
