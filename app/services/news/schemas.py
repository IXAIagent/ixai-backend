from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    symbol: str
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: str | None = None
    related_tickers: list[str] = Field(default_factory=list)
    source: str = "yfinance"
    relevance_score: float = 0
    relevance_level: str = "LOW"
    impact: str = "neutral"
    impact_reason: str = ""
    is_fcn_related: bool = False
    related_fcn_codes: list[str] = Field(default_factory=list)
    narrative: str = ""
    portfolio_exposure: str = "LOW"
    risk_direction: str = "NEUTRAL"
    attention_level: str = "LOW"
    portfolio_impact_summary: str = ""
    priority_score: int = 0
    priority_level: str = "LOW"
    alert_summary: str = ""
    ai_summary: str = ""


class PortfolioNewsResponse(BaseModel):
    portfolio_id: str
    portfolio_name: str
    articles: list[NewsArticle] = Field(default_factory=list)
    summary: str
    fetched_at: str
    is_stale: bool = False


class PortfolioPriorityResponse(BaseModel):
    top_alerts: list[NewsArticle] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    generated_at: datetime
    is_stale: bool = False
