"""Push-state persistence backed by PostgreSQL.

Replaces the legacy `.ixai_push_state.json` file. Keeps the public
`should_send_push(portfolio_id, risk_score, top_risk) -> bool` contract
so existing callers (dashboard.py) are unaffected.

Fail-soft: any DB error is logged via `logger.exception` and the function
returns True (allow push). Over-pushing during a DB outage is preferred
over silently dropping risk alerts.
"""

from __future__ import annotations

import json
import logging
import time

from app.core.database import SessionLocal
from app.models.models import PushState

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 60 * 60 * 24  # 24 hours


def _serialise(risk_score: int, top_risk: str, timestamp: int) -> str:
    return json.dumps(
        {
            "risk_score": int(risk_score or 0),
            "top_risk": str(top_risk or ""),
            "timestamp": int(timestamp),
        }
    )


def _deserialise(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def should_send_push(portfolio_id: str, risk_score: int, top_risk: str) -> bool:
    key = str(portfolio_id)
    now = int(time.time())

    db = SessionLocal()
    try:
        record = db.query(PushState).filter(PushState.key == key).first()

        if record is None:
            record = PushState(key=key, value=_serialise(risk_score, top_risk, now))
            db.add(record)
            db.commit()
            return True

        last = _deserialise(record.value)
        last_score = int(last.get("risk_score") or 0)
        last_top = str(last.get("top_risk") or "")
        last_timestamp = int(last.get("timestamp") or 0)

        score_changed = abs(int(risk_score or 0) - last_score) >= 10
        risk_changed = str(top_risk or "") != last_top
        cooldown_passed = now - last_timestamp > COOLDOWN_SECONDS

        if score_changed or risk_changed or cooldown_passed:
            record.value = _serialise(risk_score, top_risk, now)
            db.commit()
            return True

        return False
    except Exception:
        logger.exception("push_state DB access failed; allowing push as fail-soft")
        try:
            db.rollback()
        except Exception:
            pass
        return True
    finally:
        try:
            db.close()
        except Exception:
            pass
