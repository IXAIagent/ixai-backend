"""v3D: per-user preferences endpoint.

Provides GET / PUT for the IXAI preference set. Each user has exactly one row
in `user_preferences`; the row is created on first GET (lazy init) so the
endpoint can never 404 for a valid user.

Permission contract: every operation is scoped to current_user.id. There is
no path for one user to read another user's preferences.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import User, UserPreference
from app.services.audit_service import log_event

router = APIRouter(prefix="/preferences", tags=["preferences"])
logger = logging.getLogger(__name__)


SUPPORTED_LOCALES = {"zh-TW", "en", "ja", "ko", "zh-CN"}
SUPPORTED_LANDING = {"dashboard", "portfolio", "fcn", "intelligence", "market", "alerts"}
SUPPORTED_ALERT_MODES = {"criticalOnly", "all", "dailyBrief"}
SUPPORTED_RISK_MODES = {"conservative", "balanced", "aggressive"}


class UserPreferenceRead(BaseModel):
    locale: str = "zh-TW"
    default_landing_page: str = "dashboard"
    compact_mode: bool = True
    terminal_mode: bool = True
    show_advanced_intelligence: bool = False
    alert_mode: str = "criticalOnly"
    notification_telegram: bool = False
    notification_email: bool = False
    risk_interpretation_mode: str = "balanced"
    active_account_id: Optional[str] = None
    active_portfolio_id: Optional[str] = None


class UserPreferenceUpdate(BaseModel):
    locale: Optional[str] = None
    default_landing_page: Optional[str] = None
    compact_mode: Optional[bool] = None
    terminal_mode: Optional[bool] = None
    show_advanced_intelligence: Optional[bool] = None
    alert_mode: Optional[str] = None
    notification_telegram: Optional[bool] = None
    notification_email: Optional[bool] = None
    risk_interpretation_mode: Optional[str] = None
    active_account_id: Optional[str] = Field(default=None)
    active_portfolio_id: Optional[str] = Field(default=None)


def _serialise(row: UserPreference) -> UserPreferenceRead:
    return UserPreferenceRead(
        locale=row.locale,
        default_landing_page=row.default_landing_page,
        compact_mode=row.compact_mode,
        terminal_mode=row.terminal_mode,
        show_advanced_intelligence=row.show_advanced_intelligence,
        alert_mode=row.alert_mode,
        notification_telegram=row.notification_telegram,
        notification_email=row.notification_email,
        risk_interpretation_mode=row.risk_interpretation_mode,
        active_account_id=row.active_account_id,
        active_portfolio_id=row.active_portfolio_id,
    )


def _get_or_create(db: Session, user_id: str) -> UserPreference:
    row = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if row is None:
        row = UserPreference(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=UserPreferenceRead)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_or_create(db, current_user.id)
    return _serialise(row)


@router.put("", response_model=UserPreferenceRead)
def update_preferences(
    payload: UserPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_or_create(db, current_user.id)

    if payload.locale is not None and payload.locale in SUPPORTED_LOCALES:
        row.locale = payload.locale
    if (
        payload.default_landing_page is not None
        and payload.default_landing_page in SUPPORTED_LANDING
    ):
        row.default_landing_page = payload.default_landing_page
    if payload.compact_mode is not None:
        row.compact_mode = bool(payload.compact_mode)
    if payload.terminal_mode is not None:
        row.terminal_mode = bool(payload.terminal_mode)
    if payload.show_advanced_intelligence is not None:
        row.show_advanced_intelligence = bool(payload.show_advanced_intelligence)
    if payload.alert_mode is not None and payload.alert_mode in SUPPORTED_ALERT_MODES:
        row.alert_mode = payload.alert_mode
    if payload.notification_telegram is not None:
        row.notification_telegram = bool(payload.notification_telegram)
    if payload.notification_email is not None:
        row.notification_email = bool(payload.notification_email)
    if (
        payload.risk_interpretation_mode is not None
        and payload.risk_interpretation_mode in SUPPORTED_RISK_MODES
    ):
        row.risk_interpretation_mode = payload.risk_interpretation_mode
    if payload.active_account_id is not None:
        row.active_account_id = payload.active_account_id or None
    if payload.active_portfolio_id is not None:
        # Detect portfolio switch for audit purposes.
        old_portfolio = row.active_portfolio_id
        new_portfolio = payload.active_portfolio_id or None
        row.active_portfolio_id = new_portfolio
        if old_portfolio != new_portfolio and new_portfolio:
            log_event(
                "portfolio_switched",
                user_id=current_user.id,
                metadata={"to_portfolio_id": new_portfolio, "from_portfolio_id": old_portfolio},
            )

    db.commit()
    db.refresh(row)
    return _serialise(row)
