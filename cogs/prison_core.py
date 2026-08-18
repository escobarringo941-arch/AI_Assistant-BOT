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
INMATE_STATS_VERSION = 2

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

# سميات رومز ورولات الحبس الانفرادي (واحد مستقل لكل Discord ID)
SOLITARY_PREFIX = "🔗┃solitary-"
SOLITARY_ROLE_PREFIX = "Solitary"

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
        "label": "محتوى إباحي / NSFW",
        "seconds": 7 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "harassment": {
        "label": "تحرش / تنمر / تهديد",
        "seconds": 3 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "doxxing": {
        "label": "نشر معلومات شخصية / Doxxing",
        "seconds": 90 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "scam": {
        "label": "احتيال / انتحال صفة",
        "seconds": 30 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "security_bypass": {
        "label": "محاولة تجاوز حماية البوت",
        "seconds": 30 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "ban_evasion": {
        "label": "التهرب من الحظر / حساب بديل",
        "seconds": 90 * DAY,
        "cell": "max",
        "severity": 3,
    },
    "kick": {
        "label": "طرد (Kick سابقاً)",
        "seconds": 3 * DAY,
        "cell": "block",
        "severity": 2,
    },
    "raid": {
        "label": "Raid / محاولة تخريب السيرفر",
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
# كلما كانت الزنزانة الأصلية أقسح، كتكون مدة العزل الافتراضية والسقف أقسح.
SOLITARY_DEFAULT_SECONDS_BY_CELL = {
    "holding": 2 * HOUR,
    "block": 6 * HOUR,
    "max": 12 * HOUR,
}
SOLITARY_MAX_SECONDS_BY_CELL = {
    "holding": 24 * HOUR,
    "block": 3 * DAY,
    "max": 7 * DAY,
}
SOLITARY_VIOLATION_BASE_MULTIPLIER = {
    "holding": 2,
    "block": 3,
    "max": 4,
}
SOLITARY_DEFAULT_SECONDS = SOLITARY_DEFAULT_SECONDS_BY_CELL["holding"]
SOLITARY_MAX_SECONDS = max(SOLITARY_MAX_SECONDS_BY_CELL.values())

# Discord كيسمح بـ50 روم فالكاتيكوري. كل سجين معزول عندو Voice واحدة بChat ديالها.
# كنخليو هامش للرومز المؤقتة ديال الزيارات والإدارة.
SOLITARY_MAX_ROOMS = max(1, 50 - len(CHANNEL_NAMES) - len(CELL_KEYS) - 5)

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
    # الـDiscord ID كامل كيخلي الزنزانة محسوبة على الحساب بلا أي التباس.
    return f"{SOLITARY_PREFIX}{int(user_id)}"


def solitary_role_name(user_id: int, case_id: int = 0, cell: str = "") -> str:
    """رول مؤقت وفريد للسجين؛ كيتحيد نهائياً مع نهاية العزل."""
    level = str(cell or "").upper()
    level_part = f" • {level}" if level in {"HOLDING", "BLOCK", "MAX"} else ""
    suffix = f" • Case {int(case_id)}" if int(case_id) > 0 else ""
    return f"{SOLITARY_ROLE_PREFIX}{level_part} • {int(user_id)}{suffix}"[:100]


def solitary_default_seconds(cell: str) -> int:
    return int(SOLITARY_DEFAULT_SECONDS_BY_CELL.get(str(cell), SOLITARY_DEFAULT_SECONDS))


def solitary_max_seconds(cell: str) -> int:
    return int(SOLITARY_MAX_SECONDS_BY_CELL.get(str(cell), SOLITARY_MAX_SECONDS_BY_CELL["holding"]))


def gender_of(member: Any, boys_role_id: int, girls_role_id: int) -> str:
    """
    "male" / "female" / "neutral" — نفس المنطق ديال birthday_center.gender().
    كتقرا الرول ديال العضو (BOYS_ROLE_ID / GIRLS_ROLE_ID)، وملي ماعندوش
    حتى واحد منهم (ولا عندو الجوج بغلط) كترجع "neutral" باش الرسالة تبقى
    بصيغة محايدة بدل ما تخمّن.
    """
    role_ids = {role.id for role in getattr(member, "roles", [])}
    is_boy = int(boys_role_id or 0) in role_ids
    is_girl = int(girls_role_id or 0) in role_ids
    if is_boy and not is_girl:
        return "male"
    if is_girl and not is_boy:
        return "female"
    return "neutral"


def pick_by_gender(gender: str, *, male: str, female: str, neutral: str) -> str:
    """كتختار الصيغة الصحيحة حسب gender_of(). دايماً عطي الجوج التلاتة."""
    if gender == "male":
        return male
    if gender == "female":
        return female
    return neutral


def solitary_violation_multiplier(cell: str, violations: int) -> int:
    """التكرار كيزيد الضرب تدريجياً، مع سقف باش ما يفلتش الحساب بلا حدود."""
    base = int(SOLITARY_VIOLATION_BASE_MULTIPLIER.get(str(cell), 2))
    return base + min(2, max(0, int(violations) - 1))


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


# ══════ القوانين التلقائية ديال الـOwner ══════
# كل قاعدة كترتابط بمخالفة من كتالوج السجن. العقوبة والزنزانة
# كيجيو ديركت من ديك المخالفة، باش ما نكرروش نفس المنطق فبلايص مختلفة.
# 0 = بلا سقف. الـUI كتستعمل pagination حيث Discord كيسمح غير بـ25 اختيار
# فكل Select، ولكن التخزين نفسه ما عندوش حد عددي.
AUTO_RULE_MAX = 0
AUTO_RULE_KINDS = ("word", "domain", "action")
AUTO_RULE_TRIGGER_MIN = 1
AUTO_RULE_TRIGGER_MAX = 100
AUTO_ACTION_LABELS = {
    "discord_invite": "نشر دعوة Discord",
    "any_link": "نشر أي رابط",
    "mass_mentions": "منشن جماعي أو متكرر",
    "attachments": "إرسال ملف أو صورة",
    "caps_spam": "إزعاج بالحروف الكبيرة",
    "emoji_spam": "إغراق بالإيموجي",
    "message_spam": "Spam / Flood سريع",
}

# الأحكام الأصلية اللي عندها كشف أوتوماتيكي مباشر. تعديل عدد التحذيرات
# من بطاقة الحكم كيحدث جميع هاد القواعد وكيخلق الناقص منها مرة وحدة.
DEFAULT_OFFENSE_AUTO_ACTIONS = {
    "spam": ("message_spam", "caps_spam", "emoji_spam"),
    "mention_spam": ("mass_mentions",),
    # الروابط كتدوز غير إلا كانت فـAllowed Domains ديال Owner. هكا نفس حكم
    # "الروابط الممنوعة" كيتحكم فدعوات Discord وباقي الروابط من مصدر واحد.
    "links": ("discord_invite", "any_link"),
}


def normalize_auto_rule_pattern(kind: str, raw: Any) -> str:
    """تنظيف قيمة قانون تلقائي قبل التخزين والمقارنة."""
    kind = str(kind or "").strip().lower()
    text = " ".join(str(raw or "").strip().split()).casefold()
    if kind == "word":
        return text[:120]
    if kind == "action":
        return text if text in AUTO_ACTION_LABELS else ""
    if kind != "domain":
        return ""

    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in text:
        text = text.rsplit("@", 1)[-1]
    text = text.split(":", 1)[0].strip(". ")
    if text.startswith("www."):
        text = text[4:]
    if (
        "." not in text
        or len(text) > 253
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", text)
    ):
        return ""
    return text


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


def _format_arabic_count(value: int, singular: str, dual: str, plural: str) -> str:
    """صياغة عدد عربية: 1 مفرد، 2 مثنى، 3-10 جمع، ومن 11 مفرد."""
    value = int(value)
    if value == 1:
        return f"1 {singular}"
    if value == 2:
        return dual
    if 3 <= value <= 10:
        return f"{value} {plural}"
    return f"{value} {singular}"


def warning_trigger_note(trigger: int, lang: str = "darija") -> str:
    """نص موحّد لعدد التحذيرات قبل الحكم — مصدر واحد (single source of truth)
    باش الصياغة النحوية (تحذير/تحذيرين/تحذيرات) ما تتكررش غالطة فبانلز بزاف
    (Prison Code، Blacklist، إلخ). كل مكان خاصو يستدعي هاد الدالة، ماشي
    يصاوب النص بروحه.
    """
    prior = max(0, int(trigger) - 1)
    if lang == "en":
        if prior == 0:
            return "no prior warning"
        return f"after {prior} warning{'s' if prior != 1 else ''}"
    if lang == "fr":
        if prior == 0:
            return "sans avertissement préalable"
        return f"après {prior} avertissement{'s' if prior != 1 else ''}"
    if prior == 0:
        return "بلا تحذير مسبق"
    return f"بعد {_format_arabic_count(prior, 'تحذير', 'تحذيرين', 'تحذيرات')}"


def format_duration(seconds: int, lang: str = "darija") -> str:
    """Format a duration for public panels while keeping Darija as default.

    Existing prison/admin surfaces call this function without ``lang`` and
    therefore keep their exact Arabic wording.  Translated public panels can
    explicitly request English or French so no Arabic unit leaks into them.
    """
    seconds = int(seconds)
    lang = str(lang or "darija").lower()
    if lang not in {"darija", "en", "fr"}:
        lang = "darija"

    if lang in {"en", "fr"}:
        if seconds < 0:
            return "Permanent ♾️" if lang == "en" else "À vie ♾️"

        if lang == "en":
            units = (
                (DAY, "day", "days"),
                (HOUR, "hour", "hours"),
                (MINUTE, "minute", "minutes"),
            )
            second_names = ("second", "seconds")
            joiner = " and "
            under_minute = "Less than a minute"
        else:
            units = (
                (DAY, "jour", "jours"),
                (HOUR, "heure", "heures"),
                (MINUTE, "minute", "minutes"),
            )
            second_names = ("seconde", "secondes")
            joiner = " et "
            under_minute = "Moins d’une minute"

        if seconds < 60:
            singular, plural = second_names
            return f"{seconds} {singular if seconds == 1 else plural}"

        parts: list[str] = []
        remaining = seconds
        for size, singular, plural in units:
            value, remaining = divmod(remaining, size)
            if value:
                parts.append(f"{value} {singular if value == 1 else plural}")
            if len(parts) == 2:
                break
        return joiner.join(parts) if parts else under_minute

    if seconds < 0:
        return "مؤبّد ♾️"
    if seconds < 60:
        return _format_arabic_count(seconds, "ثانية", "ثانيتان", "ثوانٍ")

    units = (
        (DAY, "يوم", "يومان", "أيام"),
        (HOUR, "ساعة", "ساعتان", "ساعات"),
        (MINUTE, "دقيقة", "دقيقتان", "دقائق"),
    )
    parts: list[str] = []
    remaining = seconds
    for size, singular, dual, plural in units:
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(_format_arabic_count(value, singular, dual, plural))
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
        "offense_seq": 0,    # IDs ديال الأحكام الجديدة اللي كيزيدها الاونر
        "auto_rules": {},    # قانون تلقائي → مخالفة سجنية
        "auto_rule_seq": 0,
        # rule_id → user_id → {count, updated}; مربوط بالـID وكيصفر بعد الحكم.
        "auto_rule_strikes": {},
        "inmates": {},       # user_id → record
        "history": [],       # آخر 200 حكم
        "case_seq": 0,
        # ── الحبس الانفرادي ──
        # user_id → {channel_id, role_id, until, reason, by, cell, violations}
        "solitary": {},
        # ── الشكايات ──
        "complaints": {},    # complaint_id → {author, targets[], cell, reason, ...}
        "complaint_seq": 0,
        "complaint_cooldown": {},  # user_id → timestamp آخر شكاية
        "cell_help_message_ids": {key: 0 for key in CELL_KEYS},
        "voice_help_message_ids": {key: 0 for key in CELL_KEYS},
        # Legacy maps: النسخة الجديدة كتمسح البطاقات العمومية وكتستعمل بانل
        # واحدة + أجوبة ephemeral، ولكن كنخليو المفاتيح باش migration تكون آمنة.
        "cell_record_message_ids": {key: {} for key in CELL_KEYS},
        "voice_record_message_ids": {key: {} for key in CELL_KEYS},
        # إحصائيات دائمة حسب Discord ID؛ ما كتضيعش ملي history القديمة كتتقلم.
        "inmate_stats": {},
        "inmate_stats_version": INMATE_STATS_VERSION,
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
        # ── الروابط المسموحة (بيباس لقانون "روابط ممنوعة") ──
        "allowed_domains": [],
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
        needs_stats_migration = (
            int(record.get("inmate_stats_version", 0) or 0) < INMATE_STATS_VERSION
        )
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
        record.setdefault("voice_help_message_ids", {})
        for key in CELL_KEYS:
            record["voice_help_message_ids"].setdefault(key, 0)
        record.setdefault("cell_record_message_ids", {})
        record.setdefault("voice_record_message_ids", {})
        for key in CELL_KEYS:
            record["cell_record_message_ids"].setdefault(key, {})
            record["voice_record_message_ids"].setdefault(key, {})
        if needs_stats_migration:
            self._rebuild_inmate_stats(record)
        record.setdefault("inmate_stats", {})
        record["inmate_stats_version"] = INMATE_STATS_VERSION
        record.setdefault("visits", {})
        record.setdefault("visit_seq", 0)
        record.setdefault("visits_message_id", 0)
        record.setdefault("visits_admin_message_id", 0)
        record.setdefault("offense_seq", 0)
        record.setdefault("auto_rules", {})
        record.setdefault("auto_rule_seq", 0)
        record.setdefault("auto_rule_strikes", {})
        record.setdefault("offense_trigger_counts", {})
        return record

    @staticmethod
    def _record_cell_entries(record: dict) -> list[str]:
        """كيستخرج كل دخول لدرجة سجنية من سجل حكم واحد."""
        entries = [
            str(item.get("to"))
            for item in (record.get("cell_history") or [])
            if str(item.get("to")) in CELL_KEYS
        ]
        if not entries:
            cell = str(record.get("cell") or "")
            if cell not in CELL_KEYS:
                offense = DEFAULT_OFFENSES.get(str(record.get("offense") or ""), {})
                cell = str(offense.get("cell") or "")
            if cell in CELL_KEYS:
                entries.append(cell)
        return entries

    @staticmethod
    def _blank_inmate_stats() -> dict:
        return {
            "cases": 0,
            "cells": {key: 0 for key in CELL_KEYS},
            "completed_seconds": 0,
            "first_entry": 0,
            "last_entry": 0,
            "last_release": 0,
            "last_cell": "",
            "last_case": 0,
            "last_offense": "",
            "last_reason": "",
            "last_outcome": "",
            "last_name": "",
        }

    @classmethod
    def _rebuild_inmate_stats(cls, guild_record: dict) -> None:
        """Migration كتحتافظ بالعداد القديم وكتزيد الوقت وآخر دخول/خروج."""
        previous = guild_record.get("inmate_stats", {}) or {}
        stats: dict[str, dict] = {}

        def absorb(user_id, case_record: dict) -> None:
            try:
                uid = str(int(user_id))
            except (TypeError, ValueError):
                return
            user_stats = stats.setdefault(uid, cls._blank_inmate_stats())
            user_stats["cases"] += 1
            for cell in cls._record_cell_entries(case_record):
                user_stats["cells"][cell] += 1
            since = max(0, int(case_record.get("since", 0) or 0))
            ended = max(0, int(case_record.get("ended", 0) or 0))
            if since:
                if not user_stats["first_entry"] or since < user_stats["first_entry"]:
                    user_stats["first_entry"] = since
                if since >= user_stats["last_entry"]:
                    user_stats["last_entry"] = since
                    user_stats["last_case"] = int(case_record.get("case", 0) or 0)
                    user_stats["last_offense"] = str(case_record.get("offense") or "")
                    user_stats["last_reason"] = str(case_record.get("reason") or "")[:400]
                    user_stats["last_cell"] = str(case_record.get("cell") or "")
                    user_stats["last_name"] = str(
                        case_record.get("display_name") or case_record.get("nick") or ""
                    )[:100]
            if ended:
                user_stats["completed_seconds"] += max(0, ended - since)
                if ended >= user_stats["last_release"]:
                    user_stats["last_release"] = ended
                    user_stats["last_outcome"] = str(case_record.get("outcome") or "released")

        for entry in guild_record.get("history", []) or []:
            absorb(entry.get("user_id"), entry)
        for uid, inmate in (guild_record.get("inmates", {}) or {}).items():
            absorb(uid, inmate)

        # history كتتقلم لـ200 حكم؛ ما ننقصوش counts اللي النسخة القديمة حافظاهم.
        for uid, old in previous.items():
            if not isinstance(old, dict):
                continue
            user_stats = stats.setdefault(str(uid), cls._blank_inmate_stats())
            user_stats["cases"] = max(
                int(user_stats.get("cases", 0) or 0), int(old.get("cases", 0) or 0)
            )
            old_cells = old.get("cells", {}) or {}
            for cell in CELL_KEYS:
                user_stats["cells"][cell] = max(
                    int(user_stats["cells"].get(cell, 0) or 0),
                    int(old_cells.get(cell, 0) or 0),
                )

        guild_record["inmate_stats"] = stats
        guild_record["inmate_stats_version"] = INMATE_STATS_VERSION

    def inmate_stats(self, guild_id: int, user_id: int) -> dict:
        uid = str(int(user_id))
        stats = self.guild(guild_id).setdefault("inmate_stats", {})
        user_stats = stats.setdefault(uid, self._blank_inmate_stats())
        user_stats.setdefault("cases", 0)
        user_stats.setdefault("cells", {})
        for key in CELL_KEYS:
            user_stats["cells"].setdefault(key, 0)
        for key, default in self._blank_inmate_stats().items():
            if key != "cells":
                user_stats.setdefault(key, default)
        return user_stats

    def case_count(self, guild_id: int, user_id: int) -> int:
        return max(0, int(self.inmate_stats(guild_id, user_id).get("cases", 0) or 0))

    def cell_entry_counts(self, guild_id: int, user_id: int) -> dict[str, int]:
        cells = self.inmate_stats(guild_id, user_id).get("cells", {})
        return {key: max(0, int(cells.get(key, 0) or 0)) for key in CELL_KEYS}

    def note_cell_entry(self, guild_id: int, user_id: int, cell: str) -> None:
        if cell not in CELL_KEYS:
            return
        stats = self.inmate_stats(guild_id, user_id)
        stats["cells"][cell] = int(stats["cells"].get(cell, 0) or 0) + 1
        stats["last_cell"] = cell
        self.save()

    def registry_user_ids(self, guild_id: int, cell: Optional[str] = None) -> list[int]:
        """غير IDs ديال الناس اللي عندهم حكم حقيقي، مرتبين بآخر نشاط سجني."""
        rows: list[tuple[int, int]] = []
        for raw_uid, raw_stats in self.guild(guild_id).get("inmate_stats", {}).items():
            try:
                uid = int(raw_uid)
            except (TypeError, ValueError):
                continue
            stats = self.inmate_stats(guild_id, uid)
            if int(stats.get("cases", 0) or 0) <= 0:
                continue
            if cell in CELL_KEYS and int(stats.get("cells", {}).get(cell, 0) or 0) <= 0:
                continue
            activity = max(
                int(stats.get("last_release", 0) or 0),
                int(stats.get("last_entry", 0) or 0),
            )
            rows.append((activity, uid))
        rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [uid for _activity, uid in rows]

    def inmate_summary(self, guild_id: int, user_id: int) -> dict:
        """Snapshot صالح للبانل: stats دائمة + الوقت الجاري إلا مازال معتاقل."""
        stats = dict(self.inmate_stats(guild_id, user_id))
        stats["cells"] = dict(stats.get("cells", {}))
        active = self.inmate(guild_id, user_id)
        active_elapsed = 0
        if active is not None:
            active_elapsed = max(0, now_ts() - int(active.get("since", now_ts()) or now_ts()))
        stats["total_served_seconds"] = max(
            0, int(stats.get("completed_seconds", 0) or 0) + active_elapsed
        )
        stats["active"] = active
        return stats

    def latest_case(self, guild_id: int, user_id: int) -> Optional[dict]:
        active = self.inmate(guild_id, user_id)
        if active is not None:
            return active
        uid = int(user_id)
        for entry in self.history(guild_id, self.MAX_HISTORY):
            if int(entry.get("user_id", 0) or 0) == uid:
                return entry
        return None

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
            entry["custom"] = False
            merged[key] = entry
        # مخالفات جديدة زادها الاونر
        for key, extra in overrides.items():
            if key not in merged and isinstance(extra, dict):
                custom_entry = {
                    "label": extra.get("label", key),
                    "seconds": int(extra.get("seconds", HOUR)),
                    "cell": extra.get("cell", "holding"),
                    "severity": int(extra.get("severity", 1)),
                    "custom": True,
                    "created": int(extra.get("created", 0) or 0),
                }
                for language in ("en", "fr"):
                    translated_label = str(extra.get(f"label_{language}", "") or "").strip()
                    if translated_label:
                        custom_entry[f"label_{language}"] = translated_label[:80]
                merged[key] = custom_entry
        return merged

    def offense(self, guild_id: int, key: str) -> dict:
        catalogue = self.offenses(guild_id)
        return catalogue.get(key) or catalogue["manual"]

    def set_offense(self, guild_id: int, key: str, **changes) -> dict:
        key = str(key or "").strip()
        if not key or key not in self.offenses(guild_id):
            raise ValueError("هاد الحكم ماكاينش.")
        if changes.get("label") is not None:
            label = " ".join(str(changes["label"]).strip().split())
            if not label:
                raise ValueError("اسم الحكم ما يقدرش يكون خاوي.")
            changes["label"] = label[:80]
        if changes.get("seconds") is not None:
            seconds = int(changes["seconds"])
            if seconds == 0 or seconds < -1 or seconds > MAX_SENTENCE_SECONDS:
                raise ValueError("مدة الحكم ماشي صالحة.")
            changes["seconds"] = seconds
        if changes.get("cell") is not None:
            cell = str(changes["cell"]).strip().lower()
            if cell not in CELL_KEYS:
                raise ValueError("الزنزانة ماشي صالحة.")
            changes["cell"] = cell
            changes["severity"] = CELL_RANK[cell] + 1
        record = self.guild(guild_id)
        overrides = record.setdefault("offenses", {})
        entry = overrides.setdefault(key, {})
        for field, value in changes.items():
            if value is not None:
                entry[field] = value
        self.save()
        return self.offense(guild_id, key)

    def add_offense(
        self,
        guild_id: int,
        *,
        label: str,
        seconds: int,
        cell: str,
    ) -> tuple[str, dict]:
        """كيزيد حكم مخصص بـID ثابت، وكيخليه متاح للسجن وAuto Rules."""
        label = " ".join(str(label or "").strip().split())
        cell = str(cell or "").strip().lower()
        seconds = int(seconds)
        if not label:
            raise ValueError("اسم الحكم ما يقدرش يكون خاوي.")
        if seconds == 0 or seconds < -1 or seconds > MAX_SENTENCE_SECONDS:
            raise ValueError("مدة الحكم ماشي صالحة.")
        if cell not in CELL_KEYS:
            raise ValueError("الزنزانة ماشي صالحة.")

        guild_record = self.guild(guild_id)
        catalogue = self.offenses(guild_id)
        while True:
            guild_record["offense_seq"] = int(guild_record.get("offense_seq", 0) or 0) + 1
            key = f"custom_{guild_record['offense_seq']}"
            if key not in catalogue:
                break
        guild_record.setdefault("offenses", {})[key] = {
            "label": label[:80],
            "seconds": seconds,
            "cell": cell,
            "severity": CELL_RANK[cell] + 1,
            "custom": True,
            "created": now_ts(),
        }
        self.save()
        return key, self.offense(guild_id, key)

    def reset_offense(self, guild_id: int, key: str) -> dict:
        """كيرجع حكم أصلي للإعدادات الافتراضية ديالو."""
        key = str(key or "").strip()
        if key not in DEFAULT_OFFENSES:
            raise ValueError("غير الأحكام الأصلية اللي كتقدر ترجعها للافتراضي.")
        self.guild(guild_id).setdefault("offenses", {}).pop(key, None)
        self.save()
        return self.offense(guild_id, key)

    def remove_offense(self, guild_id: int, key: str) -> dict:
        """كيمسح حكم مخصص إلا ما كان مربوط بقانون ولا بسجين مازال معتاقل."""
        key = str(key or "").strip()
        if key in DEFAULT_OFFENSES:
            raise ValueError("الحكم الأصلي ما كيتحيدش؛ تقدر غير ترجّعو للافتراضي.")
        overrides = self.guild(guild_id).setdefault("offenses", {})
        if key not in overrides:
            raise ValueError("هاد الحكم ماكاينش.")
        if any(rule.get("offense") == key for rule in self.auto_rules(guild_id).values()):
            raise ValueError("هاد الحكم مربوط بـAuto Rule. حيّد القانون أو بدّل الحكم ديالو أولاً.")
        if any(inmate.get("offense") == key for inmate in self.inmates(guild_id).values()):
            raise ValueError("هاد الحكم مستعمل دابا عند سجين معتاقل، ما يمكنش يتحيد.")
        removed = dict(overrides.pop(key))
        self.save()
        return removed

    # ───── الروابط المسموحة ─────

    ALLOWED_DOMAINS_MAX = 50

    def allowed_domains(self, guild_id: int) -> list[str]:
        domains = self.guild(guild_id).setdefault("allowed_domains", [])
        return sorted(domains)

    def add_allowed_domains(self, guild_id: int, raw_items: list) -> dict:
        """كيزيد لائحة دومينات دفعة وحدة، وكيرجع تفاصيل شحال تزاد/تكرر/ماصحش."""
        record = self.guild(guild_id)
        existing = set(record.setdefault("allowed_domains", []))
        created: list[str] = []
        skipped: list[str] = []
        invalid: list[str] = []
        for raw in raw_items:
            text = str(raw or "").strip()
            if not text:
                continue
            domain = normalize_auto_rule_pattern("domain", text)
            if not domain:
                invalid.append(text)
                continue
            if domain in existing:
                skipped.append(domain)
                continue
            if len(existing) + len(created) >= self.ALLOWED_DOMAINS_MAX:
                invalid.append(domain)
                continue
            created.append(domain)
        if created:
            record["allowed_domains"] = sorted(existing | set(created))
            self.save()
        return {"created": created, "skipped": skipped, "invalid": invalid}

    def remove_allowed_domain(self, guild_id: int, domain: str) -> bool:
        record = self.guild(guild_id)
        domains = record.setdefault("allowed_domains", [])
        domain = str(domain or "").strip().casefold()
        if domain not in domains:
            return False
        domains.remove(domain)
        self.save()
        return True

    def is_domain_allowed(self, guild_id: int, domain: str) -> bool:
        """كيتفحص واش دومين (أو subdomain تابع ليه) موجود فلائحة المسموحين."""
        domain = str(domain or "").strip().casefold()
        if not domain:
            return False
        for allowed in self.guild(guild_id).get("allowed_domains", []):
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True
        return False

    # ───── قوانين تلقائية ديال الـOwner ─────

    def auto_rules(self, guild_id: int) -> dict[str, dict]:
        rules = self.guild(guild_id).setdefault("auto_rules", {})
        changed = False
        for rule in rules.values():
            raw = int(rule.get("trigger_count", 1) or 1)
            normalized = max(AUTO_RULE_TRIGGER_MIN, min(raw, AUTO_RULE_TRIGGER_MAX))
            if rule.get("trigger_count") != normalized:
                rule["trigger_count"] = normalized
                changed = True
        if changed:
            self.save()
        return rules

    def auto_rule(self, guild_id: int, rule_id) -> Optional[dict]:
        return self.auto_rules(guild_id).get(str(rule_id))

    def add_auto_rule(
        self,
        guild_id: int,
        *,
        kind: str,
        pattern: str,
        offense_key: str,
        trigger_count: int = 1,
    ) -> dict:
        kind = str(kind or "").strip().lower()
        if kind not in AUTO_RULE_KINDS:
            raise ValueError("نوع القانون غير صالح.")
        normalized = normalize_auto_rule_pattern(kind, pattern)
        if not normalized:
            raise ValueError("الكلمة/الموقع/الفعل غير صالح.")
        if str(offense_key) not in self.offenses(guild_id):
            raise ValueError("المخالفة السجنية ماكايناش.")

        result = self.add_auto_rules_bulk(
            guild_id,
            kind=kind,
            patterns=[normalized],
            offense_key=offense_key,
            trigger_count=trigger_count,
        )
        if not result["created"]:
            raise ValueError("هاد القانون مزاد من قبل.")
        return result["created"][0]

    def add_auto_rules_bulk(
        self,
        guild_id: int,
        *,
        kind: str,
        patterns,
        offense_key: str,
        trigger_count: int = 1,
    ) -> dict[str, list]:
        """كيزيد لائحة قوانين دفعة وحدة، بلا سقف، وبـsave وحدة."""
        kind = str(kind or "").strip().lower()
        if kind not in AUTO_RULE_KINDS:
            raise ValueError("نوع القانون غير صالح.")
        if str(offense_key) not in self.offenses(guild_id):
            raise ValueError("المخالفة السجنية ماكايناش.")
        trigger_count = int(trigger_count)
        if not AUTO_RULE_TRIGGER_MIN <= trigger_count <= AUTO_RULE_TRIGGER_MAX:
            raise ValueError(
                f"عدد التكرارات خاصو يكون بين {AUTO_RULE_TRIGGER_MIN} و {AUTO_RULE_TRIGGER_MAX}."
            )

        normalized_patterns: list[str] = []
        invalid: list[str] = []
        seen_input: set[str] = set()
        for raw in patterns or []:
            normalized = normalize_auto_rule_pattern(kind, raw)
            if not normalized:
                invalid.append(str(raw or "")[:120])
                continue
            if normalized in seen_input:
                continue
            seen_input.add(normalized)
            normalized_patterns.append(normalized)
        if not normalized_patterns:
            raise ValueError("ما لقيت حتى قيمة صالحة باش نزيدها.")

        rules = self.auto_rules(guild_id)
        existing = {
            str(rule.get("pattern"))
            for rule in rules.values()
            if rule.get("kind") == kind
        }
        guild_record = self.guild(guild_id)
        created: list[dict] = []
        skipped: list[str] = []
        for normalized in normalized_patterns:
            if normalized in existing:
                skipped.append(normalized)
                continue
            guild_record["auto_rule_seq"] = int(guild_record.get("auto_rule_seq", 0) or 0) + 1
            rule_id = str(guild_record["auto_rule_seq"])
            record = {
                "id": rule_id,
                "kind": kind,
                "pattern": normalized,
                "offense": str(offense_key),
                "trigger_count": trigger_count,
                "enabled": True,
                "created": now_ts(),
            }
            rules[rule_id] = record
            created.append(record)
            existing.add(normalized)
        if created:
            self.save()
        return {"created": created, "skipped": skipped, "invalid": invalid}

    def toggle_auto_rule(self, guild_id: int, rule_id) -> Optional[dict]:
        record = self.auto_rule(guild_id, rule_id)
        if record is None:
            return None
        record["enabled"] = not bool(record.get("enabled", True))
        self.save()
        return record

    def set_auto_rule_trigger_count(
        self, guild_id: int, rule_id, trigger_count: int
    ) -> Optional[dict]:
        record = self.auto_rule(guild_id, rule_id)
        if record is None:
            return None
        trigger_count = int(trigger_count)
        if not AUTO_RULE_TRIGGER_MIN <= trigger_count <= AUTO_RULE_TRIGGER_MAX:
            raise ValueError(
                f"عدد التكرارات خاصو يكون بين {AUTO_RULE_TRIGGER_MIN} و {AUTO_RULE_TRIGGER_MAX}."
            )
        record["trigger_count"] = trigger_count
        # أي تغيير من الـOwner كيبدا عدّاد نظيف باش ما يطبقش حكم بمخزون قديم.
        self.guild(guild_id).setdefault("auto_rule_strikes", {}).pop(str(rule_id), None)
        self.save()
        return record

    def set_auto_rule_offense(
        self, guild_id: int, rule_id, offense_key: str
    ) -> Optional[dict]:
        record = self.auto_rule(guild_id, rule_id)
        if record is None:
            return None
        if str(offense_key) not in self.offenses(guild_id):
            raise ValueError("المخالفة السجنية ماكايناش.")
        record["offense"] = str(offense_key)
        self.save()
        return record

    def offense_trigger_count(self, guild_id: int, offense_key: str) -> int:
        """عدد التحذيرات العام للحكم؛ كيتستعمل فواجهة الأحكام الأصلية والجديدة."""
        offense_key = str(offense_key)
        if offense_key not in self.offenses(guild_id):
            raise ValueError("المخالفة السجنية ماكايناش.")
        saved = self.guild(guild_id).setdefault("offense_trigger_counts", {}).get(offense_key)
        if saved is not None:
            return max(AUTO_RULE_TRIGGER_MIN, min(int(saved), AUTO_RULE_TRIGGER_MAX))
        linked = [
            int(rule.get("trigger_count", 1) or 1)
            for rule in self.auto_rules(guild_id).values()
            if str(rule.get("offense")) == offense_key
        ]
        return max(linked) if linked else 1

    def set_offense_trigger_count(
        self, guild_id: int, offense_key: str, trigger_count: int
    ) -> dict:
        """يحدث كل القواعد المرتبطة بالحكم ويخلق الكشف الأصلي الناقص."""
        offense_key = str(offense_key)
        if offense_key not in self.offenses(guild_id):
            raise ValueError("المخالفة السجنية ماكايناش.")
        trigger_count = int(trigger_count)
        if not AUTO_RULE_TRIGGER_MIN <= trigger_count <= AUTO_RULE_TRIGGER_MAX:
            raise ValueError(
                f"عدد التكرارات خاصو يكون بين {AUTO_RULE_TRIGGER_MIN} و {AUTO_RULE_TRIGGER_MAX}."
            )

        guild_record = self.guild(guild_id)
        guild_record.setdefault("offense_trigger_counts", {})[offense_key] = trigger_count
        rules = self.auto_rules(guild_id)
        existing_actions = {
            str(rule.get("pattern")): rule
            for rule in rules.values()
            if rule.get("kind") == "action"
        }
        created = 0
        for action in DEFAULT_OFFENSE_AUTO_ACTIONS.get(offense_key, ()):
            if action in existing_actions:
                # اختيار الـOwner لهاد الحكم من واجهة الأحكام هو قرار صريح
                # باش الفعل الأصلي يرجع مربوط بالحكم الصحيح.
                existing_actions[action]["offense"] = offense_key
                continue
            guild_record["auto_rule_seq"] = int(guild_record.get("auto_rule_seq", 0) or 0) + 1
            rule_id = str(guild_record["auto_rule_seq"])
            rules[rule_id] = {
                "id": rule_id,
                "kind": "action",
                "pattern": action,
                "offense": offense_key,
                "trigger_count": trigger_count,
                "enabled": True,
                "created": now_ts(),
            }
            existing_actions[action] = rules[rule_id]
            created += 1

        updated = 0
        strikes = guild_record.setdefault("auto_rule_strikes", {})
        for rule_id, rule in rules.items():
            if str(rule.get("offense")) != offense_key:
                continue
            rule["trigger_count"] = trigger_count
            strikes.pop(str(rule_id), None)
            updated += 1
        self.save()
        return {"trigger_count": trigger_count, "updated": updated, "created": created}

    def record_auto_rule_match(
        self, guild_id: int, rule_id, user_id: int
    ) -> Optional[dict]:
        return self.record_auto_rule_matches(guild_id, [rule_id], user_id).get(str(rule_id))

    def record_auto_rule_matches(
        self, guild_id: int, rule_ids, user_id: int
    ) -> dict[str, dict]:
        """Batch خفيف: كيحسب جميع القوانين المطابقة وكيكتب الداتا مرة وحدة."""
        all_strikes = self.guild(guild_id).setdefault("auto_rule_strikes", {})
        key = str(int(user_id))
        current = now_ts()
        result: dict[str, dict] = {}
        for raw_rule_id in rule_ids:
            rule_id = str(raw_rule_id)
            rule = self.auto_rule(guild_id, rule_id)
            if rule is None or not bool(rule.get("enabled", True)):
                continue
            threshold = max(
                AUTO_RULE_TRIGGER_MIN,
                min(int(rule.get("trigger_count", 1) or 1), AUTO_RULE_TRIGGER_MAX),
            )
            rule_strikes = all_strikes.setdefault(rule_id, {})
            previous = rule_strikes.get(key, {})
            count = max(0, int(previous.get("count", 0) or 0)) + 1
            triggered = count >= threshold
            if triggered:
                rule_strikes.pop(key, None)
                if not rule_strikes:
                    all_strikes.pop(rule_id, None)
            else:
                rule_strikes[key] = {"count": count, "updated": current}
            result[rule_id] = {
                "count": count,
                "threshold": threshold,
                "remaining": max(0, threshold - count),
                "triggered": triggered,
            }
        if result:
            self.save()
        return result

    def remove_auto_rule(self, guild_id: int, rule_id) -> Optional[dict]:
        record = self.auto_rules(guild_id).pop(str(rule_id), None)
        if record is not None:
            self.guild(guild_id).setdefault("auto_rule_strikes", {}).pop(str(rule_id), None)
            self.save()
        return record

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
        display_name: Optional[str] = None,
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
            "display_name": str(display_name or nick or "")[:100],
            "by": int(actor_id),
            "cell_message_id": 0,
            # الصلاحيات الفردية الأصلية ديال آخر روم/فويس قبل الاعتقال.
            # كتترجع حرفياً ملي كيسالي الحكم.
            "pre_prison_overwrites": [],
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
        stats = self.inmate_stats(guild_id, user_id)
        stats["cases"] = int(stats.get("cases", 0) or 0) + 1
        stats["cells"][record["cell"]] = int(stats["cells"].get(record["cell"], 0) or 0) + 1
        stats["first_entry"] = int(stats.get("first_entry", 0) or 0) or started
        stats["last_entry"] = started
        stats["last_cell"] = record["cell"]
        stats["last_case"] = int(record["case"])
        stats["last_offense"] = str(offense_key)
        stats["last_reason"] = str(record["reason"])[:400]
        stats["last_outcome"] = "active"
        if display_name or nick:
            stats["last_name"] = str(display_name or nick)[:100]
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
            ended = now_ts()
            record["ended"] = ended
            record["outcome"] = outcome
            stats = self.inmate_stats(guild_id, user_id)
            stats["completed_seconds"] = int(stats.get("completed_seconds", 0) or 0) + max(
                0, ended - int(record.get("since", ended) or ended)
            )
            stats["last_release"] = ended
            stats["last_outcome"] = str(outcome)
            stats["last_cell"] = str(record.get("cell") or stats.get("last_cell") or "")
            stats["last_case"] = int(record.get("case", 0) or 0)
            stats["last_offense"] = str(record.get("offense") or "")
            stats["last_reason"] = str(record.get("reason") or "")[:400]
            if record.get("display_name") or record.get("nick"):
                stats["last_name"] = str(
                    record.get("display_name") or record.get("nick")
                )[:100]
            self.push_history(
                guild_id,
                {
                    "user_id": int(user_id),
                    "case": record.get("case"),
                    "offense": record.get("offense"),
                    "reason": record.get("reason"),
                    "since": record.get("since"),
                    "ended": ended,
                    "outcome": outcome,
                    "by": int(actor_id),
                    "cell": record.get("cell", "holding"),
                    "sentence": record.get("sentence", 0),
                    "penalty_seconds_total": record.get("penalty_seconds_total", 0),
                    "cell_history": list(record.get("cell_history") or []),
                    "discipline_log": list(record.get("discipline_log") or []),
                    "display_name": record.get("display_name") or record.get("nick") or "",
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
        record = self.solitary(guild_id).get(str(int(user_id)))
        if record is not None:
            record.setdefault("role_id", 0)
            record.setdefault("violations", 0)
            record.setdefault("discipline", [])
            record.setdefault(
                "initial_seconds",
                max(0, int(record.get("until", 0) or 0) - int(record.get("since", 0) or 0)),
            )
        return record

    def add_solitary(
        self,
        guild_id: int,
        user_id: int,
        *,
        channel_id: int,
        role_id: int,
        seconds: int,
        reason: str,
        by: int,
        cell: str,
        complaint_id: int = 0,
    ) -> dict:
        record = {
            "user_id": int(user_id),
            "channel_id": int(channel_id),
            "role_id": int(role_id),
            "since": now_ts(),
            "until": now_ts() + int(seconds),
            "initial_seconds": int(seconds),
            "reason": (reason or "—")[:400],
            "by": int(by),
            "cell": cell,
            "complaint": int(complaint_id),
            "violations": 0,
            "discipline": [],
        }
        self.solitary(guild_id)[str(int(user_id))] = record
        self.save()
        return record

    def punish_solitary_violation(
        self,
        guild_id: int,
        user_id: int,
        *,
        reason: str,
    ) -> Optional[dict]:
        """كيضاعف الوقت المتبقي حسب مستوى الزنزانة وعدد المخالفات داخل العزل."""
        record = self.in_solitary(guild_id, user_id)
        if record is None:
            return None
        current = now_ts()
        cell = str(record.get("cell") or "holding")
        violations = int(record.get("violations", 0) or 0) + 1
        multiplier = solitary_violation_multiplier(cell, violations)
        old_remaining = max(60, int(record.get("until", current) or current) - current)
        maximum = solitary_max_seconds(cell)
        new_remaining = min(maximum, max(60, old_remaining * multiplier))
        record["until"] = current + new_remaining
        record["violations"] = violations
        record.setdefault("discipline", []).append(
            {
                "at": current,
                "reason": (reason or "مخالفة داخل الانفرادي")[:400],
                "multiplier": multiplier,
                "old_remaining": old_remaining,
                "new_remaining": new_remaining,
                "added_seconds": max(0, new_remaining - old_remaining),
            }
        )
        record["discipline"] = record["discipline"][-20:]
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
        total = self.case_count(guild_id, user_id)
        return max(0, total - (1 if self.is_inmate(guild_id, user_id) else 0))
