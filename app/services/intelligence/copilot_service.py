from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import PortfolioIntelligenceResponse


class IXAICopilotService:
    SUPPORTED_TOPICS = [
        "workspace mode",
        "top risks",
        "FCN sensitivity",
        "AI momentum",
        "crypto volatility",
    ]

    def answer_question(self, question: str, portfolio_context: dict[str, Any]) -> str:
        try:
            normalized = str(question or "").lower()
            intelligence: PortfolioIntelligenceResponse | None = portfolio_context.get("intelligence")
            if not intelligence:
                return "目前 intelligence context 不足，請稍後再試。"

            if "workspace" in normalized or "mode" in normalized or "模式" in normalized:
                answer = (
                    f"目前 workspace mode 為 {intelligence.workspace.workspace_mode}。"
                    f"{intelligence.workspace.primary_focus}"
                )
            elif "fcn" in normalized or "ki" in normalized or "ko" in normalized:
                answer = intelligence.narrative.fcn_narrative or "目前 FCN 風險維持例行監控。"
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
