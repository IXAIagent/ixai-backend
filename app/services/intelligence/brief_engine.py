from __future__ import annotations

from app.services.intelligence.schemas import IntelligenceBrief, IntelligenceScore, WorkspaceDecision
from app.services.news.schemas import NewsArticle


class IntelligenceBriefEngine:
    def build(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        articles: list[NewsArticle],
    ) -> IntelligenceBrief:
        try:
            summary_lines = self._summary_lines(scores, workspace, articles)
            watch_now = self._watch_now(scores, workspace, articles)
            upcoming_focus = self._upcoming_focus(workspace, articles)
            return IntelligenceBrief(
                summary_lines=summary_lines[:5],
                watch_now=watch_now[:4],
                upcoming_focus=upcoming_focus[:4],
            )
        except Exception:
            return IntelligenceBrief(
                summary_lines=["目前未偵測到重大組合風險事件。"],
                watch_now=["目前沒有需要立即處理的 intelligence。"],
                upcoming_focus=["例行監控 macro、FCN coupon 與 earnings window。"],
            )

    def _summary_lines(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        articles: list[NewsArticle],
    ) -> list[str]:
        lines = [workspace.primary_focus]
        if scores.fcn_risk_score >= 45:
            lines.append("FCN underlying 與 KI/KO 風險需要優先監控。")
        if scores.ai_momentum_score >= 45:
            lines.append("AI/chip intelligence 對組合情緒影響提高。")
        if scores.crypto_vol_score >= 45:
            lines.append("Crypto 波動對短期組合波動的影響上升。")
        if scores.macro_risk_score >= 45:
            lines.append("宏觀利率、美元或通膨訊號正在升溫。")
        if not articles:
            lines.append("目前未抓到重大持倉新聞，維持例行監控。")
        return lines

    def _watch_now(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        articles: list[NewsArticle],
    ) -> list[str]:
        items: list[str] = []
        for article in articles:
            priority = str(article.priority_level or "").upper()
            relevance = str(article.relevance_level or "").upper()
            if priority in {"CRITICAL", "HIGH"} or relevance == "HIGH" or article.is_fcn_related:
                symbol = str(article.symbol or "Portfolio")
                items.append(f"{symbol} {str(article.title or 'priority event')[:70]}")
        if workspace.workspace_mode == "FCN_RISK":
            items.append("FCN worst-of / KI distance monitor")
        if scores.crypto_vol_score >= 45:
            items.append("BTC/ETH volatility expansion")
        if scores.ai_momentum_score >= 45:
            items.append("AI/chip momentum concentration")
        return items or ["目前未偵測到需要立即處理的決策事件。"]

    def _upcoming_focus(self, workspace: WorkspaceDecision, articles: list[NewsArticle]) -> list[str]:
        focus = ["CPI/FOMC macro window", "Major earnings window"]
        if workspace.workspace_mode == "FCN_RISK" or any(article.is_fcn_related for article in articles):
            focus.insert(0, "FCN coupon / observation window")
        if workspace.workspace_mode == "CRYPTO_VOL":
            focus.insert(0, "BTC options / volatility window")
        return focus
