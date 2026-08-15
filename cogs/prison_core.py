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
CELL_RANK = {key: rank for rank, key in enumerate(CELL_KEYS)}

CHANNEL_NAMES = {
    "code":       "📜┃prison-code",       # read-only — لائحة المخالفات والمدد
    "holding":    "⛓️┃holding-cell",      # خفيف
    "block":      "🔒┃cell-block",        # متوسط
    "max":        "🚨┃maximum-security",  # قاسح
    "warden":     "🗣️┃warden-office",     # استئناف / تواصل
    "complaints": "📮┃complaint-desk",    # Warden + Owner — شكايات Holding Cell
    "visits":     "🧑‍🤝‍🧑┃visit-room",    # بانل طلب الزيارة — مفتوحة للعموم
    "visit_admin": "👮┃visit-control",     # الزيارات الجارية/الإغلاق — Warden + Owner فقط
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

# مجموع العقوبات اللي كيطلع السجين أوتوماتيكيا للدرجة الموالية.
# 24 ساعة متراكمة = بداية Cell Block | 30 يوم = Maximum Security.
# المخالفة المصنفة أصلاً Block/Max كتطلع مباشرة حتى إلا كانت مدتها أقل.
CELL_PENALTY_THRESHOLDS = {
    "block": 24 * HOUR,
    "max": 30 * DAY,
}


def cell_for_penalty(total_seconds: int, minimum_cell: str = "holding") -> str:
    """الزنزانة الدنيا الواجبة حسب مجموع العقوبات ونوع المخالفة."""
    target = minimum_cell if minimum_cell in CELL_RANK else "holding"
    if int(total_seconds) < 0:
        return "max"
    for cell, threshold in CELL_PENALTY_THRESHOLDS.items():
        if int(total_seconds) >= int(threshold) and CELL_RANK[cell] > CELL_RANK[target]:
            target = cell
    return target

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

# Discord كيسمح بـ50 روم فالكاتيكوري. كنحسبو الثابتين أوتوماتيكيا والباقي للانفرادي.
SOLITARY_MAX_ROOMS = 50 - len(CHANNEL_NAMES) - 1  # -1 هامش أمان

# مدة الانتظار بين طلبَي تدخل ديال نفس السجين. خمس دقايق كتحبس السبام
# بلا ما تخلي السجين عالق مدة طويلة إلا وقع مشكل جديد فعلاً.
COMPLAINT_COOLDOWN_SECONDS = 5 * MINUTE

# Discord User Select كيسمح بالبحث وسط لائحة كبيرة؛ كنحدّو غير عدد
# المشكي عليهم فنفس الطلب باش يبقى القرار واضح وقابل للمراجعة.
COMPLAINT_MAX_TARGETS = 10

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
    # الـID القصير كيضمن أن كل سجين عندو روم مميزة حتى إلا تشابهات السميات.
    return f"{SOLITARY_PREFIX}{cleaned}-{int(user_id) % 10000:04d}"


def complaint_route_for_cell(cell: str) -> str:
    """Holding يقدر يحسمها Warden/Owner؛ أي مستوى آخر Owner بوحدو."""
    return "warden" if str(cell) == "holding" else "owner"


# ═══════ الزيارات (Visits) ═══════
VISIT_DEFAULT_SECONDS = 15 * MINUTE
VISIT_MIN_SECONDS = 3 * MINUTE
VISIT_MAX_SECONDS = 60 * MINUTE
VISIT_INVITE_TIMEOUT_SECONDS = 5 * MINUTE
VISIT_CHANNEL_PREFIX = "💬┃visit-"


def visit_channel_name(display_name: str, user_id: int) -> str:
    """سمية فويس شانيل الزيارة المؤقتة، مبنية على اسم السجين."""
    cleaned = re.sub(r"[^a-zA-Z0-9\-]+", "-", str(display_name or "")).strip("-").lower()
    cleaned = re.sub(r"-{2,}", "-", cleaned)[:20].strip("-")
    if not cleaned:
        cleaned = f"inmate-{int(user_id) % 100000}"
    return f"{VISIT_CHANNEL_PREFIX}{cleaned}"


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
        "complaints": {},    # complaint_id → {author, targets[], cell, reason, ...}
        "complaint_seq": 0,
        "complaint_cooldown": {},  # user_id → timestamp آخر شكاية
        "cell_help_message_ids": {key: 0 for key in CELL_KEYS},
        # ── اللوحة العامة ──
        "wanted_channel_id": 0,
        "wanted_message_id": 0,
        # ── فويس شانيلز الزنازن (نفس سمية الروم النصية) ──
        "voice_channels": {key: 0 for key in CELL_KEYS},
        # ── الزيارات ──
        "visits": {},         # visit_id → record
        "visit_seq": 0,
        "visits_message_id": 0,
        "visits_admin_message_id": 0,
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
        record.setdefault("voice_channels", {})
        for key in CELL_KEYS:
            record["voice_channels"].setdefault(key, 0)
        record.setdefault("cell_help_message_ids", {})
        for key in CELL_KEYS:
            record["cell_help_message_ids"].setdefault(key, 0)
        record.setdefault("visits", {})
        record.setdefault("visit_seq", 0)
        record.setdefault("visits_message_id", 0)
        record.setdefault("visits_admin_message_id", 0)
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
            "penalty_seconds_total": int(seconds),
            "offense": offense_key,
            "reason": (reason or "ما ذكرش سبب")[:400],
            "cell": cell if cell in CELL_KEYS else "holding",
            "roles": [int(r) for r in roles],
            "nick": nick,
            "by": int(actor_id),
            "cell_message_id": 0,
            "extended": [],
            "discipline_log": [
                {
                    "at": started,
                    "offense": offense_key,
                    "reason": (reason or "ما ذكرش سبب")[:400],
                    "seconds": int(seconds),
                    "cell": cell if cell in CELL_KEYS else "holding",
                    "by": int(actor_id),
                }
            ],
            "cell_history": [
                {
                    "at": started,
                    "from": None,
                    "to": cell if cell in CELL_KEYS else "holding",
                    "reason": (reason or "الحكم الأول")[:400],
                    "by": int(actor_id),
                }
            ],
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

    # ───── فويس شانيلز الزنازن ─────

    def voice_channels(self, guild_id: int) -> dict[str, int]:
        return self.guild(guild_id).setdefault("voice_channels", {})

    def voice_channel_id(self, guild_id: int, key: str) -> int:
        return int(self.voice_channels(guild_id).get(key) or 0)

    def set_voice_channel(self, guild_id: int, key: str, channel_id: int) -> None:
        self.voice_channels(guild_id)[key] = int(channel_id)
        self.save()

    # ───── الزيارات ─────

    def visits(self, guild_id: int) -> dict[str, dict]:
        return self.guild(guild_id).setdefault("visits", {})

    def visit(self, guild_id: int, visit_id) -> Optional[dict]:
        return self.visits(guild_id).get(str(visit_id))

    def active_visit_for_inmate(self, guild_id: int, user_id: int) -> Optional[dict]:
        uid = int(user_id)
        for record in self.visits(guild_id).values():
            if int(record.get("prisoner_id", 0) or 0) == uid and record.get("status") in ("pending", "active"):
                return record
        return None

    def active_visit_for_visitor(self, guild_id: int, user_id: int) -> Optional[dict]:
        uid = int(user_id)
        for record in self.visits(guild_id).values():
            if int(record.get("visitor_id", 0) or 0) == uid and record.get("status") in ("pending", "active"):
                return record
        return None

    def next_visit_id(self, guild_id: int) -> str:
        record = self.guild(guild_id)
        record["visit_seq"] = int(record.get("visit_seq", 0) or 0) + 1
        return str(record["visit_seq"])

    def add_visit(
        self,
        guild_id: int,
        *,
        prisoner_id: int,
        visitor_id: int,
        seconds: int,
        by: int,
    ) -> dict:
        vid = self.next_visit_id(guild_id)
        record = {
            "id": vid,
            "prisoner_id": int(prisoner_id),
            "visitor_id": int(visitor_id),
            "channel_id": 0,
            "invite_channel_id": 0,
            "seconds": int(seconds),
            "since": 0,
            "until": 0,
            "created": now_ts(),
            "by": int(by),
            "status": "pending",   # pending → active → (كتمسح ملي تسالي)
        }
        self.visits(guild_id)[vid] = record
        self.save()
        return record

    def set_visit_invite_channel(self, guild_id: int, visit_id, channel_id: int) -> Optional[dict]:
        record = self.visit(guild_id, visit_id)
        if record is None:
            return None
        record["invite_channel_id"] = int(channel_id)
        self.save()
        return record

    def start_visit(self, guild_id: int, visit_id, *, channel_id: int, seconds: int) -> Optional[dict]:
        record = self.visit(guild_id, visit_id)
        if record is None:
            return None
        record["channel_id"] = int(channel_id)
        record["status"] = "active"
        record["since"] = now_ts()
        record["until"] = now_ts() + int(seconds)
        self.save()
        return record

    def remove_visit(self, guild_id: int, visit_id) -> Optional[dict]:
        record = self.visits(guild_id).pop(str(visit_id), None)
        if record is not None:
            self.save()
        return record

    def expired_visits(self, guild_id: int) -> list[tuple[str, dict]]:
        return [
            (vid, record)
            for vid, record in list(self.visits(guild_id).items())
            if record.get("status") == "active" and now_ts() >= int(record.get("until", 0) or 0)
        ]

    def expired_pending_visits(self, guild_id: int) -> list[tuple[str, dict]]:
        """دعوات بقات معلّقة أكثر من مهلة القبول (ومنها اللي فات عليها restart)."""
        return [
            (vid, record)
            for vid, record in list(self.visits(guild_id).items())
            if record.get("status") == "pending"
            and now_ts() >= int(record.get("created", 0) or 0) + VISIT_INVITE_TIMEOUT_SECONDS
        ]

    # ───── الشكايات ─────

    def complaints(self, guild_id: int) -> dict[str, dict]:
        entries = self.guild(guild_id).setdefault("complaints", {})
        changed = False
        # Migration ديال الشكايات القديمة اللي كان فيها target واحد بلا cell snapshot.
        for record in entries.values():
            targets = self.complaint_target_ids(record)
            if targets and record.get("targets") != targets:
                record["targets"] = targets
                changed = True
            if targets and int(record.get("target", 0) or 0) != targets[0]:
                record["target"] = targets[0]  # توافق مع النسخ القديمة
                changed = True
            if record.get("cell") not in CELL_KEYS:
                record["cell"] = (
                    "holding" if record.get("route") == "warden" else "block"
                )
                changed = True
        if changed:
            self.save()
        return entries

    @staticmethod
    def complaint_target_ids(record: dict) -> list[int]:
        """كترد لائحة targets نظيفة وكتفهم حتى صيغة target القديمة."""
        raw_targets = record.get("targets")
        if not isinstance(raw_targets, (list, tuple, set)):
            raw_targets = [record.get("target")]
        result: list[int] = []
        for raw in raw_targets:
            try:
                target_id = int(raw or 0)
            except (TypeError, ValueError):
                continue
            if target_id > 0 and target_id not in result:
                result.append(target_id)
        return result

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
        reason: str,
        route: str,
        cell: str = "holding",
        target_ids: Optional[list[int]] = None,
        target_id: int = 0,
    ) -> dict:
        targets = self.complaint_target_ids(
            {"targets": target_ids if target_ids is not None else [target_id]}
        )[:COMPLAINT_MAX_TARGETS]
        if not targets:
            raise ValueError("complaint requires at least one target")
        record_guild = self.guild(guild_id)
        record_guild["complaint_seq"] = int(record_guild.get("complaint_seq", 0) or 0) + 1
        cid = str(record_guild["complaint_seq"])
        record = {
            "id": cid,
            "author": int(author_id),
            "target": targets[0],       # توافق مع البيانات/الإضافات القديمة
            "targets": targets,
            "cell": cell if cell in CELL_KEYS else "holding",
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
        self,
        guild_id: int,
        complaint_id: str,
        *,
        status: str,
        handler_id: int,
        result: Optional[dict] = None,
    ) -> Optional[dict]:
        record = self.complaints(guild_id).get(str(complaint_id))
        if record is None:
            return None
        record["status"] = status
        record["handled_by"] = int(handler_id)
        record["handled_at"] = now_ts()
        if result is not None:
            record["result"] = result
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
