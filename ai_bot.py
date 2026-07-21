import os
import sys
import discord
import aiohttp
import random
import asyncio
import json
import re
from typing import Optional
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from collections import defaultdict

# ═══════ باش print() يطلع مباشرة فـ logs (Railway/containers كيعملو buffer) ═══════
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

# ═══════ مجلد التخزين الدائم (Railway Volume) ═══════
# لازم يكون مطابق تماماً للـ Mount Path اللي حطيتي فـ Railway → Volumes.
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_CHANNEL_ID = 1526384339670270012
WELCOME_CHANNEL_ID = 1524957892925456545
SERVER_NAME = "GGMW9"

# ═══════ STATUS المباشر ديال السيرفر (كل 30 دقيقة) ═══════
STATS_CHANNEL_ID = 1527800975195377804  # ← channel "STATU"
SERVER_INVITE_LINK = "https://discord.gg/5sWatSkSCY"  # ← بدلها بالرابط ديال السيرفر ديالك
STATS_UPDATE_MINUTES = 30
STATS_IMAGE_URL = ""  # ← حط هنا رابط مباشر ديال صورة (بانر) باش تبان فـ رسالة الـ STATUS، ولا خليها فارغة
# ⚠️ خاص الرابط يكون Direct Link ديال صورة حقيقية (يسالي بـ .png/.jpg/.gif فـ الرابط نفسو
# وتقدر تفتحو فـ المتصفح ويبان ليك غير الصورة بوحدها بلا حتى صفحة حداها).
# أحسن طريقة: بعث الصورة فـ أي channel ديال ديسكورد، كليك يمين عليها → Copy Link،
# وحط هاد الرابط هنا (كيبدا بـ https://cdn.discordapp.com/attachments/...).
# مواقع بحال animated-gif-creator.com عادة ماخدامينش كـ hotlink، البوت ما غاديش يقدر يبين الصورة بيهم.

AI_MODEL = "openrouter/free"  # ← مؤقت! كان "deepseek/deepseek-chat" (رجعها ملي تزيد رصيد فـ OpenRouter)

# ═══════ سلسلة الاحتياط (Fallback) ═══════
# إلا الموديل الأساسي (AI_MODEL) وقف بـ 429 (rate limit) ولا 402 (بلا رصيد)،
# البوت كيجرب أوتوماتيكيا الموديلات اللي فـ هاد اللائحة، واحد بواحد،
# قبل ما يستسلم. زيد/بدل الموديلات اللي بغيتي هنا (خاصك تتأكد من الأسماء
# الدقيقة فـ https://openrouter.ai/models قبل ما تزيدهم).
AI_MODEL_FALLBACKS = [
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ═══════ APIs جداد ═══════
OMDB_API_KEY = os.getenv("OMDB_API_KEY")           # ← سجل فـ omdbapi.com (تفاصيل الفيلم + rating)
TMDB_API_KEY = os.getenv("TMDB_API_KEY")           # ← سجل فـ themoviedb.org/settings/api (اكتشاف عشوائي)
NEWS_API_KEY = os.getenv("NEWS_API_KEY")           # ← سجل فـ newsapi.org
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")       # ← سجل فـ last.fm/api
RAWG_API_KEY = os.getenv("RAWG_API_KEY")           # ← سجل فـ rawg.io/apidocs

TMDB_URL = "https://api.themoviedb.org/3"

MEMORY_SIZE = 100
CREATIVITY = 0.85
MAX_REPLY_LENGTH = 1500
API_TIMEOUT = 15

# ═══════════════════════════════════════════════════════
# ║              CHANNELS ديال AUTO-INFO                 ║
# ═══════════════════════════════════════════════════════

NEWS_CHANNEL_IDS = [1526701863141900319]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأخبار
GAMES_CHANNEL_IDS = [1524957892925456546]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الألعاب
MOVIES_CHANNEL_IDS = [1526721884434206820]     # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأفلام
ANIME_CHANNEL_IDS = [1526726257012772985]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأنمي
MUSIC_CHANNEL_IDS = [1524957892925456547]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الموسيقى

# ═══════════════════════════════════════════════════════
# ║              MODERATION & VERIFICATION CONFIG          ║
# ═══════════════════════════════════════════════════════

MOD_LOGS_CHANNEL_ID = 1526470164235681832
VERIFY_CHANNEL_ID = 1526481352264781854
RULES_CHANNEL_ID = 1526474691789721700
BLACKLIST_CHANNEL_ID = 1526858911477661786  # ← حط هنا ID ديال channel "Blacklist things"
REPORTS_CHANNEL_ID = 1526884019105431562    # ← حط هنا ID ديال channel البلاغات (فين كتوصل البلاغات ديال !report)

UNVERIFIED_ROLE_ID = 1526452828267085915
MEMBER_ROLE_ID = 1526451890399739934
MUTED_ROLE_ID = 1526468718534590574
BOYS_ROLE_ID = 1526407092813037588   # ← حط هنا ID ديال role "Boys"
GIRLS_ROLE_ID = 1526337114164301824  # ← حط هنا ID ديال role "Girls"

# ═══════ القوانين ديال السيرفر (بدلها بالقوانين الحقيقية ديالك) ═══════
SERVER_RULES = (
    "**🇲🇦 بالدارجة:**\n"
    "1️⃣ الاحترام واجب بين كاع الأعضاء — ممنوع السب خارج نطاق المزاح، العنصرية، والتنمر.\n"
    "2️⃣ ممنوع السبام والإعلانات بلا إذن من الإدارة.\n"
    "3️⃣ ممنوع المحتوى ديال +18 ولا العنيف ولا الصادم.\n"
    "4️⃣ هضر فـ الشات المخصص ليه (بحال #games للألعاب).\n"
    "5️⃣ احترم القرارات ديال الأدمن والمشرفين.\n"
    "6️⃣ ممنوع مشاركة معلومات شخصية ديال الآخرين (Doxxing).\n"
    "7️⃣ عدم الالتزام بالقوانين غادي يأدي لعقوبة (تحذير، كتم، طرد).\n\n"
    "**🇬🇧 English:**\n"
    "1️⃣ Respect everyone — Insults/cursing are not allowed outside of joking around, racism, or bullying.\n"
    "2️⃣ No spam or ads without staff permission.\n"
    "3️⃣ No NSFW, violent, or shocking content.\n"
    "4️⃣ Talk in the right channel for each topic (e.g. #games for games).\n"
    "5️⃣ Respect staff/admin decisions.\n"
    "6️⃣ No sharing others' personal info (doxxing).\n"
    "7️⃣ Breaking the rules leads to punishment (warning, mute, kick).\n\n"
    "**🇫🇷 Français :**\n"
    "1️⃣ Le respect est obligatoire — Les insultes sont interdites en dehors du cadre de la plaisanterie., de racisme ou de harcèlement.\n"
    "2️⃣ Pas de spam ni de publicité sans autorisation.\n"
    "3️⃣ Contenu +18, violent ou choquant interdit.\n"
    "4️⃣ Parlez dans le salon approprié à chaque sujet (ex. #games pour les jeux).\n"
    "5️⃣ Respectez les décisions de l'administration.\n"
    "6️⃣ Ne partagez pas les infos personnelles des autres (doxxing).\n"
    "7️⃣ Le non-respect des règles entraîne une sanction (avertissement, mute, exclusion)."
)

# ═══════ الاستثناءات ديال Auto-Mod (Owner + أدوار معفيين) ═══════
OWNER_ID = 1260089246216097832  # صاحب السيرفر
EXEMPT_ROLE_IDS = [
    1525712399456272495,  # Admin
    1526182506272133180,  # Moderator
]

BANNED_WORDS = [
    'سبام', 'spam', 'naked.', 'discord.gg', 'العزية', 'عزي',
    'nude', 'porn', 'xxx', 'sex', 'fuck', 'shit', 'bitch'
]

# ═══════ لائحة ديناميكية: كلمات وأفعال ممنوعة كتزاد/كتحيد بالأوامر ═══════
# BANNED_WORDS فوق هي القائمة الأساسية المكتوبة فالكود. أي كلمة/عبارة كتزاد
# ولا كتحيد بالأوامر (!addword, !addaction) كتتسجل فـ BANNED_LISTS_FILE
# باش تبقى محفوظة حتى بعد ريستارت البوت. BANNED_ACTIONS هي عبارات/سلوكيات
# ممنوعة زيادة على الكلمات، وكتتبع نفس آلية الحذف/التحذير ديال BANNED_WORDS.
BANNED_LISTS_FILE = os.path.join(DATA_DIR, "banned_lists.json")
BANNED_ACTIONS = []  # كتتعمر من الملف فـ load_banned_lists()
banned_words_state = {"extra": [], "removed": []}  # كتتعمر من الملف

SPAM_THRESHOLD = 5
SPAM_INTERVAL = 5

# ═══════ درجات العقوبة حسب عدد التحذيرات (سهل التعديل) ═══════
# كل عضو كيبدا بلا تحذيرات. كل تحذير (Auto-Mod ولا !warn يدوي) كيزيد
# العداد ديالو بـ 1. من غير ما يوصل لعتبة، ما كتوقع حتى عقوبة.
# غيّر الأرقام هنا حسب بغيتك — بلا ما تمس شي حاجة أخرى فالكود.
MUTE_AFTER_WARNS = 2     # عدد التحذيرات باش يتكتم أوتوماتيكياً
MUTE_DURATION_MINUTES = 20  # شحال ديال الدقائق كيدوم الكتم التلقائي
KICK_AFTER_WARNS = 4     # عدد التحذيرات باش يتطرد أوتوماتيكياً
BAN_AFTER_WARNS = 6      # عدد التحذيرات باش يتحظر أوتوماتيكياً (نهائي)

WARN_LIMIT = KICK_AFTER_WARNS  # مستعملة فبعض الرسائل القديمة، كتبقى مرتبطة بمرحلة الطرد

# ═══════════════════════════════════════════════════════
# ║              PICK ROLES CONFIG (Dropdown)               ║
# ═══════════════════════════════════════════════════════
# نظام اختيار الأدوار بـ Dropdown Menu (بدل الـ Reactions القديمة).
# كل مجموعة (category) كتبان فـ Select Menu وحدها فـ الرسالة، والعضو
# يقدر يختار عدة أدوار من نفس المجموعة مرة وحدة.
# حط هنا label + emoji + ID ديال الرول (كليك يمين على الرول فـ Discord → Copy ID)
# خاصك تفعّل "Developer Mode" فـ Discord Settings > Advanced باش يبان ليك Copy ID
PICK_ROLES = {
    "🎯 الهوايات": [
        {"label": "Gamer", "emoji": "🎮", "role_id": 1526800480007880845},
        {"label": "Anime Fan", "emoji": "📺", "role_id": 1526800623419523072},
        {"label": "Movie Fan", "emoji": "🎬", "role_id": 1526801019458158642},
        {"label": "Music Fan", "emoji": "🎧", "role_id": 1526801165692702842},
        {"label": "Book Worm", "emoji": "📚", "role_id": 1528897494400897066},   # ← حط ID
        {"label": "Artist", "emoji": "🎨", "role_id": 1528897791089315880},      # ← حط ID
        {"label": "Coder / Tech", "emoji": "💻", "role_id": 1528897975638822924},  # ← حط ID
        {"label": "Sports Fan", "emoji": "⚽", "role_id": 1528898014863691996},  # ← حط ID
    ],
    "🔔 إشعارات (Pings)": [
        {"label": "News Ping", "emoji": "📰", "role_id": 1528916802510389278},     # ← حط ID
        {"label": "Games Ping", "emoji": "🎮", "role_id": 1528916898262159440},    # ← حط ID
        {"label": "Movies Ping", "emoji": "🎬", "role_id": 1528916993304957019},   # ← حط ID
        {"label": "Anime Ping", "emoji": "📺", "role_id": 1528917042630230097},    # ← حط ID
        {"label": "Music Ping", "emoji": "🎧", "role_id": 1528917090071871588},    # ← حط ID
        {"label": "Announcements Ping", "emoji": "📢", "role_id": 1528917133839433851},  # ← حط ID
    ],
    "🌍 اللغة": [
        {"label": "Darija", "emoji": "🇲🇦", "role_id": 1528919040792334497},   # ← حط ID
        {"label": "English", "emoji": "🇬🇧", "role_id": 1528919152767664259},  # ← حط ID
        {"label": "Français", "emoji": "🇫🇷", "role_id": 1528919222888173699},  # ← حط ID
        {"label": "Italiano", "emoji": "🇮🇹", "role_id": 1528921431990337727},   # ← حط ID
        {"label": "Español", "emoji": "🇪🇸", "role_id": 1528921497421222028},    # ← حط ID
        {"label": "العربية", "emoji": "🇸🇦", "role_id": 1528921564354056362},  # ← حط ID
    ],
}


def get_ping_mention(label: str) -> str:
    """كيرجع نص الـ mention ديال رول (بحال '<@&123> ') إلا كان معمر فـ PICK_ROLES،
    وإلا كايرجع string فارغ (باش الرسالة تبعث عادي بلا مشكل)."""
    for roles_list in PICK_ROLES.values():
        for r in roles_list:
            if r["label"] == label and r["role_id"]:
                return f"<@&{r['role_id']}> "
    return ""


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.presences = True  # ← ضروري باش نقدرو نحسبو "Online Members"، خاصك تفعلها من Discord Developer Portal
# (https://discord.com/developers/applications → البوت ديالك → Bot → Privileged Gateway Intents → Presence Intent)
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100
learned_knowledge = []
warns_db = {}
spam_tracker = {}
mute_tasks = {}

# ═══════════════════════════════════════════════════════
# ║   سجل المحتوى المنشور (باش ما يتعاودش تا شي حاجة)      ║
# ═══════════════════════════════════════════════════════
POSTED_HISTORY_FILE = os.path.join(DATA_DIR, "posted_history.json")

posted_history = {
    "news": [],     # روابط الأخبار اللي تبعثات
    "games": [],    # slugs ديال الألعاب اللي تبعثات
    "movies": [],   # IMDB IDs ديال الأفلام اللي تبعثات
    "anime": [],    # mal_id ديال الأنميات اللي تبعثات
    "music": [],    # "artist|track" اللي تبعثات
}

MAX_HISTORY = {
    "news": 500,
    "games": 250,
    "movies": 250,
    "anime": 250,
    "music": 500,
}


def load_posted_history():
    """يقرا السجل ديال المحتوى المنشور من ملف JSON (إلا كان موجود)"""
    global posted_history
    try:
        with open(POSTED_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in posted_history:
            if isinstance(data.get(key), list):
                posted_history[key] = data[key]
        print(f"[HISTORY] تحمل السجل: { {k: len(v) for k, v in posted_history.items()} }")
    except FileNotFoundError:
        print("[HISTORY] ماكاينش سجل سابق، غادي نبداو من الصفر")
    except Exception as e:
        print(f"[HISTORY] خطأ فـ التحميل: {e}")


def save_posted_history():
    """يحفظ السجل ديال المحتوى المنشور فـ ملف JSON"""
    try:
        with open(POSTED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(posted_history, f, ensure_ascii=False)
    except Exception as e:
        print(f"[HISTORY] خطأ فـ الحفظ: {e}")


def is_posted(category: str, item_id: str) -> bool:
    return item_id in posted_history.get(category, [])


def mark_posted(category: str, item_id: str):
    """يسجل حاجة كـ 'تبعثات' باش ما تتعاودش، ويقلّم السجل إلا كبر بزاف"""
    lst = posted_history.setdefault(category, [])
    if item_id not in lst:
        lst.append(item_id)
    limit = MAX_HISTORY.get(category, 300)
    if len(lst) > limit:
        posted_history[category] = lst[-limit:]
    save_posted_history()


def reset_category_history(category: str):
    """كي تسالا كاع الاختيارات ديال شي category، كنبداو من جديد"""
    posted_history[category] = []
    save_posted_history()
    print(f"[HISTORY] {category}: سالات كاع الاختيارات، بدينا من جديد")


load_posted_history()

# ملاحظة: نظام Dropdown ماعادش محتاج يحفظ IDs ديال الرسائل فـ JSON،
# لأن الـ View كتشتغل بـ custom_id ثابت (persistent view) — كتخدم
# فـ أي رسالة وحتى بعد ريستارت البوت، بلا ما نحتاجو نخزنو شي حاجة.

STATS_MESSAGE_FILE = os.path.join(DATA_DIR, "stats_message.json")
stats_message_ids = {}  # {guild_id (str): message_id}


def load_stats_message_ids():
    """يقرا ID ديال رسالة الـ status المحفوظة، باش يبدلها بدل ما يبعث وحدة جديدة كل مرة"""
    global stats_message_ids
    try:
        with open(STATS_MESSAGE_FILE, "r", encoding="utf-8") as f:
            stats_message_ids = json.load(f)
        print(f"[STATS] تحمل {len(stats_message_ids)} رسالة status محفوظة")
    except FileNotFoundError:
        print("[STATS] ماكاينش رسالة status سابقة، غادي نبعثو وحدة جديدة")
    except Exception as e:
        print(f"[STATS] خطأ فـ التحميل: {e}")


def save_stats_message_ids():
    try:
        with open(STATS_MESSAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(stats_message_ids, f, ensure_ascii=False)
    except Exception as e:
        print(f"[STATS] خطأ فـ الحفظ: {e}")


load_stats_message_ids()


# ═══════════════════════════════════════════════════════
# ║   لائحة الكلمات/الأفعال الممنوعة الديناميكية (Owner only) ║
# ═══════════════════════════════════════════════════════

def load_banned_lists():
    """يقرا الكلمات/الأفعال الممنوعة اللي تزادو بالأوامر من ملف JSON"""
    global BANNED_ACTIONS
    try:
        with open(BANNED_LISTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        banned_words_state["extra"] = data.get("extra_words", [])
        banned_words_state["removed"] = data.get("removed_words", [])
        BANNED_ACTIONS[:] = data.get("actions", [])
        print(f"[BANNED_LISTS] تحمل {len(banned_words_state['extra'])} كلمة إضافية، "
              f"{len(banned_words_state['removed'])} كلمة محيدة، {len(BANNED_ACTIONS)} فعل ممنوع")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[BANNED_LISTS] خطأ فـ التحميل: {e}")


def save_banned_lists():
    """يحفظ الكلمات/الأفعال الممنوعة الديناميكية فـ ملف JSON"""
    try:
        with open(BANNED_LISTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "extra_words": banned_words_state["extra"],
                "removed_words": banned_words_state["removed"],
                "actions": BANNED_ACTIONS,
            }, f, ensure_ascii=False)
    except Exception as e:
        print(f"[BANNED_LISTS] خطأ فـ الحفظ: {e}")


def get_active_banned_words() -> list:
    """كترجع اللائحة الفعلية: الأساسية (ناقص لي تحيد) + الإضافية"""
    words = [w for w in BANNED_WORDS if w not in banned_words_state["removed"]]
    for w in banned_words_state["extra"]:
        if w not in words:
            words.append(w)
    return words


load_banned_lists()


# ═══════════════════════════════════════════════════════
# ║   حفظ الرولات ديال العضو (باش يرجعو ليه ملي يرجع للسيرفر)   ║
# ═══════════════════════════════════════════════════════
# كل مرة عضو يخرج من السيرفر (كيك، بان، ولا خرج بنفسو) كنسجلو الرولات
# اللي كانت عندو. ملي يرجع (بعد فك الحظر ولا رجع من بعد الكيك/الخروج)
# كنعطيوه نفس الرولات مباشرة بلا ما يعاود Verification.
MEMBER_ROLES_FILE = os.path.join(DATA_DIR, "member_roles.json")
member_roles_data = {}  # {guild_id (str): {user_id (str): [role_id, ...]}}


def load_member_roles():
    global member_roles_data
    try:
        with open(MEMBER_ROLES_FILE, "r", encoding="utf-8") as f:
            member_roles_data = json.load(f)
        print(f"[MEMBER_ROLES] تحمل بيانات الرولات ديال {sum(len(v) for v in member_roles_data.values())} عضو")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[MEMBER_ROLES] خطأ فـ التحميل: {e}")


def save_member_roles():
    try:
        with open(MEMBER_ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump(member_roles_data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[MEMBER_ROLES] خطأ فـ الحفظ: {e}")


def remember_member_roles(member: discord.Member):
    """كتسجل الرولات الحالية ديال العضو (ناقص @everyone) قبل ما يخرج
    (كيك، بان، ولا خروج عادي) باش يقدر يرجع ليهم ملي يرجع للسيرفر."""
    guild_id = str(member.guild.id)
    user_id = str(member.id)
    role_ids = [r.id for r in member.roles if r.id != member.guild.id]
    if role_ids:
        member_roles_data.setdefault(guild_id, {})[user_id] = role_ids
        save_member_roles()


load_member_roles()


def is_owner(ctx) -> bool:
    """كتأكد بلي الشخص اللي بعث الأمر هو بالضبط الـ Owner (بواسطة ID)،
    بلا ما يهم شنو هي الأدوار/الصلاحيات ديالو فالسيرفر."""
    return bool(OWNER_ID) and ctx.author.id == OWNER_ID


def owner_only():
    """Decorator: كيحدد الأمر غير بالـ Owner (بواسطة ID)، حتى Admin/Mod
    ولا حتى شخص عندو Administrator ما يقدر يستعملو."""
    async def predicate(ctx):
        return is_owner(ctx)
    return commands.check(predicate)


async def _delete_trigger_silently(ctx):
    """يمسح الرسالة اللي فيها الأمر مباشرة (بحال !report) باش حتى حد
    ما يشوف الأمر ولا المحتوى ديالو فالقناة."""
    try:
        await ctx.message.delete()
    except Exception:
        pass


async def apply_warn_escalation(member: discord.Member, guild: discord.Guild, count: int,
                                 reason: str, channel=None) -> Optional[str]:
    """
    كتشوف شحال ديال التحذيرات وصلات لهاد العضو، وكتطبق العقوبة المناسبة
    حسب MUTE_AFTER_WARNS / KICK_AFTER_WARNS / BAN_AFTER_WARNS (فالـ CONFIG).
    كتبدا من الأعلى (حظر) للأسفل (كتم) باش ما تطبقش عدة عقوبات فنفس الوقت.
    كترجع "ban" / "kick" / "mute" إلا تطبقات عقوبة، وإلا None.
    """
    if BAN_AFTER_WARNS and count >= BAN_AFTER_WARNS:
        try:
            await member.ban(reason=f"{count} تحذيرات: {reason}")
            if channel:
                await channel.send(f"🚫 {member.mention} تم حظره تلقائياً ({count} تحذيرات)!", delete_after=10)
            await log_action(
                guild, "🚫 Auto-Ban",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**السبب:** {count} تحذيرات — {reason}",
                discord.Color.dark_red()
            )
            clear_warns(str(member.id))
            return "ban"
        except discord.Forbidden:
            return None

    if KICK_AFTER_WARNS and count >= KICK_AFTER_WARNS:
        try:
            await member.kick(reason=f"{count} تحذيرات: {reason}")
            if channel:
                await channel.send(f"👢 {member.mention} تم طرده تلقائياً ({count} تحذيرات)!", delete_after=10)
            await log_action(
                guild, "👢 Auto-Kick",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**السبب:** {count} تحذيرات — {reason}",
                discord.Color.orange()
            )
            clear_warns(str(member.id))
            return "kick"
        except discord.Forbidden:
            return None

    if MUTE_AFTER_WARNS and count >= MUTE_AFTER_WARNS:
        muted_role = guild.get_role(MUTED_ROLE_ID)
        if muted_role and muted_role not in member.roles:
            try:
                await member.add_roles(muted_role)
                user_id = str(member.id)
                if user_id in mute_tasks and not mute_tasks[user_id].done():
                    mute_tasks[user_id].cancel()
                task = asyncio.create_task(auto_unmute(member, MUTE_DURATION_MINUTES, guild))
                mute_tasks[user_id] = task
                if channel:
                    await channel.send(
                        f"🔇 {member.mention} تكتم تلقائياً ({count} تحذيرات، {MUTE_DURATION_MINUTES} دقيقة)!",
                        delete_after=10
                    )
                await log_action(
                    guild, "🔇 Auto-Mute",
                    f"**المستخدم:** {member.mention} ({member.name})\n"
                    f"**السبب:** {count} تحذيرات — {reason}\n"
                    f"**المدة:** {MUTE_DURATION_MINUTES} دقيقة",
                    discord.Color.yellow()
                )
                return "mute"
            except discord.Forbidden:
                return None

    return None


def get_system_prompt(user_gender="unknown"):
    base_prompt = 'أنت "GGMW9"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.'
    base_prompt += '\n\n## قواعدك الأساسية:\n\n'
    base_prompt += '1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.\n'
    base_prompt += '   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"\n'
    base_prompt += '   - الحروف اللاتينية: "3" = "ع"، "7" = "ح"، "9" = "ق"، "5" = "خ"...\n\n'
    base_prompt += '2. **الأسلوب**: \n'
    base_prompt += '   - كأنك كتهضر مع صاحبك فـ مقهى\n'
    base_prompt += '   - عصبي وذكي في نفس الوقت\n'
    base_prompt += '   - تضحك بـ "هههه" ولا "😂"\n'
    base_prompt += '   - تستخدم "خويا"، "صاحبي"، "ازبي"، "ولدي"\n\n'
    base_prompt += '3. **الذكاء والدقة**:\n'
    base_prompt += '   - جاوب **مباشرة** على السؤال\n'
    base_prompt += '   - ما تدوّرش بزاف\n'
    base_prompt += '   - حلل بـ منطق واقعي ودقيق\n\n'
    base_prompt += '4. **المصادر والروابط**:\n'
    base_prompt += '   - إلا عندك معلومة مؤكدة → قول المصدر\n'
    base_prompt += '   - مثال: "حسب Wikipedia: [رابط]"\n'
    base_prompt += '   - إلا ما عندكش → قول "حسب اللي كنعرف..."\n\n'
    base_prompt += '5. **الشتائم المغربية - فهم ورد**:\n'
    base_prompt += '   - تفهم **كاع الشتائم**: عربية ولاتينية\n'
    base_prompt += '   - ترد بـ **ذكاء وسلاسة**\n'
    base_prompt += '   - تقدر تسب **بسلاسة** إلا الزبون بدا\n\n'
    base_prompt += '6. **التعلم**: إلا شي حد علمك شي حاجة → حفظها واستعملها فـ المستقبل\n\n'
    base_prompt += '7. **الواقعية**: كأنك إنسان حقيقي، ما تقولش "أنا AI"\n\n'
    base_prompt += '8. **الاختصارات**: "hh"، "wakha"، "sa7bi"، "chof"، "3ziz"\n\n'
    base_prompt += 'رد دائماً كأنك **GGMW9 من الدار البيضاء** — واقعي، ذكي، عصبي!'

    if user_gender == "female":
        base_prompt += '\n\n9. **التعامل مع البنات**: "أختي"، "صاحبتي"، "واخا الالة"، محترم وودي'
    elif user_gender == "male":
        base_prompt += '\n\n9. **التعامل مع الدراري**: "خويا"، "صاحبي"، "ازبي"، "واخا أسيدي"، ودي ومباشر'

    return base_prompt


def detect_gender(username: str, display_name: str) -> str:
    name_lower = (username + " " + display_name).lower()
    female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                     "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                     "نور", "ليلى", "رجاء", "سميرة", "فاتي", "زينب", "أسماء",
                     "hana", "chaimae", "souad", "latifa", "meriem", "meryем"]
    male_signs = ["mohamed", "ahmed", "youssef", "omar", "karim", "amine", "hassan",
                   "mehdi", "reda", "adil", "khalid", "brahim", "said", "mustapha",
                   "عبد", "محمد", "أحمد", "يوسف", "عمر", "كريم", "أمين", "حسن",
                   "مهدي", "رضا", "عادل", "خالد", "براهيم", "سعيد", "مصطفى"]
    for sign in female_signs:
        if sign in name_lower:
            return "female"
    for sign in male_signs:
        if sign in name_lower:
            return "male"
    return "unknown"


async def call_openrouter_chat(messages: list, max_tokens: int, temperature: float) -> tuple:
    """
    كيبعث طلب لـ OpenRouter، وإلا وقف الموديل الأساسي بـ 429 (rate limit)
    ولا 402 (بلا رصيد)، كيجرب الموديلات اللي فـ AI_MODEL_FALLBACKS واحد بواحد.
    كيرجع (content, None) إلا نجح، ولا (None, error_text) إلا فشلو كامل الموديلات.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT"
    }
    models_to_try = [AI_MODEL] + [m for m in AI_MODEL_FALLBACKS if m != AI_MODEL]
    last_error = "ماكاين حتى موديل جرب"

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
                async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        try:
                            message = data["choices"][0]["message"]
                        except (KeyError, IndexError, TypeError):
                            print(f"[OPENROUTER] ❌ {model} رجع شكل غريب بلا choices/message: {str(data)[:200]}")
                            last_error = "شكل الرد ماشي متوقع (بلا choices/message)"
                            continue

                        # بعض الموديلات (خصوصا reasoning) كترجع content فارغة/None
                        # وكتحط النص فـ reasoning بدلها
                        content = message.get("content") or message.get("reasoning") or ""
                        content = content.strip() if isinstance(content, str) else ""

                        if not content:
                            print(f"[OPENROUTER] ⚠️ {model} رجع content فارغة، نجرب الموديل اللي بعدو...")
                            last_error = "content فارغة من الموديل"
                            continue

                        if model != AI_MODEL:
                            print(f"[OPENROUTER] ⚠️ الموديل الأساسي فشل، خدام بـ fallback: {model}")
                        return content, None
                    elif resp.status in (429, 402):
                        body = await resp.text()
                        print(f"[OPENROUTER] ⚠️ {model} رجع {resp.status}, نجرب الموديل اللي بعدو... ({body[:150]})")
                        last_error = f"{resp.status}: {body[:200]}"
                        continue
                    else:
                        body = await resp.text()
                        print(f"[OPENROUTER] ❌ {model} رجع {resp.status}: {body[:200]}")
                        last_error = f"{resp.status}: {body[:200]}"
                        continue
        except asyncio.TimeoutError:
            print(f"[OPENROUTER] ⏳ Timeout مع {model}")
            last_error = "timeout"
            continue
        except Exception as e:
            print(f"[OPENROUTER] ❌ Exception مع {model}: {e}")
            last_error = str(e)
            continue

    return None, last_error


async def ask_ai(user_id: str, username: str, display_name: str, prompt: str) -> str:
    gender = detect_gender(username, display_name)
    messages = [{"role": "system", "content": get_system_prompt(gender)}]
    if learned_knowledge:
        knowledge_text = "حوايج جديدة تعلمتهوم:\n" + "\n".join(learned_knowledge[-20:])
        messages.append({"role": "system", "content": knowledge_text})
    for msg in user_memory[user_id]:
        messages.append(msg)
    for msg in server_memory[-10:]:
        messages.append(msg)
    messages.append({"role": "user", "content": prompt})

    reply, error = await call_openrouter_chat(messages, MAX_REPLY_LENGTH, CREATIVITY)

    if error:
        return f"❌ Error: {error}"

    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id].append({"role": "assistant", "content": reply})
    if len(user_memory[user_id]) > MEMORY_SIZE * 2:
        user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
    server_memory.append({"role": "user", "content": f"[{username}]: {prompt}"})
    server_memory.append({"role": "assistant", "content": reply})
    if len(server_memory) > MAX_SERVER_MEMORY * 2:
        server_memory[:] = server_memory[-MAX_SERVER_MEMORY * 2:]
    return reply


# ═══════════════════════════════════════════════════════
# ║              APIs حقيقية (جديد)                        ║
# ═══════════════════════════════════════════════════════

async def fetch_json(url: str, params: dict = None, headers: dict = None) -> dict:
    """جيب JSON من أي API (مع logging باش نعرفو شنو وقع بالضبط)"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception as e:
                        print(f"[FETCH_JSON] JSON decode error من {url}: {e}")
                        return {}
                else:
                    body = await resp.text()
                    print(f"[FETCH_JSON] {url} رجع status {resp.status}: {body[:200]}")
                    return {}
    except asyncio.TimeoutError:
        print(f"[FETCH_JSON] Timeout فـ {url}")
        return {}
    except Exception as e:
        print(f"[FETCH_JSON] Exception فـ {url}: {e}")
        return {}


async def fetch_html(url: str, headers: dict = None) -> str:
    """جيب HTML خام من أي رابط (باش نقدرو نقرأو og:image مثلا)"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.text(errors="ignore")
                return ""
    except Exception as e:
        print(f"[FETCH_HTML] Exception فـ {url}: {e}")
        return ""


async def get_wikipedia_image(title: str) -> str:
    """صورة احتياطية (fallback) من Wikipedia REST API — مجاني وبلا API key"""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        data = await fetch_json(url)
        if not data:
            return ""
        original = data.get("originalimage", {}).get("source", "")
        if original:
            return original
        return data.get("thumbnail", {}).get("source", "")
    except Exception as e:
        print(f"[WIKI] خطأ فـ جلب الصورة لـ '{title}': {e}")
        return ""


async def get_og_image(page_url: str) -> str:
    """صورة احتياطية من og:image meta tag ديال صفحة الويب نفسها (مثلا صفحة الخبر) — بلا API key"""
    try:
        html = await fetch_html(page_url, headers={"User-Agent": "Mozilla/5.0 (compatible; GGMW9Bot/1.0)"})
        if not html:
            return ""
        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
        return match.group(1) if match else ""
    except Exception as e:
        print(f"[OG_IMAGE] خطأ فـ جلب الصورة من {page_url}: {e}")
        return ""


GENRE_TRANSLATIONS = {
    "action": "أكشن", "adventure": "مغامرة", "comedy": "كوميديا",
    "drama": "دراما", "horror": "رعب", "thriller": "تشويق",
    "romance": "رومانسية", "sci-fi": "خيال علمي", "science fiction": "خيال علمي",
    "fantasy": "فانتازيا", "mystery": "غموض", "crime": "جريمة",
    "animation": "أنيميشن", "documentary": "وثائقي", "family": "عائلي",
    "musical": "موسيقي", "music": "موسيقى", "war": "حرب", "history": "تاريخي",
    "western": "وسترن", "biography": "سيرة ذاتية", "sport": "رياضي",
    "sports": "رياضي", "shounen": "شونين", "shoujo": "شوجو", "seinen": "سينين",
    "josei": "جوسي", "slice of life": "حياة يومية", "supernatural": "خوارق",
    "psychological": "نفسي", "school": "مدرسي", "isekai": "إيسيكاي",
    "ecchi": "إيتشي", "mecha": "ميكا", "sci fi": "خيال علمي", "indie": "إندي",
    "rpg": "لعب أدوار", "role-playing (rpg)": "لعب أدوار", "shooter": "تصويب",
    "strategy": "استراتيجية", "puzzle": "ألغاز", "racing": "سباق",
    "simulation": "محاكاة", "platformer": "منصات", "fighting": "قتال",
    "arcade": "أركيد", "casual": "كاجوال", "massively multiplayer": "متعدد اللاعبين",
    "board games": "ألعاب طاولة", "card": "ورق", "educational": "تعليمي",
    "kids": "أطفال", "superhero": "أبطال خارقين", "suspense": "إثارة",
    "short": "قصير", "film-noir": "نوار", "talk-show": "برنامج حواري",
    "reality-tv": "واقعي", "news": "أخبار", "game-show": "مسابقات",
}


async def translate_genres(genres_text: str) -> str:
    """
    يترجم لائحة الأنواع (Action, Comedy...) للعربية/الدارجة.
    كنبداو بقاموس ثابت (سريع وموثوق) لأشهر الأنواع، وإلا لقينا نوع
    ماكاينش فالقاموس كنعيطو لـ AI باش يترجموه (fallback).
    ملاحظة: جربنا الترجمة بـ AI وحدها فـ الأول، ولكن الموديل كان
    كيخلي الأنواع كيفما هي (كيتعامل معاها كـ tags ثابتة ماشي نص عادي)،
    فـ القاموس أوثق بزاف لهاد الحالة.
    """
    if not genres_text or genres_text == "N/A":
        return genres_text
    parts = [p.strip() for p in genres_text.split(",")]
    result = []
    for p in parts:
        mapped = GENRE_TRANSLATIONS.get(p.lower())
        if mapped:
            result.append(mapped)
        else:
            ai_translated = await translate_to_darija(p)
            result.append(ai_translated if ai_translated and ai_translated.lower() != p.lower() else p)
    return "، ".join(result)


async def translate_to_darija(text: str) -> str:
    """يترجم نص من الانجليزية للدارجة المغربية عبر AI (مع fallback أوتوماتيك للموديل)"""
    if not text:
        return text
    if not OPENROUTER_API_KEY:
        print("[TRANSLATE] ⚠️ OPENROUTER_API_KEY ماكايناش (فارغة)! ماغاديش نترجمو والو.")
        return text

    messages = [
        {
            "role": "system",
            "content": (
                "نتا مترجم محترف. ترجم النص التالي من الانجليزية للدارجة المغربية "
                "بطريقة طبيعية وسلسة ومفهومة. غير الترجمة، بلا مقدمات، بلا تعليقات، "
                "بلا علامات تنصيص."
            )
        },
        {"role": "user", "content": text}
    ]

    translated, error = await call_openrouter_chat(messages, 700, 0.3)

    if error:
        print(f"[TRANSLATE] ❌ فشلو كاع الموديلات: {error}")
        return text

    translated = translated.strip()
    print(f"[TRANSLATE] ✅ قبل: '{text[:50]}' | بعد: '{translated[:50]}'")
    return translated if translated else text


async def get_movie_from_omdb() -> dict:
    """
    اكتشاف عشوائي حقيقي للأفلام (بلا لائحة ثابتة):
    1) TMDb /discover/movie بصفحة عشوائية → لائحة أفلام معروفة (مفلترة بعدد الأصوات)
    2) نجيبو imdb_id ديال كل واحد عبر TMDb external_ids
    3) نستعملو OMDb (i=imdb_id) باش نجيبو التفاصيل الكاملة + rating (نفس الفورمات ديال قبل)
    """
    if not TMDB_API_KEY or not OMDB_API_KEY:
        print("[MOVIE] TMDB_API_KEY أو OMDB_API_KEY ماكاينين! خاصك تزيدهم فـ Railway Variables.")
        return {}

    discover_url = f"{TMDB_URL}/discover/movie"
    omdb_url = "https://www.omdbapi.com/"

    for page_attempt in range(5):  # يجرب حتى 5 صفحات عشوائية ديال TMDb قبل ما يستسلم
        params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "sort_by": random.choice(["vote_average.desc", "popularity.desc"]),
            "vote_count.gte": 300,   # نتفاداو الأفلام المغمورة اللي عندها صوت ولا صوتين
            "include_adult": "false",
            "page": random.randint(1, 40),
        }
        data = await fetch_json(discover_url, params)
        results = data.get("results", []) if data else []
        if not results:
            continue

        random.shuffle(results)

        for movie in results[:12]:  # يجرب حتى 12 فيلم من نفس الصفحة
            tmdb_id = movie.get("id")
            if not tmdb_id:
                continue

            ext_data = await fetch_json(
                f"{TMDB_URL}/movie/{tmdb_id}/external_ids",
                {"api_key": TMDB_API_KEY}
            )
            imdb_id = ext_data.get("imdb_id") if ext_data else None
            if not imdb_id or is_posted("movies", imdb_id):
                continue

            omdb_data = await fetch_json(omdb_url, {
                "i": imdb_id,
                "apikey": OMDB_API_KEY,
                "plot": "full"
            })
            if not omdb_data or omdb_data.get("Response") != "True":
                continue

            rating = omdb_data.get("imdbRating", "0")
            try:
                if rating in ("N/A", None) or float(rating) < 6.0:
                    continue
            except ValueError:
                continue

            plot = omdb_data.get("Plot", "No plot available.")
            plot_ar = await translate_to_darija(plot)

            mark_posted("movies", imdb_id)

            poster = omdb_data.get("Poster", "")
            if not poster or poster == "N/A":
                poster = await get_wikipedia_image(f"{omdb_data.get('Title', '')} (film)")

            return {
                "title": omdb_data.get("Title", "Unknown"),
                "year": omdb_data.get("Year", "N/A"),
                "genre": await translate_genres(omdb_data.get("Genre", "N/A")),
                "plot": plot_ar,
                "rating": rating,
                "poster": poster,
                "imdb": f"https://www.imdb.com/title/{imdb_id}/"
            }

    return {}


async def get_anime_from_jikan() -> dict:
    """
    اكتشاف عشوائي للأنمي عبر Jikan /top/anime بصفحة عشوائية (بلا لائحة ثابتة).
    بدلنا /random/anime (كان كيرجع من كامل قاعدة بيانات MAL بما فيها آلاف
    الحوايج المغمورة، فمعدل النجاح كان ضعيف بزاف وكيحتاج بزاف طلبات) بـ
    /top/anime اللي معاها كل نتيجة مضمونة الجودة من البداية (مرتبة بالـ score)،
    فطلب واحد فـ الغالب كافي.
    """
    jikan_headers = {"User-Agent": "Mozilla/5.0 (compatible; GGMW9Bot/1.0)"}
    list_url = "https://api.jikan.moe/v4/top/anime"

    for page_attempt in range(6):  # يجرب حتى 6 صفحات عشوائية قبل ما يستسلم
        if page_attempt > 0:
            await asyncio.sleep(1.5)  # نحترمو rate-limit ديال Jikan

        params = {"page": random.randint(1, 50), "limit": 25}  # top 1250 أنمي تقريبا
        data = await fetch_json(list_url, params, headers=jikan_headers)
        results = data.get("data", []) if data else []

        if not results:
            print(f"[JIKAN] محاولة {page_attempt+1}: الصفحة رجعت فارغة (data={bool(data)})")
            continue

        random.shuffle(results)

        for anime in results:
            mal_id = anime.get("mal_id")
            if not mal_id or is_posted("anime", str(mal_id)):
                continue
            if not anime.get("synopsis"):
                continue

            print(f"[JIKAN] ✅ اختار: {anime.get('title')} (score={anime.get('score')})")
            return await _build_anime_embed_data(anime)

        print(f"[JIKAN] محاولة {page_attempt+1}: كاع نتائج الصفحة مبعوتين من قبل ولا بلا synopsis")

    print("[JIKAN] ❌ ماكاينش نتيجة بعد كل المحاولات")
    return {}


async def _build_anime_embed_data(anime: dict) -> dict:
    """يبني الـ dict الجاهز للـ embed انطلاقا من داتا أنمي جاية من Jikan"""
    mal_id = anime.get("mal_id")
    synopsis = anime.get("synopsis") or "No synopsis available."
    synopsis_ar = await translate_to_darija(synopsis)

    mark_posted("anime", str(mal_id))

    poster = anime.get("images", {}).get("jpg", {}).get("large_image_url", "")
    if not poster:
        poster = await get_wikipedia_image(f"{anime.get('title', '')} (anime)")

    return {
        "title": anime.get("title", "Unknown"),
        "title_jp": anime.get("title_japanese", ""),
        "type": anime.get("type", "TV"),
        "episodes": anime.get("episodes", "N/A"),
        "genres": await translate_genres(", ".join([g["name"] for g in anime.get("genres", [])])),
        "synopsis": synopsis_ar,
        "score": anime.get("score", 0),
        "poster": poster,
        "url": anime.get("url", "")
    }


async def get_game_from_rawg() -> dict:
    """
    اكتشاف عشوائي حقيقي للألعاب عبر RAWG /games (بلا لائحة ثابتة).
    كنختارو صفحة عشوائية من أعلى الألعاب تقييما (ordering)، ومنبعد كنجيبو
    التفاصيل الكاملة ديال اللعبة المختارة.
    """
    if not RAWG_API_KEY:
        print("[RAWG] RAWG_API_KEY ماكاينش!")
        return {}

    list_url = "https://api.rawg.io/api/games"

    for page_attempt in range(5):  # يجرب حتى 5 صفحات عشوائية قبل ما يستسلم
        params = {
            "key": RAWG_API_KEY,
            "ordering": random.choice(["-rating", "-metacritic", "-added"]),
            "page_size": 40,
            "page": random.randint(1, 150),  # كنبقاو فـ نطاق الألعاب المعروفة بزاف
        }
        data = await fetch_json(list_url, params)
        results = data.get("results", []) if data else []
        if not results:
            continue

        random.shuffle(results)

        for game in results[:10]:  # يجرب حتى 10 ألعاب من نفس الصفحة
            slug = game.get("slug")
            rating = game.get("rating", 0)
            if not slug or is_posted("games", slug) or rating < 3.2:
                continue

            detail = await fetch_json(f"{list_url}/{slug}", {"key": RAWG_API_KEY})
            if not detail or not detail.get("name"):
                continue

            description = detail.get("description_raw", "No description available.")[:500]
            description_ar = await translate_to_darija(description)

            mark_posted("games", slug)

            poster = detail.get("background_image", "")
            if not poster:
                poster = await get_wikipedia_image(f"{detail.get('name', '')} (video game)")

            return {
                "name": detail.get("name", "Unknown"),
                "released": detail.get("released", "N/A"),
                "genres": await translate_genres(", ".join([g["name"] for g in detail.get("genres", [])])),
                "description": description_ar,
                "rating": f"{rating}/5",
                "poster": poster,
                "url": f"https://rawg.io/games/{slug}"
            }

    return {}


async def get_track_artwork(artist: str, track_name: str) -> str:
    """يجيب ملصق (poster) ديال الأغنية: يجرب iTunes أولا، ولا Deezer كـ fallback (الاثنين مجانيين بلا API key)"""
    # ═══ المحاولة 1: iTunes Search API ═══
    try:
        url = "https://itunes.apple.com/search"
        params = {
            "term": f"{artist} {track_name}",
            "media": "music",
            "entity": "song",
            "limit": 1
        }
        data = await fetch_json(url, params)
        results = data.get("results", []) if data else []
        if results:
            artwork = results[0].get("artworkUrl100", "")
            if artwork:
                # نكبرو الحجم من 100x100 لـ 600x600 (كيفما كان الفورمات ديال الرابط)
                return artwork.replace("100x100", "600x600")
        else:
            print(f"[ITUNES] ماكاينش نتيجة لـ '{artist} - {track_name}'")
    except Exception as e:
        print(f"[ITUNES] خطأ فـ جلب الملصق: {e}")

    # ═══ المحاولة 2: Deezer API (fallback) ═══
    try:
        url = "https://api.deezer.com/search"
        params = {"q": f"artist:\"{artist}\" track:\"{track_name}\""}
        data = await fetch_json(url, params)
        results = data.get("data", []) if data else []
        if results:
            album = results[0].get("album", {})
            cover = album.get("cover_xl", "") or album.get("cover_big", "") or album.get("cover_medium", "")
            if cover:
                return cover
        else:
            print(f"[DEEZER] ماكاينش نتيجة لـ '{artist} - {track_name}'")
    except Exception as e:
        print(f"[DEEZER] خطأ فـ جلب الملصق: {e}")

    return ""


async def get_music_from_lastfm() -> dict:
    """
    جيب أغنية عشوائية من Last.fm. لائحة الفنانين ماشي ثابتة —
    كنجيبوها ديناميكيا من chart.getTopArtists (top chart عالمي محين)
    باش يتوسع الاختيار وميبقاش محدود فـ 30 فنان.
    """
    if not LASTFM_API_KEY:
        return {}

    url = "http://ws.audioscrobbler.com/2.0/"

    chart_data = await fetch_json(url, {
        "method": "chart.getTopArtists",
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": 200,
    })
    popular_artists = [
        a.get("name") for a in chart_data.get("artists", {}).get("artist", [])
        if a.get("name")
    ] if chart_data else []

    if not popular_artists:
        # fallback بسيط إلا chart API طاح مؤقتا
        popular_artists = [
            "The Weeknd", "Drake", "Taylor Swift", "Dua Lipa", "Bad Bunny"
        ]

    artists_to_try = random.sample(popular_artists, min(len(popular_artists), 15))

    for artist in artists_to_try:  # يجرب حتى 15 فنان (من التشارت الديناميكي) قبل ما يستسلم
        params = {
            "method": "artist.gettoptracks",
            "artist": artist,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": 10
        }

        data = await fetch_json(url, params)

        if data and "toptracks" in data and "track" in data["toptracks"]:
            tracks = data["toptracks"]["track"]
            fresh_tracks = [
                t for t in tracks
                if not is_posted("music", f"{artist}|{t.get('name', '')}")
            ]
            if not fresh_tracks:
                continue  # كاع الأغاني ديال هاد الفنان تبعثاو، نجربو فنان آخر

            track = random.choice(fresh_tracks)
            listeners_str = track.get("listeners", "0")
            try:
                listeners = int(listeners_str)
            except (ValueError, TypeError):
                listeners = 0

            mark_posted("music", f"{artist}|{track.get('name', '')}")

            poster = await get_track_artwork(artist, track.get("name", ""))

            return {
                "name": track.get("name", "Unknown"),
                "artist": artist,
                "listeners": listeners,
                "url": track.get("url", ""),
                "poster": poster
            }

    # إلا كاع الفنانين تسالاو، نبداو من جديد
    reset_category_history("music")
    return {}


async def get_news_from_api() -> dict:
    """جيب خبر من NewsAPI"""
    if not NEWS_API_KEY:
        return {}
    
    url = "https://newsapi.org/v2/top-headlines"
    categories = random.sample(["technology", "entertainment", "science", "sports"], 4)

    for category in categories:  # يجرب كاع الفئات باش يلقى خبر جديد ما تبعثش
        params = {
            "apiKey": NEWS_API_KEY,
            "category": category,
            "language": "en",
            "pageSize": 30
        }

        data = await fetch_json(url, params)

        if not data or "articles" not in data or not data["articles"]:
            continue

        # يفلتر المقالات اللي عندها عنوان ووصف حقيقيين (NewsAPI كترجع بزاف [Removed])
        # وما تبعثاتش من قبل، باش يكون دايما خبر جديد 100%
        valid_articles = [
            a for a in data["articles"]
            if a.get("title") and a.get("title") != "[Removed]"
            and a.get("url") and not is_posted("news", a["url"])
        ]
        if not valid_articles:
            continue

        article = random.choice(valid_articles)
        title_ar = await translate_to_darija(article.get("title", "Unknown"))
        desc_ar = await translate_to_darija(article.get("description", "No description."))

        mark_posted("news", article["url"])

        image = article.get("urlToImage", "")
        if not image:
            image = await get_og_image(article.get("url", ""))

        return {
            "title": title_ar,
            "description": desc_ar,
            "url": article.get("url", ""),
            "source": article.get("source", {}).get("name", "Unknown"),
            "image": image
        }

    # ماكاينش خبر جديد دابا فـ كاع الفئات، غادي نعاودو نجربو فـ الدورة الجاية
    return {}


# ═══════════════════════════════════════════════════════
# ║              MODERATION FUNCTIONS                       ║
# ═══════════════════════════════════════════════════════

async def log_action(guild, title: str, description: str, color: discord.Color):
    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"GGMW9 | {datetime.now().strftime('%H:%M:%S')}")
        await channel.send(embed=embed)


def check_role_hierarchy(guild: discord.Guild) -> list:
    """
    كيتأكد أن role ديال البوت فوق فالترتيب من الرولات اللي خاصو يعطي/يهزها
    (Member, Unverified, Muted). كيرجع لائحة ديال المشاكل (فاضية = كلشي مزيان).
    """
    problems = []
    bot_member = guild.me
    if not bot_member:
        return ["❌ ما قدرتش نلقى البوت فالسيرفر."]

    bot_top_role = bot_member.top_role

    roles_to_check = {
        "Member": MEMBER_ROLE_ID,
        "Unverified": UNVERIFIED_ROLE_ID,
        "Muted": MUTED_ROLE_ID,
    }

    for role_name, role_id in roles_to_check.items():
        role = guild.get_role(role_id)
        if not role:
            problems.append(f"⚠️ role ديال **{role_name}** (ID: `{role_id}`) ماكاينش فالسيرفر — تأكد من الـ ID فالـ CONFIG.")
            continue
        if role >= bot_top_role:
            problems.append(
                f"❌ role ديال **{role_name}** (`{role.name}`) فوق ولا مساوي لـ role ديال البوت (`{bot_top_role.name}`) "
                f"فالترتيب — خاصك تسحب role ديال البوت فوق منو فـ **Server Settings → Roles**."
            )

    if not bot_member.guild_permissions.manage_roles:
        problems.append("❌ role ديال البوت ماعندوش صلاحية **Manage Roles** — خاصك تفعلها.")

    return problems


async def send_warn_dm(member: discord.Member, count: int, reason: str):
    """
    كيبعث فـ DM تنبيه احترافي للعضو ملي ياخد تحذير (يدوي ولا أوتوماتيكي)،
    فيه رقم التحذير، السبب، وجدول العقوبات المتدرجة (كتم/طرد/حظر) مبني
    على الأرقام الحقيقية ديال الـ CONFIG. مكتوب بـ 3 لغات: الدارجة، الفرنسية، الإنجليزية.
    """
    embed = discord.Embed(
        title="⚠️ تحذير جديد | Avertissement | Warning",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="🇲🇦 بالدارجة",
        value=(
            f"خذيتي تحذير فـ **{SERVER_NAME}**.\n"
            f"**السبب:** {reason}\n"
            f"**عدد التحذيرات ديالك دابا:** {count}\n\n"
            f"⚠️ **خاصك تعرف:**\n"
            f"🔇 عند {MUTE_AFTER_WARNS} تحذيرات → كتم تلقائي لمدة {MUTE_DURATION_MINUTES} دقيقة\n"
            f"👢 عند {KICK_AFTER_WARNS} تحذيرات → طرد تلقائي من السيرفر\n"
            f"🚫 عند {BAN_AFTER_WARNS} تحذيرات → حظر نهائي من السيرفر\n\n"
            f"من فضلك احترم/ي قوانين السيرفر باش ما توصلش لهاد المراحل."
        ),
        inline=False
    )
    embed.add_field(
        name="🇫🇷 En Français",
        value=(
            f"Vous avez reçu un avertissement sur **{SERVER_NAME}**.\n"
            f"**Raison :** {reason}\n"
            f"**Nombre total d'avertissements :** {count}\n\n"
            f"⚠️ **À savoir :**\n"
            f"🔇 À {MUTE_AFTER_WARNS} avertissements → mute automatique pendant {MUTE_DURATION_MINUTES} minutes\n"
            f"👢 À {KICK_AFTER_WARNS} avertissements → expulsion automatique du serveur\n"
            f"🚫 À {BAN_AFTER_WARNS} avertissements → bannissement définitif du serveur\n\n"
            f"Merci de respecter les règles du serveur pour éviter d'en arriver là."
        ),
        inline=False
    )
    embed.add_field(
        name="🇬🇧 In English",
        value=(
            f"You have received a warning on **{SERVER_NAME}**.\n"
            f"**Reason:** {reason}\n"
            f"**Total warnings:** {count}\n\n"
            f"⚠️ **Please note:**\n"
            f"🔇 At {MUTE_AFTER_WARNS} warnings → automatic mute for {MUTE_DURATION_MINUTES} minutes\n"
            f"👢 At {KICK_AFTER_WARNS} warnings → automatic kick from the server\n"
            f"🚫 At {BAN_AFTER_WARNS} warnings → permanent ban from the server\n\n"
            f"Please follow the server rules to avoid reaching these stages."
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | Moderation System")

    try:
        await member.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def add_warn(member: discord.Member, reason: str) -> int:
    user_id = str(member.id)
    if user_id not in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}
    warns_db[user_id]["count"] += 1
    warns_db[user_id]["reasons"].append(reason)
    warns_db[user_id]["dates"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    count = warns_db[user_id]["count"]
    await send_warn_dm(member, count, reason)
    return count


def is_exempt(member: discord.Member) -> bool:
    """واش هاد العضو معفي من Auto-Mod (Owner ولا شي رول معفي)"""
    if OWNER_ID and member.id == OWNER_ID:
        return True
    if EXEMPT_ROLE_IDS:
        member_role_ids = {role.id for role in member.roles}
        if member_role_ids.intersection(EXEMPT_ROLE_IDS):
            return True
    return False


def get_warns(user_id: str) -> dict:
    return warns_db.get(user_id, {"count": 0, "reasons": [], "dates": []})


def clear_warns(user_id: str):
    if user_id in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}


async def auto_unmute(member: discord.Member, duration_minutes: int, guild: discord.Guild):
    await asyncio.sleep(duration_minutes * 60)
    muted_role = guild.get_role(MUTED_ROLE_ID)
    if muted_role and muted_role in member.roles:
        try:
            await member.remove_roles(muted_role)
            await log_action(
                guild,
                "🔊 فك الكتم (تلقائي)",
                f"**المستخدم:** {member.mention}\n"
                f"**المدة:** {duration_minutes} دقيقة\n"
                f"**السبب:** انتهت المدة",
                discord.Color.green()
            )
        except discord.Forbidden:
            pass


async def setup_verify_message(guild: discord.Guild):
    verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if not verify_channel:
        return
    async for message in verify_channel.history(limit=10):
        if message.author == bot.user and "✅" in message.content:
            return
    embed = discord.Embed(
        title="✅ تفعيل العضوية",
        description=(
            f"**مرحبا بيك فـ {SERVER_NAME}!**\n\n"
            f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n\n"
            f"**الخطوات:**\n"
            f"1️⃣ قرا/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
            f"2️⃣ كليك/ي على ✅ تحت\n\n"
            f"**ملاحظة:** إلا ما وافقتيش، ما غاديش تقدر/ي تهضر/ي ولا تفاعل/ي!"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="GGMW9 | Verification System")
    msg = await verify_channel.send(embed=embed)
    await msg.add_reaction("✅")


# ═══════════════════════════════════════════════════════
# ║   نظام القوانين + التفعيل بالأزرار (Buttons)           ║
# ║   (كيبان مباشرة تحت القوانين، بحال المواقع)              ║
# ═══════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════
# ║   اختيار اللغة حسب لغة تطبيق الديسكورد ديال المستخدم    ║
# ═══════════════════════════════════════════════════════

def get_user_lang(interaction: discord.Interaction) -> str:
    """
    كيحدد اللغة المناسبة اعتماداً على interaction.locale (لغة تطبيق
    الديسكورد ديال المستخدم لي ضغط على الزر). ماشي كاع اللغات مدعومة،
    فكنرجعو لـ 'ar' (دارجة/عربية) كافتراضي.
    """
    locale = str(interaction.locale) if interaction.locale else ""
    if locale.startswith("fr"):
        return "fr"
    if locale.startswith("en"):
        return "en"
    return "ar"


def t(interaction: discord.Interaction, ar: str, en: str, fr: str) -> str:
    """كيرجع النص بلغة الديسكورد ديال المستخدم لي دار الـ interaction"""
    lang = get_user_lang(interaction)
    return {"ar": ar, "en": en, "fr": fr}[lang]


class GenderSelectView(discord.ui.View):
    """View كتبان بعد التفعيل مباشرة، فيها زوج أزرار: ولد / بنت"""

    def __init__(self, target_user_id: int, guild_id: int):
        super().__init__(timeout=300)  # 5 دقايق باش يختار، من بعد كتسالا
        self.target_user_id = target_user_id
        self.guild_id = guild_id

    async def _assign_gender_role(self, interaction: discord.Interaction, role_id: int, other_role_id: int, label: str):
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ هاد الاختيار ماشي ديالك!", ephemeral=True)
            return

        guild = bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return
        member = guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("❌ ما لقيتكش فالسيرفر.", ephemeral=True)
            return

        if not role_id:
            await interaction.response.send_message(
                "❌ ماكاينش role ديال هاد الاختيار، بلغ الإدارة (خاص `BOYS_ROLE_ID`/`GIRLS_ROLE_ID` يتعمرو فـ CONFIG).",
                ephemeral=True
            )
            return

        role = guild.get_role(role_id)
        other_role = guild.get_role(other_role_id) if other_role_id else None

        try:
            if other_role and other_role in member.roles:
                await member.remove_roles(other_role)
            if role:
                await member.add_roles(role)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرتش نعطيك الرول، بلغ الإدارة (البوت ماعندوش صلاحية — تحقق من ترتيب الرولات بـ `!checkroles`).",
                ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True

        blacklist_note = (
            f"\n\n📌 قبل ما تبدا/ي تهضر/ي، خاصك تقرا/ي الممنوعات والعقوبات فـ <#{BLACKLIST_CHANNEL_ID}>"
            if BLACKLIST_CHANNEL_ID else ""
        )
        success_text = f"✅ تم اختيارك: **{label}**{blacklist_note}\n\n🎉 دابا تقدر/ي تدخل/ي لكاع القنوات المسموحة!"

        try:
            await interaction.response.edit_message(content=success_text, embed=None, view=self)
        except Exception:
            await interaction.response.send_message(success_text, ephemeral=True)

        await log_action(
            guild,
            "🚻 اختيار الجنس",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الاختيار:** {label}",
            discord.Color.blurple()
        )

    @discord.ui.button(label="ولد", emoji="👦", style=discord.ButtonStyle.primary)
    async def boy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_gender_role(interaction, BOYS_ROLE_ID, GIRLS_ROLE_ID, "ولد 👦")

    @discord.ui.button(label="بنت", emoji="👧", style=discord.ButtonStyle.secondary)
    async def girl_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_gender_role(interaction, GIRLS_ROLE_ID, BOYS_ROLE_ID, "بنت 👧")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        import traceback
        print(f"[GENDER VIEW ERROR] {error}")
        traceback.print_exc()
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ وقع مشكل تقني، حاول عاود من بعد شوية ولا بلغ الإدارة.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ وقع مشكل تقني، حاول عاود من بعد شوية ولا بلغ الإدارة.", ephemeral=True)
        except Exception:
            pass


class RoleCategorySelect(discord.ui.Select):
    """Select menu واحد كيمثل مجموعة (category) وحدة من PICK_ROLES.
    العضو يقدر يختار عدة خيارات مرة وحدة (multi-select)."""

    def __init__(self, category_name: str, roles_list: list):
        self.category_name = category_name
        # {role_id: label} باش نستعملوها ملي كيوصل اختيار جديد
        self.role_map = {r["role_id"]: r["label"] for r in roles_list if r["role_id"]}

        options = [
            discord.SelectOption(
                label=r["label"],
                emoji=r["emoji"] or None,
                value=str(r["role_id"]),
            )
            for r in roles_list if r["role_id"]
        ]

        super().__init__(
            placeholder=f"اختار من: {category_name}",
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            custom_id=f"pickroles_select_{category_name}",
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، حاول عاود.", ephemeral=True)
            return

        selected_ids = {int(v) for v in self.values}
        all_ids = set(self.role_map.keys())

        added, removed, failed = [], [], []

        for role_id in all_ids:
            role = guild.get_role(role_id)
            if not role:
                continue
            has_it = role in member.roles
            wants_it = role_id in selected_ids
            try:
                if wants_it and not has_it:
                    await member.add_roles(role)
                    added.append(role.name)
                elif has_it and not wants_it:
                    await member.remove_roles(role)
                    removed.append(role.name)
            except discord.Forbidden:
                failed.append(role.name)

        parts = []
        if added:
            parts.append("✅ تزادو: " + ", ".join(added))
        if removed:
            parts.append("🔄 تنزعو: " + ", ".join(removed))
        if failed:
            parts.append("❌ ما قدرتش نعطي (صلاحية): " + ", ".join(failed))
        if not parts:
            parts.append("مافيش تغيير.")

        await interaction.response.send_message("\n".join(parts), ephemeral=True)


class RolePickerView(discord.ui.View):
    """View فيها Select menu واحد لكل category فـ PICK_ROLES.
    Persistent (timeout=None) باش تبقى خدامة حتى بعد ريستارت البوت."""

    def __init__(self):
        super().__init__(timeout=None)
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if valid:
                self.add_item(RoleCategorySelect(category_name, valid))


class RulesVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # باش يبقى خدام للأبد (persistent view)

    def _is_exempt(self, member: discord.Member) -> bool:
        if member.id == OWNER_ID:
            return True
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)

    @discord.ui.button(label="✅ كنوافق / Agree / J'accepte", style=discord.ButtonStyle.success, custom_id="rules_agree_button")
    async def agree_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                t(interaction, "❌ وقع مشكل، عاود من جديد.", "❌ Something went wrong, try again.", "❌ Une erreur est survenue, réessayez."),
                ephemeral=True
            )
            return

        member_role = guild.get_role(MEMBER_ROLE_ID)
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)

        if member_role and member_role in member.roles:
            await interaction.response.send_message(
                t(interaction, "✅ راك مفعل من قبل، مرحبا بيك!", "✅ You're already verified, welcome!", "✅ Vous êtes déjà vérifié(e), bienvenue !"),
                ephemeral=True
            )
            return

        if unverified_role and unverified_role in member.roles:
            try:
                await member.remove_roles(unverified_role)
            except discord.Forbidden:
                pass
        if member_role:
            try:
                await member.add_roles(member_role)
            except discord.Forbidden:
                await interaction.response.send_message(
                    t(interaction,
                      "❌ ما قدرتش نفعلك، بلغ الإدارة (البوت ماعندوش صلاحية كافية — "
                      "غالبا role ديال البوت تحت فـ ترتيب الرولات، خاصو يكون فوق role ديال Member).",
                      "❌ I couldn't verify you, please contact staff (the bot lacks permission — "
                      "its role is probably below the Member role in the role order).",
                      "❌ Impossible de vous vérifier, contactez le staff (le bot n'a pas la permission — "
                      "son rôle est probablement en dessous du rôle Member)."),
                    ephemeral=True
                )
                await log_action(
                    guild,
                    "⚠️ فشل التفعيل (صلاحية)",
                    f"**المستخدم:** {member.mention} ({member.name})\n"
                    f"**السبب:** role ديال البوت ماعندوش صلاحية يعطي role ديال Member.\n"
                    f"**الحل:** استعمل `!checkroles` باش تشوف المشكل بالضبط.",
                    discord.Color.orange()
                )
                return

        await interaction.response.send_message(
            t(interaction,
              f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك، استمتع/ي 🎉",
              f"✅ You're verified in **{SERVER_NAME}**! Welcome, enjoy 🎉",
              f"✅ Vous êtes vérifié(e) dans **{SERVER_NAME}** ! Bienvenue, amusez-vous bien 🎉"),
            ephemeral=True
        )

        await log_action(
            guild,
            "✅ تفعيل (زر القوانين)",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الحالة:** وافق على القوانين وتفعل",
            discord.Color.green()
        )

        gender_embed = discord.Embed(
            title=t(interaction, "🚻 واش نتا/نتي ولد ولا بنت؟", "🚻 Are you a boy or a girl?", "🚻 Êtes-vous un garçon ou une fille ?"),
            description=t(interaction, "ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
                          "Click the right button to get the correct role.",
                          "Cliquez sur le bon bouton pour recevoir le rôle correspondant."),
            color=discord.Color.blurple()
        )
        await interaction.followup.send(
            embed=gender_embed,
            view=GenderSelectView(target_user_id=member.id, guild_id=guild.id),
            ephemeral=True
        )

    @discord.ui.button(label="❌ كنرفض / Refuse / Je refuse", style=discord.ButtonStyle.danger, custom_id="rules_refuse_button")
    async def refuse_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                t(interaction, "❌ وقع مشكل، عاود من جديد.", "❌ Something went wrong, try again.", "❌ Une erreur est survenue, réessayez."),
                ephemeral=True
            )
            return

        if self._is_exempt(member):
            await interaction.response.send_message(
                t(interaction,
                  "⚠️ راك أدمن/مشرف، ماغاديش نطردك، ولكن هاد الزر معناه رفض القوانين للأعضاء العاديين.",
                  "⚠️ You're an admin/moderator, so you won't be kicked — but this button means rejecting the rules for regular members.",
                  "⚠️ Vous êtes admin/modérateur, vous ne serez pas expulsé(e) — mais ce bouton signifie refuser les règles pour les membres normaux."),
                ephemeral=True
            )
            return

        try:
            await interaction.response.send_message(
                t(interaction, "❌ رفضتي القوانين، غادي تتطرد من السيرفر...",
                  "❌ You refused the rules, you will be kicked from the server...",
                  "❌ Vous avez refusé les règles, vous allez être expulsé(e) du serveur..."),
                ephemeral=True
            )
        except Exception:
            pass

        try:
            await member.send(
                t(interaction,
                  f"❌ رفضتي القوانين ديال **{SERVER_NAME}**، تم طردك من السيرفر تلقائياً.",
                  f"❌ You refused the rules of **{SERVER_NAME}**, you were automatically kicked from the server.",
                  f"❌ Vous avez refusé les règles de **{SERVER_NAME}**, vous avez été automatiquement expulsé(e) du serveur.")
            )
        except Exception:
            pass

        await log_action(
            guild,
            "🚫 رفض القوانين + طرد تلقائي",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**ID:** `{member.id}`\n"
            f"**السبب:** رفض الموافقة على القوانين (زر ❌)",
            discord.Color.red()
        )

        try:
            await guild.kick(member, reason="رفض الموافقة على قوانين السيرفر")
        except discord.Forbidden:
            await log_action(
                guild,
                "⚠️ فشل الطرد",
                f"ماقدرتش نطرد {member.mention} — البوت ماعندوش صلاحية كافية.",
                discord.Color.orange()
            )


async def setup_rules_message(guild: discord.Guild):
    rules_channel = bot.get_channel(RULES_CHANNEL_ID)
    if not rules_channel:
        return
    async for message in rules_channel.history(limit=10):
        if message.author == bot.user and message.components:
            return
    embed = discord.Embed(
        title="📜 قوانين السيرفر | Server Rules | Règles du serveur",
        description=(
            f"{SERVER_RULES}\n\n"
            f"⚠️ **بالضغط ✅ كتوافق على القوانين وكيتم التفعيل ديالك اوتوماتيكيا | By clicking ✅ you agree to the terms and your activation will be done automatically | "
            f"En cliquant sur ✅, vous acceptez les conditions et votre activation se fait automatiquement**\n"
            f"**الرفض ❌ = طرد أوتوماتيكي | Refusing ❌ = automatic kick | Refuser ❌ = exclusion automatique**"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="GGMW9 | Rules & Verification")
    await rules_channel.send(embed=embed, view=RulesVerifyView())


async def setup_blacklist_message(guild: discord.Guild):
    """كيبعث embeds فـ channel 'Blacklist things' فيه الممنوعات والعقوبات المتدرجة
    بالتفصيل — وحدة بالدارجة، وحدة بالفرنسية، ووحدة بالإنجليزية."""
    channel = bot.get_channel(BLACKLIST_CHANNEL_ID)
    if not channel:
        return

    has_darija = False
    has_fr = False
    has_en = False
    async for message in channel.history(limit=15):
        if message.author == bot.user and message.embeds:
            title = message.embeds[0].title or ""
            if "الممنوعات" in title:
                has_darija = True
            elif "Règles et Sanctions" in title:
                has_fr = True
            elif "Rules & Penalties" in title:
                has_en = True

    if not has_darija:
        embed = discord.Embed(
            title="🚫 Blacklist Things — الممنوعات والعقوبات",
            description=(
                "قرا/ي هاد الصفحة بالكامل قبل ما تبدا/ي تهضر/ي فالسيرفر. "
                "البوت كيراقب هاد النقاط **أوتوماتيكياً 24/24**، وكل مخالفة عندها ثمن.\n"
                "الهدف من هاد الصفحة ماشي نخوفوك، بغينا غير تفهم/ي شنو ممنوع بالضبط باش ما تتعاقب/ي بلا وعي."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="1️⃣ السبام والإعلانات",
            value=(
                "**ممنوع:** تكرار نفس الرسالة، بعث رابط ديسكورد ديال سيرفر آخر بلا إذن، "
                "الإعلان لقناة/منتوج/خدمة بلا موافقة الإدارة، Mention مفرط (@everyone/@here بلا حق).\n"
                "**مثال:** بعثتي `discord.gg/xxxx` فـ #general باش تجيب ناس لسيرفر آخر → تحذير + مسح الرسالة."
            ),
            inline=False
        )
        embed.add_field(
            name="2️⃣ الاحترام بين الأعضاء",
            value=(
                "**ممنوع:** السب المباشر خارج نطاق المزاح، التنمر، العنصرية، الإهانة الشخصية، التهديد بأي شكل.\n"
                "**مثال:** كتبتي كلام عنصري ولا مهين على عضو آخر → تحذير مباشر، ومع التكرار طرد/حظر."
            ),
            inline=False
        )
        embed.add_field(
            name="3️⃣ محتوى +18 / عنيف / صادم",
            value=(
                "**ممنوع:** صور/فيديوهات/روابط جنسية، محتوى عنيف صريح (دم، تعذيب...)، مشاهد صادمة.\n"
                "**مثال:** بعثتي صورة/رابط فيه محتوى جنسي حتى بشكل 'مزحة' → **حظر مباشر بلا تحذير**."
            ),
            inline=False
        )
        embed.add_field(
            name="4️⃣ الخصوصية (Doxxing)",
            value=(
                "**ممنوع:** نشر رقم تيليفون، عنوان، صور شخصية، ولا أي معلومة كتعرف بشخص آخر بلا إذنو.\n"
                "**مثال:** نشرتي سكرين شوت فيه رقم ديال عضو آخر → **حظر مباشر**."
            ),
            inline=False
        )
        embed.add_field(
            name="5️⃣ استعمال القنوات بطريقة غالطة",
            value=(
                "**ممنوع:** الهضرة خارج الموضوع فـ channel مخصص (مثلاً هضرة عادية فـ #announcements).\n"
                "**مثال:** كتبتي ميم فـ channel ديال الأخبار الرسمية → مسح الرسالة + تنبيه."
            ),
            inline=False
        )
        embed.add_field(
            name="⚖️ العقوبات المتدرجة",
            value=(
                f"1️⃣ **تحذير** — كل مخالفة خفيفة كتبان تحذير أوتوماتيكي\n"
                f"2️⃣ **كتم (Mute)** — عند {MUTE_AFTER_WARNS} تحذيرات ({MUTE_DURATION_MINUTES} دقيقة)، ولا إلا بعتي {SPAM_THRESHOLD} رسايل فـ {SPAM_INTERVAL} ثواني (سبام)\n"
                f"3️⃣ **طرد (Kick)** — عند الوصول لـ {KICK_AFTER_WARNS} تحذيرات\n"
                f"4️⃣ **حظر (Ban)** — عند الوصول لـ {BAN_AFTER_WARNS} تحذيرات، ولا مباشرة فحالة Doxxing/محتوى +18/تهديد خطير"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed.add_field(
                name="🚨 كيفاش تبلغ عن مخالفة (!report)",
                value=(
                    "إلا شفتي شي مخالفة والبوت ما تدخلش أوتوماتيكياً، عندك طريقتين:\n\n"
                    "**1) بلاغ على عضو معين:**\n"
                    "`!report @العضو السبب`\n"
                    "مثال: `!report @GGMW9 بعث رابط ديال سيرفر آخر فـ #general`\n\n"
                    "**2) بلاغ عام (بلا ما تحدد عضو):**\n"
                    "`!report وصف المشكل`\n"
                    "مثال: `!report كاين ناس كيهضرو بزربة فـ #announcements`\n\n"
                    "💡 **نصيحة:** إلا عندك سكرين شوت ديال المخالفة، بعثو مباشرة للمشرفين ولا فـ نفس الرسالة معاك (mention العضو بحال Ahmed)\n"
                    "⚠️ الرسالة ديالك كتمسح أوتوماتيك من الشات العام والبلاغ كيوصل مباشرة للإدارة، حتى حد ماغاديش يشوف بلي بلغتي."
                ),
                inline=False
            )

        embed.set_footer(text="GGMW9 | Auto-Moderation System")
        await channel.send(embed=embed)

    if not has_fr:
        embed_fr = discord.Embed(
            title="🚫 Blacklist Things — Règles et Sanctions",
            description=(
                "Lisez cette page en entier avant de discuter sur le serveur. "
                "Le bot surveille ces points **automatiquement 24h/24**, et chaque infraction a un prix.\n"
                "Le but de cette page n'est pas de vous effrayer, mais de vous faire comprendre exactement ce qui est interdit "
                "pour éviter d'être sanctionné sans le savoir."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )

        embed_fr.add_field(
            name="1️⃣ Spam et Publicité",
            value=(
                "**Interdit :** répéter le même message, poster un lien d'invitation Discord vers un autre serveur sans permission, "
                "faire de la publicité pour un salon/produit/service sans l'accord du staff, mentions excessives (@everyone/@here sans droit).\n"
                "**Exemple :** poster `discord.gg/xxxx` dans #general pour attirer des membres vers un autre serveur → avertissement + message supprimé."
            ),
            inline=False
        )
        embed_fr.add_field(
            name="2️⃣ Respect entre les membres",
            value=(
                "**Interdit :** insultes directes hors contexte de plaisanterie, harcèlement, racisme, insultes personnelles, menaces sous toute forme.\n"
                "**Exemple :** tenir des propos racistes ou insultants envers un autre membre → avertissement immédiat, "
                "en cas de récidive : exclusion/bannissement."
            ),
            inline=False
        )
        embed_fr.add_field(
            name="3️⃣ Contenu +18 / Violent / Choquant",
            value=(
                "**Interdit :** images/vidéos/liens à caractère sexuel, contenu violent explicite (sang, torture...), scènes choquantes.\n"
                "**Exemple :** envoyer une image/un lien à caractère sexuel même « pour rire » → **bannissement immédiat, sans avertissement**."
            ),
            inline=False
        )
        embed_fr.add_field(
            name="4️⃣ Vie privée (Doxxing)",
            value=(
                "**Interdit :** publier un numéro de téléphone, une adresse, des photos personnelles, ou toute information identifiant "
                "quelqu'un sans son consentement.\n"
                "**Exemple :** publier une capture d'écran contenant le numéro d'un autre membre → **bannissement immédiat**."
            ),
            inline=False
        )
        embed_fr.add_field(
            name="5️⃣ Mauvaise utilisation des salons",
            value=(
                "**Interdit :** discuter hors sujet dans un salon dédié (ex. discussion informelle dans #announcements).\n"
                "**Exemple :** poster un mème dans le salon d'actualités officiel → message supprimé + rappel."
            ),
            inline=False
        )
        embed_fr.add_field(
            name="⚖️ Sanctions progressives",
            value=(
                f"1️⃣ **Avertissement** — chaque infraction légère déclenche un avertissement automatique\n"
                f"2️⃣ **Mute** — à {MUTE_AFTER_WARNS} avertissements ({MUTE_DURATION_MINUTES} min), ou après {SPAM_THRESHOLD} messages en {SPAM_INTERVAL}s (spam)\n"
                f"3️⃣ **Kick** — à {KICK_AFTER_WARNS} avertissements\n"
                f"4️⃣ **Ban** — à {BAN_AFTER_WARNS} avertissements, ou immédiatement en cas de doxxing/contenu +18/menace grave"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed_fr.add_field(
                name="🚨 Comment signaler une infraction (!report)",
                value=(
                    "Si vous voyez une infraction et que le bot n'intervient pas automatiquement, vous avez deux options :\n\n"
                    "**1) Signaler un membre précis :**\n"
                    "`!report @Membre raison`\n"
                    "Exemple : `!report @GGMW9 a posté un lien vers un autre serveur dans #general`\n\n"
                    "**2) Signalement général (sans citer de membre) :**\n"
                    "`!report description du problème`\n"
                    "Exemple : `!report des gens spamment dans #announcements`\n\n"
                    "💡 **Conseil :** si vous avez une capture d'écran de l'infraction, envoyez-la directement au staff ou dans le même message "
                    "(en mentionnant le membre, ex. Ahmed)\n"
                    "⚠️ Votre message est automatiquement supprimé du salon public et le signalement arrive directement à l'administration, "
                    "personne ne verra que vous avez signalé."
                ),
                inline=False
            )

        embed_fr.set_footer(text="GGMW9 | Système de Modération Automatique")
        await channel.send(embed=embed_fr)

    if not has_en:
        embed_en = discord.Embed(
            title="🚫 Blacklist Things — Rules & Penalties",
            description=(
                "Read this page in full before chatting on the server. "
                "The bot monitors these points **automatically 24/7**, and every violation has a cost.\n"
                "The goal of this page isn't to scare you — we just want you to understand exactly what's forbidden "
                "so you don't get punished without knowing why."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )

        embed_en.add_field(
            name="1️⃣ Spam & Advertising",
            value=(
                "**Forbidden:** repeating the same message, posting a Discord invite link to another server without permission, "
                "advertising a channel/product/service without staff approval, excessive mentions (@everyone/@here without the right to).\n"
                "**Example:** posting `discord.gg/xxxx` in #general to bring people to another server → warning + message deleted."
            ),
            inline=False
        )
        embed_en.add_field(
            name="2️⃣ Respect Among Members",
            value=(
                "**Forbidden:** direct insults outside of joking around, bullying, racism, personal insults, threats of any kind.\n"
                "**Example:** posting racist or insulting comments about another member → immediate warning, repeated offenses lead to kick/ban."
            ),
            inline=False
        )
        embed_en.add_field(
            name="3️⃣ NSFW / Violent / Shocking Content",
            value=(
                "**Forbidden:** sexual images/videos/links, explicit violent content (blood, torture...), shocking scenes.\n"
                "**Example:** sending sexual content even as a 'joke' → **immediate ban, no warning**."
            ),
            inline=False
        )
        embed_en.add_field(
            name="4️⃣ Privacy (Doxxing)",
            value=(
                "**Forbidden:** sharing a phone number, address, personal photos, or any identifying information about someone without their consent.\n"
                "**Example:** posting a screenshot showing another member's phone number → **immediate ban**."
            ),
            inline=False
        )
        embed_en.add_field(
            name="5️⃣ Misusing Channels",
            value=(
                "**Forbidden:** off-topic chat in a dedicated channel (e.g. casual talk in #announcements).\n"
                "**Example:** posting a meme in the official news channel → message deleted + reminder."
            ),
            inline=False
        )
        embed_en.add_field(
            name="⚖️ Escalating Penalties",
            value=(
                f"1️⃣ **Warning** — every minor offense triggers an automatic warning\n"
                f"2️⃣ **Mute** — at {MUTE_AFTER_WARNS} warnings ({MUTE_DURATION_MINUTES} minutes), or after {SPAM_THRESHOLD} messages in {SPAM_INTERVAL}s (spam)\n"
                f"3️⃣ **Kick** — upon reaching {KICK_AFTER_WARNS} warnings\n"
                f"4️⃣ **Ban** — upon reaching {BAN_AFTER_WARNS} warnings, or immediately for doxxing/NSFW content/serious threats"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed_en.add_field(
                name="🚨 How to report a violation (!report)",
                value=(
                    "If you see a violation and the bot doesn't step in automatically, you have two options:\n\n"
                    "**1) Report a specific member:**\n"
                    "`!report @Member reason`\n"
                    "Example: `!report @GGMW9 posted a link to another server in #general`\n\n"
                    "**2) General report (without naming a member):**\n"
                    "`!report description of the issue`\n"
                    "Example: `!report people are spamming in #announcements`\n\n"
                    "💡 **Tip:** if you have a screenshot of the violation, send it directly to staff or in the same message "
                    "(mentioning the member, e.g. Ahmed)\n"
                    "⚠️ Your message is automatically deleted from the public chat and the report goes straight to the staff, "
                    "no one will see that you reported it."
                ),
                inline=False
            )

        embed_en.set_footer(text="GGMW9 | Auto-Moderation System")
        await channel.send(embed=embed_en)


@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    user_id = str(member.id)
    saved_role_ids = member_roles_data.get(guild_id, {}).get(user_id)

    # ═══════ عضو رجع للسيرفر (بعد كيك/بان/خروج) — رجع ليه نفس الرولات ═══════
    if saved_role_ids:
        roles_to_add = []
        for rid in saved_role_ids:
            role = member.guild.get_role(rid)
            if role:
                roles_to_add.append(role)

        restore_error = None
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="استرجاع الرولات القديمة بعد الرجوع للسيرفر")
            except discord.Forbidden as e:
                restore_error = str(e)

        welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            embed = discord.Embed(
                title=f"👋 مرحبا بيك مرة أخرى {member.display_name}!",
                description="رجعنا ليك نفس الرولات اللي كانت عندك من قبل. 🎉",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="GGMW9 | Welcome Back")
            await welcome_channel.send(embed=embed)

        await log_action(
            member.guild,
            "🔁 عضو رجع للسيرفر",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الرولات المسترجعة:** {', '.join(r.mention for r in roles_to_add) if roles_to_add else 'ماكانش عندو رولات صالحة باش ترجع'}"
            + (f"\n⚠️ **خطأ:** ما قدرتش نعطي بعض الرولات (صلاحية/ترتيب الرولات): {restore_error}" if restore_error else ""),
            discord.Color.blue()
        )
        return

    # ═══════ عضو جديد بصح — نظام Unverified/Welcome العادي ═══════
    unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except discord.Forbidden:
            pass
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"👋 مرحبا بيك {member.display_name}!",
            description=(
                f"واخا أخويا/أختي! **{SERVER_NAME}** هو السيرفر ديالك.\n\n"
                f"**قبل ما تبدأ/ي:**\n"
                f"1️⃣ قرا/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
                f"2️⃣ وافق/ي فـ <#{VERIFY_CHANNEL_ID}>\n"
                f"3️⃣ استمتع/ي! 🎉"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="GGMW9 | Verification System")
        await welcome_channel.send(embed=embed)
    try:
        await member.send(
            f"👋 مرحبا بيك فـ **{SERVER_NAME}**!\n\n"
            f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n"
            f"سير/ي لـ <#{VERIFY_CHANNEL_ID}> وكليك على ✅\n\n"
            f"شكرا! 🙏"
        )
    except discord.Forbidden:
        pass
    await log_action(
        member.guild,
        "👤 عضو جديد (Unverified)",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**الحالة:** غير مفعل\n"
        f"**الدور:** {unverified_role.mention if unverified_role else 'N/A'}",
        discord.Color.orange()
    )


@bot.event
async def on_member_remove(member):
    # كنسجلو الرولات ديالو قبل ما يخرج (كيك، بان، ولا خرج بنفسو) باش
    # يقدر يرجع ليهم تلقائياً ملي يرجع للسيرفر.
    remember_member_roles(member)
    await log_action(
        member.guild,
        "👋 عضو خرج",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**ID:** `{member.id}`",
        discord.Color.greyple()
    )


@bot.event
async def on_raw_reaction_add(payload):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    # ═══════ Verification ═══════
    if payload.channel_id != VERIFY_CHANNEL_ID:
        return
    if str(payload.emoji) != "✅":
        return
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role and unverified_role in member.roles:
        try:
            await member.remove_roles(unverified_role)
        except discord.Forbidden:
            pass
    member_role = guild.get_role(MEMBER_ROLE_ID)
    if member_role:
        try:
            await member.add_roles(member_role)
        except discord.Forbidden:
            await log_action(
                guild,
                "⚠️ فشل التفعيل (صلاحية)",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**السبب:** role ديال البوت ماعندوش صلاحية يعطي role ديال Member.\n"
                f"**الحل:** استعمل `!checkroles` باش تشوف المشكل بالضبط.",
                discord.Color.orange()
            )
            return
    await log_action(
        guild,
        "✅ تفعيل",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**الحالة:** مفعل\n"
        f"**الطريقة:** Reaction ✅",
        discord.Color.green()
    )
    try:
        gender_embed = discord.Embed(
            title="🚻 واش نتا/نتي ولد ولا بنت؟",
            description="ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
            color=discord.Color.blurple()
        )
        await member.send(
            f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉",
            embed=gender_embed,
            view=GenderSelectView(target_user_id=member.id, guild_id=guild.id)
        )
    except Exception:
        pass


@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await log_action(
        message.guild,
        "🗑️ رسالة محذوفة",
        f"**المستخدم:** {message.author.mention}\n"
        f"**القناة:** {message.channel.mention}\n"
        f"**المحتوى:** {message.content[:1000]}",
        discord.Color.red()
    )


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    await log_action(
        before.guild,
        "✏️ رسالة معدّلة",
        f"**المستخدم:** {before.author.mention}\n"
        f"**القناة:** {before.channel.mention}\n"
        f"**قبل:** {before.content[:500]}\n"
        f"**بعد:** {after.content[:500]}",
        discord.Color.yellow()
    )


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.author.bot:
        return
    await bot.process_commands(message)
    if message.content.startswith("!"):
        return
    msg_lower = message.content.lower()
    gender = detect_gender(message.author.name, message.author.display_name)

    if not is_exempt(message.author):
        for word in get_active_banned_words() + BANNED_ACTIONS:
            if word.lower() in msg_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"🚫 {message.author.mention} ممنوع السبام والروابط!",
                        delete_after=5
                    )
                    count = await add_warn(message.author, f"رسالة محذوفة (Auto-Mod): {word}")
                    await log_action(
                        message.guild,
                        "🚨 Auto-Mod | رسالة محذوفة",
                        f"**المستخدم:** {message.author.mention}\n"
                        f"**القناة:** {message.channel.mention}\n"
                        f"**الكلمة الممنوعة:** `{word}`\n"
                        f"**المحتوى:** {message.content[:500]}\n"
                        f"**التحذيرات:** {count} (كتم عند {MUTE_AFTER_WARNS}, طرد عند {KICK_AFTER_WARNS}, حظر عند {BAN_AFTER_WARNS})",
                        discord.Color.red()
                    )
                    await apply_warn_escalation(
                        message.author, message.guild, count,
                        f"Auto-Mod: {word}", channel=message.channel
                    )
                    return
                except discord.Forbidden:
                    pass
        user_id = str(message.author.id)
        now = datetime.now()
        if user_id not in spam_tracker:
            spam_tracker[user_id] = []
        spam_tracker[user_id].append(now)
        spam_tracker[user_id] = [
            t for t in spam_tracker[user_id]
            if now - t < timedelta(seconds=SPAM_INTERVAL)
        ]
        if len(spam_tracker[user_id]) >= SPAM_THRESHOLD:
            try:
                await message.channel.send(
                    f"🛑 {message.author.mention} توقف عن السبام!",
                    delete_after=5
                )
                muted_role = message.guild.get_role(MUTED_ROLE_ID)
                if muted_role:
                    await message.author.add_roles(muted_role)
                    if user_id in mute_tasks and not mute_tasks[user_id].done():
                        mute_tasks[user_id].cancel()
                    task = asyncio.create_task(auto_unmute(message.author, 5, message.guild))
                    mute_tasks[user_id] = task
                    await log_action(
                        message.guild,
                        "🛑 Auto-Mod | سبام مكتشف",
                        f"**المستخدم:** {message.author.mention}\n"
                        f"**الإجراء:** Mute 5 دقائق (تلقائي)\n"
                        f"**الرسائل:** {len(spam_tracker[user_id])} فـ {SPAM_INTERVAL} ثواني",
                        discord.Color.orange()
                    )
                    spam_tracker[user_id] = []
            except discord.Forbidden:
                pass

    if "ggmw9" in msg_lower:
        await message.reply("نعام! 😂 واش بغيتي؟", mention_author=False)
        return
    if "غيرها" in msg_lower:
        await message.reply("وخا أسي زبي 😂", mention_author=False)
        return
    if "سير تقود" in msg_lower or "تقود" in msg_lower:
        await message.reply("وخا هاني غادي نتقود دابا 🏃‍♂️", mention_author=False)
        return
    if "مالك" in msg_lower and ("ازبي" in msg_lower or "زبي" in msg_lower):
        if gender == "female":
            await message.reply("زبي فكرك مخبي ابنت القحبة 😂", mention_author=False)
        else:
            await message.reply("زبي فكرك مخبي اولد القحبة 😂", mention_author=False)
        return
    if "قحبة" in msg_lower:
        await message.reply("القحبة هي مك 😂", mention_author=False)
        return
    if "سير تحوا" in msg_lower:
        if gender == "female":
            await message.reply("سيري تحواي نتي نيت 😂", mention_author=False)
        else:
            await message.reply("سير تحوا نتا نيت 😂", mention_author=False)
        return
    if "اهيا" in msg_lower or "اه" in msg_lower:
        await message.reply("وي مالك؟ 🤔", mention_author=False)
        return
    if "شحال" in msg_lower and "ساعة" in msg_lower:
        await message.reply("ساعاتو لله 🕐", mention_author=False)
        return
    if "زبي" in msg_lower or "ازبي" in msg_lower:
        replies = [
            "ههههه ونتا؟ 😂",
            "صافي صافي، ريح مع كرك",
            "ياك خويا، هدي راسك شوية",
            "زبي فكرك مخبي 😂"
        ]
        await message.reply(random.choice(replies), mention_author=False)
        return
    if "لقلاوي" in msg_lower or "لقلاو" in msg_lower:
        await message.reply("ههههه لقلاوي نتا 😂", mention_author=False)
        return
    if "زامل" in msg_lower:
        if gender == "female":
            await message.reply("ههههه زاملة نتي 😂", mention_author=False)
        else:
            await message.reply("ههههه زامل نتا 😂", mention_author=False)
        return
    insults = ["حمار", "غبي", "قحبة", "زامل", "طاحون", "بوليس", "ولد القحبة", 
               "wld l9ahba", "nik mok", "tabon", "zamel", "7mar", "9a7ba", "tahwan",
               "لي حواك", "قواد", "طبون مك", "ابن القحبة", "ابنت القحبة",
               "نيك", "زب", "احا", "فمك", "كسمك", "كس"]
    is_insult = any(insult in msg_lower for insult in insults)
    if is_insult:
        if gender == "female":
            replies = [
                "ههههه ونتي نيت ابنت القحبة 😂",
                "صافي صافي، ريحي مع كرك 😂",
                "ياك اختي، هدي راسك شوية",
                "ههههه نتي اللي جاييا تهضري معايا؟"
            ]
        else:
            replies = [
                "ههههه ونتا نيت اولد القحبة 😂",
                "صافي صافي، ريح مع كرك 😂",
                "ياك خويا، هدي راسك شوية",
                "ههههه نتا اللي جاي تهضر معايا؟"
            ]
        await message.reply(random.choice(replies), mention_author=False)
        return
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    user_id = str(message.author.id)
    response = await ask_ai(
        user_id, 
        message.author.name, 
        message.author.display_name, 
        message.content
    )
    await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 طرد",
            description=f"**{member.mention}** تم طرده.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="الطارد", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Moderation")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "👢 طرد",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**السبب:** {reason}\n"
            f"**الطارد:** {ctx.author.mention}",
            discord.Color.orange()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🚫 حظر",
            description=f"**{member.mention}** تم حظره.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="الحاضر", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Moderation")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "🚫 حظر",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**السبب:** {reason}\n"
            f"**الحاضر:** {ctx.author.mention}",
            discord.Color.red()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        embed = discord.Embed(
            title="✅ فك الحظر",
            description=f"**{user.name}** تم فك حظره.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9 | Moderation")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "✅ فك الحظر",
            f"**المستخدم:** {user.mention} ({user.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.green()
        )
    except discord.NotFound:
        await ctx.send("❌ ما لقيتش هاد العضو!")
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        await ctx.send("❌ خاص العدد يكون بين 1 و 100!")
        return
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"🗑️ تم حذف {len(deleted) - 1} رسالة")
        await asyncio.sleep(3)
        await msg.delete()
        await log_action(
            ctx.guild,
            "🗑️ حذف رسائل",
            f"**القناة:** {ctx.channel.mention}\n"
            f"**العدد:** {len(deleted) - 1}\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.orange()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 5, *, reason="ما ذكرش سبب"):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not muted_role:
        await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.")
        return
    try:
        await member.add_roles(muted_role)
        embed = discord.Embed(
            title="🔇 كتم",
            description=f"**{member.mention}** تم كتم صوته.",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المدة", value=f"{duration} دقيقة", inline=False)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Moderation")
        await ctx.send(embed=embed)
        user_id = str(member.id)
        if user_id in mute_tasks and not mute_tasks[user_id].done():
            mute_tasks[user_id].cancel()
        task = asyncio.create_task(auto_unmute(member, duration, ctx.guild))
        mute_tasks[user_id] = task
        await log_action(
            ctx.guild,
            "🔇 كتم",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المدة:** {duration} دقيقة\n"
            f"**السبب:** {reason}\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.yellow()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not muted_role:
        await ctx.send("❌ ما لقيتش دور Mute!")
        return
    try:
        await member.remove_roles(muted_role)
        user_id = str(member.id)
        if user_id in mute_tasks and not mute_tasks[user_id].done():
            mute_tasks[user_id].cancel()
        embed = discord.Embed(
            title="🔊 فك الكتم",
            description=f"**{member.mention}** تم فك الكتم.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9 | Moderation")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "🔊 فك الكتم",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.green()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def report(ctx, member: Optional[discord.Member] = None, *, reason: str = "ماكاينش تفاصيل"):
    """أي عضو يقدر يبلغ عن مخالفة (بحال البوت ما تدخلش أوتوماتيكياً)"""
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not REPORTS_CHANNEL_ID:
        await ctx.send("❌ نظام البلاغات ماعادش مفعل، بلغ الإدارة تحط `REPORTS_CHANNEL_ID`.", delete_after=8)
        return

    reports_channel = bot.get_channel(REPORTS_CHANNEL_ID)
    if not reports_channel:
        await ctx.send("❌ ما قدرتش نلقى channel البلاغات.", delete_after=8)
        return

    embed = discord.Embed(
        title="🚨 بلاغ جديد",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 المبلّغ", value=f"{ctx.author.mention} ({ctx.author.name})", inline=False)
    if member:
        embed.add_field(name="🎯 العضو المبلَّغ عنه", value=f"{member.mention} ({member.name})", inline=False)
    embed.add_field(name="📝 السبب / التفاصيل", value=reason[:1000], inline=False)
    embed.add_field(name="📍 القناة", value=ctx.channel.mention, inline=False)
    embed.set_footer(text="GGMW9 | Report System")

    # ═══════ منشن للمشرفين/الأدمن ═══════
    mention_roles = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
    await reports_channel.send(content=mention_roles or None, embed=embed)

    # ═══════ DM لصاحب السيرفر ═══════
    try:
        owner = ctx.guild.get_member(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        if owner:
            await owner.send(embed=embed)
    except Exception:
        pass

    await ctx.send(f"✅ توصل البلاغ ديالك للإدارة، شكراً {ctx.author.mention} 🙏", delete_after=8)


@report.error
async def report_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ صبر شوية ({error.retry_after:.0f}s) قبل ما تبعت بلاغ آخر.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        # ممكن يكون ماكاينش mention، نديروه كـ بلاغ عام بلا عضو محدد
        pass


@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    count = await add_warn(member, reason)
    embed = discord.Embed(
        title="⚠️ تحذير",
        description=f"**{member.mention}** تم تحذيره.",
        color=discord.Color.yellow(),
        timestamp=datetime.now()
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(
        name="عدد التحذيرات",
        value=f"{count} (كتم عند {MUTE_AFTER_WARNS}, طرد عند {KICK_AFTER_WARNS}, حظر عند {BAN_AFTER_WARNS})",
        inline=False
    )
    embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
    embed.set_footer(text="GGMW9 | Moderation")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "⚠️ تحذير",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**السبب:** {reason}\n"
        f"**العدد:** {count}\n"
        f"**المنفذ:** {ctx.author.mention}",
        discord.Color.yellow()
    )
    action = await apply_warn_escalation(member, ctx.guild, count, reason, channel=ctx.channel)
    if action is None and count >= MUTE_AFTER_WARNS:
        await ctx.send("❌ ما قدرتش نطبق العقوبة (تأكد من صلاحيات وترتيب الأدوار ديال البوت)!")


@bot.command()
@commands.has_permissions(kick_members=True)
async def warns(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_warns = get_warns(str(member.id))
    embed = discord.Embed(
        title=f"⚠️ تحذيرات {member.display_name}",
        color=discord.Color.yellow(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="العدد",
        value=f"{user_warns['count']} (كتم عند {MUTE_AFTER_WARNS}, طرد عند {KICK_AFTER_WARNS}, حظر عند {BAN_AFTER_WARNS})",
        inline=False
    )
    if user_warns["reasons"]:
        reasons_text = "\n".join([
            f"{i+1}. {r} ({user_warns['dates'][i]})" 
            for i, r in enumerate(user_warns["reasons"])
        ])
        embed.add_field(name="الأسباب والتواريخ", value=reasons_text, inline=False)
    else:
        embed.add_field(name="الأسباب", value="ما كاين والو ✅", inline=False)
    embed.set_footer(text="GGMW9 | Moderation")
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(kick_members=True)
async def unwarn(ctx, member: discord.Member):
    clear_warns(str(member.id))
    embed = discord.Embed(
        title="✅ مسح التحذيرات",
        description=f"**{member.mention}** تم مسح تحذيراتو.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="GGMW9 | Moderation")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "✅ مسح تحذيرات",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**المنفذ:** {ctx.author.mention}",
        discord.Color.green()
    )


# ═══════════════════════════════════════════════════════
# ║   OWNER ONLY — إدارة اللائحة الممنوعة (سري، ماشي فالقناة)  ║
# ═══════════════════════════════════════════════════════
# هاد الأوامر خاصة غير بالـ Owner (بواسطة الـ ID فـ OWNER_ID)، حتى
# الـ Admins والـ Moderators ما يقدروش يستعملوها. الرسالة ديال الأمر
# كتمسح مباشرة، والجواب كيوصل بـ DM للـ Owner فقط — باش حتى حد آخر فالسيرفر
# ما يشوف واش تزادت/تحيدت شي كلمة، وواش شكون دارها.

@bot.command(name="addword")
async def addword_cmd(ctx, *, word: str = ""):
    await _delete_trigger_silently(ctx)
    if not is_owner(ctx):
        return
    word = word.strip()
    if not word:
        return
    if word in banned_words_state["removed"]:
        banned_words_state["removed"].remove(word)
    if word not in banned_words_state["extra"] and word not in BANNED_WORDS:
        banned_words_state["extra"].append(word)
    save_banned_lists()
    try:
        await ctx.author.send(f"✅ تزادت الكلمة للائحة الممنوعة. (المجموع الحالي: {len(get_active_banned_words())})")
    except Exception:
        pass


@bot.command(name="removeword")
async def removeword_cmd(ctx, *, word: str = ""):
    await _delete_trigger_silently(ctx)
    if not is_owner(ctx):
        return
    word = word.strip()
    if not word:
        return
    if word in banned_words_state["extra"]:
        banned_words_state["extra"].remove(word)
    if word in BANNED_WORDS and word not in banned_words_state["removed"]:
        banned_words_state["removed"].append(word)
    save_banned_lists()
    try:
        await ctx.author.send(f"✅ تحيدت الكلمة من اللائحة. (المجموع الحالي: {len(get_active_banned_words())})")
    except Exception:
        pass


@bot.command(name="addaction")
async def addaction_cmd(ctx, *, phrase: str = ""):
    """كتزيد عبارة/سلوك ممنوع (بحال كلمة، غير كتقدر تكون جملة كاملة)،
    وكيتبع نفس آلية الحذف/التحذير ديال BANNED_WORDS."""
    await _delete_trigger_silently(ctx)
    if not is_owner(ctx):
        return
    phrase = phrase.strip()
    if not phrase or phrase in BANNED_ACTIONS:
        return
    BANNED_ACTIONS.append(phrase)
    save_banned_lists()
    try:
        await ctx.author.send(f"✅ تزادت العبارة/الفعل الممنوع. (المجموع الحالي: {len(BANNED_ACTIONS)})")
    except Exception:
        pass


@bot.command(name="removeaction")
async def removeaction_cmd(ctx, *, phrase: str = ""):
    await _delete_trigger_silently(ctx)
    if not is_owner(ctx):
        return
    phrase = phrase.strip()
    if phrase in BANNED_ACTIONS:
        BANNED_ACTIONS.remove(phrase)
        save_banned_lists()
        try:
            await ctx.author.send(f"✅ تحيدت العبارة. (المجموع الحالي: {len(BANNED_ACTIONS)})")
        except Exception:
            pass


@bot.command(name="listbanned")
async def listbanned_cmd(ctx):
    """كيبعث اللائحة الكاملة بـ DM للـ Owner فقط (حتى الأدمن ما شايفينهاش)"""
    await _delete_trigger_silently(ctx)
    if not is_owner(ctx):
        return
    words = get_active_banned_words()
    actions = BANNED_ACTIONS
    text_words = "\n".join(f"- {w}" for w in words) or "ماكاين والو"
    text_actions = "\n".join(f"- {a}" for a in actions) or "ماكاين والو"
    try:
        await ctx.author.send(
            f"🚫 **الكلمات الممنوعة ({len(words)}):**\n{text_words}\n\n"
            f"🚫 **الأفعال/العبارات الممنوعة ({len(actions)}):**\n{text_actions}"
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# ║   OWNER ONLY — تحكم كامل فالسيرفر (كتم/حظر/طرد)          ║
# ═══════════════════════════════════════════════════════
# هاد الأوامر منفصلة على !kick/!ban/!mute العاديين (اللي خدامين بالصلاحيات
# ديال Discord)، وخاصة غير بالـ Owner بواسطة الـ ID — حتى admin/mod ما
# يقدروش يستعملوها. الـ Admins والـ Moderators كيبقاو خدامين بالأوامر
# العادية فوق حسب الصلاحيات ديال الـ role ديالهم بحال ماكانو.

@bot.command(name="ownerkick")
async def ownerkick_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if not is_owner(ctx):
        return
    if member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} تم طرده من طرف Owner.", delete_after=6)
        await log_action(
            ctx.guild, "👢 طرد (Owner)",
            f"**المستخدم:** {member.mention} ({member.name})\n**السبب:** {reason}",
            discord.Color.orange()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)


@bot.command(name="ownerban")
async def ownerban_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if not is_owner(ctx):
        return
    if member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
        return
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🚫 {member.mention} تم حظره من طرف Owner.", delete_after=6)
        await log_action(
            ctx.guild, "🚫 حظر (Owner)",
            f"**المستخدم:** {member.mention} ({member.name})\n**السبب:** {reason}",
            discord.Color.red()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)


@bot.command(name="ownermute")
async def ownermute_cmd(ctx, member: discord.Member, duration: int = 5, *, reason="ما ذكرش سبب"):
    if not is_owner(ctx):
        return
    if member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
        return
    muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not muted_role:
        await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.", delete_after=5)
        return
    try:
        await member.add_roles(muted_role)
        user_id = str(member.id)
        if user_id in mute_tasks and not mute_tasks[user_id].done():
            mute_tasks[user_id].cancel()
        task = asyncio.create_task(auto_unmute(member, duration, ctx.guild))
        mute_tasks[user_id] = task
        await ctx.send(f"🔇 {member.mention} تكتم من طرف Owner ({duration} دقيقة).", delete_after=6)
        await log_action(
            ctx.guild, "🔇 كتم (Owner)",
            f"**المستخدم:** {member.mention} ({member.name})\n**المدة:** {duration}د\n**السبب:** {reason}",
            discord.Color.yellow()
        )
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)


@bot.command(name="muteall")
async def muteall_cmd(ctx, *, reason="Server Lockdown (Owner)"):
    """كتكتم كاع الأعضاء فالسيرفر (ما عدا Owner والأدوار المعفية) — Owner فقط"""
    if not is_owner(ctx):
        return
    muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not muted_role:
        await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.", delete_after=5)
        return
    status_msg = await ctx.send("⏳ كنكتم كاع الأعضاء، صبر شوية...")
    muted_count = 0
    for member in ctx.guild.members:
        if member.bot or member.id == OWNER_ID or is_exempt(member):
            continue
        if muted_role in member.roles:
            continue
        try:
            await member.add_roles(muted_role, reason=reason)
            muted_count += 1
            await asyncio.sleep(0.4)
        except (discord.Forbidden, discord.HTTPException):
            continue
    await status_msg.edit(content=f"🔇 تكتمو {muted_count} عضو من طرف Owner.")
    await log_action(
        ctx.guild, "🔇 Mute All (Owner)",
        f"**العدد:** {muted_count}\n**السبب:** {reason}\n**المنفذ:** {ctx.author.mention}",
        discord.Color.yellow()
    )


@bot.command(name="unmuteall")
async def unmuteall_cmd(ctx):
    """كتفك الكتم على كاع الأعضاء المكتومين — Owner فقط"""
    if not is_owner(ctx):
        return
    muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not muted_role:
        await ctx.send("❌ ما لقيتش دور Mute!", delete_after=5)
        return
    status_msg = await ctx.send("⏳ كنفك الكتم على الجميع، صبر شوية...")
    unmuted_count = 0
    for member in list(muted_role.members):
        try:
            await member.remove_roles(muted_role)
            unmuted_count += 1
            user_id = str(member.id)
            if user_id in mute_tasks and not mute_tasks[user_id].done():
                mute_tasks[user_id].cancel()
            await asyncio.sleep(0.4)
        except (discord.Forbidden, discord.HTTPException):
            continue
    await status_msg.edit(content=f"🔊 تفك الكتم على {unmuted_count} عضو.")
    await log_action(
        ctx.guild, "🔊 Unmute All (Owner)",
        f"**العدد:** {unmuted_count}\n**المنفذ:** {ctx.author.mention}",
        discord.Color.green()
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def clearoldverify(ctx):
    """كيمسح رسالة/رسائل 'تفعيل العضوية' القديمة (بالريأكشن ✅) من verify channel"""
    verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
    rules_channel = bot.get_channel(RULES_CHANNEL_ID)
    deleted = 0
    for channel in {verify_channel, rules_channel}:
        if not channel:
            continue
        async for message in channel.history(limit=50):
            if message.author == bot.user and "تفعيل العضوية" in (message.embeds[0].title if message.embeds else ""):
                try:
                    await message.delete()
                    deleted += 1
                except Exception:
                    pass
    await ctx.send(f"✅ تمسحو {deleted} رسالة/رسائل قديمة." if deleted else "ماكاينش شي رسالة قديمة باش تتمسح.", delete_after=8)


@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    await setup_verify_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def setupblacklist(ctx):
    """يصاوب رسالة الممنوعات والعقوبات فـ Blacklist channel"""
    if not BLACKLIST_CHANNEL_ID:
        await ctx.send("❌ خاصك تحط `BLACKLIST_CHANNEL_ID` فالـ CONFIG أولاً!")
        return
    await setup_blacklist_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة Blacklist!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def setuprules(ctx):
    """يصاوب رسالة القوانين + زرارات كنوافق/كنرفض فـ rules channel"""
    await setup_rules_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة القوانين بالأزرار!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def setuproles(ctx):
    """يصاوب رسالة اختيار الأدوار بـ Dropdown Menus (خاصك تعمر PICK_ROLES فـ config أولاً)"""
    has_any_valid_role = any(
        r["role_id"] for roles_list in PICK_ROLES.values() for r in roles_list
    )
    if not has_any_valid_role:
        await ctx.send(
            "❌ ماكاين حتى رول صالح فـ `PICK_ROLES`!\n"
            "خاصك تحط IDs ديال الأدوار فـ config (فعّل Developer Mode فـ Discord، "
            "بعدها كليك يمين على الرول → Copy ID)."
        )
        return

    description_lines = ["اختار من اللائحة (Dropdown) تحت باش تاخد الأدوار، وعاود اختار باش تبدلها 🔄\n"]
    for category_name, roles_list in PICK_ROLES.items():
        valid = [r for r in roles_list if r["role_id"]]
        if not valid:
            continue
        description_lines.append(f"**{category_name}**")
        description_lines.append(", ".join(f"{r['emoji']} {r['label']}" for r in valid))
        description_lines.append("")

    embed = discord.Embed(
        title="🎭 اختار الأدوار ديالك",
        description="\n".join(description_lines),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="GGMW9 | Pick Roles")

    await ctx.send(embed=embed, view=RolePickerView())
    await ctx.send("✅ تصاوبات رسالة الأدوار!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def listroles(ctx):
    """يبين لائحة الأدوار المعمرة دابا فـ PICK_ROLES"""
    lines = []
    for category_name, roles_list in PICK_ROLES.items():
        valid = [r for r in roles_list if r["role_id"]]
        if not valid:
            continue
        roles_text = ", ".join(f"{r['emoji']} {r['label']} → <@&{r['role_id']}>" for r in valid)
        lines.append(f"**{category_name}**\n{roles_text}")

    if not lines:
        await ctx.send("ماكاين حتى رول معمر دابا فـ `PICK_ROLES`. عمر IDs ديال الأدوار فـ config.")
        return

    embed = discord.Embed(
        title="🎭 الأدوار المعمرة فـ PICK_ROLES",
        description="\n\n".join(lines),
        color=discord.Color.blue()
    )
    embed.set_footer(text="GGMW9 | Pick Roles")
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def verify(ctx, member: discord.Member):
    unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role)
    member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
    if member_role:
        await member.add_roles(member_role)
    embed = discord.Embed(
        title="✅ تفعيل يدوي",
        description=f"**{member.mention}** تم تفعيله.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
    embed.set_footer(text="GGMW9 | Verification")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "✅ تفعيل يدوي",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**المنفذ:** {ctx.author.mention}",
        discord.Color.green()
    )
    try:
        gender_embed = discord.Embed(
            title="🚻 واش نتا/نتي ولد ولا بنت؟",
            description="ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
            color=discord.Color.blurple()
        )
        await member.send(
            f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉",
            embed=gender_embed,
            view=GenderSelectView(target_user_id=member.id, guild_id=ctx.guild.id)
        )
    except Exception:
        pass


@bot.command()
@commands.has_permissions(administrator=True)
async def checkroles(ctx):
    """كيتأكد أن role ديال البوت قادر يعطي Member/Unverified/Muted"""
    problems = check_role_hierarchy(ctx.guild)
    if not problems:
        embed = discord.Embed(
            title="✅ كلشي مزيان",
            description="role ديال البوت فوق فالترتيب وعندو الصلاحيات اللازمة. نظام التفعيل خاصو يخدم عادي.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="⚠️ لقيت مشاكل فترتيب الرولات",
            description="\n\n".join(problems),
            color=discord.Color.red()
        )
    embed.set_footer(text="GGMW9 | Role Hierarchy Check")
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def unverify(ctx, member: discord.Member):
    member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
    if member_role and member_role in member.roles:
        await member.remove_roles(member_role)
    unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role:
        await member.add_roles(unverified_role)
    embed = discord.Embed(
        title="🔄 إلغاء التفعيل",
        description=f"**{member.mention}** تم إلغاء تفعيله.",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
    embed.set_footer(text="GGMW9 | Verification")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "🔄 إلغاء التفعيل",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**المنفذ:** {ctx.author.mention}",
        discord.Color.orange()
    )


@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latency:** {latency}ms\n**API:** DeepSeek V3",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="GGMW9")
    await ctx.send(embed=embed)


@bot.command()
async def info(ctx):
    embed = discord.Embed(
        title="🤖 معلومات GGMW9",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="💬 AI Channel", value=f"`{TARGET_CHANNEL_ID}`", inline=True)
    embed.add_field(name="👋 Welcome", value=f"`{WELCOME_CHANNEL_ID}`", inline=True)
    embed.add_field(name="✅ Verify", value=f"`{VERIFY_CHANNEL_ID}`", inline=True)
    embed.add_field(name="🧠 Memory", value=f"`{MEMORY_SIZE}` msg/user", inline=True)
    embed.add_field(name="⏱️ Timeout", value=f"`{API_TIMEOUT}`s", inline=True)
    embed.add_field(name="🤖 Model", value=f"`{AI_MODEL}`", inline=True)
    embed.add_field(name="📊 Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="🛡️ Moderation", value="✅ نشط", inline=False)
    embed.add_field(name="✅ Verification", value="✅ نشط", inline=False)
    embed.add_field(name="📰 Auto-Info", value="✅ نشط (5 channels)", inline=False)
    embed.add_field(
        name="⚠️ Warn Escalation",
        value=f"Mute@{MUTE_AFTER_WARNS} / Kick@{KICK_AFTER_WARNS} / Ban@{BAN_AFTER_WARNS}",
        inline=True
    )
    embed.add_field(name="🚫 Banned Words", value=f"`{len(get_active_banned_words())}`", inline=True)
    embed.set_footer(text="GGMW9")
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📋 قائمة أوامر GGMW9",
        description="**GGMW9** — بوت AI مغربي + Moderation + Verification + Auto-Info",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    ai_cmds = (
        "`!chat <رسالة>` — هضر مع GGMW9\n"
        "`!نسيني` — امسح ذاكرتك\n"
        "`!ذاكرة` — شحال من رسالة فالذاكرة\n"
        "`!انعلمك <حاجة>` — علم GGMW9 شي حاجة"
    )
    embed.add_field(name="🤖 AI & ذاكرة", value=ai_cmds, inline=False)
    mod_cmds = (
        "`!kick @user [سبب]` — طرد عضو\n"
        "`!ban @user [سبب]` — حظر عضو\n"
        "`!unban <user_id>` — فك الحظر\n"
        "`!mute @user <دقائق> [سبب]` — كتم\n"
        "`!unmute @user` — فك الكتم\n"
        "`!warn @user <سبب>` — تحذير\n"
        "`!warns [@user]` — عرض التحذيرات\n"
        "`!unwarn @user` — مسح التحذيرات\n"
        "`!clear <عدد>` — حذف رسائل (1-100)"
    )
    embed.add_field(name="🛡️ موديراتورز", value=mod_cmds, inline=False)
    verif_cmds = (
        "`!setupverify` — صاوب رسالة التفعيل بـ ✅ (Admin)\n"
        "`!setuprules` — صاوب رسالة القوانين بـ أزرار كنوافق/كنرفض (Admin)\n"
        "`!verify @user` — يفعّل عضو يدوياً (Admin)\n"
        "`!unverify @user` — يرجعو @Unverified (Admin)"
    )
    embed.add_field(name="✅ تفعيل", value=verif_cmds, inline=False)
    roles_cmds = (
        "`!setuproles` — صاوب رسالة اختيار الأدوار (Admin)\n"
        "`!listroles` — بين رسائل Reaction Roles الفعّالة (Admin)"
    )
    embed.add_field(name="🎭 Reaction Roles", value=roles_cmds, inline=False)
    util_cmds = (
        "`!ping` — سرعة البوت\n"
        "`!info` — معلومات البوت\n"
        "`!help` — هاد القائمة\n"
        "`!testinfo` — جرب Auto-Info فوراً (Admin)"
    )
    embed.add_field(name="🔧 أدوات", value=util_cmds, inline=False)
    auto_mod = (
        "✅ كلمات ممنوعة\n"
        "✅ كشف السبام (5 msg/5s)\n"
        "✅ Auto-mute\n"
        "✅ Auto-kick (3 warns)\n"
        "✅ Logs كاملة فـ #mod-logs"
    )
    embed.add_field(name="🤖 Auto-Mod", value=auto_mod, inline=False)
    auto_info_cmds = (
        "📰 #news — أخبار عامة (NewsAPI)\n"
        "🎮 #games — أخبار ألعاب (RAWG)\n"
        "🎬 #movies — أفلام + ملخصات (IMDB/OMDb)\n"
        "📺 #anime — أنمي + ملخصات (MyAnimeList/Jikan)\n"
        "🎧 #music — أخبار موسيقى + أغاني (Last.fm)\n"
        "⏱️ كل 30 دقيقة"
    )
    embed.add_field(name="📰 Auto-Info", value=auto_info_cmds, inline=False)
    verif_info = (
        "🔒 @Unverified — جديد (ما يهضرش)\n"
        "✅ @Member — مفعل (يهضر)\n"
        "🔄 كليك ✅ فـ verify channel، ولا الأزرار (كنوافق/كنرفض) فـ rules channel"
    )
    embed.add_field(name="🔐 نظام التفعيل", value=verif_info, inline=False)
    embed.set_footer(text="GGMW9 | Prefix: !")
    await ctx.send(embed=embed)


@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    response = await ask_ai(user_id, ctx.author.name, ctx.author.display_name, message)
    await ctx.send(response[:MAX_REPLY_LENGTH])


@bot.command()
@owner_only()
async def نسيني(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")


@bot.command()
@owner_only()
async def ذاكرة(ctx):
    user_id = str(ctx.author.id)
    count = len(user_memory.get(user_id, [])) // 2
    await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")


@bot.command()
@owner_only()
async def انعلمك(ctx, *, knowledge: str):
    learned_knowledge.append(knowledge)
    gender = detect_gender(ctx.author.name, ctx.author.display_name)
    if gender == "female":
        await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
    else:
        await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")


@bot.command()
@owner_only()
async def انعلمك_شي_حاجة_جديدة(ctx, *, knowledge: str):
    await انعلمك(ctx, knowledge=knowledge)


# ═══════════════════════════════════════════════════════
# ║        COMMAND TEST INFO (جديد!)                      ║
# ═══════════════════════════════════════════════════════

@bot.command()
@owner_only()
async def testinfo(ctx, category: str = "all"):
    """
    جرب Auto-Info فوراً!
    الاستخدام: !testinfo [news|games|movies|anime|music|all]
    """
    categories = {
        "news": ("📰 News", NEWS_CHANNEL_IDS, get_news_from_api, "NewsAPI"),
        "games": ("🎮 Games", GAMES_CHANNEL_IDS, get_game_from_rawg, "RAWG.io"),
        "movies": ("🎬 Movies", MOVIES_CHANNEL_IDS, get_movie_from_omdb, "TMDb+OMDb"),
        "anime": ("📺 Anime", ANIME_CHANNEL_IDS, get_anime_from_jikan, "Jikan"),
        "music": ("🎧 Music", MUSIC_CHANNEL_IDS, get_music_from_lastfm, "Last.fm")
    }
    
    if category == "all":
        cats_to_test = list(categories.keys())
    elif category in categories:
        cats_to_test = [category]
    else:
        await ctx.send("❌ الاستخدام: `!testinfo [news|games|movies|anime|music|all]`")
        return
    
    await ctx.send(f"🧪 جاري اختبار {len(cats_to_test)} APIs...")
    
    for cat in cats_to_test:
        name, channel_ids, func, api_name = categories[cat]
        channel = bot.get_channel(channel_ids[0]) if channel_ids else None
        
        if not channel:
            await ctx.send(f"❌ {name}: ما لقيتش القناة!")
            continue
        
        try:
            data = await func()
            if data:
                status = "✅ نجح"
                has_poster = "🖼️ فيه صورة" if data.get("poster") else "🚫 بلا صورة"
                preview = f"{has_poster}\n{str(data)[:300]}"
            else:
                status = "⚠️ ما جاب والو (API فاضي ولا مفتاح غالط)"
                preview = "ما كاينش داتا"
        except Exception as e:
            status = f"❌ خطأ: {str(e)[:100]}"
            preview = "Exception"
        
        await ctx.send(f"**{name}** ({api_name}): {status}\n```\n{preview}\n```")
    
    await ctx.send("✅ تم الاختبار!")


# ═══════════════════════════════════════════════════════
# ║              AUTO-INFO TASK (مع APIs حقيقية)           ║
# ═══════════════════════════════════════════════════════

@tasks.loop(minutes=30)
async def auto_info():
    """يبعث معلومات من APIs حقيقية — كل 30 دقيقة. كل فئة معزولة (try/except)
    باش خطأ فـ فئة وحدة ما يوقفش اللي بعدها."""

    # ═══════ 📰 NEWS — أخبار عامة ═══════
    try:
        news = await get_news_from_api()
        if news:
            embed = discord.Embed(
                title=f"📰 {news['title']}",
                description=news['description'],
                color=discord.Color.blue(),
                url=news['url'],
                timestamp=datetime.now()
            )
            embed.set_author(name=f"📡 {news['source']}")
            if news['image']:
                embed.set_image(url=news['image'])
            embed.set_footer(text="GGMW9 | NewsAPI")
            ping = get_ping_mention("News Ping") or None
            for channel_id in NEWS_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(content=ping, embed=embed)
    except Exception as e:
        print(f"[AUTO_INFO] ❌ خطأ فـ NEWS: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎮 GAMES — أخبار ألعاب ═══════
    try:
        game = await get_game_from_rawg()
        if game:
            embed = discord.Embed(
                title=f"🎮 {game['name']}",
                description=game['description'][:400] + "...",
                color=discord.Color.green(),
                url=game['url'],
                timestamp=datetime.now()
            )
            embed.add_field(name="📅 تاريخ الصدور", value=game['released'], inline=True)
            embed.add_field(name="⭐ التقييم", value=game['rating'], inline=True)
            embed.add_field(name="🎭 النوع", value=game['genres'], inline=False)
            if game['poster']:
                embed.set_image(url=game['poster'])
            embed.set_footer(text="GGMW9 | RAWG.io")
            ping = get_ping_mention("Games Ping") or None
            for channel_id in GAMES_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(content=ping, embed=embed)
    except Exception as e:
        print(f"[AUTO_INFO] ❌ خطأ فـ GAMES: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎬 MOVIES — أفلام + ملخص ═══════
    try:
        movie = await get_movie_from_omdb()
        if movie:
            embed = discord.Embed(
                title=f"🎬 {movie['title']} ({movie['year']})",
                description=movie['plot'][:500] + "...",
                color=discord.Color.gold(),
                url=movie['imdb'],
                timestamp=datetime.now()
            )
            embed.add_field(name="🎭 النوع", value=movie['genre'], inline=True)
            embed.add_field(name="⭐ تقييم IMDB", value=f"{movie['rating']}/10", inline=True)
            if movie['poster'] and movie['poster'] != "N/A":
                embed.set_image(url=movie['poster'])
            embed.set_footer(text="GGMW9 | IMDB via OMDb")
            ping = get_ping_mention("Movies Ping") or None
            for channel_id in MOVIES_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(content=ping, embed=embed)
    except Exception as e:
        print(f"[AUTO_INFO] ❌ خطأ فـ MOVIES: {e}")

    await asyncio.sleep(2)

    # ═══════ 📺 ANIME — أنمي + ملخص ═══════
    try:
        anime = await get_anime_from_jikan()
        print(f"[AUTO_INFO] get_anime_from_jikan رجع: {'فيها داتا' if anime else 'فارغة'}")
        if anime:
            embed = discord.Embed(
                title=f"📺 {anime['title']}",
                description=anime['synopsis'][:500] + "...",
                color=discord.Color.purple(),
                url=anime['url'],
                timestamp=datetime.now()
            )
            if anime['title_jp']:
                embed.add_field(name="🇯🇵 الاسم الياباني", value=anime['title_jp'], inline=False)
            embed.add_field(name="📺 النوع", value=anime['type'], inline=True)
            embed.add_field(name="📊 عدد الحلقات", value=str(anime['episodes']), inline=True)
            embed.add_field(name="⭐ تقييم MAL", value=f"{anime['score']}/10", inline=True)
            embed.add_field(name="🎭 الأنواع", value=anime['genres'], inline=False)
            if anime['poster']:
                embed.set_image(url=anime['poster'])
            embed.set_footer(text="GGMW9 | MyAnimeList via Jikan")
            ping = get_ping_mention("Anime Ping") or None
            for channel_id in ANIME_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(content=ping, embed=embed)
                    print("[AUTO_INFO] ✅ تبعث embed ديال الأنمي")
    except Exception as e:
        print(f"[AUTO_INFO] ❌ خطأ فـ ANIME: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎧 MUSIC — موسيقى + أغاني ═══════
    try:
        music = await get_music_from_lastfm()
        if music:
            embed = discord.Embed(
                title=f"🎵 {music['name']}",
                description=f"أغنية جديدة من **{music['artist']}**",
                color=discord.Color.red(),
                url=music['url'],
                timestamp=datetime.now()
            )
            embed.add_field(name="🎤 الفنان", value=music['artist'], inline=True)
            embed.add_field(name="👥 المستمعين", value=f"{music['listeners']:,}", inline=True)
            if music['poster']:
                embed.set_image(url=music['poster'])
            embed.set_footer(text="GGMW9 | Last.fm")
            ping = get_ping_mention("Music Ping") or None
            for channel_id in MUSIC_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(content=ping, embed=embed)
    except Exception as e:
        print(f"[AUTO_INFO] ❌ خطأ فـ MUSIC: {e}")


@auto_info.before_loop
async def before_auto_info():
    await bot.wait_until_ready()


# ═══════════════════════════════════════════════════════
# ║              GGMW9 STATUS (كل 30 دقيقة)                ║
# ═══════════════════════════════════════════════════════

async def build_stats_embed(guild: discord.Guild) -> discord.Embed:
    """يبني embed فيه الأرقام المباشرة ديال السيرفر"""
    members_count = guild.member_count or len(guild.members)

    # Online = عضو status ديالو ماشي offline (خاص intents.presences مفعلة، وماشي حسبان البوتات)
    online_count = sum(
        1 for m in guild.members
        if not m.bot and m.status != discord.Status.offline
    )

    voice_count = sum(len(vc.members) for vc in guild.voice_channels)

    boosts_count = guild.premium_subscription_count or 0
    boost_level = guild.premium_tier or 0
    boosters_count = len(guild.premium_subscribers) if guild.premium_subscribers else 0

    embed = discord.Embed(
        title=f"📊 {SERVER_NAME} STATUS",
        description=f"[Stats]({SERVER_INVITE_LINK})",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="👥 Members Count", value=f"{members_count:,}", inline=False)
    embed.add_field(name="🟢 Online Members", value=f"{online_count:,}", inline=False)
    embed.add_field(name="🔊 Members In Voice", value=f"{voice_count:,}", inline=False)
    embed.add_field(
        name="🚀 Server Boosts",
        value=f"Boosts Count : {boosts_count} (Level : {boost_level})",
        inline=False
    )
    embed.add_field(
        name="💎 Boosters",
        value=f"Members Are Boosting: {boosters_count}",
        inline=False
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if STATS_IMAGE_URL:
        embed.set_image(url=STATS_IMAGE_URL)
    embed.set_footer(text=f"{SERVER_NAME} | آخر تحديث")
    return embed


@tasks.loop(minutes=STATS_UPDATE_MINUTES)
async def update_stats():
    if not STATS_CHANNEL_ID:
        return
    channel = bot.get_channel(STATS_CHANNEL_ID)
    if not channel:
        print(f"[STATS] ❌ ماكاينش channel بـ ID {STATS_CHANNEL_ID}")
        return

    guild = channel.guild
    embed = await build_stats_embed(guild)
    msg_id = stats_message_ids.get(str(guild.id))

    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[STATS] خطأ فـ التعديل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        stats_message_ids[str(guild.id)] = new_msg.id
        save_stats_message_ids()
    except Exception as e:
        print(f"[STATS] خطأ فـ البعث: {e}")


@update_stats.before_loop
async def before_update_stats():
    await bot.wait_until_ready()


@update_stats.error
async def update_stats_error(error):
    print(f"[STATS] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_stats.is_running():
        update_stats.restart()


@auto_info.error
async def auto_info_error(error):
    """إلا وقع خطأ ما تصيدوش try/except ديال الفئات، هادي كنسجلوه، وكنعاودو نشغلو
    الـ loop (بلا هاد الشي، tasks.loop كيوقف نهائيا بصمت ملي يطيح خطأ ما تصيدش)."""
    print(f"[AUTO_INFO] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not auto_info.is_running():
        auto_info.restart()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ ما عندكش الصلاحية!",
            description="خاصك تكون موديراتور باش تستخدم هاد الأمر.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ ناقص شي حاجة!",
            description=f"استخدم `!help` باش تشوف كيفاش تستخدم الأمر.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        embed = discord.Embed(
            title="❌ ما لقيتش هاد العضو!",
            description="تأكد من الـ mention ولا الـ ID.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ خطأ فـ المدخلات!",
            description="الرقم ولا الـ ID ما صحيحش.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.CheckFailure):
        embed = discord.Embed(
            title="❌ ما عندكش الصلاحية!",
            description="هاد الأمر خاص غير بـ Owner ديال السيرفر.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    else:
        print(f"[ERROR] {error}")


@bot.event
async def on_ready():
    print(f"✅ GGMW9 شغال!")
    print(f"🤖 Model: {AI_MODEL}")
    print(f"💬 AI Channel: {TARGET_CHANNEL_ID}")
    print(f"👋 Welcome: {WELCOME_CHANNEL_ID}")
    print(f"✅ Verify: {VERIFY_CHANNEL_ID}")
    print(f"🛡️ Mod Logs: {MOD_LOGS_CHANNEL_ID}")
    print(f"📰 News: {NEWS_CHANNEL_IDS}")
    print(f"🎮 Games: {GAMES_CHANNEL_IDS}")
    print(f"🎬 Movies: {MOVIES_CHANNEL_IDS}")
    print(f"📺 Anime: {ANIME_CHANNEL_IDS}")
    print(f"🎧 Music: {MUSIC_CHANNEL_IDS}")
    print(f"⏱️ Timeout: {API_TIMEOUT}s")
    print(f"🛡️ Moderation: نشط")
    print(f"✅ Verification: نشط")
    print(f"📰 Auto-Info: نشط (5 channels + APIs حقيقية)")
    print(f"⚠️ Warn Escalation: Mute@{MUTE_AFTER_WARNS} / Kick@{KICK_AFTER_WARNS} / Ban@{BAN_AFTER_WARNS}")
    print(f"📊 Stats Channel: {STATS_CHANNEL_ID if STATS_CHANNEL_ID else 'ماشي معطي بعد'} (كل {STATS_UPDATE_MINUTES} د)")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"!help | {len(bot.guilds)} سيرفرات"
        )
    )

    if not auto_info.is_running():
        auto_info.start()

    if STATS_CHANNEL_ID and not update_stats.is_running():
        update_stats.start()

    bot.add_view(RulesVerifyView())  # باش الأزرار يبقاو خدامين حتى بعد ريستارت البوت
    bot.add_view(RolePickerView())   # باش الـ Dropdown ديال الأدوار يبقى خدام حتى بعد ريستارت البوت

    for guild in bot.guilds:
        # ملاحظة: ماعادش كنبعثو رسالة "تفعيل العضوية" القديمة (بالريأكشن ✅)
        # باش ما تبقاش مكررة مع رسالة القوانين الجديدة بالأزرار (setup_rules_message)
        await setup_rules_message(guild)
        if BLACKLIST_CHANNEL_ID:
            await setup_blacklist_message(guild)

        problems = check_role_hierarchy(guild)
        if problems:
            print(f"[ROLE CHECK] ⚠️ {guild.name}: مشاكل فترتيب الرولات:")
            for p in problems:
                print(f"  - {p}")
            await log_action(
                guild,
                "⚠️ مشكل فترتيب الرولات",
                "نظام التفعيل ممكن ما يخدمش مزيان:\n\n" + "\n\n".join(problems) +
                "\n\nاستعمل `!checkroles` بعد ما تصلح باش تتأكد.",
                discord.Color.orange()
            )


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
