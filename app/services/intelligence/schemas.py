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


class ScenarioResult(BaseModel):
    scenario_name: str
    impact_level: str = "LOW"
    affected_assets: list[str] = Field(default_factory=list)
    portfolio_sensitivity: str = ""
    fcn_risk_change: str = ""
    narrative: str = ""


class ScenarioResponse(BaseModel):
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    generated_at: datetime
    is_stale: bool = False


class IntelligenceGraphNode(BaseModel):
    id: str
    label: str
    node_type: str
    weight: float = 1


class IntelligenceGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    explanation: str = ""


class IntelligenceGraphResponse(BaseModel):
    nodes: list[IntelligenceGraphNode] = Field(default_factory=list)
    edges: list[IntelligenceGraphEdge] = Field(default_factory=list)
    strongest_themes: list[str] = Field(default_factory=list)
    strongest_connections: list[str] = Field(default_factory=list)
    top_correlated_risks: list[str] = Field(default_factory=list)
    generated_at: datetime
    is_stale: bool = False


class CopilotExplainRequest(BaseModel):
    question: str


class CopilotExplainResponse(BaseModel):
    answer: str
    supported_topics: list[str] = Field(default_factory=list)
    generated_at: datetime
    is_stale: bool = False


class LongMemorySummary(BaseModel):
    dominant_workspace_mode: str = "BALANCED"
    recurring_risk_themes: list[str] = Field(default_factory=list)
    historical_risk_trend: str = "STABLE"
    fcn_risk_trend: str = "STABLE"
    crypto_vol_trend: str = "STABLE"
    ai_momentum_trend: str = "STABLE"
    concentration_trend: str = "STABLE"


class ThemeEvolution(BaseModel):
    dominant_themes: list[str] = Field(default_factory=list)
    emerging_themes: list[str] = Field(default_factory=list)
    weakening_themes: list[str] = Field(default_factory=list)
    theme_confidence: float = 0
    narrative_summary: str = ""


class ReasoningResult(BaseModel):
    top_risks: list[str] = Field(default_factory=list)
    top_strengths: list[str] = Field(default_factory=list)
    key_dependencies: list[str] = Field(default_factory=list)
    concentration_analysis: str = ""
    volatility_analysis: str = ""
    reasoning_summary: str = ""
    why_workspace_mode: str = ""
    what_changed_this_week: str = ""


class PredictiveDrift(BaseModel):
    likely_workspace_shift: str = "BALANCED"
    confidence: float = 0
    prediction_reason: str = ""
    predictive_alerts: list[str] = Field(default_factory=list)


class TimelineSummary(BaseModel):
    what_changed_today: str = ""
    what_changed_this_week: str = ""
    new_risks: list[str] = Field(default_factory=list)
    improving_signals: list[str] = Field(default_factory=list)
    persistent_themes: list[str] = Field(default_factory=list)
    timeline_events: list[str] = Field(default_factory=list)


class PortfolioDNA(BaseModel):
    dominant_style: str = "Balanced Multi-Asset"
    risk_profile: str = "Balanced"
    volatility_profile: str = "Moderate"
    concentration_profile: str = "Diversified"
    AI_exposure_level: str = "LOW"
    FCN_dependency_level: str = "LOW"
    crypto_dependency_level: str = "LOW"
    macro_sensitivity: str = "MODERATE"


class ReasoningSystemResponse(BaseModel):
    long_memory: LongMemorySummary = Field(default_factory=LongMemorySummary)
    themes: ThemeEvolution = Field(default_factory=ThemeEvolution)
    reasoning: ReasoningResult = Field(default_factory=ReasoningResult)
    predictive: PredictiveDrift = Field(default_factory=PredictiveDrift)
    timeline: TimelineSummary = Field(default_factory=TimelineSummary)
    dna: PortfolioDNA = Field(default_factory=PortfolioDNA)
    generated_at: datetime
    is_stale: bool = False


class ExplainabilitySummary(BaseModel):
    why_risk_increased: str = ""
    what_changed_today: str = ""
    dominant_driver: str = ""
    hidden_correlation: str = ""
    systemic_risk: str = ""


class PortfolioSummaryV2AResponse(BaseModel):
    regime: str = "DEFENSIVE"
    dominant_risk: str = "No dominant risk"
    concentration_score: float = 0
    drift_summary: str = "No meaningful drift detected."
    explainability: ExplainabilitySummary = Field(default_factory=ExplainabilitySummary)
    top_alerts: list[str] = Field(default_factory=list)
    intelligence_confidence: float = 0
    generated_at: datetime
    is_stale: bool = False


class TimelineWindowSummary(BaseModel):
    window: str
    regime_evolution: str = "INSUFFICIENT_HISTORY"
    exposure_evolution: str = "INSUFFICIENT_HISTORY"
    risk_score_trend: str = "INSUFFICIENT_HISTORY"
    concentration_trend: str = "INSUFFICIENT_HISTORY"
    volatility_trend: str = "INSUFFICIENT_HISTORY"
    dominant_driver_history: list[str] = Field(default_factory=list)
    recurring_risks: list[str] = Field(default_factory=list)
    improving_signals: list[str] = Field(default_factory=list)
    deteriorating_signals: list[str] = Field(default_factory=list)


class TimelineIntelligenceResponse(BaseModel):
    portfolio_id: str = ""
    windows: list[TimelineWindowSummary] = Field(default_factory=list)
    regime_evolution: str = "INSUFFICIENT_HISTORY"
    exposure_evolution: str = "INSUFFICIENT_HISTORY"
    risk_score_trend: str = "INSUFFICIENT_HISTORY"
    concentration_trend: str = "INSUFFICIENT_HISTORY"
    volatility_trend: str = "INSUFFICIENT_HISTORY"
    dominant_driver_history: list[str] = Field(default_factory=list)
    recurring_risks: list[str] = Field(default_factory=list)
    improving_signals: list[str] = Field(default_factory=list)
    deteriorating_signals: list[str] = Field(default_factory=list)
    timeline_summary: str = "歷史資料仍在累積。"
    message: str = "歷史資料仍在累積。"
    confidence: float = 0
    generated_at: datetime
    is_stale: bool = False
