from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.models import FCNCouponSchedule, FCNPosition


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return value.replace(year=year, month=month, day=min(value.day, days[month - 1]))


def add_business_days(value: date, days: int) -> date:
    current = value
    remaining = max(0, days)
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def parse_date_list(raw: str | None) -> list[date]:
    if not raw:
        return []
    dates: list[date] = []
    for token in raw.replace("\n", ",").replace(";", ",").split(","):
        text = token.strip().strip('"')
        if not text:
            continue
        try:
            dates.append(date.fromisoformat(text))
        except ValueError:
            continue
    return dates


def build_fcn_schedule(
    start_date: date | None,
    tenor_months: int | None,
    frequency: str | None,
    payment_lag_days: int = 3,
    observation_dates: Iterable[date] | None = None,
    payment_dates: Iterable[date] | None = None,
) -> list[dict]:
    manual_observations = list(observation_dates or [])
    manual_payments = list(payment_dates or [])
    if manual_observations:
        return [
            {
                "period_index": index + 1,
                "observation_start_date": start_date,
                "observation_date": obs,
                "payment_date": manual_payments[index] if index < len(manual_payments) else add_business_days(obs, payment_lag_days),
                "status": "scheduled",
            }
            for index, obs in enumerate(manual_observations)
        ]

    if not start_date or not tenor_months or tenor_months <= 0:
        return []

    step = 3 if (frequency or "").lower().startswith("quarter") else 1
    rows = []
    period = 1
    for month_offset in range(step, tenor_months + 1, step):
        observation_date = add_months(start_date, month_offset)
        rows.append(
            {
                "period_index": period,
                "observation_start_date": start_date if period == 1 else add_months(start_date, month_offset - step),
                "observation_date": observation_date,
                "payment_date": add_business_days(observation_date, payment_lag_days),
                "status": "scheduled",
            }
        )
        period += 1
    return rows


def replace_fcn_schedule(
    db: Session,
    fcn: FCNPosition,
    payment_lag_days: int = 3,
) -> list[FCNCouponSchedule]:
    rows = build_fcn_schedule(
        start_date=fcn.issue_date,
        tenor_months=fcn.tenor_months,
        frequency=fcn.coupon_frequency,
        payment_lag_days=payment_lag_days,
        observation_dates=parse_date_list(fcn.observation_dates_json),
        payment_dates=parse_date_list(fcn.coupon_dates_json),
    )
    db.query(FCNCouponSchedule).filter(FCNCouponSchedule.fcn_position_id == fcn.id).delete()
    schedules = [
        FCNCouponSchedule(
            fcn_position_id=fcn.id,
            period_index=row["period_index"],
            observation_start_date=row["observation_start_date"],
            observation_date=row["observation_date"],
            payment_date=row["payment_date"],
            status=row["status"],
        )
        for row in rows
    ]
    for schedule in schedules:
        db.add(schedule)

    if schedules:
        fcn.next_observation_date = schedules[0].observation_date
        fcn.next_coupon_date = schedules[0].payment_date
    return schedules
