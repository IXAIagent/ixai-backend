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
    # v3F: backward-compatible. `question` stays optional; when `query_type`
    # is provided it routes to a structured handler.
    question: str = ""
    query_type: str | None = None


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


# ---------------------------------------------------------------------------
# v4A: Portfolio Intelligence Engine schemas
# ---------------------------------------------------------------------------
class ExposureGraphNode(BaseModel):
    label: str
    node_type: str  # asset / theme / risk_factor
    weight: float = 0


class ExposureGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str  # asset_in_theme / theme_in_risk / fcn_underlying
    weight: float = 0


class ExposureGraphSummary(BaseModel):
    nodes: list[ExposureGraphNode] = Field(default_factory=list)
    edges: list[ExposureGraphEdge] = Field(default_factory=list)
    repeated_underlyings: list[str] = Field(default_factory=list)
    dominant_themes: list[str] = Field(default_factory=list)
    high_beta_symbols: list[str] = Field(default_factory=list)
    fcn_linked_symbols: list[str] = Field(default_factory=list)


class ConcentrationSummary(BaseModel):
    single_name_pct: float = 0
    theme_pct: float = 0
    fcn_underlying_pct: float = 0
    crypto_pct: float = 0
    cash_buffer_pct: float = 0
    concentration_score: float = 0
    risk_level: str = "clear"  # clear / watch / elevated / critical
    top_concentration_label: str = ""


class PortfolioDriftSummary(BaseModel):
    allocation_drift: str = "UNCHANGED"
    concentration_drift: str = "UNCHANGED"
    volatility_drift: str = "UNCHANGED"
    fcn_pressure_drift: str = "UNCHANGED"
    regime_drift: str = "UNCHANGED"
    drift_summary: str = ""
    history_window: int = 0


class FCNSystemicRiskSummary(BaseModel):
    worst_of_pressure_pct: float = 0  # percentage points below initial level
    nearest_ki_pct: float | None = None
    repeated_underlyings: list[str] = Field(default_factory=list)
    ki_cluster_symbols: list[str] = Field(default_factory=list)
    observation_clustering: str = "spread"  # spread / clustered / unknown
    risk_level: str = "clear"


class RiskPropagationChain(BaseModel):
    chain: list[str] = Field(default_factory=list)
    explanation: str = ""


class RiskPropagationSummary(BaseModel):
    chains: list[RiskPropagationChain] = Field(default_factory=list)
    summary: str = ""


class UnifiedIntelligenceScore(BaseModel):
    exposure_score: float = 0
    concentration_score: float = 0
    fcn_stress_score: float = 0
    volatility_score: float = 0
    drift_score: float = 0
    systemic_score: float = 0
    total_intelligence_score: float = 0
    risk_state: str = "clear"  # clear / watch / elevated / critical
    confidence: float = 0


class PortfolioEngineSummaryResponse(BaseModel):
    portfolio_id: str = ""
    exposure_graph: ExposureGraphSummary = Field(default_factory=ExposureGraphSummary)
    concentration: ConcentrationSummary = Field(default_factory=ConcentrationSummary)
    drift: PortfolioDriftSummary = Field(default_factory=PortfolioDriftSummary)
    fcn_systemic_risk: FCNSystemicRiskSummary = Field(default_factory=FCNSystemicRiskSummary)
    risk_propagation: RiskPropagationSummary = Field(default_factory=RiskPropagationSummary)
    unified_score: UnifiedIntelligenceScore = Field(default_factory=UnifiedIntelligenceScore)
    generated_at: datetime
    is_stale: bool = False
    # v4E additions; all additive + default-safe so clients ignoring them
    # see unchanged contract.
    status: str = "healthy"  # healthy / partial / degraded / unavailable
    stale_reason: str = ""
    degraded_reason: str = ""
    locale: str = "en"
    failed_engines: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# v4B: Market Intelligence Engine schemas
# ---------------------------------------------------------------------------
class MarketRegimeSummary(BaseModel):
    regime: str = "data_limited"  # risk_on / risk_off / high_volatility / crypto_stress / ai_momentum / defensive / data_limited
    confidence: float = 0
    drivers: list[str] = Field(default_factory=list)
    narrative: str = ""


class VolatilityStateSummary(BaseModel):
    equity_volatility_state: str = "normal"  # low / normal / elevated / high / data_limited
    crypto_volatility_state: str = "normal"
    fcn_sensitivity_state: str = "normal"
    overall_state: str = "normal"
    data_limited: bool = False


class MacroNewsRiskTheme(BaseModel):
    theme: str
    weight: float = 0
    sample_headlines: list[str] = Field(default_factory=list)


class MacroNewsRiskSummary(BaseModel):
    rates_pressure: float = 0
    ai_pressure: float = 0
    crypto_pressure: float = 0
    geopolitics_pressure: float = 0
    earnings_pressure: float = 0
    macro_stress: float = 0
    top_themes: list[MacroNewsRiskTheme] = Field(default_factory=list)
    narrative: str = ""


class PortfolioMarketImpactSummary(BaseModel):
    fcn_impact: str = ""
    crypto_impact: str = ""
    equity_impact: str = ""
    cash_buffer_interpretation: str = ""
    overall_impact_level: str = "clear"  # clear / watch / elevated / critical


class MarketEngineSummaryResponse(BaseModel):
    portfolio_id: str = ""
    regime: MarketRegimeSummary = Field(default_factory=MarketRegimeSummary)
    volatility: VolatilityStateSummary = Field(default_factory=VolatilityStateSummary)
    macro_news: MacroNewsRiskSummary = Field(default_factory=MacroNewsRiskSummary)
    portfolio_impact: PortfolioMarketImpactSummary = Field(
        default_factory=PortfolioMarketImpactSummary
    )
    generated_at: datetime
    is_stale: bool = False
    # v4E additions
    status: str = "healthy"
    stale_reason: str = ""
    degraded_reason: str = ""
    locale: str = "en"
    failed_engines: list[str] = Field(default_factory=list)
