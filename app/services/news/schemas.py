from __future__ import annotations

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    symbol: str
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: str | None = None
    related_tickers: list[str] = Field(default_factory=list)
    source: str = "yfinance"


class PortfolioNewsResponse(BaseModel):
    portfolio_id: str
    portfolio_name: str
    articles: list[NewsArticle] = Field(default_factory=list)
    summary: str
    fetched_at: str
    is_stale: bool = False
