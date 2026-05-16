"""v4A: Risk propagation engine.

Derives possible risk chains from the unified engine outputs. Every chain
is rendered as a list of nodes plus a compliance-safe explanation.
"""

from __future__ import annotations

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    ExposureGraphSummary,
    FCNSystemicRiskSummary,
    PortfolioDriftSummary,
    RiskPropagationChain,
    RiskPropagationSummary,
)


class RiskPropagationEngine:
    def analyse(
        self,
        exposure: ExposureGraphSummary,
        concentration: ConcentrationSummary,
        fcn_risk: FCNSystemicRiskSummary,
        drift: PortfolioDriftSummary,
    ) -> RiskPropagationSummary:
        try:
            chains: list[RiskPropagationChain] = []

            # AI / chip → FCN worst-of → concentration
            ai_in_themes = "AI_CHIP" in exposure.dominant_themes or any(
                sym in exposure.fcn_linked_symbols
                for sym in ("NVDA", "TSM", "2330.TW", "AVGO", "AMD")
            )
            if ai_in_themes and fcn_risk.risk_level in {"watch", "elevated", "critical"}:
                chain = ["AI/chip basket pressure"]
                if exposure.fcn_linked_symbols:
                    chain.append(
                        "FCN worst-of underlying pressure ("
                        + ", ".join(exposure.fcn_linked_symbols[:3])
                        + ")"
                    )
                chain.append(
                    f"FCN systemic risk: {fcn_risk.risk_level}"
                )
                if concentration.risk_level in {"elevated", "critical"}:
                    chain.append(f"Concentration risk: {concentration.risk_level}")
                chains.append(
                    RiskPropagationChain(
                        chain=chain,
                        explanation=compliance_filter.sanitize_text(
                            "An AI/chip drawdown can propagate to FCN worst-of underlyings, "
                            "which may amplify concentration risk. Continue to monitor.",
                            max_length=220,
                        ),
                    )
                )

            # Repeated underlying → KI cluster
            if exposure.repeated_underlyings and fcn_risk.ki_cluster_symbols:
                chains.append(
                    RiskPropagationChain(
                        chain=[
                            "Repeated FCN underlyings",
                            f"KI cluster ({', '.join(fcn_risk.ki_cluster_symbols[:3])})",
                            "Systemic FCN sensitivity",
                        ],
                        explanation=compliance_filter.sanitize_text(
                            "Shared underlyings across FCNs concentrate KI risk. "
                            "A move in those underlyings can affect multiple structures at once.",
                            max_length=220,
                        ),
                    )
                )

            # Concentration → drift
            if (
                concentration.risk_level in {"elevated", "critical"}
                and drift.concentration_drift == "INCREASING"
            ):
                chains.append(
                    RiskPropagationChain(
                        chain=[
                            f"{concentration.top_concentration_label or 'Concentration'} cluster",
                            "Rising concentration drift",
                            f"Portfolio risk_level: {concentration.risk_level}",
                        ],
                        explanation=compliance_filter.sanitize_text(
                            "Concentration is rising relative to the recent baseline; "
                            "this is a structural attention point rather than a market event.",
                            max_length=220,
                        ),
                    )
                )

            # Crypto-only chain when crypto bucket dominates
            if concentration.crypto_pct >= 20:
                chains.append(
                    RiskPropagationChain(
                        chain=[
                            "Crypto bucket weighting",
                            "Crypto volatility risk",
                            f"Concentration {concentration.risk_level}",
                        ],
                        explanation=compliance_filter.sanitize_text(
                            "Crypto exposure is meaningful; sharp moves there can dominate "
                            "short-term portfolio volatility. Continue to monitor.",
                            max_length=220,
                        ),
                    )
                )

            if not chains:
                return RiskPropagationSummary(
                    chains=[],
                    summary=compliance_filter.sanitize_text(
                        "No dominant risk propagation chain detected; continue to monitor."
                    ),
                )

            summary_text = " · ".join(c.chain[-1] for c in chains[:3])
            return RiskPropagationSummary(
                chains=chains[:4],
                summary=compliance_filter.sanitize_text(
                    f"Active chains: {summary_text}.", max_length=240
                ),
            )
        except Exception:
            return RiskPropagationSummary(
                chains=[],
                summary=compliance_filter.sanitize_text(
                    "Risk propagation engine unavailable; using fail-soft fallback."
                ),
            )
