"""Regression tests for v3F Copilot safe-explain enhancement.

Covers:
- Every supported query_type returns a non-empty, compliance-safe answer.
- Fallback for unknown query_type is still compliance-safe.
- Backward-compat: question-string path still works.
- Forbidden trading wording is never present in any output, in either EN or zh.
"""
from __future__ import annotations

import re

import pytest

from app.services.intelligence.copilot_service import IXAICopilotService
from app.services.intelligence.schemas import (
    IntelligenceBrief,
    IntelligenceCorrelation,
    IntelligenceNarrative,
    IntelligenceScore,
    LongMemorySummary,
    PortfolioDNA,
    PortfolioIntelligenceResponse,
    PortfolioSummaryV2AResponse,
    PredictiveDrift,
    ReasoningResult,
    ReasoningSystemResponse,
    ThemeEvolution,
    TimelineIntelligenceResponse,
    TimelineSummary,
    WorkspaceDecision,
)


FORBIDDEN_PATTERNS = re.compile(
    r"\b(buy|sell|add position|reduce position|target price|stop loss)\b|"
    r"買進|賣出|加碼|減碼|目標價|停損",
    re.IGNORECASE,
)


def _stub_intelligence() -> PortfolioIntelligenceResponse:
    return PortfolioIntelligenceResponse(
        scores=IntelligenceScore(
            impact_score=40,
            portfolio_relevance_score=55,
            fcn_risk_score=70,
            ai_momentum_score=45,
            crypto_vol_score=30,
            macro_risk_score=20,
            total_score=60,
        ),
        narrative=IntelligenceNarrative(
            market_narrative="Market sentiment is mixed today.",
            portfolio_narrative="Portfolio remains diversified.",
            risk_narrative="FCN concentration is the dominant exposure.",
            fcn_narrative="FCN worst-of underlying is near KI.",
            what_changed_today="Concentration ticked higher.",
        ),
        correlations=[
            IntelligenceCorrelation(
                source_symbol="NVDA",
                related_symbols=["AMD", "TSM"],
                correlation_type="theme",
                explanation="AI/chip cluster.",
                risk_direction="up",
            )
        ],
        workspace=WorkspaceDecision(
            workspace_mode="FCN_RISK",
            primary_focus="Watch FCN KI distance.",
            risk_drift="Elevated",
            market_regime="MIXED",
            decision_signals=["FCN KI < 10%"],
        ),
        brief=IntelligenceBrief(),
        generated_at="2026-05-16T00:00:00Z",
        is_stale=False,
    )


def _stub_reasoning() -> ReasoningSystemResponse:
    return ReasoningSystemResponse(
        long_memory=LongMemorySummary(
            dominant_workspace_mode="FCN_RISK",
            recurring_risk_themes=["FCN_STRESS_BUILDING"],
            historical_risk_trend="RISING",
            fcn_risk_trend="RISING",
        ),
        themes=ThemeEvolution(
            dominant_themes=["AI_INFRA"],
            narrative_summary="AI/chip theme persists.",
        ),
        reasoning=ReasoningResult(
            top_risks=["FCN KI distance", "AI concentration", "Crypto volatility"],
            top_strengths=["Cash buffer"],
            why_workspace_mode="FCN risk dominates current view.",
            what_changed_this_week="Concentration rose this week.",
        ),
        predictive=PredictiveDrift(),
        timeline=TimelineSummary(
            what_changed_today="Concentration increased.",
            what_changed_this_week="Multiple FCN entered watch zone.",
        ),
        dna=PortfolioDNA(dominant_style="thematic", risk_profile="elevated"),
        generated_at="2026-05-16T00:00:00Z",
        is_stale=False,
    )


def _stub_summary() -> PortfolioSummaryV2AResponse:
    from app.services.intelligence.schemas import ExplainabilitySummary

    return PortfolioSummaryV2AResponse(
        regime="FCN_RISK",
        dominant_risk="FCN KI distance",
        concentration_score=72,
        drift_summary="Regime tilted toward FCN_RISK; concentration rising.",
        explainability=ExplainabilitySummary(
            why_risk_increased="Concentration above threshold.",
            what_changed_today="FCN distance narrowed.",
            dominant_driver="FCN KI proximity.",
            hidden_correlation="AI/chip cluster overlap.",
            systemic_risk="Sector rotation could amplify.",
        ),
        intelligence_confidence=70,
        generated_at="2026-05-16T00:00:00Z",
        is_stale=False,
    )


def _stub_timeline() -> TimelineIntelligenceResponse:
    return TimelineIntelligenceResponse(
        portfolio_id="pf-1",
        windows=[],
        regime_evolution="FCN_RISK persistent",
        risk_score_trend="RISING",
        concentration_trend="RISING",
        volatility_trend="STABLE",
        recurring_risks=["FCN_STRESS_BUILDING"],
        improving_signals=[],
        deteriorating_signals=["Concentration"],
        timeline_summary="Week sees FCN risk building.",
        message="History available.",
        confidence=60,
        generated_at="2026-05-16T00:00:00Z",
        is_stale=False,
    )


@pytest.fixture()
def context():
    return {
        "intelligence": _stub_intelligence(),
        "reasoning": _stub_reasoning(),
        "portfolio_summary": _stub_summary(),
        "timeline": _stub_timeline(),
    }


@pytest.mark.parametrize(
    "query_type",
    [
        "biggest_risk",
        "why_today_focus",
        "fcn_risk",
        "portfolio_drift",
        "market_impact",
        "data_freshness",
    ],
)
def test_query_type_returns_non_empty_safe_answer(query_type, context):
    svc = IXAICopilotService()
    answer = svc.answer_by_query_type(query_type, context)
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0
    assert FORBIDDEN_PATTERNS.search(answer) is None, (
        f"Forbidden trading wording leaked for query_type={query_type}: {answer!r}"
    )


def test_unknown_query_type_returns_safe_fallback(context):
    svc = IXAICopilotService()
    answer = svc.answer_by_query_type("nonexistent_type", context)
    assert "query" in answer.lower() or "biggest_risk" in answer
    assert FORBIDDEN_PATTERNS.search(answer) is None


def test_question_string_path_still_works(context):
    """Backward-compat: passing a free-form question must still produce an answer."""
    svc = IXAICopilotService()
    answer = svc.answer_question("What is my biggest risk?", context)
    assert len(answer.strip()) > 0
    assert FORBIDDEN_PATTERNS.search(answer) is None


def test_no_intelligence_context_returns_safe_fallback():
    svc = IXAICopilotService()
    answer = svc.answer_by_query_type("biggest_risk", {})
    assert isinstance(answer, str) and answer.strip()
    assert FORBIDDEN_PATTERNS.search(answer) is None


def test_compliance_filter_strips_forbidden_input(context):
    """Even if a downstream engine emitted forbidden wording, the final answer
    passes through compliance_filter.sanitize_text. Verify the filter itself."""
    from app.services.intelligence.compliance import compliance_filter

    dirty = "buy NVDA at target price 100 / 加碼 NVDA 目標價 100"
    cleaned = compliance_filter.sanitize_text(dirty)
    assert FORBIDDEN_PATTERNS.search(cleaned) is None


@pytest.mark.parametrize(
    "query_type",
    [
        "biggest_risk",
        "why_today_focus",
        "fcn_risk",
        "portfolio_drift",
        "market_impact",
        "data_freshness",
    ],
)
def test_query_type_listed_in_supported(query_type):
    assert query_type in IXAICopilotService.SUPPORTED_QUERY_TYPES
