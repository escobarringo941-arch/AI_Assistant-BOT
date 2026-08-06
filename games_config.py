# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ games_config.py — CONFIG ديال Mini Games + العملة  ║
═══════════════════════════════════════════════════════

هاد الملف فيه غير أرقام و IDs — ماكاين فيه حتى منطق.
كل ما بغيتي تبدّل شي حاجة (ثمن، ربح، channel) بدّلها هنا بوحدها.

⚠️ ماتزيد هنا حتى `import discord` — خاصو يبقى نظيف باش أي ملف يقدر
يستوردو بلا مشاكل (circular imports).
"""

import os

# ═══════════════════════════════════════════════════════
# ║ المجلدات والملفات ║
# ═══════════════════════════════════════════════════════

# نفس المجلد ديال ai_bot.py — Railway Volume
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

# مجلد banks الكلمات (كيمشي مع الكود، ماشي مع الـ Volume)
BANKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banks")

# ═══════════════════════════════════════════════════════
# ║ CHANNELS ديال Mini Games ║
# ═══════════════════════════════════════════════════════
# ⚠️ بدّل هاد الأصفار بالـ IDs الحقيقية من ديسكورد
# (Server Settings → كليك يمين على الـ channel → Copy Channel ID)

GAMES_PANEL_CHANNEL_ID = 1534234669057445998  # 🎮│games-panel — panel موحّد ديال كاع الألعاب
COUNTING_CHANNEL_ID = 1534234937530650755     # 🔢│counting — قناة العدّاد
GAMES_LEADERBOARD_CHANNEL_ID = 1534235056564867194  # 🏆│games-top — لائحة الشرف ديال الألعاب (0 = معطّل)
GAMBLING_CHANNEL_ID = 1534672591422226502     # 🎰│قمار — قناة خاصة بالألعاب اللي فيها رهان (Dice, Slots, Coinflip...) — 0 = بلا تقييد

# 🛒 قناة المتجر (بانل خاص بالـ Shop)
SHOP_PANEL_CHANNEL_ID = 1534969085862088744                     # 🛒│shop — بانل المتجر (0 = معطّل)

# Category "Mini Games" — كتستعمل غير فـ /setupminigames باش يصاوب الـ channels وحدو
MINIGAMES_CATEGORY_ID = 1533697548215128134   # 0 = يصاوب category جديدة بوحدو

# ═══════════════════════════════════════════════════════
# ║ 💰 العملة — الدراهم 🪙 ║
# ═══════════════════════════════════════════════════════

CURRENCY_NAME = "درهم"
CURRENCY_NAME_PLURAL = "دراهم"
CURRENCY_EMOJI = "💲"

# ═══════ الربح ═══════
COINS_DAILY = 25                # /daily — مكافأة يومية
COINS_DAILY_STREAK_BONUS = 5    # +5 على كل نهار متتالي (بحد أقصى تحت)
COINS_DAILY_STREAK_MAX = 50     # أقصى بونوس من الـ streak

COINS_PVP_WIN = 20              # فوز فـ X/O
COINS_PVP_DRAW = 5              # تعادل
COINS_WORDLE_WIN = 50           # فوز فـ Wordle اليومي
COINS_WORDLE_STREAK_BONUS = 25  # بونوس على streak ديال Wordle
COINS_HANGMAN_WIN = 15          # فوز فـ المشنوق
COINS_REACTION_WIN = 10         # فوز فـ أسرع ضغطة
COINS_COUNTING_MILESTONE = 20   # كل 100 رقم فالعدّاد

# ═══════ السقف اليومي (anti-farming) ═══════
COINS_DAILY_CAP = 400  # أقصى دراهم يقدر يربح العضو فنهار واحد
# ملاحظة: /daily ماكيدخلش فالسقف (هي مكافأة ماشي ربح من لعبة)

# ═══════ Cooldowns (بالثواني / بالساعات) ═══════
COOLDOWN_TICTACTOE = 30
COOLDOWN_HANGMAN = 20
COOLDOWN_REACTION = 15
COOLDOWN_DAILY_HOURS = 20  # 20 ساعة ماشي 24، باش ما يتأخرش النهار شوية بشوية

# ═══════════════════════════════════════════════════════
# ║ 🛒 SHOP — أغراض بزاف ومنوّعة ║
# ═══════════════════════════════════════════════════════
# type: "xp_boost" | "role_color" | "temp_role" | "custom_role" | "double_daily"
#       "game_retry" | "name_glow" | "poll_ticket" | "special_ping"
#       "temp_private_room" | "legend_tag" | "role_color_perm" | "bundle"
# ⚠️ الـ IDs ديال الرولات خاصك تعمّرها بوحدك (ولا خليها 0 وحيّد العنصر)

SHOP_ITEMS = [
    # ───── فئة: Boosts بسيطة ─────
    {
        "id": "xpboost_small",
        "emoji": "💫",
        "name": "XP Boost 1.5x (30 دقيقة)",
        "description": "زيادة خفيفة فالـ XP لمدة 30 دقيقة (شات + فويس).",
        "price": 150,
        "type": "xp_boost",
        "multiplier": 1.5,
        "duration_hours": 0.5,
    },
    {
        "id": "xpboost_medium",
        "emoji": "⚡",
        "name": "XP Boost 2x (1 ساعة)",
        "description": "كتربح ضعف الـ XP لمدة ساعة كاملة.",
        "price": 300,
        "type": "xp_boost",
        "multiplier": 2.0,
        "duration_hours": 1,
    },
    {
        "id": "xpboost_big",
        "emoji": "🚀",
        "name": "XP Boost 3x (1 ساعة)",
        "description": "Boost قوي فالـ XP لمدة ساعة، مزيان للي حابس فمستوى.",
        "price": 650,
        "type": "xp_boost",
        "multiplier": 3.0,
        "duration_hours": 1,
    },

    # ───── فئة: ألوان ورولات ─────
    {
        "id": "color_basic",
        "emoji": "🎨",
        "name": "لون شخصي (7 أيام)",
        "description": "رول بلون كتختارو نتا، كيبان فـ السمية ديالك (7 أيام).",
        "price": 500,
        "type": "role_color",
        "duration_days": 7,
    },
    {
        "id": "color_premium",
        "emoji": "🌈",
        "name": "لون Glowy (14 يوم)",
        "description": "لون مميز ومضيء من ألوان خاصة، كيبان فوق بزاف (14 يوم).",
        "price": 900,
        "type": "role_color",
        "duration_days": 14,
    },
    {
        "id": "customrole",
        "emoji": "🏷️",
        "name": "رول مخصص (30 يوم)",
        "description": "رول بسمية ولون كتختارهم نتا، كيبان فالقائمة بحال VIP شخصي.",
        "price": 2000,
        "type": "custom_role",
        "duration_days": 30,
    },
    {
        "id": "vip",
        "emoji": "💎",
        "name": "رول VIP (14 يوم)",
        "description": "رول VIP مؤقت مع صلاحيات/مكانة خاصة فالسيرفر.",
        "price": 1200,
        "type": "temp_role",
        "role_id": 0,  # ← ⚠️ حط هنا ID ديال رول VIP، ولا حيّد هاد العنصر
        "duration_days": 14,
    },

    # ───── فئة: امتيازات السيرفر ─────
    {
        "id": "double_daily_3d",
        "emoji": "📆",
        "name": "Double Daily (3 أيام)",
        "description": "جوائز `/daily` مضاعفة لمدة 3 أيام متتالية.",
        "price": 800,
        "type": "double_daily",
        "duration_days": 3,
    },
    {
        "id": "double_daily_7d",
        "emoji": "🗓️",
        "name": "Double Daily (7 أيام)",
        "description": "للي كيلعب بزاف: `/daily` تعطيك 2x لمدة أسبوع كامل.",
        "price": 1800,
        "type": "double_daily",
        "duration_days": 7,
    },
    {
        "id": "game_retry",
        "emoji": "🔁",
        "name": "تذكرة إعادة محاولة",
        "description": "مرة وحدة: تعطيك فرصة إعادة لعبة خسرتي فيها (Wordle/Hangman/Trivia) بلا ما تستعمل محاولة جديدة.",
        "price": 250,
        "type": "game_retry",
        "uses": 1,
    },
    {
        "id": "name_highlight",
        "emoji": "✨",
        "name": "اسم متوهّج (7 أيام)",
        "description": "Role خاص كيخلي السمية ديالك بارزة ومضيئة فجانب الرولات (cosmetic فقط).",
        "price": 700,
        "type": "name_glow",
        "duration_days": 7,
    },

    # ───── فئة: امتيازات اجتماعية ─────
    {
        "id": "poll_ticket",
        "emoji": "🗳️",
        "name": "تذكرة Poll مميّزة",
        "description": "تقدر تدير `/createpoll` حتى لو ماوصلتيش بعد لـ Level 60 (استعمال واحد).",
        "price": 600,
        "type": "poll_ticket",
        "uses": 1,
    },
    {
        "id": "ping_everyone_once",
        "emoji": "📢",
        "name": "Ping خاص (مرة وحدة)",
        "description": "حق واحد تستعمل Ping خاص فشانيل معيّنة (مثلاً @Games Ping) باتفاق مع الإدارة.",
        "price": 900,
        "type": "special_ping",
        "uses": 1,
    },
    {
        "id": "temp_private_room",
        "emoji": "🎧",
        "name": "روم صوتي خاص (يوم واحد)",
        "description": "روم صوتي خاص بإسمك لمدة 24 ساعة، فقط الناس اللي تختارهم يدخلوا.",
        "price": 1300,
        "type": "temp_private_room",
        "duration_hours": 24,
    },

    # ───── فئة: أشياء “أسطورية” وغالية ─────
    {
        "id": "legend_tag",
        "emoji": "👑",
        "name": "Legend Tag (7 أيام)",
        "description": "Tag \"LEGEND\" كيبان فبداية السمية ديالك لمدة أسبوع (Role خاص، بدون صلاحيات).",
        "price": 3000,
        "type": "legend_tag",
        "duration_days": 7,
    },
    {
        "id": "permanent_color",
        "emoji": "♾️",
        "name": "لون شخصي دائم",
        "description": "لون شخصي كيبقى ديما (بلا مدة صلاحية) حتى إلا غبتي ورجعتي للسيرفر.",
        "price": 6000,
        "type": "role_color_perm",
        "duration_days": 0,
    },
    {
        "id": "mega_bundle",
        "emoji": "🎁",
        "name": "حزمة الأسطورة",
        "description": "XP Boost 2x (1 ساعة) + لون مميز (7 أيام) + تذكرة Poll + Double Daily (3 أيام).",
        "price": 5000,
        "type": "bundle",
    },
]

# ═══════ الرولات ديال الألوان ═══════
# الرولات الشخصية ديال اللون كيتصاوبو أوتوماتيك تحت هاد الرول
# (باش يبانو فوق رولات الأعضاء العاديين) — 0 = فوق نيت
SHOP_COLOR_ROLE_ANCHOR_ID = 0

SHOP_COLORS = {
    "🔴 حمر": 0xE74C3C,
    "🔵 زرق": 0x3498DB,
    "🟢 خضر": 0x2ECC71,
    "🟡 صفر": 0xF1C40F,
    "🟣 موف": 0x9B59B6,
    "🩷 روز": 0xE91E63,
    "🟠 برتقالي": 0xE67E22,
    "⚪ بيض": 0xECF0F1,
}

# ═══════════════════════════════════════════════════════
# ║ 🔢 لعبة العدّاد (Counting) ║
# ═══════════════════════════════════════════════════════

COUNTING_ENABLED = True
COUNTING_SAME_USER_TWICE = False   # False = ممنوع نفس العضو يعدّ مرتين متتاليتين
COUNTING_DELETE_WRONG = True       # كيمسح الرقم الغالط
COUNTING_MILESTONE_EVERY = 100     # كل شحال ديال الأرقام كيعطي دراهم

# ═══════════════════════════════════════════════════════
# ║ ⭕ X/O — Tic Tac Toe ║
# ═══════════════════════════════════════════════════════

TICTACTOE_TURN_SECONDS = 60        # شحال عندو العضو باش يلعب دورو
TICTACTOE_CHALLENGE_SECONDS = 90   # شحال كيبقى التحدي مفتوح قبل ما يـexpiri

# ═══════════════════════════════════════════════════════
# ║ 🔤 Wordle بالدارجة ║
# ═══════════════════════════════════════════════════════

WORDLE_MAX_ATTEMPTS = 6
WORDLE_WORD_LENGTH = 5
WORDLE_RESET_HOUR_UTC = 0          # فأي ساعة (UTC) كتبدّل الكلمة اليومية

# ═══════════════════════════════════════════════════════
# ║ 🪢 المشنوق (Hangman) ║
# ═══════════════════════════════════════════════════════

HANGMAN_MAX_MISTAKES = 6
HANGMAN_SESSION_SECONDS = 300      # 5 دقايق قبل ما تسالي الجلسة

# ═══════════════════════════════════════════════════════
# ║ 🎲 النرد (Dice) ║
# ═══════════════════════════════════════════════════════

COOLDOWN_DICE = 5       # ثواني cooldown بين رهان ورهان
DICE_MIN_BET = 10       # أقل رهان مسموح
DICE_MAX_BET = 500      # أقصى رهان مسموح

DICE_RISK_LEVELS = {
    "easy":   {"label": "🟢 سهل",   "threshold": 8,  "multiplier": 1.5},
    "medium": {"label": "🟡 متوسط", "threshold": 13, "multiplier": 2.3},
    "hard":   {"label": "🔴 صعب",   "threshold": 18, "multiplier": 5.5},
}

# ═══════════════════════════════════════════════════════
# ║ 🪙 Coinflip (وجه ولا ظهر) ║
# ═══════════════════════════════════════════════════════

COOLDOWN_COINFLIP = 5   # ثواني cooldown بين رمية ورمية
COINFLIP_MIN_BET = 10
COINFLIP_MAX_BET = 500
COINFLIP_PAYOUT_MULTIPLIER = 1.9

# ═══════════════════════════════════════════════════════
# ║ 🎰 Slots ║
# ═══════════════════════════════════════════════════════

COOLDOWN_SLOTS = 5
SLOTS_MIN_BET = 10
SLOTS_MAX_BET = 500

SLOTS_SYMBOLS = {
    "🍒": {"weight": 35, "multiplier": 2},
    "🍋": {"weight": 28, "multiplier": 3},
    "🍇": {"weight": 20, "multiplier": 5},
    "🔔": {"weight": 10, "multiplier": 10},
    "💎": {"weight": 5,  "multiplier": 25},
    "7️⃣": {"weight": 2,  "multiplier": 50},
}

SLOTS_PAIR_MULTIPLIER = 1.2

# ═══════════════════════════════════════════════════════
# ║ 🎫 Scratch Card ║
# ═══════════════════════════════════════════════════════

COOLDOWN_SCRATCH = 5
SCRATCH_MIN_BET = 10
SCRATCH_MAX_BET = 500

SCRATCH_GRID_SIZE = 9
SCRATCH_MATCH_NEEDED = 3

SCRATCH_SYMBOLS = {
    "🍀": {"weight": 35, "multiplier": 2},
    "🍒": {"weight": 28, "multiplier": 3},
    "⭐": {"weight": 20, "multiplier": 5},
    "🔔": {"weight": 10, "multiplier": 10},
    "💎": {"weight": 5,  "multiplier": 25},
    "💰": {"weight": 2,  "multiplier": 60},
}

# ═══════════════════════════════════════════════════════
# ║ 🎟️ Lottery (اليانصيب) ║
# ═══════════════════════════════════════════════════════

COOLDOWN_LOTTERY = 8
LOTTERY_MIN_BET = 10
LOTTERY_MAX_BET = 500

LOTTERY_POOL_SIZE = 20
LOTTERY_PICK_COUNT = 4

LOTTERY_PAYOUTS = {
    2: 2,
    3: 15,
    4: 200,
}

# ═══════════════════════════════════════════════════════
# ║ ⚡ أسرع ضغطة (Reaction Speed) ║
# ═══════════════════════════════════════════════════════

REACTION_MIN_DELAY = 3
REACTION_MAX_DELAY = 15
REACTION_WINDOW_SECONDS = 10

# ═══════════════════════════════════════════════════════
# ║ 🧠 Trivia ║
# ═══════════════════════════════════════════════════════

TRIVIA_ENABLED = True
TRIVIA_ANSWER_SECONDS = 30

TRIVIA_AUTO_CHANNEL_IDS = []
TRIVIA_AUTO_INTERVAL_MINUTES = 60

TRIVIA_CHANNEL_ID = 1533700465576116236
TRIVIA_ROUNDS_PER_DIFFICULTY = 6

TRIVIA_COINS = {
    "easy": 4,
    "medium": 7,
    "hard": 12,
}

TRIVIA_SINGLE_COINS = 8

TRIVIA_OPENTDB_IDS = {
    "general": 9, "science": 17, "sports": 21, "history": 23,
    "geography": 22, "movies": 11, "music": 12, "games": 15, "anime": 31,
}

TRIVIA_CATEGORY_LABELS = {
    "general": "🌍 ثقافة عامة",
    "science": "🔬 علوم",
    "sports": "⚽ رياضة",
    "history": "📜 تاريخ",
    "geography": "🗺️ جغرافيا",
    "movies": "🎬 أفلام",
    "music": "🎵 موسيقى",
    "games": "🎮 ألعاب فيديو",
    "anime": "📺 أنمي ومانغا",
}

TRIVIA_CATEGORIES = list(TRIVIA_CATEGORY_LABELS)
