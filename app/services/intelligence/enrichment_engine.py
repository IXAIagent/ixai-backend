from __future__ import annotations

from app.services.news.schemas import NewsArticle


class IntelligenceEnrichmentEngine:
    AI_SYMBOLS = {"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB", "AMD"}
    CRYPTO_SYMBOLS = {"BTC", "BTCUSDT", "BTC-USD", "ETH", "ETHUSDT", "ETH-USD"}

    def enrich_article(self, article: NewsArticle) -> dict:
        symbol = str(article.symbol or "").upper()
        title = str(article.title or "").lower()
        entities = {symbol} if symbol else set()
        themes: set[str] = set()
        sectors: set[str] = set()
        volatility_tags: set[str] = set()
        macro_tags: set[str] = set()
        ai_tags: set[str] = set()
        crypto_tags: set[str] = set()
        fcn_tags: set[str] = set()

        if symbol in self.AI_SYMBOLS or any(term in title for term in ("ai", "gpu", "chip", "semiconductor")):
            entities.update({"AI", "GPU"})
            themes.add("AI_INFRA")
            sectors.add("SEMICONDUCTOR")
            ai_tags.add("AI_MOMENTUM")

        if symbol in self.CRYPTO_SYMBOLS or any(term in title for term in ("bitcoin", "ethereum", "crypto")):
            themes.add("CRYPTO_VOL")
            crypto_tags.add("CRYPTO_MARKET")
            if "volatility" in title or str(article.impact or "").lower() == "negative":
                volatility_tags.add("HIGH_VOL")

        if any(term in title for term in ("cpi", "inflation", "fed", "fomc", "rates", "usd", "vix")):
            macro_tags.update({"INFLATION", "FED"})
            themes.add("MACRO_RISK")

        if article.is_fcn_related:
            fcn_tags.add("UNDERLYING")
            if str(article.attention_level or "").upper() in {"HIGH", "CRITICAL"}:
                fcn_tags.add("KI_RISK")
            if str(article.portfolio_exposure or "").upper() == "HIGH":
                fcn_tags.add("WORST_OF")

        sentiment = str(article.impact or "neutral").upper()
        return {
            "entities": sorted(entity for entity in entities if entity),
            "themes": sorted(themes),
            "sectors": sorted(sectors),
            "sentiment": sentiment,
            "volatility_tags": sorted(volatility_tags),
            "macro_tags": sorted(macro_tags),
            "ai_tags": sorted(ai_tags),
            "crypto_tags": sorted(crypto_tags),
            "fcn_tags": sorted(fcn_tags),
        }

    def enrich_articles(self, articles: list[NewsArticle]) -> dict[str, dict]:
        enriched: dict[str, dict] = {}
        for article in articles:
            key = str(article.link or article.title or article.symbol or len(enriched))
            enriched[key] = self.enrich_article(article)
        return enriched
