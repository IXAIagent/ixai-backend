from __future__ import annotations

from app.services.intelligence.schemas import (
    IntelligenceCorrelation,
    IntelligenceNarrative,
    IntelligenceScore,
    WorkspaceDecision,
)
from app.services.news.schemas import NewsArticle


class IntelligenceNarrativeEngine:
    def narrate(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        articles: list[NewsArticle],
        correlations: list[IntelligenceCorrelation],
        what_changed_today: str = "",
    ) -> IntelligenceNarrative:
        try:
            return IntelligenceNarrative(
                market_narrative=self._market(workspace, scores),
                portfolio_narrative=self._portfolio(workspace, articles, correlations),
                risk_narrative=self._risk(scores, workspace),
                fcn_narrative=self._fcn(scores, articles),
                what_changed_today=what_changed_today or "目前為首次 intelligence snapshot，後續將追蹤模式與分數變化。",
            )
        except Exception:
            return IntelligenceNarrative(
                market_narrative="目前市場訊號偏中性。",
                portfolio_narrative="投資組合 intelligence 正常監控中。",
                risk_narrative="尚未偵測到明顯風險擴散。",
                fcn_narrative="FCN 風險資料目前維持觀察。",
                what_changed_today=what_changed_today or "目前沒有明顯變化。",
            )

    def _market(self, workspace: WorkspaceDecision, scores: IntelligenceScore) -> str:
        if workspace.workspace_mode == "AI_MOMENTUM":
            return "AI 與半導體相關事件正在主導市場敘事，需觀察正面情緒是否延續。"
        if workspace.workspace_mode == "CRYPTO_VOL":
            return "Crypto 波動訊號偏高，短期市場風險可能更受 BTC/ETH 情緒影響。"
        if workspace.workspace_mode == "DEFENSIVE":
            return "市場進入較防禦的監控狀態，宏觀與負面事件權重上升。"
        if scores.macro_risk_score >= 45:
            return "宏觀利率與美元相關訊號升溫，可能影響風險資產估值。"
        return "目前市場訊號偏混合，尚未由單一主題主導。"

    def _portfolio(
        self,
        workspace: WorkspaceDecision,
        articles: list[NewsArticle],
        correlations: list[IntelligenceCorrelation],
    ) -> str:
        high_articles = [article for article in articles if str(article.relevance_level or "").upper() == "HIGH"]
        if high_articles:
            symbols = "、".join(str(article.symbol or "持倉") for article in high_articles[:3])
            return f"{symbols} 出現高相關 intelligence，可能影響短期組合觀察重點。"
        if correlations:
            return "目前偵測到持倉、新聞與 FCN/主題曝險之間的關聯，建議以相關性而非單一新聞判讀。"
        if workspace.workspace_mode == "BALANCED":
            return "目前投資組合訊號相對平衡，維持例行監控即可。"
        return "投資組合訊號已切換至特定 workspace，請優先查看 primary focus。"

    def _risk(self, scores: IntelligenceScore, workspace: WorkspaceDecision) -> str:
        if workspace.risk_drift == "Increasing":
            return "風險漂移正在升高，建議優先追蹤高優先級事件、FCN 距離與集中度變化。"
        if scores.total_score >= 40:
            return "目前風險處於可控但需觀察狀態，需留意事件是否擴散到多個資產類別。"
        return "目前未觀察到明顯風險擴散，整體監控狀態穩定。"

    def _fcn(self, scores: IntelligenceScore, articles: list[NewsArticle]) -> str:
        if scores.fcn_risk_score >= 55:
            return "FCN 風險分數偏高，需留意 worst-of、KI/KO 距離與 underlying 相關新聞。"
        if any(article.is_fcn_related for article in articles):
            return "部分新聞涉及 FCN underlying，短期需持續觀察 KI/KO 敏感度。"
        return "目前 FCN 相關訊號未明顯升溫。"
