# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config
from .careers import CAREERS

TASKS = {
    "barista": [("☕ زبون طلب قهوة؛ شنو أول حاجة؟", ["نأكد الطلب", "نخليه يتسنى بلا جواب", "نسد الخدمة"], 0)],
    "restaurant": [("🍔 جا طلب جديد؛ شنو الخدمة المهنية؟", ["نأكد الطلب وننظمو", "نتجاهلو", "نلغيه بلا سبب"], 0)],
    "delivery": [("📦 عندك توصيل؛ شنو أهم حاجة؟", ["نتأكد من الطلب والعنوان", "نسلم عشوائياً", "نخلي الطلب"], 0)],
    "shop_assistant": [("🛒 زبون محتار؛ شنو تدير؟", ["نسولو شنو باغي ونقترح", "نضغط عليه يشري", "نتجاهلو"], 0)],
    "maintenance": [("🧹 لقيتي مشكل صغير؛ شنو الأفضل؟", ["نصلحو أو نوثّقو", "نخليه", "نزيد نخربو"], 0)],
    "dj": [("🎧 فعالية بدات؛ شنو كتراقب؟", ["الأجواء وتفاعل الناس", "غير الصوت ديالك", "والو"], 0)],
    "event_host": [("🎤 الجمهور ساكت؛ شنو تدير؟", ["نسول/نطلق تفاعل", "نسالي الفعالية", "نتجاهل"], 0)],
    "gaming_host": [("🎮 تحدي بدا؛ شنو أهم حاجة؟", ["قواعد واضحة وعادلة", "نبدل القواعد وسط اللعب", "نفضل صحابي"], 0)],
    "content_creator": [("📱 محتوى جديد؛ شنو البداية؟", ["هدف وجمهور واضح", "نكتب عشوائي", "ننسخ"], 0)],
    "photographer": [("📸 Session؛ شنو كيرفع الجودة؟", ["ضوء وتكوين واضح", "فوضى فالكادر", "بلا هدف"], 0)],
    "fashion_stylist": [("👗 زبون طلب ستايل؛ شنو تسول؟", ["المناسبة والتفضيلات", "نفرض ذوقي", "ما نسول والو"], 0)],
    "makeup_artist": [("💄 Consultation؛ شنو الأول؟", ["اللوك والنتيجة المطلوبة", "نختار عشوائي", "نتجاهل الطلب"], 0)],
    "mechanic": [("🔧 مشكل تقني؛ شنو الأول؟", ["التشخيص قبل الإصلاح", "نبدل كلشي", "نتجاهل الأعراض"], 0)],
    "it_technician": [("💻 User عندو مشكل؛ شنو البداية؟", ["نجمع المعلومات ونشخص", "نقولو فرمت", "نتجاهلو"], 0)],
    "graphic_designer": [("🎨 Brief جديد؛ شنو خاصك؟", ["الهدف والمقاس والستايل", "نبدا بلا brief", "ننسخ تصميم"], 0)],
    "bank_employee": [("🏦 عضو سول على البنك؛ شنو المسموح؟", ["نشرح النظام بلا دخول لحسابو", "نطلب كلمة السر", "نغير فلوسو"], 0)],
    "real_estate": [("🏠 Client باغي Asset؛ شنو تدير؟", ["نقارن الميزانية والهدف", "نضغط عليه الأغلى", "نتجاهل الميزانية"], 0)],
    "sales_rep": [("💼 عندك عرض؛ شنو كيزيد الثقة؟", ["قيمة واضحة بلا تضليل", "وعود كاذبة", "ضغط مزعج"], 0)],
}


def local_now() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def can_work_today(career_id: str, dt: datetime | None = None) -> bool:
    dt = dt or local_now()
    return dt.weekday() in set(CAREERS.get(career_id, {}).get("work_days") or range(7))


def build_shift(career_id: str, minutes: int) -> dict:
    now = local_now()
    minutes = int(minutes)
    if minutes not in config.SHIFT_OPTIONS_MINUTES:
        minutes = config.SHIFT_OPTIONS_MINUTES[0]
    prompt, options, correct = random.choice(TASKS.get(career_id) or [("📋 كمل مهمة الشيفت ديالك.",["تم", "لا"],0)])
    checkin_after = min(config.SHIFT_MIN_CHECKIN_MINUTES, max(5, minutes // 3))
    return {
        "career_id": career_id,
        "start_at": now.isoformat(),
        "planned_end": (now + timedelta(minutes=minutes)).isoformat(),
        "checkin_at": (now + timedelta(minutes=checkin_after)).isoformat(),
        "minutes": minutes,
        "task": {"prompt":prompt,"options":options,"correct":correct,"done":False,"correct_answer":False},
        "status":"active",
    }


def shift_due(shift: dict, dt: datetime | None = None) -> bool:
    dt = dt or local_now()
    return dt >= datetime.fromisoformat(shift["planned_end"])


def checkin_ready(shift: dict, dt: datetime | None = None) -> bool:
    dt = dt or local_now()
    return dt >= datetime.fromisoformat(shift["checkin_at"])


def calculate_shift_pay(career_id: str, shift: dict) -> dict:
    career = CAREERS[career_id]
    minutes = int(shift.get("minutes", 30) or 30)
    base = int(career.get("hourly", 0) or 0) * minutes // 60
    task = shift.get("task") or {}
    if task.get("done") and task.get("correct_answer"):
        performance = 100
    elif task.get("done"):
        performance = 85
    else:
        performance = 65
    gross = base * performance // 100
    xp = max(15, minutes // 2) + (15 if task.get("correct_answer") else 5 if task.get("done") else 0)
    return {"base":base,"performance":performance,"gross":gross,"career_xp":xp}
