# -*- coding: utf-8 -*-
"""GGMW9 CITY configuration.

All monetary amounts are INTERNAL CENTS because the central Economy cog stores
USD as integer cents. Time source-of-truth is Africa/Casablanca.
"""
from __future__ import annotations

import games_config as root_cfg

TIMEZONE = getattr(root_cfg, "CITY_TIMEZONE", "Africa/Casablanca")
CATEGORY_NAME = getattr(root_cfg, "CITY_CATEGORY_NAME", "🏙️・GGMW9 CITY")
CHANNEL_NAMES = dict(getattr(root_cfg, "CITY_CHANNEL_NAMES", {
    "career_center": "💼・career-center",
    "services_market": "🛍️・services-market",
    "projects_board": "🏗️・projects-board",
    "job_market": "📊・job-market",
    "city_alerts": "🔔・city-alerts",
}))

TICK_SECONDS = int(getattr(root_cfg, "CITY_TICK_SECONDS", 60))
JOB_MARKET_REFRESH_MINUTES = int(getattr(root_cfg, "CITY_JOB_MARKET_REFRESH_MINUTES", 10))
ALERT_DELETE_SECONDS = int(getattr(root_cfg, "CITY_ALERT_DELETE_SECONDS", 1800))
JOB_CHANGE_COOLDOWN_HOURS = int(getattr(root_cfg, "CITY_JOB_CHANGE_COOLDOWN_HOURS", 24))
PENDING_ORDER_HOURS = int(getattr(root_cfg, "CITY_PENDING_ORDER_HOURS", 3))
DELIVERED_AUTO_RELEASE_HOURS = int(getattr(root_cfg, "CITY_DELIVERED_AUTO_RELEASE_HOURS", 12))
ACCEPTED_OVERDUE_HOURS = int(getattr(root_cfg, "CITY_ACCEPTED_OVERDUE_HOURS", 48))
SERVICE_TAX_BPS = int(getattr(root_cfg, "CITY_SERVICE_TAX_BPS", 500))
PROJECT_TAX_BPS = int(getattr(root_cfg, "CITY_PROJECT_TAX_BPS", 300))
PROJECT_MIN_BUDGET = int(getattr(root_cfg, "CITY_PROJECT_MIN_BUDGET", 500))
PROJECT_MAX_DEADLINE_DAYS = int(getattr(root_cfg, "CITY_PROJECT_MAX_DEADLINE_DAYS", 30))
PROJECT_MAX_MILESTONES = int(getattr(root_cfg, "CITY_PROJECT_MAX_MILESTONES", 3))
EMPLOYEE_WEEK_BONUS = int(getattr(root_cfg, "CITY_EMPLOYEE_WEEK_BONUS", 2500))

# Salary windows in Casablanca local time.
DAILY_PAY_HOUR = 20
WEEKLY_PAY_WEEKDAY = 4  # Friday, Monday=0
WEEKLY_PAY_HOUR = 18

# Shifts are real-time, but kept playable for a Discord community.
SHIFT_OPTIONS_MINUTES = (30, 60, 90)
SHIFT_MIN_CHECKIN_MINUTES = 10
SHIFT_MAX_PER_DAY = 4

# Member-facing notification defaults.
DEFAULT_NOTIFICATIONS = {
    "dm": True,
    "fallback": True,
    "jobs": True,
    "orders": True,
    "shifts": True,
    "payments": True,
    "promotions": True,
    "projects": True,
}

LANGUAGES = {"darija", "en", "fr"}

# Public channel topics. Panels are used instead of member chat to keep the
# category clean and professional.
CHANNEL_TOPICS = {
    "career_center": "GGMW9 CITY • CV, job matching, career, shifts, salary, promotions and payslips.",
    "services_market": "GGMW9 CITY • Buy real member services through escrow and invoices.",
    "projects_board": "GGMW9 CITY • Fund projects, recruit members, approve milestones and release escrow.",
    "job_market": "GGMW9 CITY • Read-only live labour market, demand, salaries and employee highlights.",
    "city_alerts": "GGMW9 CITY • Private-notification fallback. Alerts auto-delete and never expose salary/order details.",
}

# ---------------------------------------------------------------------
# Fictional Underground expansion
# ---------------------------------------------------------------------
UNDERGROUND_CATEGORY_NAME = getattr(root_cfg, "CITY_UNDERGROUND_CATEGORY_NAME", "🌑・THE UNDERGROUND")
UNDERGROUND_CHANNEL_NAMES = dict(getattr(root_cfg, "CITY_UNDERGROUND_CHANNEL_NAMES", {
    "shadow_gate": "🕳️・shadow-gate",
    "black_market": "🗡️・black-market",
    "crews": "👥・crews",
    "contracts": "📜・contracts",
    "operations": "🏦・operations",
}))
UNDERGROUND_INVITE_HOURS = int(getattr(root_cfg, "CITY_UNDERGROUND_INVITE_HOURS", 24))
UNDERGROUND_MISSION_COOLDOWN_MINUTES = int(getattr(root_cfg, "CITY_UNDERGROUND_MISSION_COOLDOWN_MINUTES", 45))
UNDERGROUND_HEAT_DECAY_HOURS = int(getattr(root_cfg, "CITY_UNDERGROUND_HEAT_DECAY_HOURS", 6))
UNDERGROUND_CREW_CREATE_COST = int(getattr(root_cfg, "CITY_UNDERGROUND_CREW_CREATE_COST", 4000))
UNDERGROUND_HEIST_PREP_COST = int(getattr(root_cfg, "CITY_UNDERGROUND_HEIST_PREP_COST", 5000))
UNDERGROUND_HEIST_COOLDOWN_HOURS = int(getattr(root_cfg, "CITY_UNDERGROUND_HEIST_COOLDOWN_HOURS", 120))
UNDERGROUND_HEIST_MIN_CREW = int(getattr(root_cfg, "CITY_UNDERGROUND_HEIST_MIN_CREW", 3))
UNDERGROUND_HEIST_MIN_REP = int(getattr(root_cfg, "CITY_UNDERGROUND_HEIST_MIN_REP", 200))
UNDERGROUND_HEIST_MIN_TREASURY = int(getattr(root_cfg, "CITY_UNDERGROUND_HEIST_MIN_TREASURY", 25000))
UNDERGROUND_MARKET_TAX_BPS = int(getattr(root_cfg, "CITY_UNDERGROUND_MARKET_TAX_BPS", 650))
UNDERGROUND_CREW_HEIST_SHARE_BPS = int(getattr(root_cfg, "CITY_UNDERGROUND_CREW_HEIST_SHARE_BPS", 2500))
UNDERGROUND_CREW_INVITE_HOURS = int(getattr(root_cfg, "CITY_UNDERGROUND_CREW_INVITE_HOURS", 24))
