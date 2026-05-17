from __future__ import annotations


def get_crypto_strategy_parts(asset_type: str | None) -> list[str]:
    """Split persisted crypto strategy strings without raising.

    Examples:
    - ``grid:long`` -> ["grid", "long"]
    - ``stablecoin_earn:30:5.5`` -> ["stablecoin_earn", "30", "5.5"]
    """
    try:
        raw = str(asset_type or "").strip().lower()
        if not raw:
            return ["spot"]
        parts = [part.strip() for part in raw.split(":")]
        return [part for part in parts if part] or ["spot"]
    except Exception:
        return ["spot"]


def get_crypto_base_type(asset_type: str | None) -> str:
    parts = get_crypto_strategy_parts(asset_type)
    return parts[0] if parts else "spot"
