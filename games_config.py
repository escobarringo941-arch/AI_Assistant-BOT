# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ games_config.py — CONFIG ديال Mini Games + العملة  ║
═══════════════════════════════════════════════════════
"""

import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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

# Casino loss routing: loss already deducted from player. This only routes it.
# 60% Treasury (bank liquidity) + 15% Progressive Jackpot + 25% Burn.
GAMBLING_LOSS_TREASURY_PERCENT = 60
GAMBLING_LOSS_JACKPOT_PERCENT = 15

# Shop purchases are the main money sink.
# 55% Treasury + 15% Events + 30% permanent Burn.
SHOP_TREASURY_PERCENT = 55
SHOP_EVENTS_PERCENT = 15

ECONOMY_TRANSACTION_HISTORY_LIMIT = 1000
ECONOMY_STATS_UPDATE_MINUTES = 2
GLOBAL_JACKPOT_ENABLED = True

# ═══════ Real Bank / Savings / Transfers ═══════
# Money is stored internally as integer cents. Existing saved balances are NOT deleted
# or mutated: old 200,000 units are simply displayed as $2,000.00.
BANK_INTEREST_BASE_BPS_DAILY = 5          # 0.05% / day
BANK_INTEREST_LEVEL_BONUS_BPS_MAX = 5    # +0.01% each 20 levels, max +0.05%
BANK_INTEREST_MIN_BALANCE = 2500          # $25.00
BANK_INTEREST_DAILY_ACCOUNT_CAP = 2500    # max $25/day/account
BANK_INTEREST_TREASURY_BUDGET_PERCENT = 5 # max 5% of Treasury per daily cycle
BANK_INTEREST_BOOST_BPS = 5               # shop pass: +0.05%/day
BANK_INTEREST_LOOP_MINUTES = 60

BANK_TRANSFER_FEE_BPS = 100               # 1.00%
BANK_TRANSFER_MIN_FEE = 10                 # $0.10
BANK_TRANSFER_MAX_FEE = 500                # $5.00
BANK_TRANSFER_TREASURY_PERCENT = 70
BANK_TRANSFER_DAILY_LIMIT = 100000         # $1,000/day base
BANK_TRANSFER_LEVEL_BONUS_PER_10 = 10000   # +$100 per 10 levels
BANK_TRANSFER_MAX_DAILY_LIMIT = 200000     # hard cap $2,000/day

ASSET_RESALE_PERCENT = 40                  # asset resale funded by Treasury

# ═══════ Loans / Credit System — كامل من Bank Panel بلا Slash Commands ═══════
LOAN_MIN_AMOUNT = 2500                     # $25.00
LOAN_TERM_DAYS = 3
LOAN_INTEREST_PERCENT = 10
LOAN_INTEREST_BURN_PERCENT = 33

LOAN_DEFAULT_CREDIT_SCORE = 50
LOAN_CREDIT_ON_TIME_BONUS = 8
LOAN_CREDIT_OVERDUE_PENALTY = 15
LOAN_AUTO_COLLECT_MINUTES = 15

# Level أعلى = قرض أساسي أكبر + فائدة أقل + مدة أداء أطول. Values are cents.
LOAN_XP_TIERS = [
    {"min_level": 0,   "max_level": 4,   "name": "👤 Member",       "base_limit": 2500,   "interest": 16, "term_days": 2},
    {"min_level": 5,   "max_level": 9,   "name": "🌱 Starter",      "base_limit": 5000,   "interest": 15, "term_days": 2},
    {"min_level": 10,  "max_level": 14,  "name": "🥉 Bronze I",     "base_limit": 7500,   "interest": 14, "term_days": 2},
    {"min_level": 15,  "max_level": 19,  "name": "🥉 Bronze II",    "base_limit": 10000,  "interest": 13, "term_days": 3},
    {"min_level": 20,  "max_level": 24,  "name": "🥈 Silver I",     "base_limit": 15000,  "interest": 12, "term_days": 3},
    {"min_level": 25,  "max_level": 29,  "name": "🥈 Silver II",    "base_limit": 20000,  "interest": 11, "term_days": 3},
    {"min_level": 30,  "max_level": 34,  "name": "💠 Sapphire I",   "base_limit": 30000,  "interest": 10, "term_days": 3},
    {"min_level": 35,  "max_level": 39,  "name": "💠 Sapphire II",  "base_limit": 40000,  "interest": 10, "term_days": 4},
    {"min_level": 40,  "max_level": 44,  "name": "🥇 Gold I",       "base_limit": 50000,  "interest": 9,  "term_days": 4},
    {"min_level": 45,  "max_level": 49,  "name": "🥇 Gold II",      "base_limit": 65000,  "interest": 9,  "term_days": 4},
    {"min_level": 50,  "max_level": 59,  "name": "💎 Platinum",    "base_limit": 80000,  "interest": 8,  "term_days": 5},
    {"min_level": 60,  "max_level": 69,  "name": "💎 Diamond",     "base_limit": 100000, "interest": 8,  "term_days": 5},
    {"min_level": 70,  "max_level": 79,  "name": "🌟 Elite",        "base_limit": 125000, "interest": 7,  "term_days": 5},
    {"min_level": 80,  "max_level": 89,  "name": "👑 Master",       "base_limit": 150000, "interest": 6,  "term_days": 6},
    {"min_level": 90,  "max_level": 99,  "name": "🔱 Mythic",       "base_limit": 200000, "interest": 5,  "term_days": 6},
    {"min_level": 100, "max_level": 999, "name": "🏆 Legend",       "base_limit": 300000, "interest": 4,  "term_days": 7},
]

LOAN_CREDIT_MULTIPLIERS = [
    (0, 0.50),
    (30, 0.75),
    (50, 1.00),
    (70, 1.15),
    (85, 1.25),
]

LOAN_TREASURY_MAX_PERCENT = 20

MINIGAMES_CATEGORY_ID = 1533697548215128134

# ═══════════════════════════════════════════════════════
# ║ 💵 العملة — US Dollar (stored as integer cents) ║
# ═══════════════════════════════════════════════════════

CURRENCY_CODE = "USD"
CURRENCY_SYMBOL = "$"
CURRENCY_NAME = "دولار"
CURRENCY_NAME_PLURAL = "دولار"
CURRENCY_EMOJI = "💵"
MONEY_SCALE = 100

# Display-only FX conversion. The actual GGMW9 ledger ALWAYS stays in USD cents.
# Members can choose how balances are displayed; bets, transfers and accounting remain USD.
DISPLAY_CURRENCIES = {
    "USD": {"emoji": "🇺🇸", "symbol": "$",  "name": "US Dollar",        "decimals": 2},
    "MAD": {"emoji": "🇲🇦", "symbol": "DH", "name": "Moroccan Dirham", "decimals": 2},
    "EUR": {"emoji": "🇪🇺", "symbol": "€",  "name": "Euro",             "decimals": 2},
    "DZD": {"emoji": "🇩🇿", "symbol": "DA", "name": "Algerian Dinar",   "decimals": 2},
}
FX_API_URL = "https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR,MAD,DZD"
FX_REFRESH_MINUTES = 360  # cache daily reference rates; 6h refresh is more than enough

# Large-win feed. 0 means the bot will auto-create/find a public read-only
# channel named 💎・big-wins inside GGMW9 ECONOMY.
CASINO_BIG_WIN_CHANNEL_ID = 0
CASINO_BIG_WIN_MIN_PROFIT = 25000       # $250 net profit in one wager
CASINO_BIG_WIN_MIN_PAYOUT_MULTIPLIER = 10.0


def fmt_money(cents: int, *, signed: bool = False) -> str:
    """Format internal integer cents as USD, e.g. 200000 -> $2,000.00."""
    cents = int(cents or 0)
    sign = ""
    if cents < 0:
        sign = "-"
    elif signed and cents > 0:
        sign = "+"
    value = abs(cents) / MONEY_SCALE
    return f"{sign}{CURRENCY_SYMBOL}{value:,.2f}"


def parse_money_input(value, *, allow_negative: bool = False):
    """Parse user-facing dollars: 10 / $10 / 10.50 -> integer cents."""
    raw = str(value).strip().replace("$", "").replace(",", "").replace(" ", "")
    if not raw:
        return None
    try:
        dec = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not allow_negative and dec <= 0:
        return None
    if allow_negative and dec == 0:
        return None
    cents = int((dec * MONEY_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not allow_negative and cents <= 0:
        return None
    return cents


# Non-gambling income. Values are cents.
COINS_DAILY = 500                 # $5.00
COINS_DAILY_STREAK_BONUS = 100    # +$1/day streak
COINS_DAILY_STREAK_MAX = 1000     # max +$10

COINS_PVP_WIN = 200
COINS_PVP_DRAW = 50
COINS_WORDLE_WIN = 500
COINS_WORDLE_STREAK_BONUS = 250
COINS_HANGMAN_WIN = 150
COINS_REACTION_WIN = 100
COINS_COUNTING_MILESTONE = 200

COINS_DAILY_CAP = 5000            # $50/day from capped mini-game rewards

COOLDOWN_TICTACTOE = 30
COOLDOWN_HANGMAN = 20
COOLDOWN_REACTION = 15
COOLDOWN_DAILY_HOURS = 20

# ═══════════════════════════════════════════════════════
# ║ 🛒 SHOP — categories + real server utility ║
# ═══════════════════════════════════════════════════════

SHOP_CATEGORIES = {
    "boosts": {"emoji": "⚡", "name": "Boosts", "description": "XP وMini-game boosts مؤقتة."},
    "identity": {"emoji": "🎨", "name": "Identity", "description": "ألوان، Roles وTags شخصية."},
    "banking": {"emoji": "🏦", "name": "Banking", "description": "مزايا Savings وTransfers."},
    "social": {"emoji": "📣", "name": "Social", "description": "ظهور وتفاعل داخل السيرفر."},
    "assets": {"emoji": "🏠", "name": "Assets", "description": "ممتلكات دائمة كتدخل فـNet Worth ويمكن تعاود تبيعها."},
    "luxury": {"emoji": "👑", "name": "Luxury", "description": "Prestige sinks للناس اللي جمعو ثروة كبيرة."},
}

# type: xp_boost | coins_boost | role_color | role_color_perm | custom_role |
#       temp_role | legend_tag | shoutout | bank_interest_boost | transfer_fee_pass |
#       collectible_asset | title_role
SHOP_ITEMS = [
    # ⚡ Boosts
    {"id":"xpboost_small","category":"boosts","emoji":"💫","name":"XP Boost 1.25x (1 ساعة)","description":"XP ديال الشات والفويس ×1.25 لمدة ساعة.","price":1500,"type":"xp_boost","multiplier":1.25,"duration_hours":1},
    {"id":"xpboost_medium","category":"boosts","emoji":"⚡","name":"XP Boost 1.5x (1 ساعة)","description":"XP ديالك ×1.5 لمدة ساعة كاملة.","price":3000,"type":"xp_boost","multiplier":1.5,"duration_hours":1},
    {"id":"xpboost_big","category":"boosts","emoji":"🚀","name":"XP Boost 2x (1 ساعة)","description":"XP قوي ×2 لمدة ساعة.","price":7500,"type":"xp_boost","multiplier":2.0,"duration_hours":1},
    {"id":"coinsboost_small","category":"boosts","emoji":"🎮","name":"Mini-Game Boost 1.25x (2 ساعات)","description":"كيزيد Rewards ديال الألعاب غير القمار؛ Odds/Payout ديال Casino ماكيتبدلوش.","price":2500,"type":"coins_boost","multiplier":1.25,"duration_hours":2},

    # 🎨 Identity
    {"id":"color_basic","category":"identity","emoji":"🎨","name":"لون شخصي (7 أيام)","description":"Role بلون كتختارو لمدة 7 أيام.","price":2500,"type":"role_color","duration_days":7},
    {"id":"color_month","category":"identity","emoji":"🌈","name":"لون شخصي (30 يوم)","description":"Role بلون كتختارو لمدة شهر.","price":7000,"type":"role_color","duration_days":30},
    {"id":"permanent_color","category":"identity","emoji":"♾️","name":"لون شخصي دائم","description":"لون دائم فاسمك.","price":30000,"type":"role_color_perm"},
    {"id":"customrole_week","category":"identity","emoji":"🏷️","name":"Custom Role (7 أيام)","description":"Role باسم من اختيارك لمدة أسبوع.","price":10000,"type":"custom_role","duration_days":7},
    {"id":"customrole","category":"identity","emoji":"🏷️","name":"Custom Role (30 يوم)","description":"Role باسم من اختيارك لمدة شهر.","price":25000,"type":"custom_role","duration_days":30},
    {"id":"legend_tag","category":"identity","emoji":"👑","name":"LEGEND Tag (7 أيام)","description":"Tag 👑 LEGEND لمدة أسبوع.","price":15000,"type":"legend_tag","duration_days":7},

    # 🏦 Banking
    {"id":"interest_boost_7d","category":"banking","emoji":"📈","name":"Savings Rate Boost (7 أيام)","description":"+0.05% يومياً فوق Savings rate لمدة 7 أيام؛ الأرباح كتخلص من Treasury.","price":10000,"type":"bank_interest_boost","duration_days":7},
    {"id":"transfer_pass_7d","category":"banking","emoji":"💸","name":"Free Transfers Pass (7 أيام)","description":"0% fee على Bank→Bank transfers لمدة 7 أيام.","price":7500,"type":"transfer_fee_pass","duration_days":7},

    # 📣 Social
    {"id":"shoutout_public","category":"social","emoji":"📣","name":"Public Shoutout","description":"البوت كيدير ليك Shoutout فالقناة المخصصة.","price":3000,"type":"shoutout"},

    # 🏠 Assets — permanent collectibles + resale
    {"id":"asset_car","category":"assets","emoji":"🚗","name":"Sports Car","description":"Asset دائم فـNet Worth. إعادة البيع = 40% من الثمن اللي خلصتي وممولة من Treasury.","price":50000,"type":"collectible_asset"},
    {"id":"asset_apartment","category":"assets","emoji":"🏢","name":"City Apartment","description":"Asset دائم كيبان فالحساب وNet Worth؛ resale ممول من Treasury.","price":150000,"type":"collectible_asset"},
    {"id":"asset_business","category":"assets","emoji":"🏪","name":"GGMW9 Business","description":"Business Asset دائم للـTycoons؛ prestige بلا خلق passive money.","price":500000,"type":"collectible_asset"},
    {"id":"asset_yacht","category":"assets","emoji":"🛥️","name":"Luxury Yacht","description":"Luxury Asset نادر؛ resale 40% إلا Treasury عندها liquidity.","price":1000000,"type":"collectible_asset"},
    {"id":"asset_mansion","category":"assets","emoji":"🏰","name":"Mansion","description":"أغلى Asset فالعالم الاقتصادي ديال GGMW9؛ wealth sink دائم.","price":2500000,"type":"collectible_asset"},

    # 👑 Luxury / prestige roles
    {"id":"high_roller","category":"luxury","emoji":"🎰","name":"HIGH ROLLER (14 يوم)","description":"Prestige Role 🎰 HIGH ROLLER لمدة 14 يوم.","price":50000,"type":"title_role","role_name":"🎰 HIGH ROLLER","role_color":0xF1C40F,"duration_days":14},
    {"id":"banker_title","category":"luxury","emoji":"🏦","name":"BANKER (30 يوم)","description":"Prestige Role 🏦 BANKER لمدة 30 يوم.","price":100000,"type":"title_role","role_name":"🏦 BANKER","role_color":0x2ECC71,"duration_days":30},
    {"id":"tycoon_title","category":"luxury","emoji":"💼","name":"TYCOON (30 يوم)","description":"Prestige Role 💼 TYCOON لمدة شهر.","price":150000,"type":"title_role","role_name":"💼 TYCOON","role_color":0x9B59B6,"duration_days":30},
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
DICE_MIN_BET = 100       # $1
DICE_MAX_BET = 10000     # $100 table limit

# d20, transparent fixed odds. No per-player rigging.
DICE_RISK_LEVELS = {
    "easy":   {"label": "🟢 Low Risk",  "threshold": 9,  "multiplier": 1.55},  # 60% -> 93% RTP
    "medium": {"label": "🟡 Medium",    "threshold": 14, "multiplier": 2.65},  # 35% -> 92.75% RTP
    "hard":   {"label": "🔴 High Risk", "threshold": 19, "multiplier": 9.0},   # 10% -> 90% RTP
}

COOLDOWN_COINFLIP = 5
COINFLIP_MIN_BET = 100
COINFLIP_MAX_BET = 10000
COINFLIP_PAYOUT_MULTIPLIER = 1.90  # 95% RTP

COOLDOWN_SLOTS = 5
SLOTS_MIN_BET = 100
SLOTS_MAX_BET = 5000
SLOTS_SYMBOLS = {
    "🍒": {"weight": 35, "multiplier": 2},
    "🍋": {"weight": 28, "multiplier": 3},
    "🍇": {"weight": 20, "multiplier": 5},
    "🔔": {"weight": 10, "multiplier": 10},
    "💎": {"weight": 5,  "multiplier": 25},
    "7️⃣": {"weight": 2, "multiplier": 50},
}
SLOTS_PAIR_MULTIPLIER = 1.30  # approx 90.65% theoretical RTP

COOLDOWN_SCRATCH = 5
SCRATCH_MIN_BET = 100
SCRATCH_MAX_BET = 5000
SCRATCH_GRID_SIZE = 9
SCRATCH_MATCH_NEEDED = 3
# Fixed outcome table. The grid is constructed AFTER the fair outcome draw so a loss
# can never accidentally become a 3-match win. Theoretical RTP = 91.5%.
SCRATCH_OUTCOMES = [
    {"symbol": None, "weight": 600, "multiplier": 0.0, "label": "No win"},
    {"symbol": "🍀", "weight": 280, "multiplier": 1.5, "label": "Small win"},
    {"symbol": "🍒", "weight": 80,  "multiplier": 2.0, "label": "Double"},
    {"symbol": "⭐",  "weight": 30,  "multiplier": 5.0, "label": "5x"},
    {"symbol": "💎", "weight": 9,   "multiplier": 15.0,"label": "Diamond"},
    {"symbol": "💰", "weight": 1,   "multiplier": 50.0,"label": "Jackpot"},
]
SCRATCH_SYMBOLS = {o["symbol"]: {"multiplier": o["multiplier"]} for o in SCRATCH_OUTCOMES if o["symbol"]}

COOLDOWN_LOTTERY = 8
LOTTERY_MIN_BET = 100
LOTTERY_MAX_BET = 2500
LOTTERY_POOL_SIZE = 20
LOTTERY_PICK_COUNT = 4
LOTTERY_PAYOUTS = {2: 3, 3: 20, 4: 250}  # 76.16% base RTP + funded Global Jackpot on 4/4

# Casino fairness / anti-abuse. Odds never change per user.
CASINO_MAX_BET_WALLET_PERCENT = 25   # default max wager = 25% of Wallet; same rule for everybody
CASINO_MAX_ROUNDS_30M = 60           # anti-bot/session guard
CASINO_PROFILE_WINDOW_MINUTES = 30
CASINO_FAIRNESS_VERSION = "GGMW9 Fair RNG v1"
CASINO_RTP = {
    "coinflip": 95.0,
    "dice_low": 93.0,
    "dice_medium": 92.75,
    "dice_high": 90.0,
    "slots": 90.65,
    "scratch": 91.5,
    "lottery": 76.16,
}

REACTION_MIN_DELAY = 3
REACTION_MAX_DELAY = 15
REACTION_WINDOW_SECONDS = 10

TRIVIA_ENABLED = True
TRIVIA_ANSWER_SECONDS = 30
TRIVIA_AUTO_CHANNEL_IDS = []
TRIVIA_AUTO_INTERVAL_MINUTES = 60
TRIVIA_CHANNEL_ID = 1533700465576116236
TRIVIA_ROUNDS_PER_DIFFICULTY = 6
TRIVIA_COINS = {"easy": 50, "medium": 100, "hard": 200}  # $0.50 / $1 / $2
TRIVIA_SINGLE_COINS = 100  # $1.00
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
