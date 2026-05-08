from __future__ import annotations

from app.services.resolver.candidates import (
    crypto_candidates,
    dedupe_candidates,
    fallback_candidate,
    normalize_asset_type,
    stock_candidates,
)


def _empty_result(input_text: str, asset_type: str | None, candidates: list[dict] | None = None) -> dict:
    return {
        "input": input_text,
        "canonical_symbol": None,
        "display_name": None,
        "asset_type": normalize_asset_type(asset_type) or asset_type,
        "market": None,
        "currency": None,
        "confidence": 0.0,
        "match_type": "not_found",
        "source": "resolver",
        "candidates": candidates or [],
    }


def _resolved_result(input_text: str, candidate: dict, candidates: list[dict] | None = None) -> dict:
    return {
        "input": input_text,
        "canonical_symbol": candidate.get("canonical_symbol"),
        "display_name": candidate.get("display_name"),
        "asset_type": candidate.get("asset_type"),
        "market": candidate.get("market"),
        "currency": candidate.get("currency"),
        "confidence": candidate.get("confidence"),
        "match_type": candidate.get("match_type"),
        "source": candidate.get("source"),
        "candidates": candidates or [],
    }


def _ambiguous_result(input_text: str, asset_type: str | None, candidates: list[dict]) -> dict:
    return {
        "input": input_text,
        "canonical_symbol": None,
        "display_name": None,
        "asset_type": normalize_asset_type(asset_type) or asset_type,
        "market": None,
        "currency": None,
        "confidence": 0.4,
        "match_type": "ambiguous",
        "source": "resolver",
        "candidates": candidates,
    }


def resolve_asset_candidates(input_text: str, asset_type: str | None = None) -> list[dict]:
    normalized_type = normalize_asset_type(asset_type)
    query = str(input_text or "").strip()
    if not query:
        return []

    candidates: list[dict] = []
    if normalized_type == "crypto":
        candidates.extend(crypto_candidates(query))
    elif normalized_type == "stock":
        candidates.extend(stock_candidates(query))
    else:
        candidates.extend(stock_candidates(query))
        candidates.extend(crypto_candidates(query))

    if not candidates:
        fallback = fallback_candidate(query, normalized_type)
        if fallback:
            candidates.append(fallback)

    return dedupe_candidates(candidates)


def resolve_asset(input_text: str, asset_type: str | None = None) -> dict:
    query = str(input_text or "").strip()
    candidates = resolve_asset_candidates(query, asset_type=asset_type)
    if not query:
        return _empty_result(input_text, asset_type)
    if not candidates:
        return _empty_result(input_text, asset_type)

    top = candidates[0]
    if len(candidates) == 1:
        return _resolved_result(query, top)

    top_confidence = float(top.get("confidence", 0))
    second_confidence = float(candidates[1].get("confidence", 0))
    if top_confidence >= 0.95 and top_confidence > second_confidence:
        return _resolved_result(query, top, candidates=[])

    return _ambiguous_result(query, asset_type, candidates)

