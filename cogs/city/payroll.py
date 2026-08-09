# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config


def now_local() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def next_pay_at(cycle: str, from_dt: datetime | None = None) -> datetime | None:
    dt = from_dt or now_local()
    if cycle in {"hourly", "commission"}:
        return None
    if cycle == "daily":
        candidate = dt.replace(hour=config.DAILY_PAY_HOUR, minute=0, second=0, microsecond=0)
        if candidate <= dt:
            candidate += timedelta(days=1)
        return candidate
    # weekly
    days = (config.WEEKLY_PAY_WEEKDAY - dt.weekday()) % 7
    candidate = (dt + timedelta(days=days)).replace(hour=config.WEEKLY_PAY_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= dt:
        candidate += timedelta(days=7)
    return candidate


def pay_due(profile: dict, dt: datetime | None = None) -> bool:
    raw = profile.get("next_pay_at")
    if not raw:
        return False
    try:
        target = datetime.fromisoformat(raw)
        return (dt or now_local()) >= target
    except Exception:
        return False
