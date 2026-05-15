from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.intelligence.schemas import IntelligenceScore, WorkspaceDecision


_MEMORY_TTL = timedelta(minutes=60)
_MEMORY: dict[str, dict] = {}


class IntelligenceMemoryService:
    def compare_and_store(
        self,
        portfolio_id: str,
        workspace: WorkspaceDecision,
        scores: IntelligenceScore,
    ) -> str:
        try:
            now = datetime.now(timezone.utc)
            previous = _MEMORY.get(portfolio_id)
            _MEMORY[portfolio_id] = {
                "workspace_mode": workspace.workspace_mode,
                "total_score": scores.total_score,
                "fcn_risk_score": scores.fcn_risk_score,
                "crypto_vol_score": scores.crypto_vol_score,
                "ai_momentum_score": scores.ai_momentum_score,
                "updated_at": now,
            }

            if not previous or now - previous.get("updated_at", now) > _MEMORY_TTL:
                return "首次建立 intelligence snapshot，後續將追蹤 workspace 與風險分數變化。"

            changes: list[str] = []
            if previous.get("workspace_mode") != workspace.workspace_mode:
                changes.append(f"workspace 由 {previous.get('workspace_mode')} 切換為 {workspace.workspace_mode}")

            total_delta = scores.total_score - float(previous.get("total_score", 0) or 0)
            if total_delta >= 10:
                changes.append("整體 intelligence score 明顯升高")
            elif total_delta <= -10:
                changes.append("整體 intelligence score 下降")

            if scores.fcn_risk_score - float(previous.get("fcn_risk_score", 0) or 0) >= 10:
                changes.append("FCN risk score 升溫")
            if scores.crypto_vol_score - float(previous.get("crypto_vol_score", 0) or 0) >= 10:
                changes.append("crypto volatility score 升溫")
            if scores.ai_momentum_score - float(previous.get("ai_momentum_score", 0) or 0) >= 10:
                changes.append("AI momentum score 升溫")

            return "；".join(changes) + "。" if changes else "目前 intelligence 狀態相對穩定，尚未偵測到明顯變化。"
        except Exception:
            return "memory layer 暫時無法比較前次狀態，已回到即時 snapshot。"
