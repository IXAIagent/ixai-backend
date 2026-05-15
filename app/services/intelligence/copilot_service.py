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
