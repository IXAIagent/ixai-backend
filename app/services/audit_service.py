"""v3D: minimal audit helper.

Logs important events via structured logger. Phase 1 stub — does not write
to a DB table. When v4 needs queryable audit, swap this implementation for
DB-backed and call sites remain unchanged.

Privacy: never log secrets, tokens, passwords, or full request bodies.
Metadata should be a small dict of business identifiers only.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


SUPPORTED_EVENTS = {
    "account_created",
    "portfolio_created",
    "portfolio_switched",
    "intelligence_viewed",
    "preferences_updated",
    "user_registered",
}


def log_event(
    event: str,
    *,
    user_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    """Record a business audit event via structured logging.

    Safe to call from anywhere; never raises. Unsupported event names still
    log (with `unknown_event` flag) so we don't lose visibility on typos.
    """
    try:
        extras: dict[str, Any] = {
            "audit_event": event,
            "user_id": user_id or "-",
        }
        if event not in SUPPORTED_EVENTS:
            extras["unknown_event"] = True
        if metadata:
            for key, value in metadata.items():
                if key in {"password", "token", "secret", "api_key"}:
                    continue
                extras[f"meta_{key}"] = value
        logger.info("audit", extra=extras)
    except Exception:
        # Audit must never break the calling flow.
        logger.exception("audit logging failed")
