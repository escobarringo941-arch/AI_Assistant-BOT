# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ games_config.py — CONFIG ديال Mini Games + العملة  ║
═══════════════════════════════════════════════════════
"""

import os

# ═══════════════════════════════════════════════════════
# ║ المجلدات والملفات ║
# ═══════════════════════════════════════════════════════

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
BANKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banks")

# ═══════════════════════════════════════════════════════
# ║ CHANNELS ديال Mini Games ║
# ═══════════════════════════════════════════════════════

GAMES_PANEL_CHANNEL_ID = 1534234669057445998
COUNTING_CHANNEL_ID = 1534234937530650755
GAMES_LEADERBOARD_CHANNEL_ID = 1534235056564867194
GAMBLING_CHANNEL_ID = 1534672591422226502

SHOP_PANEL_CHANNEL_ID = 1534969085862088744  # ← حط هنا ID ديال #shop إلا بغيتي بانل المتجر
SHOP_SHOUTOUT_CHANNEL_ID = 1535047435779317843  # ← حط هنا ID ديال الشانيل اللي غادي يبان فيها الشوتاوت (بحال #general)

# ═══════ Real Economy / Central Bank (Panel-based — بلا Slash Commands جداد) ═══════
ECONOMY_CATEGORY_ID = 1535605243583397928
ECONOMY_BANK_CHANNEL_ID = 1535605452233113710
ECONOMY_STATS_CHANNEL_ID = 1535605627534057512
ECONOMY_LOGS_CHANNEL_ID = 1535605776293433404

# أي رهان تخسر فعلاً: 60% للخزينة + 25% للـ Global Jackpot + 15% Burn.
GAMBLING_LOSS_TREASURY_PERCENT = 60
GAMBLING_LOSS_JACKPOT_PERCENT = 25
# Burn كيتحسب بالباقي باش المجموع يبقى 100% حتى مع التقريب.

# أي شراء ناجح من المتجر: 50% للخزينة + 10% لصندوق Events + 40% Burn.
SHOP_TREASURY_PERCENT = 50
SHOP_EVENTS_PERCENT = 10
# Burn كيتحسب بالباقي.

ECONOMY_TRANSACTION_HISTORY_LIMIT = 500
ECONOMY_STATS_UPDATE_MINUTES = 2
GLOBAL_JACKPOT_ENABLED = True

MINIGAMES_CATEGORY_ID = 1533697548215128134

# ═══════════════════════════════════════════════════════
# ║ 💰 العملة — الدراهم 🪙 ║
# ═══════════════════════════════════════════════════════

CURRENCY_NAME = "درهم"
CURRENCY_NAME_PLURAL = "دراهم"
CURRENCY_EMOJI = "💲"

COINS_DAILY = 25
COINS_DAILY_STREAK_BONUS = 5
COINS_DAILY_STREAK_MAX = 50

COINS_PVP_WIN = 20
COINS_PVP_DRAW = 5
COINS_WORDLE_WIN = 50
COINS_WORDLE_STREAK_BONUS = 25
COINS_HANGMAN_WIN = 15
COINS_REACTION_WIN = 10
COINS_COUNTING_MILESTONE = 20

COINS_DAILY_CAP = 400

COOLDOWN_TICTACTOE = 30
COOLDOWN_HANGMAN = 20
COOLDOWN_REACTION = 15
COOLDOWN_DAILY_HOURS = 20

# ═══════════════════════════════════════════════════════
# ║ 🛒 SHOP (أنواع خدامين فعلياً) ║
# ═══════════════════════════════════════════════════════
# types: xp_boost | role_color | custom_role | temp_role | role_color_perm | legend_tag

SHOP_ITEMS = [
    # ─── Boosts ───
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
        "description": "Boost قوي فالـ XP لمدة ساعة — مزيان للي حابس فمستوى.",
        "price": 650,
        "type": "xp_boost",
        "multiplier": 3.0,
        "duration_hours": 1,
    },

    # ─── ألوان شخصية ───
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

    # ─── رول مخصص ───
    {
        "id": "customrole",
        "emoji": "🏷️",
        "name": "رول مخصص (30 يوم)",
        "description": "رول بسمية ولون كتختارهم نتا، كيبان فالقائمة بحال VIP شخصي.",
        "price": 2000,
        "type": "custom_role",
        "duration_days": 30,
    },

    # ─── رول VIP موجود ───
    {
        "id": "vip",
        "emoji": "💎",
        "name": "رول VIP (14 يوم)",
        "description": "رول VIP مؤقت مع صلاحيات/مكانة خاصة فالسيرفر.",
        "price": 1200,
        "type": "temp_role",
        "role_id": 0,  # ← حط هنا ID ديال رول VIP الصحيح
        "duration_days": 14,
    },

    # ─── لون دائم ───
    {
        "id": "permanent_color",
        "emoji": "♾️",
        "name": "لون شخصي دائم",
        "description": "لون شخصي ديالك كيبقى ديما (بلا مدة صلاحية).",
        "price": 6000,
        "type": "role_color_perm",
    },

    # ─── Legend Tag ───
    {
        "id": "legend_tag",
        "emoji": "👑",
        "name": "Legend Tag (7 أيام)",
        "description": "Role خاص فيه Tag \"LEGEND\" كيبان فبداية السمية ديالك لمدة أسبوع.",
        "price": 3000,
        "type": "legend_tag",
        "duration_days": 7,
    },

    # ─── بوستات الفلوس (كيضاعفو الأرباح ديال الألعاب/daily لمدة معينة) ───
    {
        "id": "coinsboost_small",
        "emoji": "💵",
        "name": "بوست فلوس 1.5x (45 دقيقة)",
        "description": "كل درهم كتربحو من الألعاب ولا /daily كيتضاعف 1.5x لمدة 45 دقيقة.",
        "price": 200,
        "type": "coins_boost",
        "multiplier": 1.5,
        "duration_hours": 0.75,
    },
    {
        "id": "coinsboost_big",
        "emoji": "💸",
        "name": "بوست فلوس 2x (1 ساعة ونص)",
        "description": "كل درهم كتربحو من الألعاب ولا /daily كيتضاعف 2x لمدة ساعة ونص — وقت مزيان باش تلعب بزاف.",
        "price": 450,
        "type": "coins_boost",
        "multiplier": 2.0,
        "duration_hours": 1.5,
    },

    # ─── حماية (كيحيد آخر تحذير) ───
    {
        "id": "warn_shield",
        "emoji": "🛡️",
        "name": "حيّد آخر تحذير",
        "description": "كيمسح آخر تحذير (Warn) وصلك — إلا كنتي نظيف ما تقدرش تشريه.",
        "price": 900,
        "type": "warn_removal",
    },

    # ─── شوتاوت (رسالة تألق فشانيل معينة) ───
    {
        "id": "shoutout_public",
        "emoji": "📣",
        "name": "شوتاوت عمومي",
        "description": "البوت غايبعث رسالة كتشهر بيك فـ الشانيل ديال الإعلانات، الكل يشوفك!",
        "price": 350,
        "type": "shoutout",
    },

    # ─── صناديق الحظ (مغامرة — نتيجة عشوائية ديال دراهم) ───
    {
        "id": "mysterybox_bronze",
        "emoji": "🎁",
        "name": "صندوق برونزي",
        "description": "خاطر بـ 100 🪙 وشوف شنو غادي تربح — من 50 حتى 700!",
        "price": 100,
        "type": "mystery_box",
        "outcomes": [
            {"coins": 50, "weight": 40, "label": "50 🪙 — حظ خفيف"},
            {"coins": 80, "weight": 30, "label": "80 🪙"},
            {"coins": 150, "weight": 20, "label": "150 🪙 — مزيان!"},
            {"coins": 300, "weight": 8, "label": "300 🪙 — 🔥"},
            {"coins": 700, "weight": 2, "label": "700 🪙 — JACKPOT!! 🎉"},
        ],
    },
    {
        "id": "mysterybox_silver",
        "emoji": "🎀",
        "name": "صندوق فضي",
        "description": "خاطر بـ 300 🪙 وشوف شنو غادي تربح — من 100 حتى 2000!",
        "price": 300,
        "type": "mystery_box",
        "outcomes": [
            {"coins": 100, "weight": 35, "label": "100 🪙"},
            {"coins": 250, "weight": 30, "label": "250 🪙"},
            {"coins": 450, "weight": 20, "label": "450 🪙 — مزيان!"},
            {"coins": 900, "weight": 12, "label": "900 🪙 — 🔥"},
            {"coins": 2000, "weight": 3, "label": "2000 🪙 — JACKPOT!! 🎉"},
        ],
    },
    {
        "id": "mysterybox_gold",
        "emoji": "💰",
        "name": "صندوق ذهبي",
        "description": "خاطر بـ 700 🪙 وشوف شنو غادي تربح — من 200 حتى 6000!",
        "price": 700,
        "type": "mystery_box",
        "outcomes": [
            {"coins": 200, "weight": 30, "label": "200 🪙"},
            {"coins": 600, "weight": 30, "label": "600 🪙"},
            {"coins": 1200, "weight": 20, "label": "1200 🪙 — مزيان!"},
            {"coins": 2500, "weight": 15, "label": "2500 🪙 — 🔥"},
            {"coins": 6000, "weight": 5, "label": "6000 🪙 — JACKPOT!! 🎉"},
        ],
    },
]

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
# ║ باقي الكونفيغ (counting, games, trivia ...) نفس القديم ║
# ═══════════════════════════════════════════════════════

COUNTING_ENABLED = True
COUNTING_SAME_USER_TWICE = False
COUNTING_DELETE_WRONG = True
COUNTING_MILESTONE_EVERY = 100

TICTACTOE_TURN_SECONDS = 60
TICTACTOE_CHALLENGE_SECONDS = 90

WORDLE_MAX_ATTEMPTS = 6
WORDLE_WORD_LENGTH = 5
WORDLE_RESET_HOUR_UTC = 0

HANGMAN_MAX_MISTAKES = 6
HANGMAN_SESSION_SECONDS = 300

COOLDOWN_DICE = 5
DICE_MIN_BET = 20
DICE_MAX_BET = 500

DICE_RISK_LEVELS = {
    "easy":   {"label": "🟢 سهل",   "threshold": 8,  "multiplier": 1.5},
    "medium": {"label": "🟡 متوسط", "threshold": 13, "multiplier": 2.3},
    "hard":   {"label": "🔴 صعب",   "threshold": 18, "multiplier": 5.5},
}

COOLDOWN_COINFLIP = 5
COINFLIP_MIN_BET = 20
COINFLIP_MAX_BET = 500
COINFLIP_PAYOUT_MULTIPLIER = 1.9

COOLDOWN_SLOTS = 5
SLOTS_MIN_BET = 20
SLOTS_MAX_BET = 500

SLOTS_SYMBOLS = {
    "🍒": {"weight": 35, "multiplier": 2},
    "🍋": {"weight": 28, "multiplier": 3},
    "🍇": {"weight": 20, "multiplier": 5},
    "🔔": {"weight": 10, "multiplier": 10},
    "💎": {"weight": 5,  "multiplier": 25},
    "7️⃣": {"weight": 2, "multiplier": 50},
}

SLOTS_PAIR_MULTIPLIER = 1.2

COOLDOWN_SCRATCH = 5
SCRATCH_MIN_BET = 20
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

COOLDOWN_LOTTERY = 8
LOTTERY_MIN_BET = 20
LOTTERY_MAX_BET = 500
LOTTERY_POOL_SIZE = 20
LOTTERY_PICK_COUNT = 4
LOTTERY_PAYOUTS = {2: 2, 3: 15, 4: 200}

REACTION_MIN_DELAY = 3
REACTION_MAX_DELAY = 15
REACTION_WINDOW_SECONDS = 10

TRIVIA_ENABLED = True
TRIVIA_ANSWER_SECONDS = 30
TRIVIA_AUTO_CHANNEL_IDS = []
TRIVIA_AUTO_INTERVAL_MINUTES = 60
TRIVIA_CHANNEL_ID = 1533700465576116236
TRIVIA_ROUNDS_PER_DIFFICULTY = 6
TRIVIA_COINS = {"easy": 4, "medium": 7, "hard": 12}
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
