# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║  cogs/prison_core.py — 🔒 نواة نظام السجن (بلا Discord UI)  ║
═══════════════════════════════════════════════════════

هاد الملف فيه:
  • أسماء الرومز/الرولات (بالإنجليزية) — سهل التعديل من فوق
  • كتالوج المخالفات + المدة ديال كل وحدة
  • طبقة التخزين (prison.json) بكتابة ذرية عبر storage.JsonStore
  • دوال الوقت (تنسيق المدة، parsing ديال "7d" / "12h" ...)

⚠️ ما كاين حتى تفاعل مع Discord هنا — غير data + منطق خالص،
   باش يكون سهل نختبروه ونبدلو فيه بلا ما نكسرو البوت.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

from storage import JsonStore

# ═══════════════════════════════════════════════════════
# ║                  1. السميات (English)                ║
# ═══════════════════════════════════════════════════════

PRISON_CATEGORY_NAME = "🔒 PRISON"

# المفتاح الداخلي → (اسم الروم، الوصف)
CELL_KEYS = ("holding", "block", "max")

CHANNEL_NAMES = {
    "code":       "📜┃prison-code",       # read-only — لائحة المخالفات والمدد
    "holding":    "⛓️┃holding-cell",      # خفيف
    "block":      "🔒┃cell-block",        # متوسط
    "max":        "🚨┃maximum-security",  # قاسح
    "warden":     "🗣️┃warden-office",     # استئناف / تواصل
    "complaints": "📮┃complaint-desk",    # Warden + Owner — الشكايات الخفيفة
    "log":        "📋┃prison-log",        # Owner بوحدو
}

# اللوحة العامة — **برا** كاتيكوري السجن، كيشوفها كاع السيرفر (read-only).
WANTED_BOARD_CHANNEL_NAME = "📢┃wanted-board"

# سميات رومز الحبس الانفرادي
SOLITARY_PREFIX = "🔗┃solitary-"

PRISONER_ROLE_NAME = "Prisoner"
WARDEN_ROLE_NAME = "Warden"

PRISONER_ROLE_COLOR = 0x36393F  # رمادي غامق — بحال ما كاين
WARDEN_ROLE_COLOR = 0x1ABC9C

# ═══════════════════════════════════════════════════════
# ║                  2. كتالوج المخالفات                  ║
# ═══════════════════════════════════════════════════════

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

# severity: 1 = خفيف (Warden يقدر) | 2 = متوسط | 3 = قاسح (Owner بوحدو)
DEFAULT_OFFENSES: dict[str, dict[str, Any]] = {
    "spam": {
        "label": "Spam / Flood",
        "seconds": 30 * MINUTE,
        "cell": "holding",
        "severity": 1,
    },
    "insult": {
        "label": "قلة الأدب / سب",
        "seconds": 2 * HOUR,
        "cell": "holding",
        "severity": 1,
    },
    "mention_spam": {
        "label": "Mention Spam",
        "seconds": 6 * HOUR,
        "cell": "holding",
        "severity": 1,
    },
    "mute": {
        "label": "كتم (Mute سابقاً)",
        "seconds": 1 * HOUR,
        "cell": "holding",
        "severity": 1,
    },
    "warns": {
        "label": "تراكم التحذيرات",
        "seconds": 3 * HOUR,
        "cell": "holding",
        "severity": 1,
    },
    "links": {
        "label": "روابط ممنوعة / إعلانات",
        "seconds": 1 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "temp_bypass": {
        "label": "تجاوز Block ديال Temp Room",
        "seconds": 12 * HOUR,
        "cell": "block",
        "severity": 2,
    },
    "nsfw": {
        "label": "محتوى NSFW",
        "seconds": 7 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "kick": {
        "label": "طرد (Kick سابقاً)",
        "seconds": 3 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "raid": {
        "label": "Raid / محاولة تخريب",
        "seconds": 30 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "ban": {
        "label": "حظر (Ban سابقاً)",
        "seconds": 90 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "severe": {
        "label": "مخالفة جسيمة متكررة",
        "seconds": 365 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "manual": {
        "label": "حكم يدوي من الإدارة",
        "seconds": 1 * HOUR,
        "cell": "holding",
        "severity": 1,
    },
}

# ═══════ الحبس الانفرادي (Solitary) ═══════
SOLITARY_DEFAULT_SECONDS = 2 * HOUR
SOLITARY_MAX_SECONDS = 24 * HOUR

# Discord كيسمح بـ50 روم فالكاتيكوري. عندنا 7 ثابتين → الباقي للانفرادي.
SOLITARY_MAX_ROOMS = 50 - len(CHANNEL_NAMES) - 1  # -1 هامش أمان

# مدة الانتظار بين شكايتين ديال نفس السجين
COMPLAINT_COOLDOWN_SECONDS = 30 * MINUTE

# أقصى شكايات معلقة فنفس الوقت
COMPLAINT_MAX_PENDING = 25


def solitary_channel_name(display_name: str, user_id: int) -> str:
    """
    كتصاوب سمية صالحة لروم Discord من اسم السجين.
    الحروف العربية/الرموز كيطيحو فسميات الرومز، لهذا كاين fallback على الـID.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\-]+", "-", str(display_name or "")).strip("-").lower()
    cleaned = re.sub(r"-{2,}", "-", cleaned)[:20].strip("-")
    if not cleaned:
        cleaned = f"inmate-{int(user_id) % 100000}"
    return f"{SOLITARY_PREFIX}{cleaned}"


# أقصى ما يقدر يدير الـ Warden (الشرطة): زنزانة holding + 12 ساعة.
WARDEN_MAX_SECONDS = 12 * HOUR
WARDEN_ALLOWED_CELLS = ("holding",)
WARDEN_ALLOWED_SEVERITY = 1

# سقف عام باش حتى غلطة كتابية ما تدير حبس ديال 100 عام.
MAX_SENTENCE_SECONDS = 3650 * DAY


# ═══════════════════════════════════════════════════════
# ║                  3. دوال الوقت                        ║
# ═══════════════════════════════════════════════════════

_DURATION_PATTERN = re.compile(r"(\d+)\s*([smhdwSMHDW])")

_UNIT_SECONDS = {
    "s": 1,
    "m": MINUTE,
    "h": HOUR,
    "d": DAY,
    "w": 7 * DAY,
}


def parse_duration(raw: Any) -> Optional[int]:
    """كتحول '7d' / '12h30m' / '90' (دقائق) لثواني. كترجع None إلا ماكانش صالح."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None

    if text in {"perm", "permanent", "forever", "دائم", "مؤبد"}:
        return -1

    matches = _DURATION_PATTERN.findall(text)
    if matches:
        total = 0
        for amount, unit in matches:
            total += int(amount) * _UNIT_SECONDS[unit.lower()]
        return min(total, MAX_SENTENCE_SECONDS) if total > 0 else None

    # رقم خاوي = دقائق
    if text.isdigit():
        total = int(text) * MINUTE
        return min(total, MAX_SENTENCE_SECONDS) if total > 0 else None

    return None


def format_duration(seconds: int) -> str:
    """ثواني → نص بالدارجة: '3 أيام و 4 سوايع'."""
    seconds = int(seconds)
    if seconds < 0:
        return "مؤبّد ♾️"
    if seconds < 60:
        return f"{seconds} ثانية"

    units = (
        (DAY, "يوم", "أيام"),
        (HOUR, "ساعة", "سوايع"),
        (MINUTE, "دقيقة", "دقايق"),
    )
    parts: list[str] = []
    remaining = seconds
    for size, singular, plural in units:
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value} {singular if value == 1 else plural}")
        if len(parts) == 2:
            break
    return " و ".join(parts) if parts else "أقل من دقيقة"


def now_ts() -> int:
    return int(time.time())


def remaining_seconds(record: dict) -> int:
    """كم باقي ليه. -1 = مؤبد. 0 = سالا."""
    until = int(record.get("until", 0) or 0)
    if until < 0:
        return -1
    return max(0, until - now_ts())


def is_expired(record: dict) -> bool:
    until = int(record.get("until", 0) or 0)
    if until < 0:
        return False
    return now_ts() >= until


# ═══════════════════════════════════════════════════════
# ║                  4. طبقة التخزين                      ║
# ═══════════════════════════════════════════════════════

def _blank_guild() -> dict:
    return {
        "category_id": 0,
        "channels": {key: 0 for key in CHANNEL_NAMES},
        "roles": {"prisoner": 0, "warden": 0},
        "board_message_id": 0,
        "code_message_id": 0,
        "offenses": {},      # overrides ديال الاونر فوق DEFAULT_OFFENSES
        "inmates": {},       # user_id → record
        "history": [],       # آخر 200 حكم
        "case_seq": 0,
        # ── الحبس الانفرادي ──
        "solitary": {},      # user_id → {channel_id, until, reason, by, cell}
        # ── الشكايات ──
        "complaints": {},    # complaint_id → record
        "complaint_seq": 0,
        "complaint_cooldown": {},  # user_id → timestamp آخر شكاية
        # ── اللوحة العامة ──
        "wanted_channel_id": 0,
        "wanted_message_id": 0,
    }


class PrisonStore:
    """واجهة نظيفة فوق prison.json."""

    MAX_HISTORY = 200

    def __init__(self, filename: str = "prison.json"):
        self._db = JsonStore(filename, default={"guilds": {}})
        if not isinstance(self._db.data, dict):
            self._db.data = {"guilds": {}}
        self._db.data.setdefault("guilds", {})

    # ───── أساسيات ─────

    def guild(self, guild_id: int) -> dict:
        guilds = self._db.data.setdefault("guilds", {})
        record = guilds.setdefault(str(int(guild_id)), _blank_guild())
        # migration آمن: أي مفتاح جديد كيتزاد بلا ما يمسح القديم
        blank = _blank_guild()
        for key, value in blank.items():
            record.setdefault(key, value)
        for key in CHANNEL_NAMES:
            record["channels"].setdefault(key, 0)
        record["roles"].setdefault("prisoner", 0)
        record["roles"].setdefault("warden", 0)
        return record

    def save(self) -> bool:
        return self._db.save()

    # ───── المخالفات ─────

    def offenses(self, guild_id: int) -> dict[str, dict]:
        """الكتالوج النهائي = الافتراضي + تعديلات الاونر."""
        merged: dict[str, dict] = {}
        overrides = self.guild(guild_id).get("offenses", {}) or {}
        for key, base in DEFAULT_OFFENSES.items():
            entry = dict(base)
            entry.update(overrides.get(key, {}) or {})
            merged[key] = entry
        # مخالفات جديدة زادها الاونر
        for key, extra in overrides.items():
            if key not in merged and isinstance(extra, dict):
                merged[key] = {
                    "label": extra.get("label", key),
                    "seconds": int(extra.get("seconds", HOUR)),
                    "cell": extra.get("cell", "holding"),
                    "severity": int(extra.get("severity", 1)),
                }
        return merged

    def offense(self, guild_id: int, key: str) -> dict:
        catalogue = self.offenses(guild_id)
        return catalogue.get(key) or catalogue["manual"]

    def set_offense(self, guild_id: int, key: str, **changes) -> dict:
        record = self.guild(guild_id)
        overrides = record.setdefault("offenses", {})
        entry = overrides.setdefault(key, {})
        for field, value in changes.items():
            if value is not None:
                entry[field] = value
        self.save()
        return self.offense(guild_id, key)

    # ───── السجناء ─────

    def inmates(self, guild_id: int) -> dict[str, dict]:
        return self.guild(guild_id).setdefault("inmates", {})

    def inmate(self, guild_id: int, user_id: int) -> Optional[dict]:
        return self.inmates(guild_id).get(str(int(user_id)))

    def is_inmate(self, guild_id: int, user_id: int) -> bool:
        return str(int(user_id)) in self.inmates(guild_id)

    def next_case(self, guild_id: int) -> int:
        record = self.guild(guild_id)
        record["case_seq"] = int(record.get("case_seq", 0) or 0) + 1
        return record["case_seq"]

    def add_inmate(
        self,
        guild_id: int,
        user_id: int,
        *,
        seconds: int,
        offense_key: str,
        reason: str,
        cell: str,
        actor_id: int,
        roles: list[int],
        nick: Optional[str] = None,
    ) -> dict:
        started = now_ts()
        record = {
            "user_id": int(user_id),
            "case": self.next_case(guild_id),
            "since": started,
            "until": -1 if seconds < 0 else started + int(seconds),
            "sentence": int(seconds),
            "offense": offense_key,
            "reason": (reason or "ما ذكرش سبب")[:400],
            "cell": cell if cell in CELL_KEYS else "holding",
            "roles": [int(r) for r in roles],
            "nick": nick,
            "by": int(actor_id),
            "cell_message_id": 0,
            "extended": [],
        }
        self.inmates(guild_id)[str(int(user_id))] = record
        self.save()
        return record

    def update_inmate(self, guild_id: int, user_id: int, **changes) -> Optional[dict]:
        record = self.inmate(guild_id, user_id)
        if record is None:
            return None
        record.update(changes)
        self.save()
        return record

    def remove_inmate(
        self,
        guild_id: int,
        user_id: int,
        *,
        outcome: str = "released",
        actor_id: int = 0,
    ) -> Optional[dict]:
        record = self.inmates(guild_id).pop(str(int(user_id)), None)
        if record is not None:
            self.push_history(
                guild_id,
                {
                    "user_id": int(user_id),
                    "case": record.get("case"),
                    "offense": record.get("offense"),
                    "reason": record.get("reason"),
                    "since": record.get("since"),
                    "ended": now_ts(),
                    "outcome": outcome,
                    "by": int(actor_id),
                },
            )
            self.save()
        return record

    def expired_inmates(self, guild_id: int) -> list[tuple[int, dict]]:
        return [
            (int(uid), record)
            for uid, record in list(self.inmates(guild_id).items())
            if is_expired(record)
        ]

    # ───── الحبس الانفرادي ─────

    def solitary(self, guild_id: int) -> dict[str, dict]:
        return self.guild(guild_id).setdefault("solitary", {})

    def in_solitary(self, guild_id: int, user_id: int) -> Optional[dict]:
        return self.solitary(guild_id).get(str(int(user_id)))

    def add_solitary(
        self,
        guild_id: int,
        user_id: int,
        *,
        channel_id: int,
        seconds: int,
        reason: str,
        by: int,
        cell: str,
        complaint_id: int = 0,
    ) -> dict:
        record = {
            "user_id": int(user_id),
            "channel_id": int(channel_id),
            "since": now_ts(),
            "until": now_ts() + int(seconds),
            "reason": (reason or "—")[:400],
            "by": int(by),
            "cell": cell,
            "complaint": int(complaint_id),
        }
        self.solitary(guild_id)[str(int(user_id))] = record
        self.save()
        return record

    def remove_solitary(self, guild_id: int, user_id: int) -> Optional[dict]:
        record = self.solitary(guild_id).pop(str(int(user_id)), None)
        if record is not None:
            self.save()
        return record

    def expired_solitary(self, guild_id: int) -> list[tuple[int, dict]]:
        return [
            (int(uid), record)
            for uid, record in list(self.solitary(guild_id).items())
            if now_ts() >= int(record.get("until", 0) or 0)
        ]

    def solitary_count(self, guild_id: int) -> int:
        return len(self.solitary(guild_id))

    # ───── الشكايات ─────

    def complaints(self, guild_id: int) -> dict[str, dict]:
        return self.guild(guild_id).setdefault("complaints", {})

    def pending_complaints(self, guild_id: int) -> dict[str, dict]:
        return {
            cid: record
            for cid, record in self.complaints(guild_id).items()
            if record.get("status") == "pending"
        }

    def complaint_by_message(self, guild_id: int, message_id: int) -> Optional[tuple[str, dict]]:
        for cid, record in self.complaints(guild_id).items():
            if int(record.get("message_id", 0) or 0) == int(message_id):
                return cid, record
        return None

    def complaint_cooldown_left(self, guild_id: int, user_id: int) -> int:
        cooldowns = self.guild(guild_id).setdefault("complaint_cooldown", {})
        last = int(cooldowns.get(str(int(user_id)), 0) or 0)
        return max(0, (last + COMPLAINT_COOLDOWN_SECONDS) - now_ts())

    def add_complaint(
        self,
        guild_id: int,
        *,
        author_id: int,
        target_id: int,
        reason: str,
        route: str,
    ) -> dict:
        record_guild = self.guild(guild_id)
        record_guild["complaint_seq"] = int(record_guild.get("complaint_seq", 0) or 0) + 1
        cid = str(record_guild["complaint_seq"])
        record = {
            "id": cid,
            "author": int(author_id),
            "target": int(target_id),
            "reason": (reason or "—")[:500],
            "route": route,          # "warden" ولا "owner"
            "status": "pending",
            "created": now_ts(),
            "message_id": 0,
            "channel_id": 0,
            "handled_by": 0,
            "handled_at": 0,
        }
        self.complaints(guild_id)[cid] = record
        record_guild.setdefault("complaint_cooldown", {})[str(int(author_id))] = now_ts()
        # تنظيف: كنحتافظو غير بآخر 100 شكاية
        entries = self.complaints(guild_id)
        if len(entries) > 100:
            for key in sorted(entries, key=lambda k: int(entries[k].get("created", 0)))[:-100]:
                entries.pop(key, None)
        self.save()
        return record

    def resolve_complaint(
        self, guild_id: int, complaint_id: str, *, status: str, handler_id: int
    ) -> Optional[dict]:
        record = self.complaints(guild_id).get(str(complaint_id))
        if record is None:
            return None
        record["status"] = status
        record["handled_by"] = int(handler_id)
        record["handled_at"] = now_ts()
        self.save()
        return record

    # ───── السجل ─────

    def push_history(self, guild_id: int, entry: dict) -> None:
        history = self.guild(guild_id).setdefault("history", [])
        history.append(entry)
        if len(history) > self.MAX_HISTORY:
            del history[: len(history) - self.MAX_HISTORY]

    def history(self, guild_id: int, limit: int = 15) -> list[dict]:
        return list(reversed(self.guild(guild_id).get("history", [])))[:limit]

    def record_count(self, guild_id: int, user_id: int) -> int:
        """شحال من مرة تسجن هاد العضو قبل (سوابق)."""
        uid = int(user_id)
        past = sum(
            1
            for entry in self.guild(guild_id).get("history", [])
            if int(entry.get("user_id", 0) or 0) == uid
        )
        return past
