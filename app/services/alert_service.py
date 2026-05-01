from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Alert


def now_utc() -> datetime:
    return datetime.utcnow()


def build_alert_key(asset_class: str, asset_ref: str, title: str) -> tuple[str, str, str]:
    return (asset_class, asset_ref, title)


def get_open_alert(
    db: Session,
    portfolio_id: str,
    asset_class: str,
    asset_ref: str,
    title: str,
) -> Alert | None:
    return (
        db.query(Alert)
        .filter(
            Alert.portfolio_id == portfolio_id,
            Alert.asset_class == asset_class,
            Alert.asset_ref == asset_ref,
            Alert.title == title,
            Alert.status == "open",
        )
        .first()
    )


def ensure_open_alert(
    db: Session,
    portfolio_id: str,
    asset_class: str,
    asset_ref: str,
    severity: str,
    title: str,
    message: str,
) -> tuple[Alert, bool]:
    existing = get_open_alert(db, portfolio_id, asset_class, asset_ref, title)
    if existing:
        existing.severity = severity
        existing.level = severity
        existing.message = message
        existing.status = "open"
        existing.triggered_at = now_utc()
        return existing, False

    alert = Alert(
        portfolio_id=portfolio_id,
        asset_class=asset_class,
        asset_ref=asset_ref,
        severity=severity,
        level=severity,
        title=title,
        message=message,
        status="open",
        triggered_at=now_utc(),
    )
    db.add(alert)
    return alert, True


def close_resolved_alerts(
    db: Session,
    portfolio_id: str,
    active_keys: set[tuple[str, str, str]],
) -> list[Alert]:
    open_alerts = db.query(Alert).filter(Alert.portfolio_id == portfolio_id, Alert.status == "open").all()
    closed: list[Alert] = []
    for alert in open_alerts:
        key = (alert.asset_class or "", alert.asset_ref or "", alert.title or "")
        if key not in active_keys:
            alert.status = "closed"
            closed.append(alert)
    return closed
