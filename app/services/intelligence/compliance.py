from __future__ import annotations

import re
from typing import Any


class IntelligenceComplianceFilter:
    BLOCKED_TERMS = {
        "buy": "review",
        "sell": "review",
        "add position": "review exposure",
        "reduce": "review risk",
        "target price": "price sensitivity",
        "entry price": "entry context",
        "stop loss": "risk threshold",
        "買進": "觀察",
        "賣出": "觀察",
        "加碼": "檢視曝險",
        "減碼": "檢視風險",
        "目標價": "價格敏感度",
        "停損": "風險門檻",
    }

    def sanitize_text(self, value: Any, max_length: int = 240) -> str:
        text = str(value or "").strip()
        for term, replacement in self.BLOCKED_TERMS.items():
            text = re.sub(re.escape(term), replacement, text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip("，。；,. ") + "。"

    def sanitize_list(self, values: list[str], max_length: int = 160) -> list[str]:
        return [self.sanitize_text(value, max_length=max_length) for value in values]


compliance_filter = IntelligenceComplianceFilter()
