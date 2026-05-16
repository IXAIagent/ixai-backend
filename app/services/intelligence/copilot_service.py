from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import PortfolioIntelligenceResponse, ReasoningSystemResponse


class IXAICopilotService:
    SUPPORTED_TOPICS = [
        "workspace mode",
        "top risks",
        "FCN sensitivity",
        "AI momentum",
        "crypto volatility",
        "theme evolution",
        "this week changes",
        "portfolio DNA",
    ]

    # v3F: structured query types supported by /copilot/explain.
    SUPPORTED_QUERY_TYPES = (
        "biggest_risk",
        "why_today_focus",
        "fcn_risk",
        "portfolio_drift",
        "market_impact",
        "data_freshness",
    )

    def answer_question(self, question: str, portfolio_context: dict[str, Any]) -> str:
        try:
            normalized = str(question or "").lower()
            intelligence: PortfolioIntelligenceResponse | None = portfolio_context.get("intelligence")
            reasoning: ReasoningSystemResponse | None = portfolio_context.get("reasoning")
            if not intelligence:
                return "目前 intelligence context 不足，請稍後再試。"

            if "biggest" in normalized or "risk" in normalized or "最大" in normalized or "風險" in normalized:
                if reasoning and reasoning.reasoning.top_risks:
                    answer = "目前主要風險為：" + "；".join(reasoning.reasoning.top_risks[:3])
                else:
                    answer = intelligence.narrative.risk_narrative
            elif "shift" in normalized or "workspace" in normalized or "mode" in normalized or "模式" in normalized:
                answer = (
                    f"目前 workspace mode 為 {intelligence.workspace.workspace_mode}。"
                    f"{reasoning.reasoning.why_workspace_mode if reasoning else intelligence.workspace.primary_focus}"
                )
            elif "theme" in normalized or "主題" in normalized:
                answer = reasoning.themes.narrative_summary if reasoning else "目前主題演變資料不足。"
            elif "week" in normalized or "本週" in normalized or "changed" in normalized:
                answer = reasoning.timeline.what_changed_this_week if reasoning else intelligence.narrative.what_changed_today
            elif "dna" in normalized or "profile" in normalized or "風格" in normalized:
                answer = (
                    f"Portfolio DNA: {reasoning.dna.dominant_style}，"
                    f"risk profile 為 {reasoning.dna.risk_profile}。"
                    if reasoning
                    else "目前 DNA context 不足。"
                )
            elif "fcn" in normalized or "ki" in normalized or "ko" in normalized:
                answer = (
                    reasoning.reasoning.why_workspace_mode
                    if reasoning and reasoning.long_memory.fcn_risk_trend != "STABLE"
                    else intelligence.narrative.fcn_narrative or "目前 FCN 風險維持例行監控。"
                )
            elif "crypto" in normalized or "btc" in normalized or "加密" in normalized:
                answer = (
                    "Crypto volatility score 為 "
                    f"{intelligence.scores.crypto_vol_score:.0f}。"
                    "此分數用於判斷 BTC/ETH 新聞、曝險與槓桿是否升溫。"
                )
            elif "ai" in normalized or "nvda" in normalized or "momentum" in normalized:
                answer = (
                    "AI momentum score 為 "
                    f"{intelligence.scores.ai_momentum_score:.0f}。"
                    "此分數反映 AI/chip 持倉與相關 intelligence flow。"
                )
            else:
                answer = intelligence.narrative.risk_narrative or intelligence.workspace.primary_focus

            return compliance_filter.sanitize_text(answer, max_length=260)
        except Exception:
            return "Copilot foundation 暫時無法產生解釋，但不影響 dashboard intelligence。"

    def answer_by_query_type(
        self, query_type: str, portfolio_context: dict[str, Any]
    ) -> str:
        """v3F: structured handler. All branches return compliance-safe text.

        Unknown query_type falls back to a safe default. Any exception is
        caught and converted into a safe fallback string.
        """
        try:
            intelligence: PortfolioIntelligenceResponse | None = portfolio_context.get(
                "intelligence"
            )
            reasoning: ReasoningSystemResponse | None = portfolio_context.get("reasoning")
            summary = portfolio_context.get("portfolio_summary")
            timeline = portfolio_context.get("timeline")
            if not intelligence:
                return compliance_filter.sanitize_text(
                    "目前 intelligence context 不足，請稍後再試。"
                )

            normalized = str(query_type or "").strip().lower()
            if normalized not in self.SUPPORTED_QUERY_TYPES:
                return compliance_filter.sanitize_text(
                    "目前無法解析此 query。請使用 biggest_risk / why_today_focus / "
                    "fcn_risk / portfolio_drift / market_impact / data_freshness。"
                )

            if normalized == "biggest_risk":
                top_risks = (
                    reasoning.reasoning.top_risks
                    if reasoning and reasoning.reasoning and reasoning.reasoning.top_risks
                    else []
                )
                if top_risks:
                    answer = "目前主要風險為：" + "；".join(top_risks[:3])
                else:
                    answer = (
                        intelligence.narrative.risk_narrative
                        or "目前未發現顯著單一風險，建議持續監控。"
                    )

            elif normalized == "why_today_focus":
                workspace_mode = (
                    intelligence.workspace.workspace_mode if intelligence.workspace else ""
                )
                primary_focus = (
                    intelligence.workspace.primary_focus if intelligence.workspace else ""
                )
                why_mode = (
                    reasoning.reasoning.why_workspace_mode
                    if reasoning and reasoning.reasoning
                    else ""
                )
                answer = (
                    f"目前 workspace 為 {workspace_mode or 'BALANCED'}。"
                    f"{why_mode or primary_focus or '建議監控既有資產與訊息流。'}"
                )

            elif normalized == "fcn_risk":
                fcn_narrative = intelligence.narrative.fcn_narrative if intelligence.narrative else ""
                fcn_trend = (
                    reasoning.long_memory.fcn_risk_trend
                    if reasoning and reasoning.long_memory
                    else ""
                )
                answer = fcn_narrative or "目前 FCN 風險維持例行監控。"
                if fcn_trend and fcn_trend != "STABLE":
                    answer = f"FCN 風險趨勢：{fcn_trend}。{answer}"

            elif normalized == "portfolio_drift":
                drift = ""
                if summary:
                    drift = getattr(summary, "drift_summary", "") or ""
                if not drift and reasoning and reasoning.timeline:
                    drift = (
                        reasoning.timeline.what_changed_this_week
                        or reasoning.timeline.what_changed_today
                        or ""
                    )
                answer = drift or "目前 portfolio drift 尚未顯著，建議持續觀察。"

            elif normalized == "market_impact":
                market = (
                    intelligence.narrative.market_narrative if intelligence.narrative else ""
                )
                systemic = ""
                if summary and getattr(summary, "explainability", None):
                    systemic = getattr(summary.explainability, "systemic_risk", "") or ""
                answer = market or systemic or "目前外部市場訊息對 portfolio 影響有限。"

            elif normalized == "data_freshness":
                summary_stale = bool(getattr(summary, "is_stale", False)) if summary else False
                timeline_stale = bool(getattr(timeline, "is_stale", False)) if timeline else False
                if summary_stale or timeline_stale:
                    answer = (
                        "部分 intelligence 來源為 stale，建議稍後再開啟以取得最新 snapshot。"
                    )
                else:
                    answer = "目前 intelligence snapshot 為 fresh，可作為觀察依據。"

            else:  # pragma: no cover - guarded by SUPPORTED_QUERY_TYPES above
                answer = "目前無法解析此 query。"

            return compliance_filter.sanitize_text(answer, max_length=260)
        except Exception:
            return compliance_filter.sanitize_text(
                "Copilot 暫時無法回答此 query，請稍後再試。"
            )
