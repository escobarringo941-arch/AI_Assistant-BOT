# -*- coding: utf-8 -*-
"""GGMW9 CITY — fictional Underground game domain.

Everything here is a Discord economy simulation. Items, operations and heists are
virtual game mechanics only; there are no real-world weapon, intrusion or evasion
instructions.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config


def local_now() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


UNDERGROUND_PATHS = {
    "fixer": {"emoji":"🕴️","name":"Fixer","desc":"يربط Contacts بعقود سرية وكيخدم كوسيط.","mission":"broker"},
    "shadow_courier": {"emoji":"🌘","name":"Shadow Courier","desc":"كيكمل deliveries افتراضية داخل خريطة CITY.","mission":"courier"},
    "smuggler": {"emoji":"📦","name":"Smuggler","desc":"عمليات لوجستية افتراضية عالية المخاطر.","mission":"cargo"},
    "black_broker": {"emoji":"🕳️","name":"Black Market Broker","desc":"تجارة Game Items داخل السوق السري.","mission":"market"},
    "ghost_tech": {"emoji":"💻","name":"Ghost Tech","desc":"ألغاز Terminal خيالية داخل محاكاة CITY فقط.","mission":"tech"},
    "bookmaker": {"emoji":"🎴","name":"Bookmaker","desc":"عقود وتحليلات Casino خيالية بلا أي تغيير فالـRNG.","mission":"book"},
}

# Virtual-only inventory. No real-world specs or acquisition instructions.
VIRTUAL_ITEMS = {
    "ghost_sidearm": {"emoji":"🔫","name":"Ghost Sidearm","price":4200,"rep":60,"op_bonus":3,"heat_reduction":0,"reward_bps":0,"mission_reward_bps":0,"desc":"Virtual mission item • +3 simulated operation score only."},
    "shadow_armor": {"emoji":"🛡️","name":"Shadow Armor","price":3600,"rep":40,"op_bonus":0,"heat_reduction":5,"reward_bps":0,"mission_reward_bps":0,"desc":"Virtual protection • lowers simulated Heat impact."},
    "signal_mask": {"emoji":"📡","name":"Signal Mask","price":2800,"rep":25,"op_bonus":0,"heat_reduction":3,"reward_bps":0,"mission_reward_bps":0,"desc":"Fictional signal item • lowers simulated Heat only."},
    "vault_token": {"emoji":"🪙","name":"Vault Token","price":5200,"rep":80,"op_bonus":8,"heat_reduction":0,"reward_bps":0,"mission_reward_bps":0,"desc":"Rare virtual token • +8 simulated operation score."},
    "night_case": {"emoji":"💼","name":"Night Case","price":1800,"rep":15,"op_bonus":0,"heat_reduction":0,"reward_bps":500,"mission_reward_bps":0,"desc":"Virtual cargo case • +5% simulated operation payout."},
    "lucky_chip": {"emoji":"🎰","name":"Lucky Chip","price":2200,"rep":20,"op_bonus":0,"heat_reduction":0,"reward_bps":0,"mission_reward_bps":500,"desc":"Collectible • +5% Underground mission payout; NEVER changes Casino odds."},
}

MISSION_POOL = {
    "broker": [
        ("🕴️ Contact محتاج وسيط فـSector Neon. اختار أسلوب التعامل:", ["نثبت الشروط داخل العقد الافتراضي","نبدل الثمن من بعد الاتفاق","نرسل الرسالة للعموم"], 0),
        ("🕴️ جوج Contacts مختلفين باغين نفس Slot:", ["نرتبهم حسب Contract timestamp","نبيع نفس Slot بجوج","نفضح أسماءهم فالروم العام"], 0),
        ("🕴️ Client بغا تبديل فالعقد من بعد الحجز:", ["نستعمل Change Request داخل النظام","نحيد Escrow برا النظام","نبدل البيانات بلا موافقة"], 0),
    ],
    "courier": [
        ("🌘 عندك Virtual Drop بين Sector Echo وSector Nova:", ["نتأكد من Contract ID قبل التسليم","نسلم لأي واحد","نرمي Package"], 0),
        ("🌘 جوج Drop Points بانوا فالماب الخيالي:", ["نتبع النقطة المرتبطة بالOrder ID","نختار الأقرب بلا تحقق","ننشر Location للعموم"], 0),
        ("🌘 Receiver بدل Nickname ديالو:", ["نتحقق بالDiscord ID داخل العقد","نعتمد غير على الاسم","نسلم لشي واحد آخر"], 0),
    ],
    "cargo": [
        ("📦 Cargo Simulation عطاك 3 manifests:", ["نختار الـmanifest المطابق للمهمة","نبدل البيانات عشوائياً","نتجاهل الـcontract"], 0),
        ("📦 Virtual Case وصل ناقص Tag:", ["نوقف التسليم ونطلب System verification","نخمن Tag","نكرر نفس Item فـInventory"], 0),
        ("📦 Crew محتاجة توزيع Cargo على جوج Contracts:", ["نقسم حسب الكمية المسجلة","نضاعف الكمية","نحيد History"], 0),
    ],
    "market": [
        ("🕳️ Listing جديدة فالسوق السري:", ["نتأكد من Item والـEscrow قبل البيع","نطلب الدفع خارج النظام","نبيع نفس Item جوج مرات"], 0),
        ("🕳️ Buyer بغا يرجع يدفع خارج GGMW9:", ["نرفض ونخلي المعاملة داخل Escrow","نرسل معلومات دفع حقيقية","نسد Listing ونطلب DM خارجي"], 0),
        ("🕳️ Listing تباعت قبل ما تضغط عليها:", ["نحترم Status SOLD ونقلب على أخرى","نخصم Buyer مرة ثانية","ننسخ Item جديدة"], 0),
    ],
    "tech": [
        ("💻 Ghost Terminal خيالي عطاك 3 Nodes:", ["نحل Puzzle ديال Node الصحيح داخل اللعبة","نجرب أدوات خارج Discord","نطلب معلومات حساب حقيقي"], 0),
        ("💻 Simulation عطاك checksum مختلف:", ["نرجع للVirtual Contract ونطابق الرمز","نطلب Password حقيقي","نجرب على موقع خارجي"], 0),
        ("💻 Node داخل اللعبة عطاك Access Error:", ["نستعمل Retry/Abort ديال المحاكاة","نحاول اختراق خدمة حقيقية","نطلب Token ديال عضو"], 0),
    ],
    "book": [
        ("🎴 Contract مرتبط بالCasino:", ["نحلل الـledger بلا ما نبدل RNG","نضمن الربح للاعب","نغير odds من الخلف"], 0),
        ("🎴 Player طلب منك طريقة تضمن Slots:", ["نوضح أن RNG ما كيتبدلش ونخدم غير التحليل","نعدلو الحظ ديالو","نعطيه نتيجة مسبقة"], 0),
        ("🎴 Crew باغية Budget لليلة Casino:", ["نحدد Budget افتراضي وحد خسارة","نستعمل Crew Vault كاملة","نبدل RTP"], 0),
    ],
}

HEIST_STAGES = [
    {"title":"🔎 Phase 1 — Recon Simulation","prompt":"Bank Sim عطاك 3 Virtual Beacons. اختار الـbeacon المطابق للـcontract:","options":["Echo-7","Public-Noise","Broken-Link"],"correct":0},
    {"title":"🧩 Phase 2 — Vault Puzzle","prompt":"الـVault الخيالي كيطلب protocol صحيح:","options":["Ghost-Key Puzzle","Random Rush","Abort Logs"],"correct":0},
    {"title":"🌑 Phase 3 — Extraction","prompt":"آخر مرحلة فالمحاكاة:","options":["Contract Exit Beacon","Spam Route","Unknown Member"],"correct":0},
]


def operation_modifiers(inventory: dict) -> dict:
    """Virtual-only equipment modifiers; duplicate copies do not stack."""
    chance = heat = reward = mission_reward = 0
    for item_id, qty in (inventory or {}).items():
        if int(qty or 0) <= 0:
            continue
        item = VIRTUAL_ITEMS.get(item_id)
        if not item:
            continue
        chance += int(item.get("op_bonus", 0) or 0)
        heat += int(item.get("heat_reduction", 0) or 0)
        reward += int(item.get("reward_bps", 0) or 0)
        mission_reward += int(item.get("mission_reward_bps", 0) or 0)
    return {
        "chance_bonus": min(12, chance),
        "heat_reduction": min(10, heat),
        "reward_bps": min(800, reward),
        "mission_reward_bps": min(500, mission_reward),
    }


def prepare_heist_stages() -> list[dict]:
    """Shuffle every fictional puzzle so 'always click first' never works."""
    prepared = []
    for stage in HEIST_STAGES:
        original = list(stage["options"])
        correct_text = original[int(stage["correct"])]
        options = list(original)
        # Fisher-Yates using secrets for game randomness.
        for i in range(len(options) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            options[i], options[j] = options[j], options[i]
        prepared.append({
            "title": stage["title"],
            "prompt": stage["prompt"],
            "options": options,
            "correct": options.index(correct_text),
        })
    return prepared


def choose_mission(path_id: str) -> tuple[str, list[str], int]:
    path = UNDERGROUND_PATHS.get(path_id) or UNDERGROUND_PATHS["fixer"]
    rows = MISSION_POOL.get(path["mission"]) or MISSION_POOL["broker"]
    return rows[secrets.randbelow(len(rows))]


def mission_outcome(*, correct: bool, reputation: int, heat: int) -> dict:
    chance = 56 + (12 if correct else -8) + min(12, reputation // 100) - min(20, heat // 4)
    chance = max(20, min(82, chance))
    success = secrets.randbelow(100) < chance
    reward = 350 + secrets.randbelow(651) if success else 0  # $3.50–$10.00
    rep = 18 + secrets.randbelow(18) if success else 4
    heat_delta = 3 + secrets.randbelow(5) if success else 8 + secrets.randbelow(8)
    item = None
    if success and secrets.randbelow(100) < 22:
        item = list(VIRTUAL_ITEMS)[secrets.randbelow(len(VIRTUAL_ITEMS))]
    return {"success":success,"chance":chance,"reward":reward,"rep":rep,"heat":heat_delta,"item":item}


def heist_success_chance(*, crew_reputation: int, leader_heat: int, correct_steps: int, equipment_bonus: int = 0) -> int:
    chance = 28 + min(18, crew_reputation // 75) + correct_steps * 11 + max(0, min(12, int(equipment_bonus))) - min(22, leader_heat // 3)
    return max(12, min(76, chance))


def heist_gross_reward(crew_size: int) -> int:
    base = 14000 + min(5, max(3, int(crew_size))) * 3500
    return base + secrets.randbelow(8501)  # roughly $245–$330 for a 3-person crew


def cooldown_ready(last_iso: str | None, hours: int) -> tuple[bool, datetime | None]:
    if not last_iso:
        return True, None
    try:
        ready = datetime.fromisoformat(last_iso) + timedelta(hours=hours)
    except Exception:
        return True, None
    return local_now() >= ready, ready
