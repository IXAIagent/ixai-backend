import json
import os
import time

STATE_FILE = ".ixai_push_state.json"
COOLDOWN_SECONDS = 60 * 60 * 24  # 24 小時


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def should_send_push(portfolio_id: str, risk_score: int, top_risk: str):
    state = _load_state()
    now = int(time.time())

    key = f"{portfolio_id}"

    last = state.get(key)

    # 第一次一定發
    if not last:
        state[key] = {
            "risk_score": risk_score,
            "top_risk": top_risk,
            "timestamp": now,
        }
        _save_state(state)
        return True

    # === 判斷變化 ===
    score_changed = abs(risk_score - last["risk_score"]) >= 10
    risk_changed = top_risk != last["top_risk"]

    cooldown_passed = now - last["timestamp"] > COOLDOWN_SECONDS

    if score_changed or risk_changed or cooldown_passed:
        state[key] = {
            "risk_score": risk_score,
            "top_risk": top_risk,
            "timestamp": now,
        }
        _save_state(state)
        return True

    return False
