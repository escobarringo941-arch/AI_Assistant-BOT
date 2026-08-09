# -*- coding: utf-8 -*-
from __future__ import annotations

from . import config


def parse_milestones(raw: str, budget: int) -> list[dict]:
    parts = [p.strip() for p in (raw or "").split("|") if p.strip()]
    parts = parts[:config.PROJECT_MAX_MILESTONES]
    if not parts:
        parts = ["التسليم النهائي"]
    count = len(parts)
    each = budget // count
    amounts = [each] * count
    amounts[-1] += budget - each * count
    return [
        {"index":i,"title":parts[i][:80],"amount":amounts[i],"status":"pending","delivery":"","submitted_at":None,"approved_at":None}
        for i in range(count)
    ]


def current_milestone(project: dict):
    for m in project.get("milestones", []) or []:
        if m.get("status") in {"pending","delivered"}:
            return m
    return None
