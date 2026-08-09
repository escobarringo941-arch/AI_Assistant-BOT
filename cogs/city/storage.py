# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import games_config as root_cfg


class CityStore:
    """Small atomic JSON store dedicated to GGMW9 CITY.

    Economy balances stay in cogs/economy.py. This file stores only CITY state:
    CVs, employment, orders, projects, invoices, payslips and UI/channel IDs.
    """

    def __init__(self, filename: str = "ggmw9_city.json"):
        base = Path(getattr(root_cfg, "DATA_DIR", "/app/data"))
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / filename
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                value = json.load(f)
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            print(f"[CITY] ⚠️ failed to load {self.path}: {exc}")
            return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(prefix="city_", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def guild(self, guild_id: int) -> dict:
        g = self.data.setdefault(str(guild_id), {})
        g.setdefault("setup", {})
        g.setdefault("profiles", {})
        g.setdefault("orders", {})
        g.setdefault("projects", {})
        g.setdefault("invoices", {})
        g.setdefault("payslips", {})
        g.setdefault("employee_week", {})
        g.setdefault("counters", {"order": 1, "project": 1, "invoice": 1, "payslip": 1})
        return g

    def profile(self, guild_id: int, user_id: int, defaults: dict | None = None) -> dict:
        profiles = self.guild(guild_id).setdefault("profiles", {})
        p = profiles.setdefault(str(user_id), {})
        for k, v in (defaults or {}).items():
            if k not in p:
                p[k] = v.copy() if isinstance(v, dict) else list(v) if isinstance(v, list) else v
        return p

    def next_id(self, guild_id: int, key: str, prefix: str) -> str:
        g = self.guild(guild_id)
        counters = g.setdefault("counters", {})
        n = int(counters.get(key, 1) or 1)
        counters[key] = n + 1
        self.save()
        return f"{prefix}-{n:06d}"
