"""v4B: Macro / news risk engine.

Classifies recent news into 6 themes (rates / AI / crypto / geopolitics /
earnings / macro_stress) and emits per-theme pressures + sample headlines.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import (
    MacroNewsRiskSummary,
    MacroNewsRiskTheme,
)


THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "rates": ("fed", "rate", "cpi", "inflation", "fomc", "yield", "treasury", "央行", "利率", "通膨"),
    "ai": ("nvda", "ai", "chip", "semiconductor", "tsm", "gpu", "data center", "晶片", "ai 晶片", "輝達"),
    "crypto": ("btc", "bitcoin", "eth", "ethereum", "crypto", "stablecoin", "幣"),
    "geopolitics": ("war", "tariff", "sanction", "geopolit", "taiwan", "china", "戰", "制裁"),
    "earnings": ("earnings", "revenue", "guidance", "profit", "loss warning", "財報", "獲利"),
    "macro": ("recession", "gdp", "unemployment", "pmi", "manufacturing", "macro"),
}


def _safe_lower(value: Any) -> str:
    return str(value or "").lower()


def _impact_weight(impact: Any) -> float:
    # Theme presence always contributes a positive floor; impact direction
    # only modulates intensity. Negative tone is the risk amplifier.
    label = _safe_lower(impact)
    if label == "negative":
        return 1.5
    if label == "positive":
        return 0.5
    return 1.0


class MacroNewsRiskEngine:
    def analyse(self, context: dict[str, Any]) -> MacroNewsRiskSummary:
        try:
            articles = context.get("articles") or []
            if not articles:
                return MacroNewsRiskSummary(
                    narrative=compliance_filter.sanitize_text(
                        "Macro news context limited; thematic pressures unset."
                    )
                )

            pressures: dict[str, float] = {key: 0.0 for key in THEME_KEYWORDS}
            samples: dict[str, list[str]] = {key: [] for key in THEME_KEYWORDS}

            for article in articles:
                title = _safe_lower(getattr(article, "title", "") or "")
                summary = _safe_lower(
                    getattr(article, "alert_summary", "")
                    or getattr(article, "narrative", "")
                    or getattr(article, "portfolio_impact_summary", "")
                )
                weight = _impact_weight(getattr(article, "impact", None))
                text_blob = f"{title} {summary}"
                for theme, keywords in THEME_KEYWORDS.items():
                    if any(keyword in text_blob for keyword in keywords):
                        pressures[theme] += weight
                        if len(samples[theme]) < 3:
                            raw_title = str(getattr(article, "title", "") or "").strip()
                            if raw_title:
                                samples[theme].append(raw_title[:120])

            # Normalise pressures to 0..100 using soft scaling
            def scale(p: float) -> float:
                return round(min(100.0, max(0.0, p * 12.0)), 2)

            rates = scale(pressures["rates"])
            ai = scale(pressures["ai"])
            crypto = scale(pressures["crypto"])
            geo = scale(pressures["geopolitics"])
            earnings = scale(pressures["earnings"])
            macro_stress = scale(pressures["macro"])

            top_themes = sorted(
                [
                    (label, value, samples[key])
                    for key, value, label in [
                        ("rates", rates, "rates"),
                        ("ai", ai, "ai"),
                        ("crypto", crypto, "crypto"),
                        ("geopolitics", geo, "geopolitics"),
                        ("earnings", earnings, "earnings"),
                        ("macro", macro_stress, "macro_stress"),
                    ]
                ],
                key=lambda triple: triple[1],
                reverse=True,
            )

            top_payload = [
                MacroNewsRiskTheme(
                    theme=label,
                    weight=value,
                    sample_headlines=[
                        compliance_filter.sanitize_text(headline, max_length=120)
                        for headline in headlines
                    ],
                )
                for label, value, headlines in top_themes
                if value > 0
            ][:4]

            narrative = self._narrative(rates, ai, crypto, geo, earnings, macro_stress)

            return MacroNewsRiskSummary(
                rates_pressure=rates,
                ai_pressure=ai,
                crypto_pressure=crypto,
                geopolitics_pressure=geo,
                earnings_pressure=earnings,
                macro_stress=macro_stress,
                top_themes=top_payload,
                narrative=compliance_filter.sanitize_text(narrative, max_length=240),
            )
        except Exception:
            return MacroNewsRiskSummary(
                narrative=compliance_filter.sanitize_text(
                    "Macro / news risk engine unavailable; using fail-soft fallback."
                )
            )

    def _narrative(self, *pressures: float) -> str:
        labels = ("rates", "ai", "crypto", "geopolitics", "earnings", "macro_stress")
        pairs = sorted(zip(labels, pressures), key=lambda kv: kv[1], reverse=True)
        active = [label for label, value in pairs if value > 0]
        if not active:
            return "No dominant macro / news theme detected today."
        leaders = ", ".join(active[:3])
        return f"Dominant macro / news pressures: {leaders}."
