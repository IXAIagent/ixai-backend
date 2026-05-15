from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntelligenceScore(BaseModel):
    impact_score: float = 0
    portfolio_relevance_score: float = 0
    fcn_risk_score: float = 0
    ai_momentum_score: float = 0
    crypto_vol_score: float = 0
    macro_risk_score: float = 0
    total_score: float = 0


class IntelligenceNarrative(BaseModel):
    market_narrative: str = ""
    portfolio_narrative: str = ""
    risk_narrative: str = ""
    fcn_narrative: str = ""
    what_changed_today: str = ""


class IntelligenceCorrelation(BaseModel):
    source_symbol: str = ""
    related_symbols: list[str] = Field(default_factory=list)
    correlation_type: str = ""
    explanation: str = ""
    risk_direction: str = "NEUTRAL"


class WorkspaceDecision(BaseModel):
    workspace_mode: str = "BALANCED"
    primary_focus: str = "Portfolio stable"
    risk_drift: str = "Stable"
    market_regime: str = "MIXED ROTATION"
    decision_signals: list[str] = Field(default_factory=list)


class IntelligenceBrief(BaseModel):
    summary_lines: list[str] = Field(default_factory=list)
    watch_now: list[str] = Field(default_factory=list)
    upcoming_focus: list[str] = Field(default_factory=list)


class PortfolioIntelligenceResponse(BaseModel):
    scores: IntelligenceScore = Field(default_factory=IntelligenceScore)
    narrative: IntelligenceNarrative = Field(default_factory=IntelligenceNarrative)
    correlations: list[IntelligenceCorrelation] = Field(default_factory=list)
    workspace: WorkspaceDecision = Field(default_factory=WorkspaceDecision)
    brief: IntelligenceBrief = Field(default_factory=IntelligenceBrief)
    generated_at: datetime
    is_stale: bool = False
