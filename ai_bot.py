import os
import sys
import discord
import aiohttp
import random
import asyncio
import json
import re
import io
import math
import html
from typing import Optional
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ Pillow ماشي مثبت — Welcome Cards (الصور) غادي تكون معطلة. دير: pip install Pillow")

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

# ═══════ Welcome Cards (صورة ترحيبية مخصصة لكل عضو جديد) ═══════
WELCOME_CARD_ENABLED = False
WELCOME_CARD_BACKGROUND_PATH = None  # ← حط هنا path ديال صورة (مثلا "assets/welcome_bg.png")، None = خلفية بتدرج لوني افتراضي
WELCOME_CARD_ACCENT_RGB = (88, 101, 242)  # لون Discord Blurple، تقدر تبدلو بأي لون RGB (R, G, B)
WELCOME_CARD_ACCENT2_RGB = (235, 90, 180)  # لون ثاني للتدرج القطري (وردي/بنفسجي بشكل افتراضي)
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

AI_MODEL = "deepseek/deepseek-v4-flash"  # ← موديل مدفوع رخيص بزاف ($0.0983/مليون token دخول، $0.1966/مليون خروج)
#   ✅ متحقق منو فـ openrouter.ai/deepseek — الاسم صحيح 100% وخدام (نسخة أبريل 2026، 1M context).
#   بـ 9$ ديال الرصيد عندك تقريبا 90 مليون token دخول — يعني آلاف الردود. ماكاين حتى مشكل هنا.

# ⚠️ DeepSeek V4 Flash هو reasoning model: كيصرف جزء من max_tokens على "التفكير"
# قبل ما يكتب الجواب. علاش خاصنا نطفيو الـ reasoning فـ المهام القصيرة (بحال الترجمة)،
# وإلا كيرجع content فارغة وكيبان ليك بلي "الموديل ماخدامش". شوف AI_DISABLE_REASONING تحت.
AI_DISABLE_REASONING = True

# ═══════ سلسلة الاحتياط (Fallback) ═══════
# إلا AI_MODEL فشل لسبب ما (بحال خلص الرصيد)، البوت كيجرب أوتوماتيكيا الموديلات
# المجانية اللي فـ هاد اللائحة، واحد بواحد، قبل ما يستسلم.
# ✅ هاد اللائحة تحققت منها فـ 3 غشت 2026 من openrouter.ai (كاع الأسماء خدامة).
# ⚠️ ملاحظة: "qwen/qwen3-next-80b-a3b-instruct:free" اللي كان هنا قبل تحيد من OpenRouter
# فـ يوليوز 2026 — كان كيرجع 404 وهو من الأسباب اللي خلات الترجمة ما تخدمش.
AI_MODEL_FALLBACKS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",   # أقوى موديل مجاني حاليا (1M context)
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "openrouter/free",   # ← auto-router ديال OpenRouter: كيختار وحدو شي موديل مجاني متاح.
                         #   خليه دايما فالآخر — هو اللي كيضمن ليك البوت مايوقفش ملي
                         #   OpenRouter يحيد شي موديل مجاني بلا سابق إنذار.
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

# ═══════ تفعيل/تعطيل كل فئة ديال Auto-Info بوحدها ═══════
# (كل فئة كتستعمل translate_to_darija → طلب OpenRouter. عطلها مؤقتا باش توفر
# الحصة اليومية المجانية للترجمة بالعلم، وشعلها ملي تزيد رصيد ولا تبغي)
AUTO_INFO_NEWS_ENABLED = False
AUTO_INFO_GAMES_ENABLED = False
AUTO_INFO_MOVIES_ENABLED = False
AUTO_INFO_ANIME_ENABLED = False
AUTO_INFO_MUSIC_ENABLED = False

# ═══════════════════════════════════════════════════════
# ║              🧠 Trivia — لعبة أسئلة ثقافة عامة          ║
# ═══════════════════════════════════════════════════════
# كتستعمل OpenTDB (API مجاني 100%، بلا key، بلا علاقة بـ OpenRouter) —
# ماكاينش خطر على الحصة ديال الترجمة/AI.
TRIVIA_ENABLED = True
TRIVIA_XP_REWARD = 8           # ← شحال XP كياخد اللي جاوب صحيح (قللناها من 15، باش تكون قريبة من XP الشات العادي)
TRIVIA_ANSWER_SECONDS = 30     # ← شحال ديال الوقت (بالثواني) معطى للجواب قبل ما يتسالا السؤال
# ═══════ Trivia أوتوماتيكي (اختياري) ═══════
TRIVIA_AUTO_CHANNEL_IDS = []           # ← خاوية = معطل. عامرة بـ IDs = كيبعث سؤال أوتوماتيك فهاد الـ channels
TRIVIA_AUTO_INTERVAL_MINUTES = 60      # ← كل شحال ديال الدقايق كيبعث سؤال جديد أوتوماتيك

# ═══════ Trivia Channel — panel دائم فـ channel خاص (زر "ابدأ اللعب" → اختار مجال → أسئلة متتالية) ═══════
# 1) دير category جديدة فديسكورد سميها مثلا "🎮 Mini Games"
# 2) دير channel جوجها (مثلا "🧠│trivia") وحط الـ ID ديالها هنا:
TRIVIA_CHANNEL_ID = 1533700465576116236
# 💡 خليها 0 وسير دير `/setuptrivia` مباشرة فالـ channel اللي بغيتي — البوت غايصاوب
#    الـ panel تما أوتوماتيكيا. (بدلها بالـ ID غير إلا بغيتي البوت يصاوبها وحدو ملي كيشعل)
TRIVIA_ROUNDS_PER_DIFFICULTY = 6   # ← كل ما جاوب صحيح هاد العدد ديال الأسئلة متتالية، الصعوبة تطلع درجة (ساهل ← متوسط ← صعيب)
TRIVIA_XP_BY_DIFFICULTY = {        # ← تحكم كامل فشحال XP كل درجة صعوبة (بدلها كيفما بغيتي)
    "easy": 4,
    "medium": 7,
    "hard": 12,
}

# ═══════════════════════════════════════════════════════
# ║              MODERATION & VERIFICATION CONFIG          ║
# ═══════════════════════════════════════════════════════

MOD_LOGS_CHANNEL_ID = 1526470164235681832
VERIFY_CHANNEL_ID = 1526481352264781854
RULES_CHANNEL_ID = 1526474691789721700
BLACKLIST_CHANNEL_ID = 1526858911477661786  # ← حط هنا ID ديال channel "Blacklist things"
REPORTS_CHANNEL_ID = 1526884019105431562    # ← حط هنا ID ديال channel البلاغات (فين كتوصل البلاغات ديال /report)

# ═══════ نظام Tickets (بدل/جنب /report — channels خاصة بكل مشكل) ═══════
TICKETS_PANEL_CHANNEL_ID = 1532144216958959839   # ← channel فين غادي تبان رسالة "🎫 دير Ticket" بالزر
TICKETS_CATEGORY_ID = 1532144108754440355        # ← ID ديال Category (فولدر) "Tickets" فين كيتخلقو الـ channels الخاصة
TICKET_LOGS_CHANNEL_ID = 1532144316611428352     # ← channel فين كيتبعث ملخص/transcript الـ ticket ملي يتسد (إلا خليتها 0 غايستعمل MOD_LOGS_CHANNEL_ID)

# ═══════ نظام Applications (طلبات الانضمام لفريق الإدارة/Staff) ═══════
APPLICATIONS_PANEL_CHANNEL_ID = 1532910298585890927     # ← حط هنا ID ديال channel فين غادي تبان رسالة "📋 قدم طلب" بالزر
APPLICATIONS_REVIEW_CHANNEL_ID = 1532910345352515666    # ← حط هنا ID ديال channel فين كتوصل الطلبات (خاصك تحطو Private، يشوفو غير Owner+Admins فـ Discord)
APPLICATION_ACCEPTED_ROLE_ID = 1532910587301068930      # ← (اختياري) رول كيتعطى أوتوماتيكياً ملي يتقبل الطلب — خليها 0 إلا مابغيتيش
APPLICATIONS_COOLDOWN_HOURS = 168     # ← شحال ديال الساعات خاص العضو يصبر بعد الرفض قبل ما يقدر يعاود يقدم (168 = أسبوع)
# ═══════ شكون يقدر يقبل/يرفض الطلبات (Owner + هاد الأدوار فقط — Moderators ماشي معنيين) ═══════
APPLICATIONS_REVIEWER_ROLE_IDS = [
    1525712399456272495,  # نفس role "Admin"
]

# ═══════ نظام Suggestions (اقتراحات الأعضاء) ═══════
SUGGESTIONS_CHANNEL_ID = 1532913868509155358            # ← حط هنا ID ديال channel فين كيتبعثو الاقتراحات

# ═══════ نظام Birthdays (أعياد الميلاد) ═══════
BIRTHDAY_ANNOUNCE_CHANNEL_ID = 1533241235630854224   # ← حط هنا ID ديال channel فين كيتبعث تهنئة عيد الميلاد (بحال #general)
BIRTHDAY_ROLE_ID = 1533241332473008229               # ← (اختياري) رول 🎂 كيتعطى نهار عيد الميلاد وكيتحيد الغد — خليها 0 إلا مابغيتيش
BIRTHDAY_ANNOUNCE_HOUR = 9         # ← فأي ساعة (UTC، من 0 لـ 23) كيتبعث التهنئة كل نهار

# ═══════ نظام Marry/Bestfriend (أزواج/أصدقاء) ═══════
MARRIAGE_ROLE_ID = 1533987822216810706     # ← (اختياري) رول عام 💍 كيتعطى للجوج ملي يتزوجو (بزيادة على الرول الشخصي) — خليها 0 إلا مابغيتيش
BESTFRIEND_ROLE_ID = 1533988290011594824   # ← (اختياري) رول عام 🤝 كيتعطى للجوج ملي يوليو Best Friends (بزيادة على الرول الشخصي) — خليها 0 إلا مابغيتيش
RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS = 300   # ← شحال ديال الوقت (بالثواني) عندو الشخص التاني باش يرد على الطلب
RELATIONSHIP_DM_PROPOSALS = True    # ← الطلب يتبعث فـ DM للشخص المطلوب (True)، ولا فنفس الـ channel ديال السيرفر (False)
RELATIONSHIP_ANNOUNCE_CHANNEL_ID = 1524957892925456545   # ← الـ channel (# general) فين كيتبعث إعلان عام ملي شي حد يقبل الزواج/الصداقة، ولا يطلق/يقطع الصداقة — خليها 0 إلا مابغيتيش
RELATIONSHIP_PERSONAL_ROLE_ENABLED = True   # ← كل واحد فالعلاقة ياخد رول شخصي بسمية الشريك ديالو (بحال "💍 Aya")
MARRIAGE_PERSONAL_ROLE_COLOR = 0xd41b1b     # ← لون الرولات الشخصية ديال الزواج (روز)
BESTFRIEND_PERSONAL_ROLE_COLOR = 0xf1c40f   # ← لون الرولات الشخصية ديال الصداقة (أزرق فاتح)

# ═══════ رولات الأبراج — كيتعطى أوتوماتيكياً ملي العضو يدير /setbirthday حسب التاريخ ═══════
# ⚠️ بدل كل 0 برقم الـ Role ID الحقيقي ديالك (Server Settings → Roles → كليك يمين → Copy Role ID)
# خلي شي واحد 0 إلا مابغيتيش رول لهاد البرج (البوت غايتخطاه بلا مشكل)
ZODIAC_ROLE_IDS = {
    "aries": 1533244997858492426,        # ♈ الحمل (21 مارس - 19 أبريل)
    "taurus": 1533245155782561904,       # ♉ الثور (20 أبريل - 20 ماي)
    "gemini": 1533245357805404260,       # ♊ الجوزاء (21 ماي - 20 يونيو)
    "cancer": 1533245304789274744,       # ♋ السرطان (21 يونيو - 22 يوليوز)
    "leo": 1533245515871948952,          # ♌ الأسد (23 يوليوز - 22 غشت)
    "virgo": 1533245580615352380,        # ♍ العذراء (23 غشت - 22 شتنبر)
    "libra": 1533245685141340354,        # ♎ الميزان (23 شتنبر - 22 أكتوبر)
    "scorpio": 1533245753252905070,      # ♏ العقرب (23 أكتوبر - 21 نونبر)
    "sagittarius": 1533245801088684145,  # ♐ القوس (22 نونبر - 21 دجنبر)
    "capricorn": 1533245849964908614,    # ♑ الجدي (22 دجنبر - 19 يناير)
    "aquarius": 1533245909561901249,     # ♒ الدلو (20 يناير - 18 فبراير)
    "pisces": 1533245967275393137,       # ♓ الحوت (19 فبراير - 20 مارس)
}

# ═══════ شكون يقدر يستعمل Room Mute Panel (/roommutepanel) — Owner + هاد اللائحة بوحدهم ═══════
ROOM_MUTE_PANEL_ALLOWED_USER_IDS = [
    900839094106603671,  # ← الأدمين اللي زدتي
]

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

# ═══════ لائحة الإدارة (Owner + Admins + Mods) فـ channel "Administrators" ═══════
ADMINISTRATORS_CHANNEL_ID = 1532115828450000967  # ← حط هنا ID ديال channel "Administrators"
ADMIN_LIST_UPDATE_MINUTES = 30  # ← كل شحال ديال الدقائق كيتحدث المساج

# الأدوار اللي غادي تبان فـ اللائحة، بالترتيب اللي بغيتي تبان بيه (من فوق لتحت).
# زيد/بدل label و role_id حسب الرولات ديالك (الـ Owner كيبان فوق بوحدو من OWNER_ID).
STAFF_ROLES_ORDER = [
    {"label": "🔱 Admins", "role_id": 1525712399456272495},      # نفس role "Admin"
    {"label": "🛡️ Moderators", "role_id": 1526182506272133180},  # نفس role "Moderator"
]

BANNED_WORDS = [
    'سبام', 'spam', 'naked.', 'discord.gg', 'العزية', 'عزي',
    'nude', 'porn', 'xxx', 'sex', 'fuck', 'shit', 'bitch'
]

# ═══════ لائحة ديناميكية: كلمات وأفعال ممنوعة كتزاد/كتحيد بالأوامر ═══════
# BANNED_WORDS فوق هي القائمة الأساسية المكتوبة فالكود. أي كلمة/عبارة كتزاد
# ولا كتحيد بالأوامر (/addword, /addaction) كتتسجل فـ BANNED_LISTS_FILE
# باش تبقى محفوظة حتى بعد ريستارت البوت. BANNED_ACTIONS هي عبارات/سلوكيات
# ممنوعة زيادة على الكلمات، وكتتبع نفس آلية الحذف/التحذير ديال BANNED_WORDS.
BANNED_LISTS_FILE = os.path.join(DATA_DIR, "banned_lists.json")
BANNED_ACTIONS = []  # كتتعمر من الملف فـ load_banned_lists()
banned_words_state = {"extra": [], "removed": []}  # كتتعمر من الملف

SPAM_THRESHOLD = 5
SPAM_INTERVAL = 5

# ═══════ Anti-Raid Protection (كشف الهجوم الجماعي) ═══════
ANTI_RAID_ENABLED = True
RAID_JOIN_THRESHOLD = 10          # عدد الأعضاء الجداد
RAID_JOIN_INTERVAL_SECONDS = 30   # فـ هاد المدة (بالثواني) → إلا توصلات = Raid محتمل
RAID_ACTION = "kick"              # شنو يتدار فالعضو ملي يكون Raid Mode مفعل: "kick" ولا "ban"
RAID_LOCKDOWN_DURATION_MINUTES = 30  # شحال كيدوم Lockdown قبل ما يرجع عادي أوتوماتيكياً (0 = يبقى حتى /unlockdown يدوي)

# كشف الحسابات الجداد بزاف (كثير ما كتكون هي لي فراود) — كيبعث غير تنبيه،
# ما كيديرش عقوبة تلقائية إلا كان Raid Mode مفعل
RAID_MIN_ACCOUNT_AGE_HOURS = 24

# ═══════ Leveling System (XP + Levels + رولات أوتوماتيكية) ═══════
LEVELING_ENABLED = True
XP_MIN_PER_MESSAGE = 10
XP_MAX_PER_MESSAGE = 25
XP_COOLDOWN_SECONDS = 60   # ماخذيش XP مرة أخرى من نفس العضو قبل ما تعدي هاد المدة
LEVEL_UP_CHANNEL_ID = 1532872432778743978    # ← channel فين كيتبعث "مبروك وصلتي لـ Level X" (0 = نفس channel لي هضر فيه العضو)
LEVELS_INFO_CHANNEL_ID = 1532613980466446387  # ← channel فين غادي تبان رسالة شرح نظام الـ Leveling + لائحة كاع المستويات ورولاتهم

# ═══════ Leaderboard أوتوماتيكي (كيتحدث بروحو فـ channel معين) ═══════
LEADERBOARD_CHANNEL_ID = 1532613980466446387   # ← channel فين غادي تتبعث/تتحدث لائحة الشرف أوتوماتيكياً
LEADERBOARD_UPDATE_MINUTES = 15                 # ← كل شحال ديال الدقايق كيتحدث

# رولات أوتوماتيكية عند مستويات معينة: {level: role_id}
# العضو كيحتفظ بكل الرولات السابقة (تراكمية، ماشي بديل)
# ⚠️ بدل كل 0 برقم الـ Role ID الحقيقي ديالك (Server Settings → Roles → كليك يمين → Copy Role ID)
LEVEL_ROLES = {
    5: 1532874771287507135,
    10: 1532877605366268116,
    15: 1532877729052233988,
    20: 1532877833125232740,
    25: 1532877955414360336,
    30: 1532877995306651853,
    35: 1532878086893207653,
    40: 1532878137430380674,
    45: 1532878260428341390,
    50: 1532878348752261331,
    60: 1532878501278126251,
    70: 1532878632371097881,
    80: 1532878710745596064,
    90: 1532878803075076106,
    100: 1532878888986738869,
}

# ═══════ الترجمة التلقائية بالـ Reaction (علم الدولة 🇬🇧🇫🇷 على أي رسالة) ═══════
AUTO_TRANSLATE_ENABLED = True
# ⚠️ كل عضو (ماشي بوت) يقدر يستعملها فأي channel — البوت خاصو صلاحية "Add Reactions" و"Send Messages"
# زيد/بدل الأعلام اللي بغيتي هنا: emoji العلم → (الاسم بالعربية للعرض، الاسم بالانجليزية للـ AI)
FLAG_TO_LANGUAGE = {
    "🇬🇧": ("الإنجليزية", "English"),
    "🇺🇸": ("الإنجليزية", "English"),
    "🇫🇷": ("الفرنسية", "French"),
    "🇪🇸": ("الإسبانية", "Spanish"),
    "🇩🇪": ("الألمانية", "German"),
    "🇮🇹": ("الإيطالية", "Italian"),
    "🇵🇹": ("البرتغالية", "Portuguese"),
    "🇹🇷": ("التركية", "Turkish"),
    "🇷🇺": ("الروسية", "Russian"),
    "🇯🇵": ("اليابانية", "Japanese"),
    "🇰🇷": ("الكورية", "Korean"),
    "🇨🇳": ("الصينية", "Chinese"),
    "🇸🇦": ("العربية الفصحى", "Modern Standard Arabic"),
    "🇲🇦": ("الدارجة المغربية", "Moroccan Darija"),
}

# ═══════ Auto-React: البوت كيزيد الأعلام كـ reactions أوتوماتيك على كل رسالة ═══════
# (بدل ما العضو يكتب/يلقى العلم بيدو، البوت كيحطهم ليه جاهزين، وغير يكليكي على اللي بغا)
AUTO_REACT_TRANSLATE_ENABLED = False   # ← بدلها True باش تخدم
AUTO_REACT_FLAGS = ["🇬🇧", "🇫🇷", "🇪🇸"]  # ← الأعلام اللي غادي تتزاد أوتوماتيك (خاصهم يكونو موجودين فـ FLAG_TO_LANGUAGE فوق)
AUTO_REACT_CHANNEL_IDS = []   # ← خاوية [] = فكاع الـ channels. إلا بغيتي غير channels معينة، زيد IDs هنا مثلا [111, 222]

for _flag in AUTO_REACT_FLAGS:
    if _flag not in FLAG_TO_LANGUAGE:
        print(f"[CONFIG] ⚠️ AUTO_REACT_FLAGS فيها علم '{_flag}' ماكاينش فـ FLAG_TO_LANGUAGE — زيدو لهاديك اللائحة ولا حيدو من AUTO_REACT_FLAGS.")

# ═══════ نظام الصوت — Join to Create (روم صوتية مؤقتة) ═══════
JOIN_TO_CREATE_ENABLED = True
JOIN_TO_CREATE_CHANNEL_ID = 1533290892947882064   # ← ID ديال الـ voice channel "➕ دير روم" (العضو كيدخل ليه فيتخلق ليه روم خاص بيه)
TEMP_VC_CATEGORY_ID = 1533257707543461939          # ← ID ديال الـ Category فين غادي تتخلق الروومات المؤقتة (0 = نفس category ديال JOIN_TO_CREATE_CHANNEL_ID)
TEMP_VC_NAME_TEMPLATE = "🔊 روم ديال {name}"
TEMP_VC_DEFAULT_LIMIT = 0        # ← 0 = بلا حد أقصى للأعضاء

# ═══════ نظام الصوت — Voice XP (نقط XP على الوقت فالـ Voice) ═══════
VOICE_XP_ENABLED = True
VOICE_XP_PER_INTERVAL = 10        # ← شحال ديال XP كياخد العضو كل VOICE_XP_INTERVAL_MINUTES (غير كيهضر/كيتواجد فـ فويس عادي)
VOICE_XP_INTERVAL_MINUTES = 5
VOICE_XP_MIN_HUMANS_IN_CHANNEL = 2   # ← خاص يكونو على الأقل هاد العدد ديال البشر (ماشي بوتات) فنفس الروم باش ياخدو XP (كيمنع الفارمينغ وحدك)
VOICE_XP_COUNT_MUTED_DEAFENED = False  # ← False = العضو اللي self-mute/self-deafen كياخد نسبة AFK المخفضة (ماشي القيمة الكاملة). True = كياخد نفس XP بحال اللي حال المايك
VOICE_XP_EXCLUDE_CHANNEL_IDS = []   # ← زيد هنا IDs ديال أي voice channel ماباغيش يعطي حتى XP فيه (كيتحيد كامل، حتى XP ديال AFK)
STREAM_XP_PER_INTERVAL = 20   # ← شحال ديال XP كياخد العضو كل VOICE_XP_INTERVAL_MINUTES ملي كيدير Go Live (لايفستريم) — بالافتراض أكثر من الفويس العادي حيت المجهود أكبر (كيبان لكل الروم، ماشي غير كيتواجد)

# ═══════ نظام الصوت — XP ديال الـ AFK (درجات مخفضة) ═══════
# الفكرة: حتى اللي سد المايك ولا دار Deafen كياخد XP، ولكن أقل من اللي كيهضر.
# وباش نشجعو الناس يمشيو للروم ديال AFK بدل ما يبقاو ساكنين فالرومات النشيطة،
# الـ AFK فالروم الرسمية ديال AFK كياخد أكثر من الـ AFK فروم عادية.
#
# 📊 الترتيب من الأكثر للأقل:
#    🎥 لايفستريم (Go Live)          → STREAM_XP_PER_INTERVAL      (20)
#    🎤 مايك محلول / كيهضر          → VOICE_XP_PER_INTERVAL       (10)
#    💤 AFK فالروم الرسمية ديال AFK  → AFK_CHANNEL_XP_PER_INTERVAL  (4)
#    🔇 AFK (مايك مسدود) فروم عادية → AFK_MUTED_XP_PER_INTERVAL    (2)
AFK_XP_ENABLED = True
AFK_CHANNEL_XP_PER_INTERVAL = 4   # ← XP كل فترة للي مريح فالروم ديال AFK (guild.afk_channel ولا AFK_CHANNEL_IDS تحت)
AFK_MUTED_XP_PER_INTERVAL = 2     # ← XP كل فترة للي سد المايك/دار Deafen وهو فروم عادية
AFK_CHANNEL_IDS = []              # ← (اختياري) زيد هنا IDs ديال رومات AFK إضافية. البوت أصلا كيعرف الروم الرسمية ديال السيرفر (Server Settings → Overview → Inactive Channel)
AFK_XP_REQUIRE_MIN_HUMANS = False # ← False = XP ديال AFK كيتعطى حتى لو كان بوحدو (طبيعي، حيت الروم ديال AFK غالبا خاوية)
AFK_XP_DAILY_CAP = 150            # ← سقف يومي لـ XP ديال AFK لكل عضو (0 = بلا سقف). كيمنع اللي كيخلي البيسي شعال 24/24 يفرمي

# ⚠️ القيم اللي فوق (XP_MIN_PER_MESSAGE, XP_MAX_PER_MESSAGE, XP_COOLDOWN_SECONDS,
# VOICE_XP_PER_INTERVAL, VOICE_XP_INTERVAL_MINUTES, VOICE_XP_MIN_HUMANS_IN_CHANNEL,
# STREAM_XP_PER_INTERVAL) هي غير القيم الافتراضية عند أول تشغيل. من بعد، تقدر تبدلهم
# مباشرة من ديسكورد بالأمر /xppanel (Admin) بلا ماتمس الكود ولا تعاود ريستارت البوت،
# والتبديلات كيتحفظو فـ xp_settings.json باش يبقاو حتى بعد ريستارت.

# ═══════ درجات العقوبة حسب عدد التحذيرات (سهل التعديل) ═══════
# كل عضو كيبدا بلا تحذيرات. كل تحذير (Auto-Mod ولا /warn يدوي) كيزيد
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
# ═══════ ملاحظة: command_prefix باقي محطوط تقنياً (discord.py كيطلبو)، ولكن
# ماعادش كيتستعمل — bot.process_commands() تنيح فـ on_message، فـ "!" ماعادش
# كيخدم. كاع الأوامر دابا Slash (/) بوحدها. ═══════
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100
learned_knowledge = []
warns_db = {}
spam_tracker = {}
mute_tasks = {}
_slash_synced = False  # باش ما نعاودوش sync ديال Slash Commands كل مرة on_ready يتلاق (reconnect)

# ═══════ Anti-Raid: تتبع الأعضاء الجداد + حالة الـ Lockdown ═══════
recent_joins = defaultdict(list)  # {guild_id: [datetime, datetime, ...]}
raid_state = {}                   # {guild_id: {"active": bool, "previous_verification_level": ..., "revert_task": Task}}

# ═══════════════════════════════════════════════════════
# ║   نظام Case ID (سجل كامل لكل عقوبة برقم فريد)          ║
# ═══════════════════════════════════════════════════════
# كل عقوبة (warn/mute/kick/ban/unmute/unban/unwarn) كتاخد رقم Case فريد
# ومتزايد (#1, #2, #3...)، وكتتسجل فـ cases.json باش تبقى محفوظة حتى
# بعد ريستارت البوت. استعمل /history @user باش تشوف كاع الحالات ديال
# عضو معين، ولا /case <رقم> باش تشوف حالة معينة بالتفصيل.
CASES_FILE = os.path.join(DATA_DIR, "cases.json")
cases_db = {"next_id": 1, "cases": {}}  # cases: {"1": {...}, "2": {...}}


def load_cases():
    global cases_db
    try:
        with open(CASES_FILE, "r", encoding="utf-8") as f:
            cases_db = json.load(f)
        print(f"[CASES] تحمل {len(cases_db.get('cases', {}))} حالة محفوظة (التالية: #{cases_db.get('next_id', 1)})")
    except FileNotFoundError:
        print("[CASES] ماكاينش حالات سابقة، غادي نبداو من Case #1")
    except Exception as e:
        print(f"[CASES] خطأ فـ التحميل: {e}")


def save_cases():
    try:
        with open(CASES_FILE, "w", encoding="utf-8") as f:
            json.dump(cases_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[CASES] خطأ فـ الحفظ: {e}")


load_cases()

# ═══════════════════════════════════════════════════════
# ║   نظام Tickets (channels خاصة لكل مشكل/استفسار)         ║
# ═══════════════════════════════════════════════════════
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
tickets_db = {"next_id": 1, "open": {}}  # open: {channel_id (str): {id, opener_id, opened_at, claimed_by}}


def load_tickets():
    global tickets_db
    try:
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            tickets_db = json.load(f)
        print(f"[TICKETS] تحمل {len(tickets_db.get('open', {}))} ticket مفتوح")
    except FileNotFoundError:
        print("[TICKETS] ماكاينش tickets سابقين، غادي نبداو من Ticket #1")
    except Exception as e:
        print(f"[TICKETS] خطأ فـ التحميل: {e}")


def save_tickets():
    try:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(tickets_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[TICKETS] خطأ فـ الحفظ: {e}")


def get_open_ticket_for_user(user_id: int):
    """كترجع (channel_id, record) ديال ticket مفتوح ديال هاد العضو، وإلا None"""
    for channel_id, record in tickets_db.get("open", {}).items():
        if record.get("opener_id") == user_id:
            return channel_id, record
    return None, None


load_tickets()

# ═══════════════════════════════════════════════════════
# ║   نظام Applications (طلبات الانضمام لفريق الإدارة)      ║
# ═══════════════════════════════════════════════════════
APPLICATIONS_FILE = os.path.join(DATA_DIR, "applications.json")
# applications: {"1": {applicant_id, answers, status, review_message_id, review_channel_id, submitted_at, decided_by, decided_at}}
# last_rejected: {user_id (str): "YYYY-MM-DD HH:MM:SS"} — باش نحسبو الـ cooldown
applications_db = {"next_id": 1, "applications": {}, "last_rejected": {}}


def load_applications():
    global applications_db
    try:
        with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
            applications_db = json.load(f)
        applications_db.setdefault("last_rejected", {})
        print(f"[APPLICATIONS] تحمل {len(applications_db.get('applications', {}))} طلب محفوظ")
    except FileNotFoundError:
        print("[APPLICATIONS] ماكاينش طلبات سابقة، غادي نبداو من Application #1")
    except Exception as e:
        print(f"[APPLICATIONS] خطأ فـ التحميل: {e}")


def save_applications():
    try:
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(applications_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[APPLICATIONS] خطأ فـ الحفظ: {e}")


def find_application_by_message_id(message_id: int):
    """كترجع (app_id, record) ديال الطلب اللي رسالة المراجعة ديالو هي هاد الـ message_id، وإلا (None, None)"""
    for app_id, record in applications_db.get("applications", {}).items():
        if record.get("review_message_id") == message_id:
            return app_id, record
    return None, None


def get_pending_application_for_user(user_id: int):
    for app_id, record in applications_db.get("applications", {}).items():
        if record.get("applicant_id") == user_id and record.get("status") == "pending":
            return app_id, record
    return None, None


def application_cooldown_remaining(user_id: int) -> Optional[timedelta]:
    """كترجع الوقت الباقي فالـ cooldown (Timedelta) إلا العضو مازال ما يقدرش يعاود يقدم، وإلا None"""
    last = applications_db.get("last_rejected", {}).get(str(user_id))
    if not last:
        return None
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except Exception:
        return None
    remaining = timedelta(hours=APPLICATIONS_COOLDOWN_HOURS) - elapsed
    return remaining if remaining.total_seconds() > 0 else None


load_applications()

# ═══════════════════════════════════════════════════════
# ║              نظام Suggestions (اقتراحات الأعضاء)        ║
# ═══════════════════════════════════════════════════════
SUGGESTIONS_FILE = os.path.join(DATA_DIR, "suggestions.json")
# suggestions: {"1": {author_id, text, status, message_id, channel_id, created_at, decided_by, decided_at, reason}}
suggestions_db = {"next_id": 1, "suggestions": {}}


def load_suggestions():
    global suggestions_db
    try:
        with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
            suggestions_db = json.load(f)
        print(f"[SUGGESTIONS] تحمل {len(suggestions_db.get('suggestions', {}))} اقتراح محفوظ")
    except FileNotFoundError:
        print("[SUGGESTIONS] ماكاينش اقتراحات سابقة، غادي نبداو من Suggestion #1")
    except Exception as e:
        print(f"[SUGGESTIONS] خطأ فـ التحميل: {e}")


def save_suggestions():
    try:
        with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(suggestions_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[SUGGESTIONS] خطأ فـ الحفظ: {e}")


def find_suggestion_by_message_id(message_id: int):
    for sug_id, record in suggestions_db.get("suggestions", {}).items():
        if record.get("message_id") == message_id:
            return sug_id, record
    return None, None


load_suggestions()

# ═══════════════════════════════════════════════════════
# ║        Phase 8 — نظام Birthdays (أعياد الميلاد)         ║
# ═══════════════════════════════════════════════════════
BIRTHDAYS_FILE = os.path.join(DATA_DIR, "birthdays.json")
# birthdays: {"<user_id>": {"day": int, "month": int, "last_announced_year": int|null}}
# role_holders: [user_id, ...] — العضاء اللي عندهم الرول ديال اليوم دابا، باش نحيدوه غدا
birthdays_db = {"birthdays": {}, "role_holders": []}


def load_birthdays():
    global birthdays_db
    try:
        with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
            birthdays_db = json.load(f)
        birthdays_db.setdefault("role_holders", [])
        print(f"[BIRTHDAYS] تحمل {len(birthdays_db.get('birthdays', {}))} عيد ميلاد محفوظ")
    except FileNotFoundError:
        print("[BIRTHDAYS] ماكاينش أعياد ميلاد محفوظين من قبل")
    except Exception as e:
        print(f"[BIRTHDAYS] خطأ فـ التحميل: {e}")


def save_birthdays():
    try:
        with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
            json.dump(birthdays_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[BIRTHDAYS] خطأ فـ الحفظ: {e}")


load_birthdays()

# ═══════════════════════════════════════════════════════
# ║   نظام Marry/Bestfriend (أزواج/أصدقاء) — 💌               ║
# ═══════════════════════════════════════════════════════
RELATIONSHIPS_FILE = os.path.join(DATA_DIR, "relationships.json")
# marriages/bestfriends: {"pair_key": {"user_a": id, "user_b": id, "since": "YYYY-MM-DD HH:MM:SS"}}
# pair_key = "min_id-max_id" باش يبقى فريد لكل زوج
relationships_db = {"marriages": {}, "bestfriends": {}}


def load_relationships():
    global relationships_db
    try:
        with open(RELATIONSHIPS_FILE, "r", encoding="utf-8") as f:
            relationships_db = json.load(f)
        relationships_db.setdefault("marriages", {})
        relationships_db.setdefault("bestfriends", {})
        print(f"[RELATIONSHIPS] تحمل {len(relationships_db['marriages'])} زواج و {len(relationships_db['bestfriends'])} صداقة")
    except FileNotFoundError:
        print("[RELATIONSHIPS] ماكاينش علاقات محفوظة من قبل")
    except Exception as e:
        print(f"[RELATIONSHIPS] خطأ فـ التحميل: {e}")
        relationships_db = {"marriages": {}, "bestfriends": {}}


def save_relationships():
    try:
        with open(RELATIONSHIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(relationships_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[RELATIONSHIPS] خطأ فـ الحفظ: {e}")


def _pair_key(user_id_1: int, user_id_2: int) -> str:
    a, b = sorted([user_id_1, user_id_2])
    return f"{a}-{b}"


def find_relationship(kind: str, user_id: int):
    """كترجع (pair_key, record) ديال أول علاقة كتلقاها للعضو (marriages ولا bestfriends)، وإلا (None, None).
    للـ marriages (علاقة وحدة بالضرورة) هادي كافية. للـ bestfriends خاصك find_all_relationships حيت ممكن يكون بزاف."""
    for key, record in relationships_db.get(kind, {}).items():
        if record.get("user_a") == user_id or record.get("user_b") == user_id:
            return key, record
    return None, None


def find_all_relationships(kind: str, user_id: int):
    """كترجع لائحة [(pair_key, record), ...] ديال كل العلاقات ديال العضو من نوع معين.
    مفيدة للـ bestfriends حيت عضو وحد يقدر يكون عندو بزاف ديال الأصدقاء المقربين فنفس الوقت."""
    result = []
    for key, record in relationships_db.get(kind, {}).items():
        if record.get("user_a") == user_id or record.get("user_b") == user_id:
            result.append((key, record))
    return result


def has_relationship_with(kind: str, user_id_1: int, user_id_2: int) -> bool:
    """واش كاينة ديجا علاقة (من هاد النوع) بالضبط بين هاد الجوج ديال الناس."""
    return _pair_key(user_id_1, user_id_2) in relationships_db.get(kind, {})


def get_partner_id(record: dict, user_id: int) -> int:
    return record["user_b"] if record["user_a"] == user_id else record["user_a"]


def create_relationship(kind: str, user_id_1: int, user_id_2: int) -> str:
    key = _pair_key(user_id_1, user_id_2)
    relationships_db.setdefault(kind, {})[key] = {
        "user_a": user_id_1, "user_b": user_id_2,
        "since": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "personal_role_ids": {}  # {"<user_id>": role_id} — الرول الشخصي بسمية الشريك، لكل واحد فيهم
    }
    save_relationships()
    return key


def set_relationship_personal_roles(kind: str, pair_key: str, role_id_for_user: dict):
    """كتسجل الـ IDs ديال الرولات الشخصية (بسمية الشريك) باش نقدرو نحيدوهم/نمسحوهم منين تنتهي العلاقة.
    role_id_for_user: {user_id (int): role_id (int)}"""
    record = relationships_db.get(kind, {}).get(pair_key)
    if not record:
        return
    record.setdefault("personal_role_ids", {})
    for uid, rid in role_id_for_user.items():
        record["personal_role_ids"][str(uid)] = rid
    save_relationships()


def end_relationship(kind: str, pair_key: str):
    relationships_db.get(kind, {}).pop(pair_key, None)
    save_relationships()


def format_duration_since(since_str: str) -> str:
    try:
        since_dt = datetime.strptime(since_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"
    delta = datetime.now() - since_dt
    days = delta.days
    if days < 1:
        hours = delta.seconds // 3600
        return f"{hours} ساعة" if hours > 0 else "دقايق قلال"
    if days < 30:
        return f"{days} يوم"
    if days < 365:
        months = days // 30
        return f"{months} شهر"
    years = days // 365
    remaining_months = (days % 365) // 30
    return f"{years} عام" + (f" و{remaining_months} شهر" if remaining_months else "")


load_relationships()

# ═══════ حساب البرج من التاريخ (يوم/شهر) ═══════
ZODIAC_SIGNS = [
    # (key, الاسم بالعربية, emoji, (شهر البداية, يوم البداية), (شهر النهاية, يوم النهاية))
    ("capricorn", "الجدي", "♑", (12, 22), (1, 19)),
    ("aquarius", "الدلو", "♒", (1, 20), (2, 18)),
    ("pisces", "الحوت", "♓", (2, 19), (3, 20)),
    ("aries", "الحمل", "♈", (3, 21), (4, 19)),
    ("taurus", "الثور", "♉", (4, 20), (5, 20)),
    ("gemini", "الجوزاء", "♊", (5, 21), (6, 20)),
    ("cancer", "السرطان", "♋", (6, 21), (7, 22)),
    ("leo", "الأسد", "♌", (7, 23), (8, 22)),
    ("virgo", "العذراء", "♍", (8, 23), (9, 22)),
    ("libra", "الميزان", "♎", (9, 23), (10, 22)),
    ("scorpio", "العقرب", "♏", (10, 23), (11, 21)),
    ("sagittarius", "القوس", "♐", (11, 22), (12, 21)),
]


def get_zodiac_sign(day: int, month: int):
    """كترجع (key, الاسم بالعربية, emoji) ديال البرج حسب اليوم والشهر، وإلا (None, None, None)"""
    for key, label, emoji, start, end in ZODIAC_SIGNS:
        start_month, start_day = start
        end_month, end_day = end
        if start_month == end_month:
            if month == start_month and start_day <= day <= end_day:
                return key, label, emoji
        else:
            # البرج كيمتد عبر شهرين (بحال الجدي: 22 دجنبر - 19 يناير)
            if (month == start_month and day >= start_day) or (month == end_month and day <= end_day):
                return key, label, emoji
    return None, None, None


async def sync_zodiac_role(member: discord.Member, zodiac_key: Optional[str]):
    """كتبدل رول البرج ديال العضو: كتحيد أي رول برج قديم عندو (إلا بدل التاريخ)
    وكتعطيه الرول الجديد المطابق للبرج ديالو."""
    all_zodiac_role_ids = {rid for rid in ZODIAC_ROLE_IDS.values() if rid}
    if not all_zodiac_role_ids:
        return
    new_role_id = ZODIAC_ROLE_IDS.get(zodiac_key) if zodiac_key else None
    to_remove = [r for r in member.roles if r.id in all_zodiac_role_ids and r.id != new_role_id]
    try:
        if to_remove:
            await member.remove_roles(*to_remove, reason="تبديل رول البرج")
        if new_role_id:
            new_role = member.guild.get_role(new_role_id)
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role, reason="رول البرج حسب عيد الميلاد")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# ║              Leveling System (XP + Levels)               ║
# ═══════════════════════════════════════════════════════
LEVELS_FILE = os.path.join(DATA_DIR, "levels.json")
levels_db = {}  # {guild_id (str): {user_id (str): {"xp": int, "level": int}}}
xp_cooldowns = {}  # {(guild_id, user_id): datetime آخر مرة خذا XP}


def load_levels():
    global levels_db
    try:
        with open(LEVELS_FILE, "r", encoding="utf-8") as f:
            levels_db = json.load(f)
        print(f"[LEVELS] تحمل بيانات {sum(len(v) for v in levels_db.values())} عضو")
    except FileNotFoundError:
        print("[LEVELS] ماكاينش بيانات سابقة، غادي نبداو من الصفر")
    except Exception as e:
        print(f"[LEVELS] خطأ فـ التحميل: {e}")


def save_levels():
    try:
        with open(LEVELS_FILE, "w", encoding="utf-8") as f:
            json.dump(levels_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[LEVELS] خطأ فـ الحفظ: {e}")


TRIVIA_SCORES_FILE = os.path.join(DATA_DIR, "trivia_scores.json")
trivia_scores = {}  # {guild_id (str): {user_id (str): عدد الإجابات الصحيحة}}


def load_trivia_scores():
    global trivia_scores
    try:
        with open(TRIVIA_SCORES_FILE, "r", encoding="utf-8") as f:
            trivia_scores = json.load(f)
    except FileNotFoundError:
        trivia_scores = {}
    except Exception as e:
        print(f"[TRIVIA] خطأ فـ تحميل النقط: {e}")
        trivia_scores = {}


def save_trivia_scores():
    try:
        with open(TRIVIA_SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(trivia_scores, f, ensure_ascii=False)
    except Exception as e:
        print(f"[TRIVIA] خطأ فـ حفظ النقط: {e}")


def bump_trivia_score(guild_id: int, user_id: int):
    g = trivia_scores.setdefault(str(guild_id), {})
    g[str(user_id)] = g.get(str(user_id), 0) + 1
    save_trivia_scores()


load_trivia_scores()


# ═══════ مجموع XP + أحسن سلسلة ديال كل عضو فـ Trivia (تاريخ دائم) ═══════
# باش ملي العضو يخسر نقدرو نوريوه: «جمعتي X XP من هاد الجولة، ومجموعك من اللعبة كامل هو Y»
TRIVIA_XP_FILE = os.path.join(DATA_DIR, "trivia_xp_totals.json")
trivia_xp_totals = {}  # {guild_id (str): {user_id (str): {"xp": int, "games": int, "best_streak": int}}}


def load_trivia_xp_totals():
    global trivia_xp_totals
    try:
        with open(TRIVIA_XP_FILE, "r", encoding="utf-8") as f:
            trivia_xp_totals = json.load(f)
    except FileNotFoundError:
        trivia_xp_totals = {}
    except Exception as e:
        print(f"[TRIVIA] خطأ فـ تحميل مجموع XP: {e}")
        trivia_xp_totals = {}


def save_trivia_xp_totals():
    try:
        with open(TRIVIA_XP_FILE, "w", encoding="utf-8") as f:
            json.dump(trivia_xp_totals, f, ensure_ascii=False)
    except Exception as e:
        print(f"[TRIVIA] خطأ فـ حفظ مجموع XP: {e}")


def get_trivia_stats(guild_id: int, user_id: int) -> dict:
    g = trivia_xp_totals.setdefault(str(guild_id), {})
    entry = g.setdefault(str(user_id), {})
    entry.setdefault("xp", 0)
    entry.setdefault("games", 0)
    entry.setdefault("best_streak", 0)
    return entry


def add_trivia_xp(guild_id: int, user_id: int, amount: int):
    """كيزيد XP اللي ربح العضو دابا للمجموع الدائم ديالو."""
    entry = get_trivia_stats(guild_id, user_id)
    entry["xp"] += amount
    save_trivia_xp_totals()


def finish_trivia_game(guild_id: int, user_id: int, streak: int) -> dict:
    """كيتسجل ملي تسالا جولة: كيزيد عداد الجولات وكيحدث أحسن سلسلة.
    كيرجع الإحصائيات الكاملة ديال العضو + واش هادي رقم قياسي جديد."""
    entry = get_trivia_stats(guild_id, user_id)
    entry["games"] += 1
    is_record = streak > entry["best_streak"]
    if is_record:
        entry["best_streak"] = streak
    save_trivia_xp_totals()
    return {**entry, "is_record": is_record}


load_trivia_xp_totals()


def xp_needed_for_level(level: int) -> int:
    """صيغة كتخلي كل مستوى محتاج XP أكثر من لي قبلو (بحال MEE6 تقريباً).
    من بعد Level 30، كتزاد صعوبة إضافية (نمو أسرع) باش المستويات العالية
    يبقاو يستاهلو أكثر وقت/جهد. كتضرب فـ level_xp_multiplier (قابلة للتعديل
    من /xppanel) — 0.5 يهبط الكل بالنص، 2.0 يضاعف، إلخ."""
    base = 5 * (level ** 2) + 50 * level + 100
    if level >= 30:
        extra_levels = level - 30
        base += 15 * (extra_levels ** 2) + 200 * extra_levels
    multiplier = xp_settings.get("level_xp_multiplier", 1.0) if "xp_settings" in globals() else 1.0
    return max(1, round(base * multiplier))


def get_user_level_data(guild_id: int, user_id: int) -> dict:
    g = levels_db.setdefault(str(guild_id), {})
    return g.setdefault(str(user_id), {"xp": 0, "level": 0})


def total_xp_earned(data: dict) -> int:
    """XP الكلية اللي ربحها العضو من بداياتو (مجموع كل المستويات السابقة + التقدم الحالي)"""
    total = data["xp"]
    for lvl in range(data["level"]):
        total += xp_needed_for_level(lvl)
    return total


def get_target_level_role(new_level: int):
    """كترجع (target_level, role_id) ديال أعلى threshold فـ LEVEL_ROLES اللي
    new_level وصل ليه ولا فاقو، وإلا (None, None) إلا مازال ماوصلش لحتى واحد."""
    eligible = [lvl for lvl in LEVEL_ROLES if lvl <= new_level]
    if not eligible:
        return None, None
    target_level = max(eligible)
    return target_level, LEVEL_ROLES[target_level]


async def sync_level_roles(member: discord.Member, guild: discord.Guild, new_level: int):
    """كيخلي عند العضو غير الرول اللي كيمثل أعلى level وصل ليه (من LEVEL_ROLES)،
    وكيحيد أي رولات ديال levels تحتانية/فوقانية كانت عندو من قبل — يعني رول
    واحد بوحدو ديال الـ level فأي وقت (سواء صعد ولا هبط المستوى). كترجع
    (roles_added, roles_removed) — لائحتين ديال mentions."""
    all_level_role_ids = {rid for rid in LEVEL_ROLES.values()}
    _, target_role_id = get_target_level_role(new_level)

    roles_added, roles_removed = [], []

    to_remove = [r for r in member.roles if r.id in all_level_role_ids and r.id != target_role_id]
    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason=f"Level Role Sync — دابا Level {new_level}")
            roles_removed = [r.mention for r in to_remove]
        except (discord.Forbidden, discord.HTTPException):
            pass

    if target_role_id:
        target_role = guild.get_role(target_role_id)
        if target_role and target_role not in member.roles:
            try:
                await member.add_roles(target_role, reason=f"Level Role Sync — دابا Level {new_level}")
                roles_added.append(target_role.mention)
            except (discord.Forbidden, discord.HTTPException):
                pass

    return roles_added, roles_removed


async def grant_xp_and_announce(member: discord.Member, guild: discord.Guild, amount: int,
                                 fallback_channel: Optional[discord.abc.Messageable] = None,
                                 source: str = "unknown"):
    """كتزيد XP للعضو (من رسالة ولا من Voice ولا Trivia)، كتشوف واش صعد لمستوى جديد،
    كتعطي الرولات ديال LEVEL_ROLES، وكتبعث رسالة "مبروك" إلا صعد.
    نفس المنطق اللي كان مستعمل غير مع رسائل الشات، دابا مشترك بين النصين والـ Voice.
    'source' كيتسجل فـ xp_log.jsonl باش نقدرو نتبعو منين جاي كل XP (audit)."""
    if not bot_settings['leveling_enabled'] or not guild:
        return

    data = get_user_level_data(guild.id, member.id)
    data["xp"] += amount

    leveled_up = False
    while data["xp"] >= xp_needed_for_level(data["level"]):
        data["xp"] -= xp_needed_for_level(data["level"])
        data["level"] += 1
        leveled_up = True

    save_levels()

    channel_id = getattr(fallback_channel, "id", None) if fallback_channel else None
    log_xp_event(guild.id, member.id, source, amount, channel_id=channel_id,
                 new_total_level=data["level"])
    try:
        await check_xp_anomaly(member, guild, source)
    except Exception as e:
        print(f"[XP-AUDIT] خطأ فـ check_xp_anomaly: {e}")

    if not leveled_up:
        return

    new_level = data["level"]
    roles_added, _ = await sync_level_roles(member, guild, new_level)

    target_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID) if LEVEL_UP_CHANNEL_ID else fallback_channel
    if target_channel:
        desc = f"🎉 {member.mention} وصل/ات لـ **Level {new_level}**!"
        if roles_added:
            desc += f"\n🎁 حصل/ات على: {', '.join(roles_added)}"
        embed = discord.Embed(description=desc, color=discord.Color.gold(), timestamp=datetime.now())
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await target_channel.send(embed=embed)
        except Exception as e:
            print(f"[LEVELS] خطأ فـ بعث رسالة Level Up: {e}")


load_levels()

# ═══════════════════════════════════════════════════════
# ║   XP Settings — الإعدادات القابلة للتعديل من /xppanel   ║
# ═══════════════════════════════════════════════════════
# هاد الـ dict هو المصدر الحقيقي (source of truth) لكل قيم XP فالبوت وهو خدام.
# كيتبدا بالقيم الافتراضية من فوق، ومن بعد كيتقرا فوقهم أي تبديل محفوظ فـ
# xp_settings.json (يعني إلا بدلتي شي حاجة من /xppanel قبل، غادي تتحافظ حتى
# بعد ريستارت البوت). ماكاينش داعي تبدل الكود، كامل التحكم من ديسكورد.
XP_SETTINGS_FILE = os.path.join(DATA_DIR, "xp_settings.json")
xp_settings = {
    "chat_min": XP_MIN_PER_MESSAGE,
    "chat_max": XP_MAX_PER_MESSAGE,
    "chat_cooldown": XP_COOLDOWN_SECONDS,
    "voice_per_interval": VOICE_XP_PER_INTERVAL,
    "voice_interval_minutes": VOICE_XP_INTERVAL_MINUTES,
    "voice_min_humans": VOICE_XP_MIN_HUMANS_IN_CHANNEL,
    "stream_per_interval": STREAM_XP_PER_INTERVAL,
    "afk_channel_per_interval": AFK_CHANNEL_XP_PER_INTERVAL,
    "afk_muted_per_interval": AFK_MUTED_XP_PER_INTERVAL,
    "afk_daily_cap": AFK_XP_DAILY_CAP,
    "trivia_easy": TRIVIA_XP_BY_DIFFICULTY["easy"],
    "trivia_medium": TRIVIA_XP_BY_DIFFICULTY["medium"],
    "trivia_hard": TRIVIA_XP_BY_DIFFICULTY["hard"],
    "trivia_single": TRIVIA_XP_REWARD,
    "level_xp_multiplier": 1.0,   # ← 1.0 = عادي، 0.5 = يهبط المستويات بنص الـ XP المطلوب، 2.0 = يضاعفو
}


def get_trivia_xp(difficulty: str) -> int:
    """شحال XP كياخد جواب صحيح فبانل Trivia حسب الصعوبة — كتقرا من xp_settings
    (قابلة للتعديل من /xppanel)، مع fallback للقيم الافتراضية."""
    key = f"trivia_{difficulty}"
    return int(xp_settings.get(key, TRIVIA_XP_BY_DIFFICULTY.get(difficulty, TRIVIA_XP_BY_DIFFICULTY["easy"])))


def get_trivia_single_xp() -> int:
    """شحال XP كياخد جواب صحيح فسؤال Trivia الفردي (/trivia) — قابلة للتعديل من /xppanel."""
    return int(xp_settings.get("trivia_single", TRIVIA_XP_REWARD))


def load_xp_settings():
    global xp_settings
    try:
        with open(XP_SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        xp_settings.update({k: v for k, v in saved.items() if k in xp_settings})
        print(f"[XP-SETTINGS] تحملات الإعدادات المحفوظة: {xp_settings}")
    except FileNotFoundError:
        print("[XP-SETTINGS] ماكاينش إعدادات محفوظة، غادي نستعملو القيم الافتراضية من الكود.")
    except Exception as e:
        print(f"[XP-SETTINGS] خطأ فـ التحميل: {e}")


def save_xp_settings():
    try:
        with open(XP_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(xp_settings, f, ensure_ascii=False)
    except Exception as e:
        print(f"[XP-SETTINGS] خطأ فـ الحفظ: {e}")


load_xp_settings()

# ═══════════════════════════════════════════════════════
# ║   عداد يومي لـ XP ديال AFK (باش السقف اليومي يخدم)     ║
# ═══════════════════════════════════════════════════════
# كيتصيفط أوتوماتيكيا كل نهار جديد (حسب UTC). كيتحفظ فـ الديسك باش السقف
# يبقى محترم حتى إلا تعاود ريستارت البوت وسط النهار.
AFK_XP_DAILY_FILE = os.path.join(DATA_DIR, "afk_xp_daily.json")
afk_xp_daily = {"date": "", "users": {}}


def load_afk_xp_daily():
    global afk_xp_daily
    try:
        with open(AFK_XP_DAILY_FILE, "r", encoding="utf-8") as f:
            afk_xp_daily = json.load(f)
    except FileNotFoundError:
        afk_xp_daily = {"date": "", "users": {}}
    except Exception as e:
        print(f"[AFK-XP] خطأ فـ التحميل: {e}")
        afk_xp_daily = {"date": "", "users": {}}


def save_afk_xp_daily():
    try:
        with open(AFK_XP_DAILY_FILE, "w", encoding="utf-8") as f:
            json.dump(afk_xp_daily, f, ensure_ascii=False)
    except Exception as e:
        print(f"[AFK-XP] خطأ فـ الحفظ: {e}")


def _afk_reset_if_new_day():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if afk_xp_daily.get("date") != today:
        afk_xp_daily["date"] = today
        afk_xp_daily["users"] = {}
        save_afk_xp_daily()


def afk_xp_used_today(guild_id: int, user_id: int) -> int:
    _afk_reset_if_new_day()
    return int(afk_xp_daily["users"].get(f"{guild_id}:{user_id}", 0))


def afk_xp_allowed(guild_id: int, user_id: int, wanted: int) -> int:
    """كيرجع شحال من XP مسموح لهاد العضو ياخد دابا (كيحترم السقف اليومي).
    0 = وصل للسقف ديال النهار."""
    cap = int(xp_settings.get("afk_daily_cap", 0) or 0)
    if cap <= 0:
        return wanted
    used = afk_xp_used_today(guild_id, user_id)
    return max(0, min(wanted, cap - used))


def bump_afk_xp_used(guild_id: int, user_id: int, amount: int):
    _afk_reset_if_new_day()
    key = f"{guild_id}:{user_id}"
    afk_xp_daily["users"][key] = afk_xp_used_today(guild_id, user_id) + amount
    save_afk_xp_daily()


load_afk_xp_daily()

# ═══════════════════════════════════════════════════════
# ║   XP Audit Log — سجل دائم لكل XP event (باش نكشفو الغش)   ║
# ═══════════════════════════════════════════════════════
# كل مرة كيتعطى XP (شات/فويس/trivia/afk) كيتسجل سطر JSON فهاد الملف.
# ماكيتحيدش شي حاجة قديمة — فقط كيزاد. تقدر تفتحو بأي text editor
# ولا تقراه بـ /xpaudit فديسكورد.
XP_LOG_FILE = os.path.join(DATA_DIR, "xp_log.jsonl")

# تتبع فالذاكرة (ماشي محفوظ فالديسك) باش نكتشفو سرعة مشبوهة فـ الوقت الحقيقي.
# كل مفتاح (guild_id, user_id) → لائحة ديال الأوقات (datetime) ديال آخر XP events.
xp_event_times: dict = defaultdict(list)
# آخر مرة تبعث فيها تنبيه لهاد العضو، باش ما نبعتوش تنبيه على كل رسالة زايدة.
xp_alert_cooldowns: dict = {}

# ═══ إعدادات الكشف عن السرعة المشبوهة (بدلهم كيفما بغيتي) ═══
XP_ANOMALY_WINDOW_MINUTES = 15   # ← النافذة الزمنية اللي كنشوفو فيها عدد الـ events
XP_ANOMALY_THRESHOLD = 12        # ← إلا وصل عدد XP events لهاد الرقم فالنافذة ← تنبيه
XP_ANOMALY_ALERT_COOLDOWN_MINUTES = 60  # ← ما نبعتوش تنبيه ثاني لنفس العضو قبل ما تعدي هاد المدة


def log_xp_event(guild_id: int, user_id: int, source: str, amount: int,
                  channel_id: Optional[int] = None, new_total_level: Optional[int] = None):
    """كيسجل سطر واحد JSON فـ xp_log.jsonl لكل XP event. source مثلا:
    'chat', 'voice', 'afk_channel', 'afk_muted', 'stream', 'trivia', 'trivia_panel'."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "guild": guild_id,
        "user": user_id,
        "source": source,
        "amount": amount,
        "channel": channel_id,
    }
    if new_total_level is not None:
        entry["level_after"] = new_total_level
    try:
        with open(XP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[XP-AUDIT] خطأ فـ تسجيل XP event: {e}")


async def check_xp_anomaly(member: discord.Member, guild: discord.Guild, source: str):
    """كيشوف واش هاد العضو كيربح XP بسرعة مشبوهة، وإلا كان كيبعث تنبيه لـ MOD_LOGS
    (بلا ما يعاقبو حتى واحد أوتوماتيكيا — غير كيعلم الإدارة باش تشيك بعينها)."""
    key = (guild.id, member.id)
    now = datetime.now()
    window = timedelta(minutes=XP_ANOMALY_WINDOW_MINUTES)

    times = [t for t in xp_event_times[key] if now - t < window]
    times.append(now)
    xp_event_times[key] = times

    if len(times) < XP_ANOMALY_THRESHOLD:
        return

    last_alert = xp_alert_cooldowns.get(key)
    if last_alert and (now - last_alert).total_seconds() < XP_ANOMALY_ALERT_COOLDOWN_MINUTES * 60:
        return
    xp_alert_cooldowns[key] = now

    await log_action(
        guild,
        "🚩 سرعة مشبوهة فـ كسب XP",
        f"**العضو:** {member.mention} (`{member.id}`)\n"
        f"**آخر مصدر:** `{source}`\n"
        f"**العدد:** {len(times)} XP events فـ آخر {XP_ANOMALY_WINDOW_MINUTES} دقيقة\n\n"
        f"ماشي بالضرورة غش — يمكن نشاط عادي مكثف. تقدر تشيك التفاصيل بـ `/xpaudit @{member.display_name}`.",
        discord.Color.orange()
    )


def get_xp_audit_summary(guild_id: int, user_id: int, limit: int = 20) -> dict:
    """كيقرا xp_log.jsonl وكيرجع ملخص لعضو معين: التوزيع حسب المصدر + آخر events."""
    by_source = defaultdict(lambda: {"count": 0, "total": 0})
    events = []
    try:
        with open(XP_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("guild") != guild_id or e.get("user") != user_id:
                    continue
                src = e.get("source", "unknown")
                by_source[src]["count"] += 1
                by_source[src]["total"] += int(e.get("amount", 0))
                events.append(e)
    except FileNotFoundError:
        pass
    events.sort(key=lambda e: e.get("ts", ""))
    return {
        "by_source": dict(by_source),
        "total_events": len(events),
        "total_xp": sum(int(e.get("amount", 0)) for e in events),
        "recent": events[-limit:],
    }


# ═══════ Leaderboard أوتوماتيكي — تخزين ID ديال الرسالة (باش تتبدل ماشي تتبعث من جديد) ═══════
LEADERBOARD_MESSAGE_FILE = os.path.join(DATA_DIR, "leaderboard_message.json")
leaderboard_message_ids = {}  # {guild_id (str): message_id}


def load_leaderboard_message_ids():
    global leaderboard_message_ids
    try:
        with open(LEADERBOARD_MESSAGE_FILE, "r", encoding="utf-8") as f:
            leaderboard_message_ids = json.load(f)
        print(f"[LEADERBOARD] تحمل {len(leaderboard_message_ids)} رسالة leaderboard محفوظة")
    except FileNotFoundError:
        print("[LEADERBOARD] ماكاينش رسالة leaderboard سابقة، غادي نبعثو وحدة جديدة")
    except Exception as e:
        print(f"[LEADERBOARD] خطأ فـ التحميل: {e}")


def save_leaderboard_message_ids():
    try:
        with open(LEADERBOARD_MESSAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(leaderboard_message_ids, f, ensure_ascii=False)
    except Exception as e:
        print(f"[LEADERBOARD] خطأ فـ الحفظ: {e}")


load_leaderboard_message_ids()

# ═══════════════════════════════════════════════════════
# ║   Bot Settings — إعدادات عامة قابلة للتعديل من /botpanel   ║
# ═══════════════════════════════════════════════════════
# نفس المبدأ ديال xp_settings: dict وحدة هي المصدر الحقيقي (source of truth)
# لكل التبديلات والعتبات الكبيرة فالبوت، كتبدا بالقيم الافتراضية من فوق فالـ
# CONFIG، ومن بعد كتقرا فوقهم أي تبديل محفوظ فـ bot_settings.json. التحكم كامل
# من ديسكورد بالأمر /botpanel (Admin)، بلا ماتمس الكود ولا تعاود ريستارت البوت.
BOT_SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")
bot_settings = {
    "leveling_enabled": LEVELING_ENABLED,
    "voice_xp_enabled": VOICE_XP_ENABLED,
    "join_to_create_enabled": JOIN_TO_CREATE_ENABLED,
    "welcome_card_enabled": WELCOME_CARD_ENABLED,
    "auto_translate_enabled": AUTO_TRANSLATE_ENABLED,
    "auto_react_enabled": AUTO_REACT_TRANSLATE_ENABLED,
    "auto_info_news": AUTO_INFO_NEWS_ENABLED,
    "auto_info_games": AUTO_INFO_GAMES_ENABLED,
    "auto_info_movies": AUTO_INFO_MOVIES_ENABLED,
    "auto_info_anime": AUTO_INFO_ANIME_ENABLED,
    "auto_info_music": AUTO_INFO_MUSIC_ENABLED,
    "anti_raid_enabled": ANTI_RAID_ENABLED,
    "raid_join_threshold": RAID_JOIN_THRESHOLD,
    "raid_join_interval_seconds": RAID_JOIN_INTERVAL_SECONDS,
    "raid_action": RAID_ACTION,
    "raid_lockdown_duration_minutes": RAID_LOCKDOWN_DURATION_MINUTES,
    "mute_after_warns": MUTE_AFTER_WARNS,
    "mute_duration_minutes": MUTE_DURATION_MINUTES,
    "kick_after_warns": KICK_AFTER_WARNS,
    "ban_after_warns": BAN_AFTER_WARNS,
}


def load_bot_settings():
    global bot_settings
    try:
        with open(BOT_SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        bot_settings.update({k: v for k, v in saved.items() if k in bot_settings})
        print(f"[BOT-SETTINGS] تحملات الإعدادات المحفوظة: {bot_settings}")
    except FileNotFoundError:
        print("[BOT-SETTINGS] ماكاينش إعدادات محفوظة، غادي نستعملو القيم الافتراضية من الكود.")
    except Exception as e:
        print(f"[BOT-SETTINGS] خطأ فـ التحميل: {e}")


def save_bot_settings():
    try:
        with open(BOT_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(bot_settings, f, ensure_ascii=False)
    except Exception as e:
        print(f"[BOT-SETTINGS] خطأ فـ الحفظ: {e}")


load_bot_settings()

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

ADMIN_LIST_MESSAGE_FILE = os.path.join(DATA_DIR, "admin_list_message.json")
admin_list_message_ids = {}  # {guild_id (str): message_id}


def load_admin_list_message_ids():
    """يقرا ID ديال رسالة لائحة الإدارة المحفوظة، باش يبدلها بدل ما يبعث وحدة جديدة كل مرة"""
    global admin_list_message_ids
    try:
        with open(ADMIN_LIST_MESSAGE_FILE, "r", encoding="utf-8") as f:
            admin_list_message_ids = json.load(f)
        print(f"[ADMIN_LIST] تحمل {len(admin_list_message_ids)} رسالة لائحة محفوظة")
    except FileNotFoundError:
        print("[ADMIN_LIST] ماكاينش رسالة لائحة سابقة، غادي نبعثو وحدة جديدة")
    except Exception as e:
        print(f"[ADMIN_LIST] خطأ فـ التحميل: {e}")


def save_admin_list_message_ids():
    try:
        with open(ADMIN_LIST_MESSAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(admin_list_message_ids, f, ensure_ascii=False)
    except Exception as e:
        print(f"[ADMIN_LIST] خطأ فـ الحفظ: {e}")


load_admin_list_message_ids()


# ═══════════════════════════════════════════════════════
# ║                  نظام التذكيرات (Reminders)             ║
# ═══════════════════════════════════════════════════════
# كل واحد يقدر يصاوب تذكير لراسو بـ /remind <وقت> <رسالة>
# مثال: /remind 10m اشرب الما  /  /remind 2h30m اجتماع  /  /remind 1d تذكير
# البوت كيحفظ التذكيرات فـ ملف JSON باش ما تضيعش حتى ملي يعاود ريستارت.
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
reminders = []  # [{id, user_id, channel_id, guild_id, message, remind_at, created_at}]
next_reminder_id = 1


def load_reminders():
    """يقرا التذكيرات المحفوظة من ملف JSON (إلا كانت موجودة)"""
    global reminders, next_reminder_id
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            reminders = data
        if reminders:
            next_reminder_id = max(r.get("id", 0) for r in reminders) + 1
        print(f"[REMINDERS] تحمل {len(reminders)} تذكير محفوظ")
    except FileNotFoundError:
        print("[REMINDERS] ماكاينش تذكيرات سابقة، غادي نبداو من الصفر")
    except Exception as e:
        print(f"[REMINDERS] خطأ فـ التحميل: {e}")


def save_reminders():
    """يحفظ التذكيرات فـ ملف JSON"""
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False)
    except Exception as e:
        print(f"[REMINDERS] خطأ فـ الحفظ: {e}")


def parse_duration(text: str):
    """
    يحول صيغة بحال '10m' / '2h' / '1h30m' / '1d' / '45s' لـ timedelta.
    الوحدات: s=ثواني، m=دقايق، h=ساعات، d=أيام. كتقدر تخلط بينهم (بحال 1h30m).
    كيرجع None إلا الصيغة ماشي صحيحة.
    """
    cleaned = text.strip().lower().replace(" ", "")
    matches = re.findall(r'(\d+)(d|h|m|s)', cleaned)
    if not matches:
        return None
    # تأكد بلي الماتشات كيغطيو كامل النص (باش ما يقبلش حاجة غريبة زايدة)
    rebuilt = "".join(f"{num}{unit}" for num, unit in matches)
    if rebuilt != cleaned:
        return None
    units = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
    kwargs = {}
    for num, unit in matches:
        key = units[unit]
        kwargs[key] = kwargs.get(key, 0) + int(num)
    return timedelta(**kwargs)


def parse_time_input(text: str):
    """
    كيقبل 3 صيغ ديال الوقت (باش كل واحد يحدد الوقت اللي بغى بالضبط):
    1) مدة نسبية:      10m / 2h / 1h30m / 1d   → بعد X من دابا
    2) وقت اليوم:      21:00                    → اليوم إلا مازال ماجاش، وإلا غدا
    3) تاريخ + وقت:    2026-07-25-21:00         → نهار محدد بالضبط
    كيرجع datetime إلا الصيغة صحيحة، وإلا None.
    """
    text = text.strip()
    now = datetime.now()

    # 1) مدة نسبية
    delta = parse_duration(text)
    if delta is not None and delta.total_seconds() > 0:
        return now + delta

    # 2) وقت اليوم بالساعة:دقيقة (HH:MM)
    m = re.match(r'^(\d{1,2}):(\d{2})$', text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
        return None

    # 3) تاريخ كامل: YYYY-MM-DD-HH:MM
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(\d{1,2}):(\d{2})$', text)
    if m:
        year, month, day, hour, minute = map(int, m.groups())
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    return None


load_reminders()


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
    """يمسح الرسالة اللي فيها الأمر مباشرة (بحال /report) باش حتى حد
    ما يشوف الأمر ولا المحتوى ديالو فالقناة."""
    try:
        await ctx.message.delete()
    except Exception:
        pass


async def apply_warn_escalation(member: discord.Member, guild: discord.Guild, count: int,
                                 reason: str, channel=None) -> Optional[str]:
    """
    كتشوف شحال ديال التحذيرات وصلات لهاد العضو، وكتطبق العقوبة المناسبة
    حسب bot_settings['mute_after_warns'] / bot_settings['kick_after_warns'] / bot_settings['ban_after_warns'] (فالـ CONFIG).
    كتبدا من الأعلى (حظر) للأسفل (كتم) باش ما تطبقش عدة عقوبات فنفس الوقت.
    كترجع "ban" / "kick" / "mute" إلا تطبقات عقوبة، وإلا None.
    """
    if bot_settings['ban_after_warns'] and count >= bot_settings['ban_after_warns']:
        try:
            await member.ban(reason=f"{count} تحذيرات: {reason}")
            case_id = await log_case(
                guild, "🚫 حظر تلقائي (Auto-Ban)", "🚫", discord.Color.dark_red(),
                target=member, moderator=None,
                reason=reason, extra=f"عدد التحذيرات: {count}"
            )
            if channel:
                await channel.send(f"🚫 {member.mention} تم حظره تلقائياً ({count} تحذيرات) — Case #{case_id}!", delete_after=10)
            clear_warns(str(member.id))
            return "ban"
        except discord.Forbidden:
            return None

    if bot_settings['kick_after_warns'] and count >= bot_settings['kick_after_warns']:
        try:
            await member.kick(reason=f"{count} تحذيرات: {reason}")
            case_id = await log_case(
                guild, "👢 طرد تلقائي (Auto-Kick)", "👢", discord.Color.orange(),
                target=member, moderator=None,
                reason=reason, extra=f"عدد التحذيرات: {count}"
            )
            if channel:
                await channel.send(f"👢 {member.mention} تم طرده تلقائياً ({count} تحذيرات) — Case #{case_id}!", delete_after=10)
            clear_warns(str(member.id))
            return "kick"
        except discord.Forbidden:
            return None

    if bot_settings['mute_after_warns'] and count >= bot_settings['mute_after_warns']:
        muted_role = guild.get_role(MUTED_ROLE_ID)
        if muted_role and muted_role not in member.roles:
            try:
                await member.add_roles(muted_role)
                user_id = str(member.id)
                if user_id in mute_tasks and not mute_tasks[user_id].done():
                    mute_tasks[user_id].cancel()
                task = asyncio.create_task(auto_unmute(member, bot_settings['mute_duration_minutes'], guild))
                mute_tasks[user_id] = task
                case_id = await log_case(
                    guild, "🔇 كتم تلقائي (Auto-Mute)", "🔇", discord.Color.yellow(),
                    target=member, moderator=None,
                    reason=reason, extra=f"عدد التحذيرات: {count} | المدة: {bot_settings['mute_duration_minutes']} دقيقة"
                )
                if channel:
                    await channel.send(
                        f"🔇 {member.mention} تكتم تلقائياً ({count} تحذيرات، {bot_settings['mute_duration_minutes']} دقيقة) — Case #{case_id}!",
                        delete_after=10
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
        # ⚠️ مهم بزاف: DeepSeek V4 (ومعاه بزاف ديال الموديلات الجديدة) هوما reasoning models.
        # بلا هاد السطر كيصرفو كاع max_tokens على "التفكير" وكيرجعو content فارغة —
        # وهادشي هو اللي كان كيخلي الترجمة ترجع None وتبان ليك بلي الموديل خاسر.
        if AI_DISABLE_REASONING:
            payload["reasoning"] = {"enabled": False, "exclude": True}
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
                        # وكتحط النص فـ reasoning بدلها — كناخدو content أولاً دايماً
                        content = message.get("content")
                        if not (isinstance(content, str) and content.strip()):
                            content = message.get("reasoning") or ""
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


async def translate_text(text: str, target_language_en: str) -> Optional[str]:
    """يترجم نص لأي لغة (مستعملة فـ الترجمة التلقائية بالـ Reaction). كيرجع None إلا فشلت الترجمة،
    باش نفرقو بين 'ماكاينش OPENROUTER_API_KEY' و 'النص هو نفسو الترجمة' (contrairement لـ translate_to_darija)."""
    if not text or not text.strip():
        return None
    if not OPENROUTER_API_KEY:
        print("[AUTO-TRANSLATE] ❌ OPENROUTER_API_KEY ماكاينش/فارغة — ماقدرش نترجم حتى نص.")
        return None

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a professional translator. Translate the user's message into "
                f"{target_language_en}. Reply with ONLY the translation, no preamble, "
                f"no quotation marks, no explanations. If the message is already in "
                f"{target_language_en}, reply with it unchanged."
            )
        },
        {"role": "user", "content": text}
    ]

    translated, error = await call_openrouter_chat(messages, 700, 0.3)
    if error or not translated:
        print(f"[AUTO-TRANSLATE] ❌ فشلت الترجمة لـ {target_language_en}: {error}")
        return None

    return translated.strip()


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


TRIVIA_CATEGORIES = {
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

# ═══════════════════════════════════════════════════════
# ║   🇲🇦 بنك الأسئلة بالدارجة (المصدر الأساسي ديال اللعبة)  ║
# ═══════════════════════════════════════════════════════
# علاش بنك محلي وماشي API؟
#   • OpenTDB كيقبل غير طلب واحد كل 5 ثواني لكل IP — وعلى Railway الـ IP مشترك،
#     يعني كنت كتاخد 429 شبه دايما، وهادشي هو السبب الحقيقي اللي خلا "ملي كتكليكي
#     على المجال ماكيوقع والو". هنا الأسئلة عندنا فالذاكرة → 0 انتظار، 0 خطأ.
#   • الترجمة الأوتوماتيكية بالـ AI كانت كتزيد 3-6 ثواني لكل سؤال وكتصرف من الرصيد.
#     دابا الأسئلة مكتوبة بالدارجة من الأصل → فورية وبالفابور.
#
# الشكل: كل سؤال = ("نص السؤال", ["جواب0", "جواب1", "جواب2", "جواب3"], index الجواب الصحيح)
# باغي تزيد أسئلة ديالك؟ غير زيد tuple جديد فـ اللائحة اللي بغيتي — والسلام.

TRIVIA_DARIJA_BANK = {
    "general": {
        "easy": [
            ("شحال من لون كاين فـ قوس قزح؟", ["7", "5", "6", "9"], 0),
            ("شنو هي العاصمة ديال المغرب؟", ["الرباط", "الدار البيضاء", "مراكش", "فاس"], 0),
            ("شحال من يوم كاين فـ السنة العادية؟", ["365", "360", "366", "350"], 0),
            ("شنو هو أكبر محيط فـ العالم؟", ["المحيط الهادي", "المحيط الأطلسي", "المحيط الهندي", "المحيط المتجمد"], 0),
            ("شحال من لاعب كيكون فـ فريق كرة القدم داخل الميدان؟", ["11", "10", "12", "9"], 0),
            ("بشحال من رجل كتمشي العنكبوت؟", ["8", "6", "4", "10"], 0),
            ("أشمن حيوان كيتسمى «ملك الغابة»؟", ["السبع", "الفيل", "الدب", "الذيب"], 0),
            ("شحال من ثانية كاين فـ الساعة الوحدة؟", ["3600", "60", "1000", "600"], 0),
        ],
        "medium": [
            ("شحال من قارة كاينة فـ العالم؟", ["7", "5", "6", "8"], 0),
            ("شنو هي أكبر دولة فـ العالم من ناحية المساحة؟", ["روسيا", "كندا", "الصين", "أمريكا"], 0),
            ("العلم ديال اليابان فيه شنو فـ الوسط؟", ["دائرة حمرا", "نجمة", "هلال", "مثلث"], 0),
            ("شحال من قلب عند الأخطبوط؟", ["3", "1", "2", "4"], 0),
            ("شنو هي العملة ديال اليابان؟", ["الين", "اليوان", "الوون", "الروبية"], 0),
            ("شحال من مفتاح عند البيانو العادي؟", ["88", "66", "76", "100"], 0),
        ],
        "hard": [
            ("شنو هي أصغر دولة فـ العالم؟", ["الفاتيكان", "موناكو", "سان مارينو", "ناورو"], 0),
            ("شحال من عضمة عند الإنسان البالغ؟", ["206", "300", "180", "250"], 0),
            ("أشمن لغة هي الأكثر انتشارا فـ العالم كلغة أم؟", ["الصينية الماندرين", "الإنجليزية", "الإسبانية", "العربية"], 0),
            ("أشمن دولة عندها أكبر عدد ديال الجزر فـ العالم؟", ["السويد", "إندونيسيا", "الفلبين", "اليابان"], 0),
            ("شنو كتسمى الخوف من الأماكن المغلوقة؟", ["كلاوستروفوبيا", "أكروفوبيا", "أراكنوفوبيا", "أغورافوبيا"], 0),
        ],
    },
    "science": {
        "easy": [
            ("شنو هو الرمز الكيميائي ديال الما؟", ["H2O", "CO2", "O2", "NaCl"], 0),
            ("شحال من كوكب كاين فـ النظام الشمسي؟", ["8", "9", "7", "10"], 0),
            ("أشمن كوكب كيتسمى «الكوكب الأحمر»؟", ["المريخ", "الزهرة", "المشتري", "عطارد"], 0),
            ("أشمن غاز كيخرجو الشجر وكنتنفسوه حنا؟", ["الأوكسجين", "الأزوت", "ثاني أكسيد الكاربون", "الهيدروجين"], 0),
            ("شنو هو أكبر عضو فـ جسم الإنسان؟", ["الجلد", "الكبد", "الدماغ", "الرية"], 0),
            ("فشحال من درجة كيغلي الما (بالضغط العادي)؟", ["100", "90", "80", "120"], 0),
            ("شنو هو النجم اللي أقرب للأرض؟", ["الشمس", "القمر", "سيريوس", "بولاريس"], 0),
            ("شحال من سنّة عند الإنسان البالغ (بضراس العقل)؟", ["32", "28", "30", "36"], 0),
        ],
        "medium": [
            ("شنو هو الرمز الكيميائي ديال الذهب؟", ["Au", "Ag", "Go", "Fe"], 0),
            ("أشمن غاز هو الأكثر فـ الغلاف الجوي ديال الأرض؟", ["الأزوت", "الأوكسجين", "ثاني أكسيد الكاربون", "الهيدروجين"], 0),
            ("شحال من كروموزوم عند الإنسان العادي؟", ["46", "44", "48", "23"], 0),
            ("شكون اللي اكتشف البنسلين؟", ["ألكسندر فليمينغ", "لويس باستور", "إسحاق نيوتن", "ألبرت أينشتاين"], 0),
            ("سرعة الضو تقريبا شحال فـ الثانية؟", ["300 ألف كيلومتر", "300 كيلومتر", "3 مليون كيلومتر", "30 ألف كيلومتر"], 0),
            ("شنو كيقيس جهاز «سيسموغراف»؟", ["الزلازل", "الحرارة", "الضغط", "الرطوبة"], 0),
        ],
        "hard": [
            ("شنو هي الوحدة ديال قياس المقاومة الكهربائية؟", ["الأوم", "الفولط", "الأمبير", "الواط"], 0),
            ("شنو هو أصلب معدن طبيعي؟", ["الماس", "الحديد", "الذهب", "الكوارتز"], 0),
            ("أشمن جزء ديال الخلية كيتسمى «معمل الطاقة»؟", ["الميتوكوندري", "النواة", "الريبوزوم", "الغشاء"], 0),
            ("شحال من عنصر معترف بيه فـ الجدول الدوري؟", ["118", "100", "92", "150"], 0),
            ("شكون اللي حط نظرية النسبية؟", ["ألبرت أينشتاين", "إسحاق نيوتن", "نيلز بور", "ماكس بلانك"], 0),
        ],
    },
    "sports": {
        "easy": [
            ("شحال من لاعب كيلعبو فـ فريق كرة السلة داخل الميدان؟", ["5", "6", "7", "11"], 0),
            ("كأس العالم لكرة القدم كيتنظم كل شحال من عام؟", ["4", "2", "3", "5"], 0),
            ("أشمن رياضة كيلعبو فيها ميسي ورونالدو؟", ["كرة القدم", "كرة السلة", "التنس", "الملاكمة"], 0),
            ("المنتخب المغربي كيتلقب بشنو؟", ["أسود الأطلس", "نسور قرطاج", "الفراعنة", "محاربو الصحراء"], 0),
            ("شحال من شوط كاين فـ ماتش كرة القدم العادي؟", ["2", "3", "4", "1"], 0),
            ("الألعاب الأولمبية الصيفية كيتنظمو كل شحال من عام؟", ["4", "2", "5", "3"], 0),
            ("فـ التنس، شنو كتسمى النتيجة «صفر»؟", ["Love", "Zero", "Nil", "Duck"], 0),
            ("شحال من حكم رئيسي كيكون فـ الميدان فـ ماتش كرة القدم؟", ["1", "2", "3", "4"], 0),
        ],
        "medium": [
            ("شكون هو المنتخب اللي ربح كأس العالم 2022؟", ["الأرجنتين", "فرنسا", "البرازيل", "كرواتيا"], 0),
            ("فأي عام وصل المغرب لنصف النهائي ديال كأس العالم؟", ["2022", "2018", "2014", "1986"], 0),
            ("شحال من نقطة كتعطي الرمية الثلاثية فـ كرة السلة؟", ["3", "2", "1", "4"], 0),
            ("أشمن نادي كيلعب فـ ملعب «كامب نو»؟", ["برشلونة", "ريال مدريد", "أتلتيكو مدريد", "إشبيلية"], 0),
            ("شحال من جولة كحد أقصى فـ نزال الملاكمة المحترفة ديال البطولة؟", ["12", "10", "15", "8"], 0),
            ("أشمن نادي مغربي ربح دوري أبطال إفريقيا أكثر مرة؟", ["الرجاء البيضاوي", "الوداد البيضاوي", "الجيش الملكي", "المغرب الفاسي"], 0),
        ],
        "hard": [
            ("شكون هي أول مغربية ربحات ميدالية ذهبية أولمبية؟", ["نوال المتوكل", "حسنة بنحسي", "زهرة وعزيز", "سلمى الغزالي"], 0),
            ("شحال من مرة ربحات البرازيل كأس العالم؟", ["5", "4", "6", "3"], 0),
            ("أشمن دولة نظمات أول كأس العالم لكرة القدم؟", ["الأوروغواي", "البرازيل", "إيطاليا", "فرنسا"], 0),
            ("فـ الغولف، شنو كتسمى ضربة وحدة تحت الـ par؟", ["Birdie", "Eagle", "Bogey", "Albatross"], 0),
            ("أشمن عداء مغربي ربح ذهبية 1500 متر فـ أولمبياد أثينا 2004؟", ["هشام الكروج", "سعيد عويطة", "خالد سكاح", "براهيم بولامي"], 0),
        ],
    },
    "history": {
        "easy": [
            ("فأي عام حصل المغرب على الاستقلال؟", ["1956", "1962", "1930", "1975"], 0),
            ("المسيرة الخضراء وقعات فأي عام؟", ["1975", "1956", "1961", "1980"], 0),
            ("الحرب العالمية الثانية سالات فأي عام؟", ["1945", "1939", "1918", "1950"], 0),
            ("الأهرامات الكبيرة كاينين فأشمن دولة؟", ["مصر", "العراق", "السودان", "المكسيك"], 0),
            ("شكون كان أول إنسان حط رجليه فوق القمر؟", ["نيل أرمسترونغ", "يوري غاغارين", "باز ألدرين", "جون غلين"], 0),
            ("الحرب العالمية الأولى بدات فأي عام؟", ["1914", "1918", "1939", "1900"], 0),
            ("أشمن حضارة بنات الكولوسيوم فـ روما؟", ["الرومان", "اليونان", "المصريين", "الفينيقيين"], 0),
            ("شنو كتسمى الكتابة القديمة ديال المصريين؟", ["الهيروغليفية", "المسمارية", "اللاتينية", "الرونية"], 0),
        ],
        "medium": [
            ("أشمن دولة بنات مدينة مراكش؟", ["المرابطين", "الموحدين", "المرينيين", "السعديين"], 0),
            ("أشمن دولة استعمرات معظم المغرب قبل 1956؟", ["فرنسا", "إسبانيا", "البرتغال", "إنجلترا"], 0),
            ("سور برلين طاح فأي عام؟", ["1989", "1991", "1985", "1975"], 0),
            ("شكون كان أول رئيس ديال الولايات المتحدة؟", ["جورج واشنطن", "أبراهام لينكولن", "توماس جيفرسون", "جون آدامز"], 0),
            ("معركة وادي المخازن (معركة الملوك الثلاثة) وقعات فأشمن قرن؟", ["القرن 16", "القرن 15", "القرن 17", "القرن 14"], 0),
            ("شكون كتب «المقدمة» وكيتعتبر مؤسس علم الاجتماع؟", ["ابن خلدون", "ابن بطوطة", "ابن رشد", "ابن سينا"], 0),
        ],
        "hard": [
            ("فأي عام تأسست جامعة القرويين فـ فاس؟", ["859", "1000", "1150", "750"], 0),
            ("شنو كانت العاصمة ديال الدولة الموحدية؟", ["مراكش", "فاس", "الرباط", "تلمسان"], 0),
            ("الثورة الفرنسية بدات فأي عام؟", ["1789", "1799", "1750", "1804"], 0),
            ("أشمن إمبراطورية سقطات بسقوط القسطنطينية عام 1453؟", ["البيزنطية", "الرومانية الغربية", "العثمانية", "الفارسية"], 0),
            ("شكون هو الرحالة المغربي اللي دار حوالي 120 ألف كيلومتر ديال الأسفار؟", ["ابن بطوطة", "ابن خلدون", "الإدريسي", "ليون الإفريقي"], 0),
        ],
    },
    "geography": {
        "easy": [
            ("شنو هي العاصمة ديال فرنسا؟", ["باريس", "ليون", "مرسيليا", "نيس"], 0),
            ("المغرب كاين فأشمن قارة؟", ["إفريقيا", "أوروبا", "آسيا", "أمريكا"], 0),
            ("شنو هو أطول نهر فـ إفريقيا؟", ["النيل", "الكونغو", "النيجر", "الزمبيزي"], 0),
            ("أشمن سلسلة جبال كتعدا فـ المغرب؟", ["الأطلس", "الألب", "الهيمالايا", "الأنديز"], 0),
            ("شنو هي أكبر صحراء حارة فـ العالم؟", ["الصحراء الكبرى", "كالاهاري", "غوبي", "أتاكاما"], 0),
            ("شنو هي العاصمة ديال إسبانيا؟", ["مدريد", "برشلونة", "إشبيلية", "فالنسيا"], 0),
            ("أشمن بحر كيحد المغرب من الشمال؟", ["البحر الأبيض المتوسط", "البحر الأحمر", "بحر قزوين", "البحر الأسود"], 0),
            ("شنو كيفصل المغرب على إسبانيا؟", ["مضيق جبل طارق", "قناة السويس", "مضيق البوسفور", "قناة بنما"], 0),
        ],
        "medium": [
            ("شنو هي أعلى قمة فـ المغرب؟", ["توبقال", "المكون", "تيدغين", "بويبلان"], 0),
            ("مدينة اسطنبول كاينة فأشمن دولة؟", ["تركيا", "اليونان", "بلغاريا", "سوريا"], 0),
            ("شنو هي أكبر جزيرة فـ العالم؟", ["غرينلاند", "مدغشقر", "بورنيو", "سومطرة"], 0),
            ("أشمن نهر كيعدا من مدينة القاهرة؟", ["النيل", "الفرات", "دجلة", "الأردن"], 0),
            ("شنو هي العاصمة ديال كندا؟", ["أوتاوا", "تورونتو", "مونتريال", "فانكوفر"], 0),
            ("أشمن مدينة مغربية كتسمى «العاصمة العلمية»؟", ["فاس", "مراكش", "الرباط", "طنجة"], 0),
        ],
        "hard": [
            ("شنو هي أعمق نقطة فـ المحيطات؟", ["خندق ماريانا", "خندق بورتوريكو", "خندق جافا", "البحر الميت"], 0),
            ("أشمن جوج دول كيتقاسمو أطول حدود برية فـ العالم؟", ["أمريكا وكندا", "روسيا والصين", "الأرجنتين والشيلي", "الهند والصين"], 0),
            ("شنو هي العاصمة ديال أستراليا؟", ["كانبيرا", "سيدني", "ملبورن", "بيرث"], 0),
            ("أشمن بحيرة هي الأكبر فـ العالم من ناحية المساحة؟", ["بحر قزوين", "بحيرة سوبيريور", "بحيرة فيكتوريا", "بحيرة بايكال"], 0),
            ("شنو هي أطول سلسلة جبال فـ العالم فوق اليابسة؟", ["الأنديز", "الهيمالايا", "الروكي", "الألب"], 0),
        ],
    },
    "movies": {
        "easy": [
            ("شنو هوما الألوان الأساسية ديال البدلة ديال سبايدرمان؟", ["حمرا وزرقا", "خضرا وصفرا", "كحلة وبيضا", "سوداء وحمرا"], 0),
            ("فيلم «Titanic» كيحكي على شنو؟", ["باخرة غرقات", "طيارة طاحت", "قطار تحطم", "حرب عالمية"], 0),
            ("فـ «Frozen»، شكون عندها قوة الجليد؟", ["إلسا", "آنا", "أولاف", "كريستوف"], 0),
            ("«سيمبا» فـ The Lion King أشمن حيوان هو؟", ["سبع", "نمر", "دب", "ذيب"], 0),
            ("«Fast and Furious» كيهضر على شنو أساسا؟", ["الطوموبيلات والسباق", "الفضاء", "البحر", "الطبخ"], 0),
            ("شنو كتسمى أكبر جائزة فـ السينما الأمريكية؟", ["الأوسكار", "الغرامي", "الإيمي", "التوني"], 0),
            ("فـ «Harry Potter»، شنو كتسمى مدرسة السحر؟", ["هوغوارتس", "نارنيا", "أزكابان", "دورمسترانغ"], 0),
            ("فـ «Jurassic Park»، شنو هوما الحيوانات الرئيسية؟", ["الديناصورات", "القرود", "الحيتان", "الذياب"], 0),
        ],
        "medium": [
            ("شكون خرّج فيلم «Inception»؟", ["كريستوفر نولان", "ستيفن سبيلبرغ", "كوينتين تارانتينو", "مارتن سكورسيزي"], 0),
            ("أشمن فيلم ناطق بالكورية ربح أوسكار أحسن فيلم؟", ["Parasite", "Oldboy", "Train to Busan", "Burning"], 0),
            ("شكون كيمثل دور «Iron Man»؟", ["روبرت داوني جونيور", "كريس إيفانز", "كريس هيمسوورث", "مارك رافالو"], 0),
            ("أشمن استوديو خرّج «Toy Story»؟", ["Pixar", "DreamWorks", "Warner Bros", "Universal"], 0),
            ("فـ «The Matrix»، أشمن حبة كيختار نيو باش يعرف الحقيقة؟", ["الحمرا", "الزرقا", "الخضرا", "الصفرا"], 0),
            ("شكون هو المخرج ديال «Titanic» و«Avatar»؟", ["جيمس كاميرون", "ريدلي سكوت", "بيتر جاكسون", "جورج لوكاس"], 0),
        ],
        "hard": [
            ("شنو هو أول فيلم رسوم متحركة طويل ديال ديزني؟", ["Snow White", "Pinocchio", "Bambi", "Fantasia"], 0),
            ("شكون خرّج فيلم «Pulp Fiction»؟", ["كوينتين تارانتينو", "كريستوفر نولان", "ديفيد فينشر", "الإخوة كوين"], 0),
            ("فـ «The Godfather»، شنو كتسمى العائلة الرئيسية؟", ["كورليوني", "سوبرانو", "غامبينو", "باربوسا"], 0),
            ("أشمن فيلم ربح 11 أوسكار (رقم قياسي متعادل)؟", ["Ben-Hur", "Gladiator", "The Godfather", "Avatar"], 0),
            ("فأي عام خرج أول فيلم «Star Wars»؟", ["1977", "1980", "1972", "1985"], 0),
        ],
    },
    "music": {
        "easy": [
            ("شحال من وتر عند الغيتارة الكلاسيكية العادية؟", ["6", "4", "5", "7"], 0),
            ("أشمن آلة كتضرب عليها بالعصي؟", ["الطبل", "الغيتارة", "الفلوت", "البيانو"], 0),
            ("شنو كتسمى الموسيقى التقليدية المغربية المرتبطة بالأندلس؟", ["الطرب الأندلسي", "الراب", "الجاز", "الروك"], 0),
            ("فرقة «The Beatles» من أشمن دولة؟", ["إنجلترا", "أمريكا", "فرنسا", "أستراليا"], 0),
            ("شنو كتسمى الغناية اللي كيغنيها واحد بوحدو؟", ["سولو", "ديو", "تريو", "كورال"], 0),
            ("آلة «العود» مشهورة عند شكون؟", ["العرب", "اليابانيين", "الروس", "البرازيليين"], 0),
            ("أشمن آلة كتنفخ فيها؟", ["الفلوت", "الكمان", "البيانو", "الطبل"], 0),
            ("«جدبة» و«شعبي» هوما أنواع موسيقية من أشمن دولة؟", ["المغرب", "لبنان", "مصر", "العراق"], 0),
        ],
        "medium": [
            ("شكون هو الملقب بـ «ملك البوب»؟", ["مايكل جاكسون", "إلفيس بريسلي", "برينس", "جيمس براون"], 0),
            ("أشمن نوع موسيقي خرج من جامايكا؟", ["الريغي", "السالسا", "الفلامنكو", "التانغو"], 0),
            ("شحال من نوطة كاينة فـ السلم الموسيقي الأساسي؟", ["7", "5", "8", "12"], 0),
            ("«ناس الغيوان» جماعة موسيقية من أشمن دولة؟", ["المغرب", "الجزائر", "تونس", "مصر"], 0),
            ("شنو كيستعمل الدي جي باش يخلط الأصوات؟", ["الميكسر", "الفلوت", "الكمان", "البوق"], 0),
            ("شكون كيتلقب بـ «كوكب الشرق»؟", ["أم كلثوم", "فيروز", "وردة", "أسمهان"], 0),
        ],
        "hard": [
            ("شكون ألّف السيمفونية التاسعة المشهورة بـ «نشيد الفرح»؟", ["بيتهوفن", "موزارت", "باخ", "شوبان"], 0),
            ("«العيطة» نوع موسيقي مرتبط أساسا بأشمن منطقة فـ المغرب؟", ["الشاوية وعبدة", "الريف", "سوس", "الصحراء"], 0),
            ("شحال من عضو كانو فـ فرقة The Beatles؟", ["4", "3", "5", "6"], 0),
            ("أشمن واحد فهاد اللائحة هو مقام موسيقي عربي؟", ["الحجاز", "الدوريان", "البلوز", "البنتاتونيك"], 0),
            ("شنو كتسمى الموسيقى الروحية المرتبطة بالطقوس ديال كناوة؟", ["الليلة", "الحضرة", "العرس", "الوعدة"], 0),
        ],
    },
    "games": {
        "easy": [
            ("فـ «Minecraft»، شنو كتستعمل أساسا باش تبني؟", ["البلوكات", "الطوموبيلات", "الطيارات", "الفلوس"], 0),
            ("أشمن شركة صنعات «Mario»؟", ["نينتندو", "سوني", "مايكروسوفت", "سيغا"], 0),
            ("«EA FC» (اللي كان FIFA) لعبة ديال شنو؟", ["كرة القدم", "السباق", "الحرب", "المغامرة"], 0),
            ("فـ «Among Us»، شكون كيحاول يقتل الباقين؟", ["الإمبوستر", "الكرومايت", "الكابتن", "الطبيب"], 0),
            ("«PlayStation» شكون كيصنعها؟", ["سوني", "نينتندو", "مايكروسوفت", "سامسونغ"], 0),
            ("فـ «Pac-Man»، شنو كياكل باكمان؟", ["النقط", "التفاح", "اللحم", "الفلوس"], 0),
            ("«Fortnite» و«PUBG» أشمن نوع ديال ألعاب؟", ["باتل رويال", "سباق", "طبخ", "رياضة"], 0),
            ("فـ «Tetris»، شنو خاصك دير بالبلوكات؟", ["تعمر سطور كاملة", "تقتل الأعداء", "تجمع الفلوس", "تسوق طوموبيل"], 0),
        ],
        "medium": [
            ("أشمن شركة خرجات «GTA»؟", ["Rockstar Games", "EA", "Ubisoft", "Activision"], 0),
            ("«Xbox» شكون كيصنعها؟", ["مايكروسوفت", "سوني", "نينتندو", "أبل"], 0),
            ("فـ «Pokémon»، شنو هو أول بوكيمون فـ البوكيديكس؟", ["بولباصور", "بيكاتشو", "تشارمندر", "سكويرتل"], 0),
            ("أشمن لعبة باعت أكثر نسخ فـ التاريخ؟", ["Minecraft", "GTA V", "Tetris", "Wii Sports"], 0),
            ("«Assassin's Creed» من صنع أشمن شركة؟", ["Ubisoft", "Rockstar", "Bethesda", "Capcom"], 0),
            ("فـ «League of Legends»، شنو خاصك تهدم باش تربح؟", ["النيكسوس", "القاعدة", "البرج الأول", "التنين"], 0),
        ],
        "hard": [
            ("فأي عام خرجات أول نسخة ديال «Super Mario Bros»؟", ["1985", "1990", "1980", "1995"], 0),
            ("أشمن شركة صنعات «The Legend of Zelda»؟", ["نينتندو", "سيغا", "كابكوم", "كونامي"], 0),
            ("«Half-Life» من صنع أشمن استوديو؟", ["Valve", "id Software", "Blizzard", "Epic Games"], 0),
            ("أشمن لعبة كتعتبر أول لعبة فيديو تجارية ناجحة؟", ["Pong", "Tetris", "Space Invaders", "Pac-Man"], 0),
            ("«Dark Souls» من صنع أشمن استوديو ياباني؟", ["FromSoftware", "Square Enix", "Konami", "Capcom"], 0),
        ],
    },
    "anime": {
        "easy": [
            ("فـ «Naruto»، شنو هو الحلم ديال ناروتو؟", ["يولي هوكاجي", "يولي طبيب", "يهرب من القرية", "يبقى معلم"], 0),
            ("شكون هو البطل ديال «One Piece»؟", ["لوفي", "زورو", "سانجي", "نامي"], 0),
            ("فـ «Dragon Ball»، شنو كيجمع غوكو باش تتحقق أمنية؟", ["كرات التنين", "النجوم", "الحجرات", "الكنوز"], 0),
            ("شكون هو البطل ديال أنمي «Pokémon»؟", ["آش", "بروك", "ميستي", "غاري"], 0),
            ("فـ «Attack on Titan»، على شكون كيتحاربو؟", ["العمالقة", "التنانين", "الروبوهات", "القراصنة"], 0),
            ("«Doraemon» شنو هو؟", ["قط روبوت", "كلب", "فأر", "إنسان آلي طويل"], 0),
            ("فـ «Death Note»، شنو كيستعمل لايت باش يقتل؟", ["دفتر", "سيف", "سم", "مسدس"], 0),
            ("فـ «Captain Tsubasa»، أشمن رياضة كيلعبو؟", ["كرة القدم", "كرة السلة", "التنس", "البيسبول"], 0),
        ],
        "medium": [
            ("شكون هو مؤلف «One Piece»؟", ["إييتشيرو أودا", "ماساشي كيشيموتو", "أكيرا تورياما", "تايت كوبو"], 0),
            ("فـ «Naruto»، شنو كتسمى القرية ديال ناروتو؟", ["كونوها", "سونا", "كيري", "إيوا"], 0),
            ("أشمن استوديو خرّج «Spirited Away»؟", ["استوديو غيبلي", "توي أنيميشن", "مادهاوس", "بونز"], 0),
            ("فـ «Bleach»، شنو كتسمى السيوف ديال الشينيغامي؟", ["زانباكوتو", "كاتانا", "كوناي", "شوريكن"], 0),
            ("شكون هو البطل ديال «Demon Slayer»؟", ["تانجيرو", "زينيتسو", "إينوسكي", "غيو"], 0),
            ("فـ «One Punch Man»، شكون كيقتل أي عدو بضربة وحدة؟", ["سايتاما", "جينوس", "كينغ", "باكوغو"], 0),
        ],
        "hard": [
            ("شكون ألّف مانغا «Dragon Ball»؟", ["أكيرا تورياما", "إييتشيرو أودا", "ماساشي كيشيموتو", "هيرومو أراكاوا"], 0),
            ("فـ «Fullmetal Alchemist»، شنو هو القانون الأساسي ديال الخيمياء؟", ["التبادل المتكافئ", "التحول الحر", "قانون النار", "قانون الدم"], 0),
            ("أشمن أنمي ربح أوسكار أحسن فيلم رسوم متحركة؟", ["Spirited Away", "Your Name", "Akira", "Ghost in the Shell"], 0),
            ("فـ «Code Geass»، شنو كتسمى القوة ديال ليلوش؟", ["غياس", "شارينغان", "نين", "هاكي"], 0),
            ("شكون هو المخرج ديال «Princess Mononoke» و«My Neighbor Totoro»؟", ["هاياو ميازاكي", "ماكوتو شينكاي", "ساتوشي كون", "إيساو تاكاهاتا"], 0),
        ],
    },
}


# ═══════════════════════════════════════════════════════
# ║        محرك الأسئلة (بنك دارجة + احتياط OpenTDB)        ║
# ═══════════════════════════════════════════════════════

def build_bank_question(category: str, difficulty: str, used_keys: set) -> Optional[dict]:
    """كيختار سؤال عشوائي بالدارجة من البنك المحلي، بلا ما يعاود شي سؤال تسول ديجا
    فنفس الجلسة. كيخلط ترتيب الأجوبة كل مرة باش ماتحفظش «دايما الأول»."""
    pool = TRIVIA_DARIJA_BANK.get(category, {}).get(difficulty, [])
    available = [
        (i, q) for i, q in enumerate(pool)
        if f"{category}:{difficulty}:{i}" not in used_keys
    ]
    if not available:
        return None

    idx, (question_text, options, correct_idx) = random.choice(available)
    correct = options[correct_idx]
    shuffled = list(options)
    random.shuffle(shuffled)

    return {
        "question": question_text,
        "correct": correct,
        "options": shuffled,
        "category": TRIVIA_CATEGORY_LABELS.get(category, category),
        "difficulty": difficulty,
        "key": f"{category}:{difficulty}:{idx}",
        "source": "bank",
    }


# ═══════ حماية من الـ rate limit ديال OpenTDB ═══════
# OpenTDB كيسمح غير بطلب واحد كل 5 ثواني لكل IP (كيرجع response_code=5 ولا HTTP 429).
# البوت القديم كان كيبعث الطلب ديال الـ token وطلب السؤال ورا بعضياتهم فنفس اللحظة
# → دايما 429 → «كنكليكي على المجال وماكيوقع والو». هاد الـ lock كيضمن التباعد.
_opentdb_lock = asyncio.Lock()
_opentdb_last_call = 0.0
OPENTDB_MIN_INTERVAL = 5.5   # ثواني بين كل طلبين (5 هو الحد الرسمي، زدنا 0.5 احتياط)


async def opentdb_request(url: str, params: dict) -> dict:
    """كل طلب لـ OpenTDB كيعدا من هنا — مضمون التباعد بيناتهم."""
    global _opentdb_last_call
    async with _opentdb_lock:
        elapsed = asyncio.get_event_loop().time() - _opentdb_last_call
        if elapsed < OPENTDB_MIN_INTERVAL:
            await asyncio.sleep(OPENTDB_MIN_INTERVAL - elapsed)
        data = await fetch_json(url, params=params)
        _opentdb_last_call = asyncio.get_event_loop().time()
        return data


async def get_new_trivia_token() -> Optional[str]:
    """يطلب Session Token من OpenTDB — كيخلي OpenTDB مايعاودش نفس السؤال فنفس الجلسة."""
    data = await opentdb_request("https://opentdb.com/api_token.php", {"command": "request"})
    if data and data.get("response_code") == 0:
        return data.get("token")
    return None


async def fetch_trivia_question(category: str = None, difficulty: str = None, token: str = None) -> Optional[dict]:
    """جيب سؤال Trivia من OpenTDB (بالإنجليزية). كيرجع None إلا فشل.
    كيتعامل مع: code 4 (خلصو الأسئلة → reset) و code 5 (rate limit → استنى وعاود)."""
    params = {"amount": 1, "type": "multiple"}
    if category and category in TRIVIA_CATEGORIES:
        params["category"] = TRIVIA_CATEGORIES[category]
    if difficulty in ("easy", "medium", "hard"):
        params["difficulty"] = difficulty
    if token:
        params["token"] = token

    data = await opentdb_request("https://opentdb.com/api.php", params)
    code = data.get("response_code") if data else None

    if code == 5:   # rate limit → التباعد كيتكفل بيه opentdb_request، غير نعاودو
        print("[TRIVIA] OpenTDB rate limit (code 5) — كنعاود المحاولة...")
        data = await opentdb_request("https://opentdb.com/api.php", params)
        code = data.get("response_code") if data else None

    if code == 4 and token:   # الطوكن خلص كاع الأسئلة الممكنة → نصيفطوه ونعاودو
        await opentdb_request("https://opentdb.com/api_token.php", {"command": "reset", "token": token})
        data = await opentdb_request("https://opentdb.com/api.php", params)
        code = data.get("response_code") if data else None

    if not data or code != 0 or not data.get("results"):
        return None

    q = data["results"][0]
    correct = html.unescape(q["correct_answer"])
    options = [html.unescape(a) for a in q["incorrect_answers"]] + [correct]
    random.shuffle(options)

    return {
        "question": html.unescape(q["question"]),
        "correct": correct,
        "options": options,
        "category": html.unescape(q.get("category", "عامة")),
        "difficulty": q.get("difficulty", "medium"),
        "source": "opentdb",
    }


# ═══════ الترجمة للدارجة (للأسئلة الجايين من OpenTDB فقط) + كاش دائم ═══════
DARIJA_CACHE_FILE = os.path.join(DATA_DIR, "trivia_darija_cache.json")
darija_cache = {}


def load_darija_cache():
    global darija_cache
    try:
        if os.path.exists(DARIJA_CACHE_FILE):
            with open(DARIJA_CACHE_FILE, "r", encoding="utf-8") as f:
                darija_cache = json.load(f)
            print(f"✅ تحملو {len(darija_cache)} ترجمة محفوظة ديال Trivia")
    except Exception as e:
        print(f"⚠️ خطأ فتحميل كاش الترجمة: {e}")
        darija_cache = {}


def save_darija_cache():
    try:
        with open(DARIJA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(darija_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطأ فحفظ كاش الترجمة: {e}")


load_darija_cache()


async def translate_question_to_darija(question: str, options: list) -> Optional[tuple]:
    """كيترجم السؤال + 4 أجوبة للدارجة المغربية بطلب واحد. كيحفظ النتيجة فـ كاش
    دائم باش نفس السؤال ماياخدش طلب ثاني أبدا. كيرجع (سؤال, [أجوبة]) ولا None."""
    cache_key = question.strip()
    cached = darija_cache.get(cache_key)
    if cached and len(cached.get("options", [])) == 4:
        return cached["question"], cached["options"]

    if not OPENROUTER_API_KEY:
        return None

    lines = [f"Q: {question}"] + [f"{chr(65 + i)}: {opt}" for i, opt in enumerate(options)]
    messages = [
        {
            "role": "system",
            "content": (
                "You translate quiz content into MOROCCAN DARIJA written in Arabic script "
                "(the everyday spoken Moroccan dialect, NOT Modern Standard Arabic). "
                "Use natural Darija words like: شنو، شحال، أشمن، فين، علاش، كيفاش، واش، بزاف، دابا. "
                "Keep proper nouns (names of people, films, games, brands) in their original spelling. "
                "Reply with EXACTLY 5 lines and nothing else: one line starting with 'Q:' "
                "then four lines starting with 'A:', 'B:', 'C:', 'D:'. "
                "No preamble, no explanation, no markdown."
            )
        },
        {"role": "user", "content": "\n".join(lines)}
    ]
    result, error = await call_openrouter_chat(messages, 900, 0.3)
    if error or not result:
        print(f"[TRIVIA] فشلت الترجمة للدارجة: {error}")
        return None

    parsed = {}
    for line in result.strip().split("\n"):
        line = line.strip().lstrip("*").strip()
        for key in ("Q", "A", "B", "C", "D"):
            prefix = f"{key}:"
            if line.startswith(prefix) and key not in parsed:
                parsed[key] = line[len(prefix):].strip()
                break

    if not all(parsed.get(k) for k in ("Q", "A", "B", "C", "D")):
        print(f"[TRIVIA] الرد ديال الترجمة جا بشكل غير متوقع: {result[:150]}")
        return None

    translated = (parsed["Q"], [parsed["A"], parsed["B"], parsed["C"], parsed["D"]])
    darija_cache[cache_key] = {"question": translated[0], "options": translated[1]}
    save_darija_cache()
    return translated


async def get_darija_question(category: str, difficulty: str, used_keys: set,
                              token: Optional[str] = None) -> Optional[dict]:
    """المصدر الوحيد ديال الأسئلة فاللعبة — دايما كيرجع سؤال بالدارجة:
      1) كيقلب أولا فـ البنك المحلي (فوري، بلا إنترنت، بلا فلوس)
      2) إلا سالاو أسئلة هاد المجال/الصعوبة، كيجيب من OpenTDB وكيترجمو أوتوماتيك
      3) إلا فشلات الترجمة تاهي، كيرجع لسؤال من البنك حتى لو تعاود
    """
    q = build_bank_question(category, difficulty, used_keys)
    if q:
        return q

    online = await fetch_trivia_question(category, difficulty, token)
    if online:
        translated = await translate_question_to_darija(online["question"], online["options"])
        if translated:
            new_question, new_options = translated
            correct_idx = online["options"].index(online["correct"])
            online["question"] = new_question
            online["options"] = new_options
            online["correct"] = new_options[correct_idx]
            online["category"] = TRIVIA_CATEGORY_LABELS.get(category, online["category"])
            online["key"] = f"otdb:{new_question[:60]}"
            return online

    # آخر حل: نعاودو من البنك (كنمسحو التاريخ ديال هاد المجال/الصعوبة)
    fallback_keys = {k for k in used_keys if not k.startswith(f"{category}:{difficulty}:")}
    return build_bank_question(category, difficulty, fallback_keys)


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


async def log_case(guild, action: str, emoji: str, color: discord.Color,
                    target, moderator, reason: str, extra: str = None) -> int:
    """
    كتسجل عقوبة/إجراء كـ 'Case' برقم فريد ومتزايد، كتحفظها فـ cases.json
    (باقية حتى بعد ريستارت)، وكتبعث embed احترافي موحد فـ MOD_LOGS_CHANNEL_ID.
    target/moderator: discord.Member/discord.User أو None (مثلا Auto-Mod بلا منفذ بشري).
    كترجع رقم الـ Case باش تقدر تبينو للمستخدم مباشرة.
    """
    case_id = cases_db.get("next_id", 1)
    cases_db["next_id"] = case_id + 1

    target_id = getattr(target, "id", None)
    target_name = str(target) if target else "غير معروف"
    mod_id = getattr(moderator, "id", None)
    mod_name = str(moderator) if moderator else "Auto-Mod (System)"

    record = {
        "id": case_id,
        "action": action,
        "target_id": target_id,
        "target_name": target_name,
        "moderator_id": mod_id,
        "moderator_name": mod_name,
        "reason": reason or "ما ذكرش سبب",
        "extra": extra,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    cases_db.setdefault("cases", {})[str(case_id)] = record
    save_cases()

    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"{emoji} {action} — Case #{case_id}",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🎯 العضو",
            value=f"{target.mention} ({target_name})" if hasattr(target, "mention") else target_name,
            inline=False
        )
        embed.add_field(
            name="🛡️ نفذ من طرف",
            value=(moderator.mention if hasattr(moderator, "mention") else mod_name),
            inline=False
        )
        embed.add_field(name="📝 السبب", value=reason or "ما ذكرش سبب", inline=False)
        if extra:
            embed.add_field(name="ℹ️ تفاصيل إضافية", value=extra, inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Case #{case_id}")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[CASES] خطأ فـ بعث embed ديال Case #{case_id}: {e}")

    return case_id


def get_case(case_id) -> Optional[dict]:
    return cases_db.get("cases", {}).get(str(case_id))


def get_cases_for_user(user_id: int) -> list:
    """كترجع كاع الحالات ديال عضو معين، الأحدث فالأول"""
    all_cases = list(cases_db.get("cases", {}).values())
    user_cases = [c for c in all_cases if c.get("target_id") == user_id]
    user_cases.sort(key=lambda c: c["id"], reverse=True)
    return user_cases


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
            f"🔇 عند {bot_settings['mute_after_warns']} تحذيرات → كتم تلقائي لمدة {bot_settings['mute_duration_minutes']} دقيقة\n"
            f"👢 عند {bot_settings['kick_after_warns']} تحذيرات → طرد تلقائي من السيرفر\n"
            f"🚫 عند {bot_settings['ban_after_warns']} تحذيرات → حظر نهائي من السيرفر\n\n"
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
            f"🔇 À {bot_settings['mute_after_warns']} avertissements → mute automatique pendant {bot_settings['mute_duration_minutes']} minutes\n"
            f"👢 À {bot_settings['kick_after_warns']} avertissements → expulsion automatique du serveur\n"
            f"🚫 À {bot_settings['ban_after_warns']} avertissements → bannissement définitif du serveur\n\n"
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
            f"🔇 At {bot_settings['mute_after_warns']} warnings → automatic mute for {bot_settings['mute_duration_minutes']} minutes\n"
            f"👢 At {bot_settings['kick_after_warns']} warnings → automatic kick from the server\n"
            f"🚫 At {bot_settings['ban_after_warns']} warnings → permanent ban from the server\n\n"
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
                "❌ ما قدرتش نعطيك الرول، بلغ الإدارة (البوت ماعندوش صلاحية — تحقق من ترتيب الرولات بـ `/checkroles`).",
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
                    f"**الحل:** استعمل `/checkroles` باش تشوف المشكل بالضبط.",
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
                f"2️⃣ **كتم (Mute)** — عند {bot_settings['mute_after_warns']} تحذيرات ({bot_settings['mute_duration_minutes']} دقيقة)، ولا إلا بعتي {SPAM_THRESHOLD} رسايل فـ {SPAM_INTERVAL} ثواني (سبام)\n"
                f"3️⃣ **طرد (Kick)** — عند الوصول لـ {bot_settings['kick_after_warns']} تحذيرات\n"
                f"4️⃣ **حظر (Ban)** — عند الوصول لـ {bot_settings['ban_after_warns']} تحذيرات، ولا مباشرة فحالة Doxxing/محتوى +18/تهديد خطير"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed.add_field(
                name="🚨 كيفاش تبلغ عن مخالفة (/report)",
                value=(
                    "إلا شفتي شي مخالفة والبوت ما تدخلش أوتوماتيكياً، عندك طريقتين:\n\n"
                    "**1) بلاغ على عضو معين:**\n"
                    "`/report @العضو السبب`\n"
                    "مثال: `/report @GGMW9 بعث رابط ديال سيرفر آخر فـ #general`\n\n"
                    "**2) بلاغ عام (بلا ما تحدد عضو):**\n"
                    "`/report وصف المشكل`\n"
                    "مثال: `/report كاين ناس كيهضرو بزربة فـ #announcements`\n\n"
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
                f"2️⃣ **Mute** — à {bot_settings['mute_after_warns']} avertissements ({bot_settings['mute_duration_minutes']} min), ou après {SPAM_THRESHOLD} messages en {SPAM_INTERVAL}s (spam)\n"
                f"3️⃣ **Kick** — à {bot_settings['kick_after_warns']} avertissements\n"
                f"4️⃣ **Ban** — à {bot_settings['ban_after_warns']} avertissements, ou immédiatement en cas de doxxing/contenu +18/menace grave"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed_fr.add_field(
                name="🚨 Comment signaler une infraction (/report)",
                value=(
                    "Si vous voyez une infraction et que le bot n'intervient pas automatiquement, vous avez deux options :\n\n"
                    "**1) Signaler un membre précis :**\n"
                    "`/report @Membre raison`\n"
                    "Exemple : `/report @GGMW9 a posté un lien vers un autre serveur dans #general`\n\n"
                    "**2) Signalement général (sans citer de membre) :**\n"
                    "`/report description du problème`\n"
                    "Exemple : `/report des gens spamment dans #announcements`\n\n"
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
                f"2️⃣ **Mute** — at {bot_settings['mute_after_warns']} warnings ({bot_settings['mute_duration_minutes']} minutes), or after {SPAM_THRESHOLD} messages in {SPAM_INTERVAL}s (spam)\n"
                f"3️⃣ **Kick** — upon reaching {bot_settings['kick_after_warns']} warnings\n"
                f"4️⃣ **Ban** — upon reaching {bot_settings['ban_after_warns']} warnings, or immediately for doxxing/NSFW content/serious threats"
            ),
            inline=False
        )

        if REPORTS_CHANNEL_ID:
            embed_en.add_field(
                name="🚨 How to report a violation (/report)",
                value=(
                    "If you see a violation and the bot doesn't step in automatically, you have two options:\n\n"
                    "**1) Report a specific member:**\n"
                    "`/report @Member reason`\n"
                    "Example: `/report @GGMW9 posted a link to another server in #general`\n\n"
                    "**2) General report (without naming a member):**\n"
                    "`/report description of the issue`\n"
                    "Example: `/report people are spamming in #announcements`\n\n"
                    "💡 **Tip:** if you have a screenshot of the violation, send it directly to staff or in the same message "
                    "(mentioning the member, e.g. Ahmed)\n"
                    "⚠️ Your message is automatically deleted from the public chat and the report goes straight to the staff, "
                    "no one will see that you reported it."
                ),
                inline=False
            )

        embed_en.set_footer(text="GGMW9 | Auto-Moderation System")
        await channel.send(embed=embed_en)


# ═══════════════════════════════════════════════════════
# ║              نظام Tickets (channels خاصة)               ║
# ═══════════════════════════════════════════════════════

def _is_ticket_staff(member: discord.Member) -> bool:
    if OWNER_ID and member.id == OWNER_ID:
        return True
    return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)


class TicketControlView(discord.ui.View):
    """الأزرار جوة channel ديال ticket وحدة (Claim + Close). Persistent —
    كتخدم بـ interaction.channel باش تعرف شنو الـ ticket، بلا ما تحتاج تخزن
    شي حاجة خاصة بكل ticket فـ الـ View نفسها."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 نستلمو (Claim)", style=discord.ButtonStyle.secondary, custom_id="ticket_claim_button")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if not isinstance(member, discord.Member) or not _is_ticket_staff(member):
            await interaction.response.send_message("❌ هاد الزر خاص غير بالإدارة.", ephemeral=True)
            return

        record = tickets_db.get("open", {}).get(str(interaction.channel.id))
        if not record:
            await interaction.response.send_message("❌ ماكاينش هاد الـ ticket فالسجل ديالنا.", ephemeral=True)
            return

        record["claimed_by"] = member.id
        save_tickets()
        await interaction.response.send_message(f"✅ {member.mention} استلم هاد الـ ticket ودابا كيتكلف بيه.")

    @discord.ui.button(label="🔒 سد الـ Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_button")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        record = tickets_db.get("open", {}).get(str(interaction.channel.id))
        if not record:
            await interaction.response.send_message("❌ ماكاينش هاد الـ ticket فالسجل ديالنا (ممكن تسد من قبل).", ephemeral=True)
            return

        is_opener = member.id == record.get("opener_id")
        if not (is_opener or (isinstance(member, discord.Member) and _is_ticket_staff(member))):
            await interaction.response.send_message("❌ غير صاحب الـ ticket ولا الإدارة يقدرو يسدوه.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 غادي نسدو هاد الـ ticket من بعد 5 ثواني... كنجمعو transcript.")

        channel = interaction.channel
        guild = interaction.guild
        ticket_id = record["id"]

        # ═══════ تجميع transcript بسيط (نص) ═══════
        lines = []
        try:
            async for msg in channel.history(limit=500, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or "[بلا نص / embed / attachment]"
                lines.append(f"[{ts}] {msg.author}: {content}")
        except Exception as e:
            lines.append(f"[خطأ فـ تجميع transcript: {e}]")

        transcript_text = "\n".join(lines) if lines else "ماكاين حتى رسالة."
        transcript_path = f"/tmp/ticket_{ticket_id}_transcript.txt"
        try:
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
        except Exception as e:
            print(f"[TICKETS] خطأ فـ كتابة transcript: {e}")
            transcript_path = None

        log_channel_id = TICKET_LOGS_CHANNEL_ID or MOD_LOGS_CHANNEL_ID
        log_channel = bot.get_channel(log_channel_id) if log_channel_id else None
        if log_channel:
            opener_id = record.get("opener_id")
            claimed_by = record.get("claimed_by")
            embed = discord.Embed(
                title=f"🎫 Ticket #{ticket_id} — تسد",
                color=discord.Color.dark_grey(),
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 صاحب الـ Ticket", value=f"<@{opener_id}>" if opener_id else "غير معروف", inline=False)
            embed.add_field(name="🙋 استلمو", value=(f"<@{claimed_by}>" if claimed_by else "محدش استلمو"), inline=False)
            embed.add_field(name="🔒 سداه", value=member.mention, inline=False)
            embed.add_field(name="🕐 تحلق فـ", value=record.get("opened_at", "—"), inline=False)
            embed.set_footer(text=f"{SERVER_NAME} | Ticket #{ticket_id}")
            try:
                if transcript_path:
                    await log_channel.send(embed=embed, file=discord.File(transcript_path, filename=f"ticket-{ticket_id}-transcript.txt"))
                else:
                    await log_channel.send(embed=embed)
            except Exception as e:
                print(f"[TICKETS] خطأ فـ بعث الـ transcript: {e}")

        if str(channel.id) in tickets_db.get("open", {}):
            del tickets_db["open"][str(channel.id)]
            save_tickets()

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket #{ticket_id} تسد من طرف {member}")
        except Exception as e:
            print(f"[TICKETS] خطأ فـ حذف الـ channel: {e}")


class TicketPanelView(discord.ui.View):
    """زر واحد "🎫 دير Ticket" — كيخلق channel خاص للعضو ملي يضغط عليه.
    Persistent (timeout=None) باش يبقى خدام حتى بعد ريستارت البوت."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 دير Ticket", style=discord.ButtonStyle.success, custom_id="open_ticket_button")
    async def open_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return

        if not TICKETS_CATEGORY_ID:
            await interaction.response.send_message(
                "❌ نظام الـ Tickets ماعادش معطي (`TICKETS_CATEGORY_ID` فارغة)، بلغ الإدارة.",
                ephemeral=True
            )
            return

        category = guild.get_channel(TICKETS_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ ما لقيتش Category ديال الـ Tickets، بلغ الإدارة (`TICKETS_CATEGORY_ID`).",
                ephemeral=True
            )
            return

        existing_channel_id, existing_record = get_open_ticket_for_user(member.id)
        if existing_channel_id:
            existing_channel = guild.get_channel(int(existing_channel_id))
            if existing_channel:
                await interaction.response.send_message(
                    f"⚠️ عندك ديجا ticket مفتوح: {existing_channel.mention}",
                    ephemeral=True
                )
                return
            else:
                # الـ channel تحذاف بطريقة أخرى، نمسحو من السجل ونكملو
                del tickets_db["open"][existing_channel_id]
                save_tickets()

        await interaction.response.send_message("⏳ كنخلق الـ ticket ديالك...", ephemeral=True)

        ticket_id = tickets_db.get("next_id", 1)
        tickets_db["next_id"] = ticket_id + 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for rid in EXEMPT_ROLE_IDS:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        safe_name = re.sub(r"[^a-z0-9\-]", "", member.name.lower().replace(" ", "-")) or "user"
        channel_name = f"ticket-{ticket_id}-{safe_name}"[:90]

        try:
            new_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket #{ticket_id} فتحو {member}"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ ما عنديش الصلاحية باش نخلق channel (Manage Channels)، بلغ الإدارة.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ خطأ فـ خلق الـ ticket: {e}", ephemeral=True)
            return

        tickets_db.setdefault("open", {})[str(new_channel.id)] = {
            "id": ticket_id,
            "opener_id": member.id,
            "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "claimed_by": None,
        }
        save_tickets()

        staff_mentions = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id}",
            description=(
                f"مرحبا {member.mention}! شرح المشكل ولا السؤال ديالك هنا بالتفصيل، "
                f"وواحد من الإدارة غادي يجاوبك فأقرب وقت.\n\n"
                f"🙋 الإدارة تقدر تدير **Claim** باش تعرفك شكون كيتكلف بيك.\n"
                f"🔒 ملي تخلص المشكل، اضغط **سد الـ Ticket** (نتا ولا الإدارة)."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Ticket #{ticket_id}")
        await new_channel.send(content=f"{member.mention} {staff_mentions}", embed=embed, view=TicketControlView())

        await interaction.followup.send(f"✅ تحلق الـ ticket ديالك: {new_channel.mention}", ephemeral=True)


async def setup_tickets_panel(guild: discord.Guild):
    if not TICKETS_PANEL_CHANNEL_ID:
        return
    channel = bot.get_channel(TICKETS_PANEL_CHANNEL_ID)
    if not channel:
        return
    async for message in channel.history(limit=10):
        if message.author == bot.user and message.components:
            return
    embed = discord.Embed(
        title="🎫 الدعم / Support",
        description=(
            "عندك مشكل، سؤال، ولا بغيتي تبلغ عن شي حاجة بطريقة خاصة؟\n"
            "اضغط على الزر تحت وغادي يتحلق ليك channel خاص بيك وبالإدارة غير حتى."
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Ticket System")
    await channel.send(embed=embed, view=TicketPanelView())


@bot.hybrid_command(name="setuptickets")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setuptickets_cmd(ctx):
    """كيصاوب/يعاود يصاوب رسالة اللوحة ديال Tickets فـ TICKETS_PANEL_CHANNEL_ID (Admin)"""
    if not TICKETS_PANEL_CHANNEL_ID:
        await ctx.send("❌ حط `TICKETS_PANEL_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
        return
    if not TICKETS_CATEGORY_ID:
        await ctx.send("⚠️ `TICKETS_CATEGORY_ID` فارغة — الزر غايبان ولكن ما غاديش يخدم حتى تحطها.", delete_after=10)
    await setup_tickets_panel(ctx.guild)
    await ctx.send("✅ رسالة اللوحة ديال Tickets تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)


# ═══════════════════════════════════════════════════════
# ║   Phase 7 — نظام Applications (طلبات الانضمام للإدارة)  ║
# ═══════════════════════════════════════════════════════

def _is_staff_reviewer(member: discord.Member) -> bool:
    """كيتأكد بلي العضو عندو صلاحية يقبل/يرفض اقتراحات (Owner + الأدوار المعفية، شامل Moderators)"""
    if OWNER_ID and member.id == OWNER_ID:
        return True
    return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)


def _is_application_reviewer(member: discord.Member) -> bool:
    """كيتأكد بلي العضو عندو صلاحية يقبل/يرفض طلبات Applications — Owner
    و APPLICATIONS_REVIEWER_ROLE_IDS (Admins) بوحدهم، Moderators ماشي معنيين."""
    if OWNER_ID and member.id == OWNER_ID:
        return True
    return any(role.id in APPLICATIONS_REVIEWER_ROLE_IDS for role in member.roles)


class ApplicationModal(discord.ui.Modal, title="📋 طلب انضمام لفريق الإدارة"):
    age = discord.ui.TextInput(label="شحال عندك من عام؟", placeholder="مثلا: 18", max_length=10)
    experience = discord.ui.TextInput(
        label="عندك تجربة سابقة كموديراتور/أدمن؟",
        style=discord.TextStyle.paragraph, required=False, max_length=500,
        placeholder="اكتب 'لا' إلا ماعندكش، ولا فين ومنين إلا عندك"
    )
    why = discord.ui.TextInput(
        label="علاش بغيتي تكون Staff فهاد السيرفر؟",
        style=discord.TextStyle.paragraph, max_length=700
    )
    availability = discord.ui.TextInput(
        label="فوقاش/شحال من ساعة كتكون متواجد؟",
        max_length=150, placeholder="مثلا: كل نهار من 6 مغرب لـ 11 ليل"
    )

    async def on_submit(self, interaction: discord.Interaction):
        applicant = interaction.user
        app_id = applications_db.get("next_id", 1)

        review_channel_id = APPLICATIONS_REVIEW_CHANNEL_ID or MOD_LOGS_CHANNEL_ID
        review_channel = bot.get_channel(review_channel_id) if review_channel_id else None
        if not review_channel:
            await interaction.response.send_message(
                "❌ وقع مشكل تقني (channel المراجعة ماعادش معطي)، بلغ الإدارة.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 طلب انضمام #{app_id}",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.set_author(name=str(applicant), icon_url=applicant.display_avatar.url)
        embed.add_field(name="👤 المتقدم", value=applicant.mention, inline=False)
        embed.add_field(name="🎂 العمر", value=self.age.value or "—", inline=True)
        embed.add_field(name="🕐 التواجد", value=self.availability.value or "—", inline=True)
        embed.add_field(name="📜 تجربة سابقة", value=self.experience.value or "بلا تجربة", inline=False)
        embed.add_field(name="💬 علاش بغيتي تكون Staff", value=self.why.value, inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Application #{app_id} | Pending")

        reviewer_mentions = " ".join(f"<@&{rid}>" for rid in APPLICATIONS_REVIEWER_ROLE_IDS)
        try:
            review_msg = await review_channel.send(
                content=reviewer_mentions or None, embed=embed, view=ApplicationReviewView()
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ خطأ فـ بعث الطلب: {e}", ephemeral=True)
            return

        applications_db["next_id"] = app_id + 1
        applications_db.setdefault("applications", {})[str(app_id)] = {
            "applicant_id": applicant.id,
            "answers": {
                "age": self.age.value, "experience": self.experience.value,
                "why": self.why.value, "availability": self.availability.value,
            },
            "status": "pending",
            "review_message_id": review_msg.id,
            "review_channel_id": review_msg.channel.id,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "decided_by": None,
            "decided_at": None,
        }
        save_applications()

        await interaction.response.send_message(
            f"✅ تم بعث طلبك (#{app_id})! غادي تجاوبك الإدارة بالـ DM ملي يشوفو فيه.", ephemeral=True
        )


class ApplicationPanelView(discord.ui.View):
    """زر واحد "📋 قدم طلب" — كيحل Modal للعضو باش يعمر معلوماتو. Persistent
    (timeout=None) باش يبقى خدام حتى بعد ريستارت البوت."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 قدم طلب Staff", style=discord.ButtonStyle.primary, custom_id="open_application_button")
    async def open_application_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return

        pending_id, _ = get_pending_application_for_user(member.id)
        if pending_id:
            await interaction.response.send_message(
                f"⚠️ عندك ديجا طلب مبعوث (#{pending_id}) مازال كيتسنى المراجعة.", ephemeral=True
            )
            return

        remaining = application_cooldown_remaining(member.id)
        if remaining:
            hours_left = int(remaining.total_seconds() // 3600) + 1
            await interaction.response.send_message(
                f"⏳ طلبك السابق تُرفض، خاصك تصبر تقريباً {hours_left} ساعة قبل ما تعاود تقدم.", ephemeral=True
            )
            return

        await interaction.response.send_modal(ApplicationModal())


class ApplicationReviewView(discord.ui.View):
    """أزرار القبول/الرفض جوة review channel. Persistent — كتلقى الطلب بواسطة
    message id ديال الرسالة اللي فيها الأزرار (بحال TicketControlView كيلقى
    الـ ticket بواسطة channel id)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success, custom_id="app_accept_button")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=True)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger, custom_id="app_reject_button")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=False)

    async def _decide(self, interaction: discord.Interaction, accepted: bool):
        member = interaction.user
        if not isinstance(member, discord.Member) or not _is_application_reviewer(member):
            await interaction.response.send_message("❌ هاد الزر خاص غير بـ Owner والـ Admins.", ephemeral=True)
            return

        app_id, record = find_application_by_message_id(interaction.message.id)
        if not record:
            await interaction.response.send_message("❌ ماكاينش هاد الطلب فالسجل ديالنا.", ephemeral=True)
            return
        if record.get("status") != "pending":
            await interaction.response.send_message("⚠️ هاد الطلب تدار فيه قرار من قبل.", ephemeral=True)
            return

        record["status"] = "accepted" if accepted else "rejected"
        record["decided_by"] = member.id
        record["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not accepted:
            applications_db.setdefault("last_rejected", {})[str(record["applicant_id"])] = record["decided_at"]
        save_applications()

        guild = interaction.guild
        applicant = guild.get_member(record["applicant_id"]) if guild else None

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green() if accepted else discord.Color.red()
        embed.add_field(
            name="✅ القرار" if accepted else "❌ القرار",
            value=f"{'تقبل' if accepted else 'تُرفض'} من طرف {member.mention}",
            inline=False
        )
        embed.set_footer(text=f"{SERVER_NAME} | Application #{app_id} | {'Accepted' if accepted else 'Rejected'}")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

        if applicant:
            try:
                if accepted:
                    if APPLICATION_ACCEPTED_ROLE_ID:
                        role = guild.get_role(APPLICATION_ACCEPTED_ROLE_ID)
                        if role:
                            await applicant.add_roles(role, reason=f"Application #{app_id} تقبل")
                    await applicant.send(
                        f"🎉 مبروك! طلبك (#{app_id}) باش تكون Staff فـ **{SERVER_NAME}** تقبل! "
                        f"الإدارة غادي تتواصل معاك قريب."
                    )
                else:
                    await applicant.send(
                        f"❌ طلبك (#{app_id}) باش تكون Staff فـ **{SERVER_NAME}** تُرفض هاد المرة. "
                        f"تقدر تعاود تقدم من بعد {APPLICATIONS_COOLDOWN_HOURS} ساعة."
                    )
            except Exception:
                pass

        if guild:
            await log_action(
                guild,
                f"📋 Application #{app_id} — {'قبول' if accepted else 'رفض'}",
                f"**المتقدم:** <@{record['applicant_id']}>\n**القرار من طرف:** {member.mention}",
                discord.Color.green() if accepted else discord.Color.red()
            )


async def setup_applications_panel(guild: discord.Guild):
    if not APPLICATIONS_PANEL_CHANNEL_ID:
        return
    channel = bot.get_channel(APPLICATIONS_PANEL_CHANNEL_ID)
    if not channel:
        return
    async for message in channel.history(limit=10):
        if message.author == bot.user and message.components:
            return
    embed = discord.Embed(
        title="📋 قدم لفريق الإدارة",
        description=(
            "بغيتي تكون جزء من فريق الإدارة ديال السيرفر؟ اضغط على الزر تحت وعمر الاستمارة.\n"
            "غادي تجاوبك الإدارة بالـ DM ملي يشوفو الطلب ديالك."
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Staff Applications")
    await channel.send(embed=embed, view=ApplicationPanelView())


@bot.hybrid_command(name="setupapplications")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setupapplications_cmd(ctx):
    """كيصاوب/يعاود يصاوب رسالة اللوحة ديال Applications فـ APPLICATIONS_PANEL_CHANNEL_ID (Admin)"""
    if not APPLICATIONS_PANEL_CHANNEL_ID:
        await ctx.send("❌ حط `APPLICATIONS_PANEL_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
        return
    if not APPLICATIONS_REVIEW_CHANNEL_ID:
        await ctx.send("⚠️ `APPLICATIONS_REVIEW_CHANNEL_ID` فارغة — غايستعمل MOD_LOGS_CHANNEL_ID بدلها.", delete_after=10)
    await setup_applications_panel(ctx.guild)
    await ctx.send("✅ رسالة اللوحة ديال Applications تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)


@bot.hybrid_command(name="applications")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def applications_cmd(ctx):
    """كيبين لائحة الطلبات اللي مازال Pending (Owner + Admins فقط)"""
    if not _is_application_reviewer(ctx.author):
        await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admins.", delete_after=5)
        return
    pending = [
        (app_id, r) for app_id, r in applications_db.get("applications", {}).items()
        if r.get("status") == "pending"
    ]
    if not pending:
        await ctx.send("✅ ماكاين حتى طلب معلق دابا.")
        return
    lines = [f"**#{app_id}** — <@{r['applicant_id']}> (بعث فـ {r.get('submitted_at', '—')})"
              for app_id, r in sorted(pending, key=lambda x: int(x[0]))]
    embed = discord.Embed(
        title=f"📋 الطلبات المعلقة ({len(pending)})",
        description="\n".join(lines),
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Applications")
    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║   Phase 7 — نظام Suggestions (اقتراحات الأعضاء)         ║
# ═══════════════════════════════════════════════════════

class SuggestionReviewView(discord.ui.View):
    """أزرار قبول/رفض الاقتراح، بنفس المنطق ديال ApplicationReviewView. Persistent."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ مقبول", style=discord.ButtonStyle.success, custom_id="suggestion_accept_button")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=True)

    @discord.ui.button(label="❌ مرفوض", style=discord.ButtonStyle.danger, custom_id="suggestion_reject_button")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=False)

    async def _decide(self, interaction: discord.Interaction, accepted: bool):
        member = interaction.user
        if not isinstance(member, discord.Member) or not _is_staff_reviewer(member):
            await interaction.response.send_message("❌ هاد الزر خاص غير بالإدارة.", ephemeral=True)
            return

        sug_id, record = find_suggestion_by_message_id(interaction.message.id)
        if not record:
            await interaction.response.send_message("❌ ماكاينش هاد الاقتراح فالسجل ديالنا.", ephemeral=True)
            return
        if record.get("status") != "pending":
            await interaction.response.send_message("⚠️ هاد الاقتراح تدار فيه قرار من قبل.", ephemeral=True)
            return

        record["status"] = "accepted" if accepted else "rejected"
        record["decided_by"] = member.id
        record["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_suggestions()

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green() if accepted else discord.Color.red()
        embed.set_footer(
            text=f"{SERVER_NAME} | Suggestion #{sug_id} | "
                 f"{'✅ Accepted' if accepted else '❌ Rejected'} من طرف {member.display_name}"
        )
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

        guild = interaction.guild
        author = guild.get_member(record["author_id"]) if guild else None
        if author:
            try:
                if accepted:
                    await author.send(f"🎉 الاقتراح ديالك (#{sug_id}) تقبل من طرف الإدارة فـ **{SERVER_NAME}**!")
                else:
                    await author.send(f"❌ الاقتراح ديالك (#{sug_id}) تُرفض هاد المرة فـ **{SERVER_NAME}**.")
            except Exception:
                pass


# ═══════════════════════════════════════════════════════
# ║              🧠 Trivia — لعبة أسئلة ثقافة عامة          ║
# ═══════════════════════════════════════════════════════

class TriviaView(discord.ui.View):
    """أزرار الأجوبة ديال سؤال Trivia. أول واحد يكليكي على الجواب الصحيح كيربح XP.
    ماشي Persistent (timeout محدد) حيت كل سؤال مرتبط بمثيل واحد ديال هاد الـ View."""

    def __init__(self, correct_answer: str, options: list, reward: int, timeout_seconds: int):
        super().__init__(timeout=timeout_seconds)
        self.correct_answer = correct_answer
        self.reward = reward
        self.answered_users = set()
        self.winner = None
        self.message: Optional[discord.Message] = None

        for option in options:
            btn = discord.ui.Button(label=option[:80], style=discord.ButtonStyle.secondary)
            btn.callback = self._make_callback(option)
            self.add_item(btn)

    def _make_callback(self, option_text: str):
        async def callback(interaction: discord.Interaction):
            if self.winner:
                await interaction.response.send_message("⏱️ هاد السؤال تسالا ديجا، استنى السؤال الجاي!", ephemeral=True)
                return
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message("❌ درتي جواب ديجا فهاد السؤال — استنى السؤال الجاي.", ephemeral=True)
                return
            self.answered_users.add(interaction.user.id)

            if option_text != self.correct_answer:
                await interaction.response.send_message("❌ جواب غالط، جرب مرة أخرى!", ephemeral=True)
                return

            self.winner = interaction.user
            for child in self.children:
                child.disabled = True
                if isinstance(child, discord.ui.Button) and child.label == self.correct_answer[:80]:
                    child.style = discord.ButtonStyle.success
            self.stop()

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"🎉 {interaction.user.mention} جاوب صحيح! الجواب هو **{self.correct_answer}** (+{self.reward} XP)"
            )
            if interaction.guild:
                await grant_xp_and_announce(interaction.user, interaction.guild, self.reward,
                                            fallback_channel=interaction.channel, source="trivia")
                bump_trivia_score(interaction.guild.id, interaction.user.id)
                add_trivia_xp(interaction.guild.id, interaction.user.id, self.reward)

        return callback

    async def on_timeout(self):
        if self.winner or not self.message:
            return
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
            await self.message.reply(
                f"⏱️ خلص الوقت! حتى واحد ما جاوب صحيح. الجواب الصحيح كان: **{self.correct_answer}**",
                mention_author=False
            )
        except discord.HTTPException:
            pass


async def send_trivia_question(channel: discord.abc.Messageable, category: str = None):
    """كتجيب سؤال بالدارجة وتبعثو فـ channel معينة، بـ view ديال الأجوبة.
    مستعملة من الأمر /trivia ومن الـ loop التلقائي."""
    cat = category if category in TRIVIA_CATEGORIES else random.choice(list(TRIVIA_CATEGORIES))
    difficulty = random.choice(["easy", "medium", "medium", "hard"])
    q = await get_darija_question(cat, difficulty, set())
    if not q:
        return None

    embed = discord.Embed(
        title="🧠 Trivia — سؤال ثقافة عامة",
        description=f"**{q['question']}**",
        color=discord.Color.teal(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📚 المجال", value=q["category"], inline=True)
    embed.add_field(name="🎯 الصعوبة", value=TRIVIA_DIFFICULTY_LABELS.get(q["difficulty"], q["difficulty"]), inline=True)
    embed.set_footer(text=f"عندك {TRIVIA_ANSWER_SECONDS} ثانية — أول واحد يجاوب صحيح ياخد +{get_trivia_single_xp()} XP")

    view = TriviaView(q["correct"], q["options"], get_trivia_single_xp(), TRIVIA_ANSWER_SECONDS)
    msg = await channel.send(embed=embed, view=view)
    view.message = msg
    return msg


# ═══════════════════════════════════════════════════════
# ║   Trivia — panel دائم فـ channel خاص (صعوبة متصاعدة)   ║
# ═══════════════════════════════════════════════════════

TRIVIA_DIFFICULTY_LABELS = {
    "easy": "🟢 ساهل",
    "medium": "🟡 متوسط",
    "hard": "🔴 صعيب",
}


def get_trivia_difficulty(round_num: int) -> str:
    if round_num <= TRIVIA_ROUNDS_PER_DIFFICULTY:
        return "easy"
    elif round_num <= TRIVIA_ROUNDS_PER_DIFFICULTY * 2:
        return "medium"
    return "hard"


def build_trivia_session_embed(question_text: str, options: list, category_label: str, difficulty: str,
                               round_num: int, streak: int, expires_at: datetime,
                               prefix: str = "") -> discord.Embed:
    reward = get_trivia_xp(difficulty)
    letters = ["🇦", "🇧", "🇨", "🇩"]
    options_text = "\n".join(f"{letters[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(
        title=f"🧠 Trivia — سؤال #{round_num}",
        description=f"{prefix}**{question_text}**\n\n{options_text}",
        color=discord.Color.teal(),
    )
    embed.add_field(name="📚 المجال", value=category_label, inline=True)
    embed.add_field(name="🎯 الصعوبة", value=TRIVIA_DIFFICULTY_LABELS.get(difficulty, difficulty), inline=True)
    embed.add_field(name="🔥 السلسلة", value=f"{streak} صحيح متتالي", inline=True)
    embed.add_field(name="⏱️ الوقت", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
    embed.set_footer(text=f"جاوب صحيح تربح +{reward} XP")
    return embed


class TriviaReplayView(discord.ui.View):
    """زر 'العب مرة أخرى' فآخر الجلسة — كيرجع لاختيار المجال بلا ما يحتاج العضو يرجع لـ channel."""

    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.button(label="🔄 العب مرة أخرى", style=discord.ButtonStyle.success)
    async def replay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد اللعبة ماشي ديالك.", ephemeral=True)
            return
        view = TriviaCategorySelectView(self.user)
        await interaction.response.edit_message(
            content="📚 شنو المجال لي بغيتي تلعب فيه؟", embed=None, view=view
        )


class TriviaSessionView(discord.ui.View):
    """جلسة لعب فردية (ephemeral، غير صاحبها كيشوفها): كل ما جاوب صحيح، كيجي سؤال جديد
    أصعب وبـ XP أكثر، حتى يغلط ولا يخلص الوقت.

    🇲🇦 كاع الأسئلة والأجوبة كيبانو بالدارجة مباشرة — ماكاينش شي قائمة ديال اللغات
    وماكاينش انتظار ديال الترجمة.

    ⏱️ الوقت كيتحسب بـ watchdog يدوي (asyncio.sleep) مربوط بـ self.expires_at الثابتة —
    ماشي بـ discord.py timeout العادي (timeout=None).

    ⚠️ ملاحظة تقنية مهمة: الرسالة ephemeral، وDiscord ماكيسمحش تعدلها بـ message.edit().
    علاش كنحتافظو بآخر Interaction وكنعدلو بـ interaction.edit_original_response() —
    هادشي هو اللي كان خلي شاشة «سالا الوقت» ماكتبانش فالنسخة القديمة."""

    def __init__(self, user: discord.abc.User, category: str, round_num: int, streak: int,
                 question: dict, interaction: discord.Interaction,
                 used_keys: Optional[set] = None, token: Optional[str] = None,
                 session_xp: int = 0, correct_by_difficulty: Optional[dict] = None):
        super().__init__(timeout=None)   # كنعطلو الـ timeout الأوتوماتيكي، وكنديرو واحد يدوي تحت
        self.user = user
        self.category = category
        self.round_num = round_num
        self.streak = streak
        self.token = token
        self.interaction = interaction          # ← آخر interaction، بيه كنعدلو الرسالة ephemeral
        self.used_keys = used_keys if used_keys is not None else set()
        self.ended = False

        # ═══ تتبع الربح ديال هاد الجولة (باش نوريوه ملي يخسر) ═══
        self.session_xp = session_xp
        self.correct_by_difficulty = correct_by_difficulty or {"easy": 0, "medium": 0, "hard": 0}

        self.question_text = question["question"]
        self.options = list(question["options"])
        self.correct_index = self.options.index(question["correct"])
        self.difficulty = question["difficulty"]
        self.category_label = question.get("category", TRIVIA_CATEGORY_LABELS.get(category, category))
        if question.get("key"):
            self.used_keys.add(question["key"])

        self.expires_at = datetime.now() + timedelta(seconds=TRIVIA_ANSWER_SECONDS)
        self._build_components()
        self._watchdog_task = asyncio.create_task(self._watchdog())

    def build_embed(self, prefix: str = "") -> discord.Embed:
        return build_trivia_session_embed(
            self.question_text, self.options, self.category_label, self.difficulty,
            self.round_num, self.streak, self.expires_at, prefix=prefix
        )

    def build_summary(self, title: str, top_text: str, color: discord.Color,
                      guild: Optional[discord.Guild]) -> discord.Embed:
        """ملخص نهاية الجولة — كيبين شحال جمع من XP فهاد اللعبة، التفصيل حسب الصعوبة،
        والمجموع الدائم ديالو من Trivia كامل."""
        embed = discord.Embed(title=title, description=top_text, color=color)

        # ═══ الربح ديال هاد الجولة ═══
        breakdown = []
        for diff in ("easy", "medium", "hard"):
            n = self.correct_by_difficulty.get(diff, 0)
            if n:
                gained = n * get_trivia_xp(diff)
                breakdown.append(f"{TRIVIA_DIFFICULTY_LABELS[diff]} × {n} = **{gained}** XP")

        embed.add_field(
            name="💰 ربحتي فهاد الجولة",
            value=(
                f"**+{self.session_xp} XP**\n" + ("\n".join(breakdown) if breakdown else "*ماجاوبتي على حتى سؤال صحيح*")
            ),
            inline=True
        )
        embed.add_field(
            name="🎯 النتيجة",
            value=f"**{self.streak}** صحيح متتالي\n📚 {TRIVIA_CATEGORY_LABELS.get(self.category, self.category)}",
            inline=True
        )

        # ═══ المجموع الدائم ═══
        if guild:
            stats = finish_trivia_game(guild.id, self.user.id, self.streak)
            total_correct = trivia_scores.get(str(guild.id), {}).get(str(self.user.id), 0)
            record_line = "\n🏅 **رقم قياسي جديد ديالك!** 🎉" if stats["is_record"] else \
                          f"\n🥇 أحسن سلسلة ديالك: **{stats['best_streak']}**"
            embed.add_field(
                name="🏆 المجموع ديالك من Trivia",
                value=(
                    f"💎 **{stats['xp']}** XP إجمالي\n"
                    f"✅ **{total_correct}** جواب صحيح\n"
                    f"🎮 **{stats['games']}** جولة تلعبات"
                    f"{record_line}"
                ),
                inline=False
            )

        embed.set_footer(text="كليكي 🔄 باش تعاود من جديد")
        return embed

    async def _watchdog(self):
        """كيستنى بالضبط حتى الوقت ديال expires_at، وإلا حتى واحد ما جاوب، كيسالي اللعبة."""
        try:
            remaining = (self.expires_at - datetime.now()).total_seconds()
            if remaining > 0:
                await asyncio.sleep(remaining)
            if self.ended:
                return
            await self._end_session_timeout()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[TRIVIA] خطأ فـ watchdog: {e}")

    def _cancel_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

    def _build_components(self):
        self.clear_items()
        letters = ["🇦", "🇧", "🇨", "🇩"]
        for i, option in enumerate(self.options):
            btn = discord.ui.Button(
                label=f"{letters[i]} {option}"[:80],
                style=discord.ButtonStyle.secondary,
                row=i // 2
            )
            btn.callback = self._make_answer_callback(i)
            self.add_item(btn)

    def _disable_and_reveal(self):
        for i, child in enumerate(self.children):
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                if i == self.correct_index:
                    child.style = discord.ButtonStyle.success

    def _make_answer_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ هاد اللعبة ماشي ديالك.", ephemeral=True)
                return
            if self.ended:
                await interaction.response.defer()
                return

            self.ended = True
            self._cancel_watchdog()
            self.stop()
            self.interaction = interaction
            await interaction.response.defer()   # جلب السؤال الجاي + XP ممكن ياخدو أكثر من 3 ثواني

            # ═══ جواب غالط → سالات اللعبة ═══
            if index != self.correct_index:
                self._disable_and_reveal()
                embed = self.build_summary(
                    title="❌ جواب غالط — سالات اللعبة!",
                    top_text=f"الجواب الصحيح كان: **{self.options[self.correct_index]}**",
                    color=discord.Color.red(),
                    guild=interaction.guild
                )
                await interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.user))
                return

            # ═══ جواب صحيح ═══
            reward = get_trivia_xp(self.difficulty)
            self.session_xp += reward
            self.correct_by_difficulty[self.difficulty] = self.correct_by_difficulty.get(self.difficulty, 0) + 1
            if interaction.guild:
                await grant_xp_and_announce(interaction.user, interaction.guild, reward,
                                            fallback_channel=interaction.channel, source="trivia_panel")
                bump_trivia_score(interaction.guild.id, interaction.user.id)
                add_trivia_xp(interaction.guild.id, interaction.user.id, reward)

            next_round = self.round_num + 1
            next_streak = self.streak + 1
            next_q = await get_darija_question(
                self.category, get_trivia_difficulty(next_round), self.used_keys, self.token
            )

            if not next_q:
                self.streak = next_streak
                embed = self.build_summary(
                    title=f"🎉 صحيح! سالاو الأسئلة ديال هاد المجال",
                    top_text=(
                        f"وصلتي لـ **{next_streak}** سؤال صحيح متتالي وكملتي المجال كامل! 🔥\n"
                        f"جرب مجال آخر باش تكمل تجمع."
                    ),
                    color=discord.Color.gold(),
                    guild=interaction.guild
                )
                await interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.user))
                return

            new_view = TriviaSessionView(
                self.user, self.category, next_round, next_streak, next_q,
                interaction, self.used_keys, self.token,
                session_xp=self.session_xp, correct_by_difficulty=self.correct_by_difficulty
            )
            await interaction.edit_original_response(
                embed=new_view.build_embed(
                    prefix=f"✅ صحيح! (+{reward} XP) — مجموعك فهاد الجولة: **{self.session_xp} XP**\n\n"
                ),
                view=new_view
            )

        return callback

    async def _end_session_timeout(self):
        self.ended = True
        self.stop()
        funny_lines = [
            "حاول مرة أخرى! ⏱️",
            "معرفتيش لعيبة بحالك 😅 جرب عاود!",
            "الوقت هرب منك هاد المرة، عاود الكرة!",
        ]
        guild = self.interaction.guild if self.interaction else None
        embed = self.build_summary(
            title="⏱️ سالا الوقت!",
            top_text=(
                f"الجواب الصحيح كان: **{self.options[self.correct_index]}**\n\n"
                f"{random.choice(funny_lines)}"
            ),
            color=discord.Color.orange(),
            guild=guild
        )
        try:
            await self.interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.user))
        except (discord.HTTPException, discord.NotFound) as e:
            print(f"[TRIVIA] ماقدرتش نعدل رسالة نهاية الوقت: {e}")


class TriviaCategorySelectView(discord.ui.View):
    """Select menu باش يختار المجال قبل ما تبدا الجلسة.
    ⚡ دابا السؤال كيجي من البنك المحلي بالدارجة → فوري، بلا API، بلا rate limit."""

    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.select(
        placeholder="📚 اختار المجال لي بغيتي الأسئلة ديالو...",
        min_values=1, max_values=1,
        options=[discord.SelectOption(label=TRIVIA_CATEGORY_LABELS[c], value=c) for c in TRIVIA_CATEGORIES]
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد الاختيار ماشي ديالك.", ephemeral=True)
            return

        await interaction.response.defer()
        self.stop()

        category = select.values[0]
        used_keys = set()
        q = await get_darija_question(category, "easy", used_keys)

        if not q:
            await interaction.edit_original_response(
                content="❌ ما قدرتش نجيب سؤال دابا، جرب مجال آخر ولا عاود من بعد شوية.",
                embed=None, view=None
            )
            return

        view = TriviaSessionView(self.user, category, 1, 0, q, interaction, used_keys)
        await interaction.edit_original_response(content=None, embed=view.build_embed(), view=view)


class TriviaGamePanelView(discord.ui.View):
    """الزر الدائم فـ channel اللعبة. Persistent."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 ابدأ اللعب", style=discord.ButtonStyle.success, custom_id="trivia_start_game_button")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not TRIVIA_ENABLED:
            await interaction.response.send_message("❌ لعبة Trivia معطلة دابا.", ephemeral=True)
            return
        view = TriviaCategorySelectView(interaction.user)
        await interaction.response.send_message("📚 شنو المجال لي بغيتي تلعب فيه؟", view=view, ephemeral=True)


async def setup_trivia_panel(guild: discord.Guild, channel: Optional[discord.abc.Messageable] = None,
                             force: bool = False):
    """كيبعث رسالة الشرح + زر البداية فـ channel اللعبة.
    إلا ماعطيتيش channel، كيستعمل TRIVIA_CHANNEL_ID."""
    if channel is None:
        if not TRIVIA_CHANNEL_ID:
            return False
        channel = bot.get_channel(TRIVIA_CHANNEL_ID)
    if not channel:
        return False

    if not force:
        async for message in channel.history(limit=15):
            if message.author == bot.user and message.embeds and message.embeds[0].title and "Trivia" in message.embeds[0].title:
                return True

    total_questions = sum(
        len(qs) for diffs in TRIVIA_DARIJA_BANK.values() for qs in diffs.values()
    )
    embed = discord.Embed(
        title="🧠 مرحبا بيك فـ لعبة Trivia",
        description="اختبر معلوماتك وربح XP! كليكي على الزر تحت، اختار المجال لي بغيتي، وابدا تجاوب على الأسئلة.",
        color=discord.Color.teal(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="🎯 كيفاش كتخدم",
        value=(
            "1️⃣ كليكي **🎮 ابدأ اللعب** تحت\n"
            f"2️⃣ اختار المجال لي بغيتي (من {len(TRIVIA_CATEGORIES)} مجالات)\n"
            f"3️⃣ جاوب على الأسئلة — عندك {TRIVIA_ANSWER_SECONDS} ثانية لكل سؤال\n"
            "4️⃣ كل ما جاوبتي صحيح، الأسئلة كتزاد صعوبة وXP كتزاد معاها — حتى تغلط ولا يخلص الوقت!"
        ),
        inline=False
    )
    embed.add_field(
        name="🇲🇦 كلشي بالدارجة",
        value=(
            f"كاع الأسئلة والأجوبة مكتوبين بالدارجة المغربية من الأصل ({total_questions} سؤال) — "
            "بلا ترجمة، بلا انتظار، وكيبانو ليك فالحين ملي تختار المجال."
        ),
        inline=False
    )
    embed.add_field(
        name="💰 شحال XP كتربح",
        value=(
            f"🟢 سهل: **{get_trivia_xp('easy')}** XP\n"
            f"🟡 متوسط: **{get_trivia_xp('medium')}** XP\n"
            f"🔴 صعيب: **{get_trivia_xp('hard')}** XP\n"
            "(غلطة وحدة كتوقف السلسلة وخاصك تبدا من جديد)"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | Trivia Game")
    try:
        await channel.send(embed=embed, view=TriviaGamePanelView())
        return True
    except discord.HTTPException as e:
        print(f"[TRIVIA] ما قدرتش نبعث panel: {e}")
        return False


@bot.hybrid_command(name="setuptrivia", description="كيصاوب panel لعبة Trivia فالـ channel الحالي (Admin)")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setuptrivia_cmd(ctx):
    """كيصاوب panel لعبة Trivia. إلا TRIVIA_CHANNEL_ID = 0، كيصاوبو فالـ channel
    اللي درتي فيها الأمر — يعني ماعندكش علاش تبدل الـ CONFIG (Admin)"""
    target = bot.get_channel(TRIVIA_CHANNEL_ID) if TRIVIA_CHANNEL_ID else ctx.channel
    if not target:
        await ctx.send("❌ ما لقيتش الـ channel ديال Trivia — تأكد من `TRIVIA_CHANNEL_ID`.", delete_after=10)
        return
    ok = await setup_trivia_panel(ctx.guild, channel=target, force=True)
    if ok:
        await ctx.send(f"✅ panel لعبة Trivia تصاوب فـ {target.mention}.", delete_after=8)
    else:
        await ctx.send("❌ ما قدرتش نصاوب الـ panel — شوف الصلاحيات ديال البوت فهاد الـ channel.", delete_after=10)


@bot.hybrid_command(name="trivia", description="لعبة أسئلة ثقافة عامة — جاوب صحيح وربح XP!")
@app_commands.describe(category="اختياري: فئة السؤال")
@app_commands.choices(category=[
    app_commands.Choice(name="🌍 ثقافة عامة", value="general"),
    app_commands.Choice(name="🔬 علوم", value="science"),
    app_commands.Choice(name="⚽ رياضة", value="sports"),
    app_commands.Choice(name="📜 تاريخ", value="history"),
    app_commands.Choice(name="🗺️ جغرافيا", value="geography"),
    app_commands.Choice(name="🎬 أفلام", value="movies"),
    app_commands.Choice(name="🎵 موسيقى", value="music"),
    app_commands.Choice(name="🎮 ألعاب فيديو", value="games"),
    app_commands.Choice(name="📺 أنمي ومانغا", value="anime"),
])
async def trivia_cmd(ctx, category: Optional[str] = None):
    if not TRIVIA_ENABLED:
        await ctx.send("❌ لعبة Trivia معطلة دابا.", delete_after=6)
        return
    result = await send_trivia_question(ctx.channel, category)
    if not result:
        await ctx.send("❌ ما قدرتش نجيب سؤال دابا (مشكل فـ OpenTDB)، جرب مرة أخرى بعد شوية.", delete_after=8)


@bot.hybrid_command(name="triviatop", aliases=["trivialb"], description="أفضل 10 أعضاء فـ Trivia (الأكثر إجابات صحيحة)")
async def triviatop_cmd(ctx):
    guild_scores = trivia_scores.get(str(ctx.guild.id), {})
    guild_xp = trivia_xp_totals.get(str(ctx.guild.id), {})
    if not guild_scores and not guild_xp:
        await ctx.send("ماكاين حتى عضو جاوب صحيح فـ Trivia دابا — كون أول واحد بـ `/trivia`!")
        return

    # كنرتبو بـ XP (وإلا ماكاينش، بعدد الأجوبة الصحيحة)
    all_ids = set(guild_scores) | set(guild_xp)
    def _xp(uid):
        return int(guild_xp.get(uid, {}).get("xp", 0))
    ranked = sorted(all_ids, key=lambda u: (_xp(u), guild_scores.get(u, 0)), reverse=True)[:10]

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, user_id in enumerate(ranked):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"عضو غادر ({user_id})"
        prefix = medals[i] if i < 3 else f"#{i + 1}"
        correct = guild_scores.get(user_id, 0)
        stats = guild_xp.get(user_id, {})
        best = int(stats.get("best_streak", 0))
        lines.append(
            f"{prefix} **{name}** — 💎 {_xp(user_id)} XP • ✅ {correct} صحيح"
            + (f" • 🔥 أحسن سلسلة {best}" if best else "")
        )

    embed = discord.Embed(
        title="🧠 أفضل 10 فـ Trivia",
        description="\n".join(lines),
        color=discord.Color.teal(),
        timestamp=datetime.now()
    )
    # الإحصائيات الشخصية ديال اللي طلب الأمر
    me = get_trivia_stats(ctx.guild.id, ctx.author.id)
    if me["games"] or me["xp"]:
        embed.add_field(
            name="👤 أنت",
            value=(
                f"💎 **{me['xp']}** XP • ✅ **{guild_scores.get(str(ctx.author.id), 0)}** صحيح • "
                f"🎮 **{me['games']}** جولة • 🔥 أحسن سلسلة **{me['best_streak']}**"
            ),
            inline=False
        )
    embed.set_footer(text=f"{SERVER_NAME} | Trivia Leaderboard")
    await ctx.send(embed=embed)


@tasks.loop(minutes=TRIVIA_AUTO_INTERVAL_MINUTES)
async def trivia_auto_loop():
    if not TRIVIA_ENABLED or not TRIVIA_AUTO_CHANNEL_IDS:
        return
    for channel_id in TRIVIA_AUTO_CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await send_trivia_question(channel)
            except Exception as e:
                print(f"[TRIVIA] خطأ فـ trivia_auto_loop لـ channel {channel_id}: {e}")


@trivia_auto_loop.before_loop
async def before_trivia_auto_loop():
    await bot.wait_until_ready()


@trivia_auto_loop.error
async def trivia_auto_loop_error(error):
    print(f"[TRIVIA] خطأ كبير وقف trivia_auto_loop: {error}")


# ═══════════════════════════════════════════════════════
# ║   🔎 /aicheck — تشيك مباشر على الموديل والرصيد ديال OpenRouter   ║
# ═══════════════════════════════════════════════════════

async def test_single_model(model: str) -> tuple:
    """كيجرب موديل واحد بالضبط (بلا fallback) بسؤال صغير بزاف.
    كيرجع (نجح?, وصف, الوقت بالثواني)."""
    if not OPENROUTER_API_KEY:
        return False, "ماكاينش OPENROUTER_API_KEY فـ الـ environment", 0.0

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 20,
        "temperature": 0,
    }
    if AI_DISABLE_REASONING:
        payload["reasoning"] = {"enabled": False, "exclude": True}

    start = asyncio.get_event_loop().time()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                took = asyncio.get_event_loop().time() - start
                body = await resp.text()
                if resp.status != 200:
                    short = body[:120].replace("\n", " ")
                    return False, f"HTTP {resp.status} — {short}", took
                data = json.loads(body)
                msg = data.get("choices", [{}])[0].get("message", {}) or {}
                content = (msg.get("content") or msg.get("reasoning") or "").strip()
                if not content:
                    return False, "رجع رد فارغ (reasoning صرف كاع الـ tokens)", took
                return True, content[:60], took
    except asyncio.TimeoutError:
        return False, "Timeout (تعدا 25 ثانية)", 25.0
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:120], asyncio.get_event_loop().time() - start


async def get_openrouter_credits() -> Optional[dict]:
    """كيجيب الرصيد الحقيقي من OpenRouter."""
    if not OPENROUTER_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = await fetch_json("https://openrouter.ai/api/v1/credits", headers=headers)
    return (data or {}).get("data")


@bot.hybrid_command(name="aicheck", description="تشيك واش الموديل ديال الـ AI والرصيد خدامين مزيان")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def aicheck_cmd(ctx):
    """كيدير تشيك حقيقي (ماشي نظري): كيبعث طلب فعلي للموديل المدفوع، كيقيس الوقت،
    كيجيب الرصيد اللي باقي، وكيجرب الترجمة للدارجة."""
    msg = await ctx.send("🔎 كنشيكي على OpenRouter... صبر شوية (تقريبا 30 ثانية).")

    lines = []

    # 1) الرصيد
    credits = await get_openrouter_credits()
    if credits:
        total = float(credits.get("total_credits", 0) or 0)
        used = float(credits.get("total_usage", 0) or 0)
        left = total - used
        lines.append(
            f"💳 **الرصيد**: خلصتي `${total:.2f}` — صرفتي `${used:.4f}` — "
            f"باقي ليك **`${left:.4f}`**"
        )
        # DeepSeek V4 Flash: $0.0983/M in, $0.1966/M out
        approx_msgs = int(left / 0.0004) if left > 0 else 0
        lines.append(f"   └ يعني تقريبا **{approx_msgs:,}** رد آخر بهاد الموديل 🎯")
    else:
        lines.append("💳 **الرصيد**: ما قدرتش نجيبو (تأكد من `OPENROUTER_API_KEY`)")

    # 2) الموديل الأساسي المدفوع
    ok, detail, took = await test_single_model(AI_MODEL)
    icon = "✅" if ok else "❌"
    lines.append(f"\n{icon} **الموديل الأساسي** `{AI_MODEL}`")
    lines.append(f"   └ {'خدام مزيان' if ok else 'ماخدامش'} — `{took:.2f}s` — {detail}")

    # 3) موديلات الاحتياط
    lines.append("\n🔁 **موديلات الاحتياط (المجانية):**")
    for fb in AI_MODEL_FALLBACKS:
        fok, fdetail, ftook = await test_single_model(fb)
        lines.append(f"   {'✅' if fok else '❌'} `{fb}` — `{ftook:.2f}s`" + ("" if fok else f" — {fdetail}"))

    # 4) تجربة الترجمة للدارجة
    test = await translate_question_to_darija(
        "What is the capital city of Japan?", ["Tokyo", "Osaka", "Kyoto", "Nagoya"]
    )
    if test:
        lines.append(f"\n🇲🇦 **الترجمة للدارجة**: ✅ خدامة\n   └ مثال: *{test[0]}*")
    else:
        lines.append("\n🇲🇦 **الترجمة للدارجة**: ❌ ماخدماش — ولكن اللعبة ماغاديش تتأثر "
                     "حيت الأسئلة ديال Trivia مكتوبة بالدارجة من الأصل.")

    # 5) بنك الأسئلة
    total_q = sum(len(qs) for diffs in TRIVIA_DARIJA_BANK.values() for qs in diffs.values())
    lines.append(f"\n🧠 **بنك أسئلة Trivia بالدارجة**: ✅ {total_q} سؤال فـ {len(TRIVIA_DARIJA_BANK)} مجالات "
                 f"(كيخدم بلا إنترنت وبلا فلوس)")

    embed = discord.Embed(
        title="🔎 تشيك على نظام الـ AI",
        description="\n".join(lines)[:4000],
        color=discord.Color.green() if ok else discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{SERVER_NAME} | AI Health Check")
    try:
        await msg.edit(content=None, embed=embed)
    except discord.HTTPException:
        await ctx.send(embed=embed)


@bot.hybrid_command(name="suggest")
async def suggest_cmd(ctx, *, idea: str):
    """كيبعث اقتراح جديد للإدارة، والأعضاء يقدرو يصوتو عليه بـ 👍/👎"""
    if not SUGGESTIONS_CHANNEL_ID:
        await ctx.send("❌ نظام الاقتراحات ماعادش معطي (`SUGGESTIONS_CHANNEL_ID` فارغة)، بلغ الإدارة.", delete_after=8)
        return
    channel = bot.get_channel(SUGGESTIONS_CHANNEL_ID)
    if not channel:
        await ctx.send("❌ ما لقيتش channel الاقتراحات، بلغ الإدارة.", delete_after=8)
        return

    sug_id = suggestions_db.get("next_id", 1)

    embed = discord.Embed(
        title=f"💡 اقتراح #{sug_id}",
        description=idea[:1000],
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"{SERVER_NAME} | Suggestion #{sug_id} | Pending")

    try:
        msg = await channel.send(embed=embed, view=SuggestionReviewView())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
    except Exception as e:
        await ctx.send(f"❌ خطأ فـ بعث الاقتراح: {e}", delete_after=8)
        return

    suggestions_db["next_id"] = sug_id + 1
    suggestions_db.setdefault("suggestions", {})[str(sug_id)] = {
        "author_id": ctx.author.id,
        "text": idea,
        "status": "pending",
        "message_id": msg.id,
        "channel_id": msg.channel.id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decided_by": None,
        "decided_at": None,
    }
    save_suggestions()

    if channel.id != ctx.channel.id:
        await ctx.send(f"✅ تم بعث الاقتراح ديالك (#{sug_id}) فـ {channel.mention}!", delete_after=8)
    else:
        await ctx.send(f"✅ تم بعث الاقتراح ديالك (#{sug_id})!", delete_after=5)


async def setup_suggestions_info(guild: discord.Guild):
    """كيبعث (مرة وحدة، أول مرة) رسالة تشرح لأعضاء channel الاقتراحات
    شنو يقدرو يقترحو وكيفاش، باش ما يبقاش الناس تايهين."""
    if not SUGGESTIONS_CHANNEL_ID:
        return
    channel = bot.get_channel(SUGGESTIONS_CHANNEL_ID)
    if not channel:
        return

    async for message in channel.history(limit=15):
        if message.author == bot.user and message.embeds and message.embeds[0].title and "الاقتراحات" in message.embeds[0].title:
            return  # الرسالة موجودة ديجا، ماخاصناش نبعثوها مرة أخرى

    embed = discord.Embed(
        title="💡 مرحبا بيك فـ channel الاقتراحات",
        description=(
            "هادي هي البلاصة فين تقدر تقترح أي فكرة باش نزيدو نطورو السيرفر سوا. "
            "كل اقتراح كيبان هنا وكيقدر كل واحد يصوت عليه بـ 👍/👎، والإدارة كتراجعو وكتقرر."
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="✅ شنو تقدر تقترح",
        value=(
            "• شي feature/أمر جديد تحب تزاد للبوت\n"
            "• شي channel/role جديد يفيد السيرفر\n"
            "• شي فعالية، مسابقة، ولا event تحب تشوفو\n"
            "• تعديل على القوانين ولا التنظيم ديال السيرفر\n"
            "• أي فكرة أخرى تحس بلي غادي تحسن السيرفر"
        ),
        inline=False
    )
    embed.add_field(
        name="🚫 شنو ماشي مكانو هنا",
        value=(
            "• مشكل تقني ولا بوغ فالبوت → دير Ticket بدل الاقتراح\n"
            "• شكاية على عضو معين ولا تبليغ → استعمل `/report`\n"
            "• طلب انضمام للإدارة → عندو channel خاص بيه (Applications)"
        ),
        inline=False
    )
    embed.add_field(
        name="📝 كيفاش تقترح؟",
        value=(
            "اكتب الأمر:\n"
            "`/suggest <الفكرة ديالك بالتفصيل>`\n\n"
            "مثال: `/suggest نزيدو channel خاص بالميمز`\n\n"
            "الاقتراح غادي يتبعث هنا أوتوماتيك، والأعضاء غايقدرو يصوتو عليه. "
            "كون واضح ومباشر باش الإدارة تفهم الفكرة بسرعة!"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | نظام الاقتراحات")
    await channel.send(embed=embed)


@bot.hybrid_command(name="setupsuggestions")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setupsuggestions_cmd(ctx):
    """كيصاوب/يعاود يصاوب رسالة الشرح ديال channel الاقتراحات فـ SUGGESTIONS_CHANNEL_ID (Admin)"""
    if not SUGGESTIONS_CHANNEL_ID:
        await ctx.send("❌ حط `SUGGESTIONS_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
        return
    await setup_suggestions_info(ctx.guild)
    await ctx.send("✅ رسالة الشرح ديال الاقتراحات تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)


# ═══════════════════════════════════════════════════════
# ║        Phase 8 — أوامر نظام Birthdays                   ║
# ═══════════════════════════════════════════════════════

@bot.hybrid_command(name="setbirthday")
async def setbirthday_cmd(ctx, day: int, month: int):
    """سجل عيد ميلادك (اليوم والشهر بوحدهم، بلا عام) — البوت غايعطيك رول البرج أوتوماتيكياً"""
    try:
        # كنستعملو عام كبيسة (2024) باش فبراير 29 يخدم زوين
        datetime(2024, month, day)
    except (ValueError, TypeError):
        await ctx.send("❌ التاريخ ماشي صحيح. اكتب مثلا `/setbirthday day:15 month:8`.", delete_after=8)
        return

    zodiac_key, zodiac_label, zodiac_emoji = get_zodiac_sign(day, month)

    birthdays_db.setdefault("birthdays", {})[str(ctx.author.id)] = {
        "day": day, "month": month, "last_announced_year": None, "zodiac": zodiac_key
    }
    save_birthdays()

    zodiac_note = ""
    if isinstance(ctx.author, discord.Member):
        await sync_zodiac_role(ctx.author, zodiac_key)
        if zodiac_key and ZODIAC_ROLE_IDS.get(zodiac_key):
            zodiac_note = f"\n{zodiac_emoji} عطيناك رول برج **{zodiac_label}**!"
        elif zodiac_key:
            zodiac_note = f"\n{zodiac_emoji} البرج ديالك هو **{zodiac_label}** (الرول ديالو ماعادش معطي فالإعدادات)."

    await ctx.send(
        f"🎂 تم تسجيل عيد ميلادك: **{day:02d}/{month:02d}**! غادي نهنيوك نهار عيد ميلادك.{zodiac_note}",
        delete_after=15
    )


@bot.hybrid_command(name="removebirthday")
async def removebirthday_cmd(ctx):
    """حيد عيد الميلاد ديالك من السجل (وكيحيد رول البرج زيادة)"""
    removed = birthdays_db.get("birthdays", {}).pop(str(ctx.author.id), None)
    if removed:
        save_birthdays()
        if isinstance(ctx.author, discord.Member):
            await sync_zodiac_role(ctx.author, None)  # كيحيد أي رول برج عندو بلا مايعطي جديد
        await ctx.send("🗑️ تم حيد عيد الميلاد ديالك من السجل.", delete_after=8)
    else:
        await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل أصلاً.", delete_after=8)


@bot.hybrid_command(name="birthday")
async def birthday_cmd(ctx, member: Optional[discord.Member] = None):
    """بين عيد الميلاد ديالك ولا ديال عضو آخر (والبرج ديالو)"""
    target = member or ctx.author
    record = birthdays_db.get("birthdays", {}).get(str(target.id))
    if not record:
        if target == ctx.author:
            await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل. استعمل `/setbirthday`.", delete_after=8)
        else:
            await ctx.send(f"⚠️ {target.mention} ماعندوش عيد ميلاد مسجل.", delete_after=8)
        return

    zodiac_key = record.get("zodiac")
    zodiac_line = ""
    if zodiac_key:
        _, zodiac_label, zodiac_emoji = get_zodiac_sign(record["day"], record["month"])
        zodiac_line = f"\n{zodiac_emoji} البرج: **{zodiac_label}**"
    await ctx.send(f"🎂 عيد ميلاد {target.mention}: **{record['day']:02d}/{record['month']:02d}**{zodiac_line}")


@bot.hybrid_command(name="birthdays")
async def birthdays_cmd(ctx):
    """بين لائحة أقرب 10 أعياد ميلاد جاية فالسيرفر"""
    today = datetime.now()
    today_date = today.date()
    entries = []
    for user_id, record in birthdays_db.get("birthdays", {}).items():
        member = ctx.guild.get_member(int(user_id)) if ctx.guild else None
        if not member:
            continue
        day, month = record["day"], record["month"]
        try:
            this_year_date = datetime(today.year, month, day).date()
        except ValueError:
            continue  # 29 فبراير فعام ماشي كبيسة
        next_date = this_year_date if this_year_date >= today_date else datetime(today.year + 1, month, day).date()
        days_left = (next_date - today_date).days
        entries.append((days_left, member, day, month))

    if not entries:
        await ctx.send("📭 ماكاين حتى عيد ميلاد مسجل دابا فالسيرفر.")
        return

    entries.sort(key=lambda x: x[0])
    lines = []
    for days_left, member, day, month in entries[:10]:
        when = "🎉 اليوم!" if days_left == 0 else f"بعد {days_left} يوم"
        lines.append(f"**{day:02d}/{month:02d}** — {member.mention} ({when})")

    embed = discord.Embed(
        title="🎂 أقرب أعياد الميلاد",
        description="\n".join(lines),
        color=discord.Color.pink()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Birthdays")
    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║   نظام Marry/Bestfriend (أزواج/أصدقاء) — 💌 الأوامر        ║
# ═══════════════════════════════════════════════════════

RELATIONSHIP_LABELS = {
    "marriages": {
        "verb_propose": "يتزوج", "noun": "زواج", "emoji": "💍", "verb_done": "تزوجو",
        "role_prefix": "💍", "color": discord.Color.from_rgb(255, 93, 162),
        "title_propose": "💍 طلب زواج جديد", "title_accept": "💍 مبروك! زواج جديد",
        "exclusive": True,   # ← عضو وحد ما يقدرش يكون عندو كتر من زواج واحد فنفس الوقت
    },
    "bestfriends": {
        "verb_propose": "يكون Best Friend ديال", "noun": "صداقة", "emoji": "🤝", "verb_done": "وليو Best Friends",
        "role_prefix": "🤝", "color": discord.Color.from_rgb(85, 193, 255),
        "title_propose": "🤝 طلب صداقة (Best Friend) جديد", "title_accept": "🤝 مبروك! صداقة جديدة",
        "exclusive": False,  # ← عضو وحد يقدر يكون عندو بزاف ديال الـ Best Friends فنفس الوقت
    },
}


def _relationship_role_id(kind: str) -> int:
    return MARRIAGE_ROLE_ID if kind == "marriages" else BESTFRIEND_ROLE_ID


def _personal_role_color(kind: str) -> int:
    return MARRIAGE_PERSONAL_ROLE_COLOR if kind == "marriages" else BESTFRIEND_PERSONAL_ROLE_COLOR


def _safe_role_name(prefix: str, display_name: str) -> str:
    """كيبني سمية رول صحيحة (Discord كيسمح بحد أقصى 100 حرف)."""
    name = f"{prefix} {display_name}"
    return name[:100]


def _relationship_conflict_message(kind: str, proposer_id: int, target_id: int, target_mention: str) -> Optional[str]:
    """كتشوف واش كاين شي مانع باش هاد الجوج يديرو العلاقة، وكترجع رسالة الخطأ (وإلا None إلا ماكاين والو).
    - marriages: exclusive → حتى واحد فيهم مايكونش عندو زواج آخر.
    - bestfriends: ماشي exclusive → غير كنمنعو نفس الجوج بالضبط يكررو الصداقة مرتين."""
    label = RELATIONSHIP_LABELS[kind]
    if label["exclusive"]:
        existing_key, existing_record = find_relationship(kind, proposer_id)
        if existing_key:
            partner_id = get_partner_id(existing_record, proposer_id)
            return f"❌ عندك ديجا {label['noun']} مع <@{partner_id}>. دير `/divorce` أولاً."
        target_key, _ = find_relationship(kind, target_id)
        if target_key:
            return f"❌ {target_mention} عندو ديجا {label['noun']} مع شي حد آخر."
    else:
        if has_relationship_with(kind, proposer_id, target_id):
            return f"❌ عندك ديجا {label['noun']} مع {target_mention}."
    return None


async def _create_personal_partner_roles(guild: discord.Guild, kind: str,
                                          proposer: discord.Member, target: discord.Member):
    """كتصاوب جوج رولات شخصية: وحدة للـ proposer بسمية الـ target، ووحدة للـ target بسمية الـ proposer.
    كترجع dict {user_id: role_id} — وإلا فشلات (صلاحيات ناقصة مثلا)، كترجع {}."""
    if not RELATIONSHIP_PERSONAL_ROLE_ENABLED:
        return {}
    label = RELATIONSHIP_LABELS[kind]
    color = discord.Color(_personal_role_color(kind))
    result = {}
    try:
        role_for_proposer = await guild.create_role(
            name=_safe_role_name(label["role_prefix"], target.display_name),
            color=color, hoist=False, mentionable=False,
            reason=f"{label['noun']} — رول شخصي لـ {proposer} بسمية {target}"
        )
        role_for_target = await guild.create_role(
            name=_safe_role_name(label["role_prefix"], proposer.display_name),
            color=color, hoist=False, mentionable=False,
            reason=f"{label['noun']} — رول شخصي لـ {target} بسمية {proposer}"
        )
        await proposer.add_roles(role_for_proposer, reason=f"{label['noun']} — قبول")
        await target.add_roles(role_for_target, reason=f"{label['noun']} — قبول")
        result = {proposer.id: role_for_proposer.id, target.id: role_for_target.id}
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[RELATIONSHIPS] ما قدرتش نصاوب الرولات الشخصية: {e}")
    return result


async def _delete_personal_partner_roles(guild: discord.Guild, record: dict):
    """كتحيد وكتمسح الرولات الشخصية المرتبطة بهاد العلاقة (منين تنتهي)."""
    role_ids = record.get("personal_role_ids", {}) or {}
    for uid_str, role_id in role_ids.items():
        role = guild.get_role(role_id)
        if not role:
            continue
        try:
            await role.delete(reason="العلاقة انتهات")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[RELATIONSHIPS] ما قدرتش نمسح الرول {role_id}: {e}")


async def _send_relationship_announcement(guild: discord.Guild, embed: discord.Embed, content: Optional[str] = None):
    """كتبعث إعلان عام فـ RELATIONSHIP_ANNOUNCE_CHANNEL_ID (مثلا #general) — مفيدة للاحتفال
    بزواج/صداقة جديدة، ولا لتبيان بلي علاقة انتهات. كتفشل بصمت إلا الـ channel ماكاينش/ماعندوش صلاحية."""
    if not RELATIONSHIP_ANNOUNCE_CHANNEL_ID:
        return
    channel = guild.get_channel(RELATIONSHIP_ANNOUNCE_CHANNEL_ID)
    if not channel:
        return
    try:
        await channel.send(content=content, embed=embed)
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[RELATIONSHIPS] ما قدرتش نبعث الإعلان فـ #general: {e}")


async def _finalize_end_relationship(guild: discord.Guild, kind: str, key: str, record: dict,
                                      ended_by_id: int):
    """المنطق المشترك باش نسالو علاقة: كتحيد الرول العام + الرولات الشخصية، كتمسح السجل،
    وكتبعث تنبيه DM للطرف الآخر + إعلان عام. كترجع partner_id."""
    label = RELATIONSHIP_LABELS[kind]
    partner_id = get_partner_id(record, ended_by_id)

    role_id = _relationship_role_id(kind)
    if role_id:
        role = guild.get_role(role_id)
        if role:
            partner_member = guild.get_member(partner_id)
            ender_member = guild.get_member(ended_by_id)
            for m in (ender_member, partner_member):
                if m and role in m.roles:
                    # نتأكدو بلي ماعندوش علاقة أخرى بنفس النوع قبل ما نحيدو الرول العام (حالة bestfriends المتعددة)
                    if label["exclusive"] or not find_all_relationships(kind, m.id):
                        try:
                            await m.remove_roles(role, reason=f"{kind} — سالات")
                        except (discord.Forbidden, discord.HTTPException):
                            pass

    await _delete_personal_partner_roles(guild, record)
    end_relationship(kind, key)

    await log_action(
        guild, f"💔 {label['noun'].capitalize()} انتهى",
        f"<@{ended_by_id}> + <@{partner_id}>", discord.Color.dark_grey()
    )

    end_verb = "طلقو بعضياتهم 💔" if kind == "marriages" else "ماعادوش أصدقاء مقربين 💔"
    ender_member_for_announce = guild.get_member(ended_by_id)
    end_announce = discord.Embed(
        description=(
            f"## 💔 {label['noun'].capitalize()} انتهى\n"
            f"### <@{ended_by_id}>  ⛓️‍💥  <@{partner_id}>\n\n"
            f"{label['emoji']} {end_verb}"
        ),
        color=discord.Color.dark_grey(), timestamp=datetime.now()
    )
    if ender_member_for_announce:
        end_announce.set_thumbnail(url=ender_member_for_announce.display_avatar.url)
    end_announce.set_footer(text=SERVER_NAME)
    end_content = f"# 💔 {label['noun'].capitalize()} انتهى"
    await _send_relationship_announcement(guild, end_announce, content=end_content)

    partner_member = guild.get_member(partner_id)
    if partner_member:
        try:
            ender = guild.get_member(ended_by_id)
            ender_name = str(ender) if ender else "شي عضو"
            await partner_member.send(embed=discord.Embed(
                description=f"💔 **{ender_name}** نهى معاك {label['noun']} ديالكم.",
                color=discord.Color.dark_grey()
            ))
        except discord.HTTPException:
            pass

    return partner_id


class RelationshipProposalView(discord.ui.View):
    """طلب الزواج/الصداقة — كتتبعث فـ DM للشخص المطلوب، غير هو لي يقدر يدوس على الأزرار.
    كنخزنو الـ guild و IDs (ماشي discord.Member) حيت فـ DM ماكاينش guild context."""

    def __init__(self, kind: str, guild: discord.Guild, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS)
        self.kind = kind
        self.guild = guild
        self.proposer_id = proposer.id
        self.target_id = target.id
        self.proposer_display = str(proposer)
        self.target_display = str(target)
        self.responded = False
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        if self.responded:
            return
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content=None,
                    embed=discord.Embed(
                        description=f"⏱️ الطلب انتهت مدتو، {self.target_display} ما ردش فالوقت.",
                        color=discord.Color.dark_grey()
                    ),
                    view=self
                )
            except discord.HTTPException:
                pass
        proposer = self.guild.get_member(self.proposer_id)
        if proposer:
            try:
                await proposer.send(f"⏱️ الطلب ديالك لـ **{self.target_display}** انتهت مدتو بلا رد.")
            except discord.HTTPException:
                pass

    async def _fetch_pair(self):
        target = self.guild.get_member(self.target_id) or await self.guild.fetch_member(self.target_id)
        proposer = self.guild.get_member(self.proposer_id) or await self.guild.fetch_member(self.proposer_id)
        return proposer, target

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ هاد الطلب ماشي ليك.", ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        label = RELATIONSHIP_LABELS[self.kind]

        try:
            proposer, target = await self._fetch_pair()
        except discord.NotFound:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=discord.Embed(
                description="❌ ما قدرتش نلقى العضو فالسيرفر (يمكن خرج).", color=discord.Color.red()
            ), view=self)
            return

        # نتأكدو مرة أخرى بلي مازال ماكاين حتى مانع (بين ما تصاوب الطلب ودابا)
        conflict = _relationship_conflict_message(self.kind, proposer.id, target.id, target.mention)
        if conflict:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=discord.Embed(
                description=f"❌ {conflict.lstrip('❌ ')}\nالطلب لغي.", color=discord.Color.red()
            ), view=self)
            return

        pair_key = create_relationship(self.kind, proposer.id, target.id)

        # ═══ الرول العام (اختياري) ═══
        role_note = ""
        general_role_id = _relationship_role_id(self.kind)
        if general_role_id:
            general_role = self.guild.get_role(general_role_id)
            if general_role:
                try:
                    await proposer.add_roles(general_role, reason=f"{label['noun']} — قبول")
                    await target.add_roles(general_role, reason=f"{label['noun']} — قبول")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ═══ الرولات الشخصية بسمية الشريك ═══
        personal_roles = await _create_personal_partner_roles(self.guild, self.kind, proposer, target)
        if personal_roles:
            set_relationship_personal_roles(self.kind, pair_key, personal_roles)
            role_note = "\n✨ كل واحد فيكم ياخد رول شخصي بسمية الآخر."

        for child in self.children:
            child.disabled = True
        result_embed = discord.Embed(
            title=label["title_accept"],
            description=(
                f"**{proposer.mention}** {label['emoji']} **{target.mention}**\n\n"
                f"{label['verb_done'].capitalize()} رسمياً دابا!{role_note}"
            ),
            color=label["color"], timestamp=datetime.now()
        )
        result_embed.set_footer(text=SERVER_NAME)
        await interaction.response.edit_message(content=None, embed=result_embed, view=self)

        # نعلمو الـ proposer بلي تقبل (هو ماشي حاضر فهاد الـ DM)
        try:
            notify_embed = discord.Embed(
                title=label["title_accept"],
                description=f"{target.mention} قبل الطلب ديالك ديال {label['noun']}! {label['emoji']}{role_note}",
                color=label["color"]
            )
            await proposer.send(embed=notify_embed)
        except discord.HTTPException:
            pass

        await log_action(
            self.guild, f"{label['emoji']} {label['noun'].capitalize()} جديد",
            f"**{proposer.mention}** + **{target.mention}**", label["color"]
        )

        # ═══ إعلان عام فـ #general — كبير وعاطي لعين، يبان قدام الناس ═══
        announce_embed = discord.Embed(
            description=(
                f"## {label['emoji']} {label['verb_done'].capitalize()} رسمياً! {label['emoji']}\n"
                f"### {proposer.mention}  ✨  {target.mention}\n\n"
                f"{'💍 علاقة زواج جديدة انولدات فـ' if self.kind == 'marriages' else '🤝 صداقة جديدة انولدات فـ'} "
                f"**{self.guild.name}**! مبروك عليكم 🎉"
            ),
            color=label["color"], timestamp=datetime.now()
        )
        announce_embed.set_author(name=f"{label['noun'].capitalize()} جديد 🎊",
                                   icon_url=target.display_avatar.url)
        announce_embed.set_thumbnail(url=proposer.display_avatar.url)
        announce_embed.set_image(url=target.display_avatar.url)
        announce_embed.add_field(name="📅 بدات", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
        announce_embed.set_footer(
            text=f"{SERVER_NAME} • مبروك للجوج! 🎊",
            icon_url=self.guild.icon.url if self.guild.icon else None
        )
        announce_content = f"# {label['emoji']} {proposer.display_name} × {target.display_name} {label['emoji']}"
        await _send_relationship_announcement(self.guild, announce_embed, content=announce_content)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ هاد الطلب ماشي ليك.", ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(description=f"💔 رفضتي الطلب ديال **{self.proposer_display}**.",
                                 color=discord.Color.dark_grey()),
            view=self
        )
        proposer = self.guild.get_member(self.proposer_id)
        if proposer:
            try:
                label = RELATIONSHIP_LABELS[self.kind]
                await proposer.send(embed=discord.Embed(
                    description=f"💔 **{self.target_display}** رفض الطلب ديالك ديال {label['noun']}.",
                    color=discord.Color.dark_grey()
                ))
            except discord.HTTPException:
                pass


async def _propose_relationship(ctx, kind: str, target: discord.Member):
    label = RELATIONSHIP_LABELS[kind]
    proposer = ctx.author

    if target.id == proposer.id:
        await ctx.send(f"❌ ما تقدرش {label['verb_propose']} نفسك 😅", delete_after=8, ephemeral=True)
        return
    if target.bot:
        await ctx.send("❌ ما تقدرش تدير هادشي مع بوت 🤖", delete_after=8, ephemeral=True)
        return

    conflict = _relationship_conflict_message(kind, proposer.id, target.id, target.mention)
    if conflict:
        await ctx.send(conflict, delete_after=10, ephemeral=True)
        return

    view = RelationshipProposalView(kind, ctx.guild, proposer, target)
    proposal_embed = discord.Embed(
        title=label["title_propose"],
        description=(
            f"{proposer.mention} بغا {label['verb_propose']}ك فـ **{ctx.guild.name}**! {label['emoji']}\n\n"
            f"واش كتقبل؟ (عندك {RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS // 60} دقايق باش تجاوب)"
        ),
        color=label["color"], timestamp=datetime.now()
    )
    proposal_embed.set_thumbnail(url=proposer.display_avatar.url)
    proposal_embed.set_footer(text=SERVER_NAME)

    sent_in_dm = False
    if RELATIONSHIP_DM_PROPOSALS:
        try:
            msg = await target.send(embed=proposal_embed, view=view)
            view.message = msg
            sent_in_dm = True
        except discord.HTTPException:
            sent_in_dm = False

    if sent_in_dm:
        # كتبان غير للشخص لي دار الأمر (ephemeral) — حتى واحد آخر فالشات ما غايشوفها.
        # الطلب الحقيقي راه تبعث فـ DM ديال target، هو لي غايشوف الـ embed والأزرار.
        await ctx.send(
            f"📨 بعثت الطلب ديال {label['noun']} لـ {target.mention} فـ DM ديالو، فـ انتظار الرد.",
            delete_after=15, ephemeral=True
        )
    else:
        # الـ DMs ديالو سادين — ماكاين حل آخر غير نبعثو الطلب هنا فنفس الـ channel كـ fallback
        # (خاص يكون view/embed مبان له باش يقدر يدوس على الأزرار، فهاد الحالة بوحدها كيبان فالشات)
        note = "" if not RELATIONSHIP_DM_PROPOSALS else "\n*(ما قدرتش نبعثلو DM — الطلب هنا)*"
        proposal_embed.description += note
        msg = await ctx.send(content=target.mention, embed=proposal_embed, view=view)
        view.message = msg


async def _end_relationship_cmd(ctx, kind: str):
    """للـ marriages (exclusive) — عندو غير علاقة وحدة، نسالوها مباشرة بلا اختيار.
    الرد هنا ephemeral (خاص بالشخص وحدو) — الإعلان الحقيقي كيتبعث فـ #general (_finalize_end_relationship)."""
    label = RELATIONSHIP_LABELS[kind]
    key, record = find_relationship(kind, ctx.author.id)
    if not key:
        await ctx.send(f"⚠️ ماعندكش {label['noun']} دابا.", delete_after=8, ephemeral=True)
        return

    partner_id = await _finalize_end_relationship(ctx.guild, kind, key, record, ctx.author.id)
    verb = "طلقتي" if kind == "marriages" else "قطعتي الصداقة مع"
    await ctx.send(f"{label['emoji']} {verb} <@{partner_id}>. 💔", ephemeral=True)


class BestfriendRemoveSelect(discord.ui.Select):
    def __init__(self, owner_id: int, guild: discord.Guild, pairs: list):
        # pairs: [(pair_key, record), ...] — كل وحدة كتولي خيار فـ dropdown
        options = []
        for key, record in pairs[:25]:
            partner_id = get_partner_id(record, owner_id)
            member = guild.get_member(partner_id)
            label_text = member.display_name if member else f"عضو ({partner_id})"
            duration = format_duration_since(record["since"])
            options.append(discord.SelectOption(label=label_text[:100], description=f"صديق مقرب منذ {duration}"[:100], value=key))
        super().__init__(placeholder="اختار شكون بغيتي تحيد من لائحة Best Friends ديالك...",
                          min_values=1, max_values=1, options=options)
        self.owner_id = owner_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ هادي مقاديرش تستعملها.", ephemeral=True)
            return
        key = self.values[0]
        record = relationships_db.get("bestfriends", {}).get(key)
        if not record:
            await interaction.response.edit_message(content="⚠️ هاد العلاقة ماعادش موجودة (يمكن تحيدات من قبل).", embed=None, view=None)
            return

        partner_id = await _finalize_end_relationship(self.guild, "bestfriends", key, record, self.owner_id)
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(description=f"🤝💔 قطعتي الصداقة مع <@{partner_id}>.", color=discord.Color.dark_grey()),
            view=self.view
        )


class BestfriendRemoveView(discord.ui.View):
    def __init__(self, owner_id: int, guild: discord.Guild, pairs: list):
        super().__init__(timeout=60)
        self.add_item(BestfriendRemoveSelect(owner_id, guild, pairs))


async def unbestfriend_interactive(ctx):
    """بدل ما نحيدو مباشرة، كنوريو للعضو لائحة (dropdown) بكل الـ Best Friends ديالو دابا
    باش يختار بالضبط شكون بغى يحيد — مفيدة حيت عضو وحد يقدر يكون عندو بزاف ديالهم فنفس الوقت.
    كلشي هنا ephemeral (خاص بالشخص وحدو) — الإعلان الحقيقي كيتبعث فـ #general (_finalize_end_relationship)."""
    label = RELATIONSHIP_LABELS["bestfriends"]
    pairs = find_all_relationships("bestfriends", ctx.author.id)
    if not pairs:
        await ctx.send(f"⚠️ ماعندكش حتى {label['noun']} دابا.", delete_after=8, ephemeral=True)
        return

    lines = []
    for key, record in pairs:
        partner_id = get_partner_id(record, ctx.author.id)
        duration = format_duration_since(record["since"])
        lines.append(f"• <@{partner_id}> — منذ **{duration}**")

    embed = discord.Embed(
        title="🤝 شكون بغيتي تحيد؟",
        description="\n".join(lines) + "\n\nختار من اللائحة تحت 👇",
        color=label["color"]
    )
    view = BestfriendRemoveView(ctx.author.id, ctx.guild, pairs)
    await ctx.send(embed=embed, view=view, ephemeral=True)


async def _relationship_info_cmd(ctx, kind: str, member: Optional[discord.Member]):
    label = RELATIONSHIP_LABELS[kind]
    target = member or ctx.author

    if not label["exclusive"]:
        # bestfriends: نوريو الكل (ممكن يكون عندو بزاف)
        pairs = find_all_relationships(kind, target.id)
        if not pairs:
            who = "عندك" if target == ctx.author else f"عند {target.mention}"
            await ctx.send(f"💔 ما{who}ش {label['noun']} دابا.", delete_after=8)
            return
        lines = []
        for key, record in pairs:
            partner_id = get_partner_id(record, target.id)
            duration = format_duration_since(record["since"])
            lines.append(f"• <@{partner_id}> — منذ **{duration}**")
        embed = discord.Embed(
            title=f"{label['emoji']} {label['noun'].capitalize()} ديال {target.display_name}",
            description="\n".join(lines),
            color=label["color"]
        )
        await ctx.send(embed=embed)
        return

    key, record = find_relationship(kind, target.id)
    if not key:
        who = "عندك" if target == ctx.author else f"عند {target.mention}"
        await ctx.send(f"💔 ما{who}ش {label['noun']} دابا.", delete_after=8)
        return

    partner_id = get_partner_id(record, target.id)
    duration = format_duration_since(record["since"])
    embed = discord.Embed(
        title=f"{label['emoji']} {label['noun'].capitalize()}",
        description=f"{target.mention} + <@{partner_id}>\n⏳ منذ **{duration}**",
        color=label["color"]
    )
    await ctx.send(embed=embed)


async def _relationship_leaderboard_cmd(ctx, kind: str):
    label = RELATIONSHIP_LABELS[kind]
    records = list(relationships_db.get(kind, {}).values())
    if not records:
        await ctx.send(f"📭 ماكاين حتى {label['noun']} مسجلة دابا فالسيرفر.")
        return

    def _sort_key(r):
        try:
            return datetime.strptime(r["since"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now()

    records.sort(key=_sort_key)  # الأقدم = الأطول مدة
    lines = []
    for i, r in enumerate(records[:10], 1):
        duration = format_duration_since(r["since"])
        lines.append(f"**{i}.** <@{r['user_a']}> + <@{r['user_b']}> — **{duration}**")

    embed = discord.Embed(
        title=f"{label['emoji']} أطول {label['noun']}ات فالسيرفر",
        description="\n".join(lines),
        color=label["color"]
    )
    embed.set_footer(text=f"{SERVER_NAME} | {label['noun'].capitalize()} Leaderboard")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="marry", description="اطلب من عضو يتزوجك 💍 (كيتبعث ليه DM)")
async def marry_cmd(ctx, user: discord.Member):
    """اطلب من عضو يتزوجك 💍 — كيتبعث ليه طلب فـ DM وخاصو يقبل بزر"""
    await _propose_relationship(ctx, "marriages", user)


@bot.hybrid_command(name="divorce")
async def divorce_cmd(ctx):
    """طلق الزوج/الزوجة ديالك 💔 (كيحيد الرولات الشخصية ديال الجوج)"""
    await _end_relationship_cmd(ctx, "marriages")


@bot.hybrid_command(name="marriage")
async def marriage_cmd(ctx, user: Optional[discord.Member] = None):
    """بين معلومات الزواج ديالك ولا ديال عضو آخر"""
    await _relationship_info_cmd(ctx, "marriages", user)


@bot.hybrid_command(name="marriages")
async def marriages_cmd(ctx):
    """أطول 10 علاقات زواج فالسيرفر (Leaderboard)"""
    await _relationship_leaderboard_cmd(ctx, "marriages")


@bot.hybrid_command(name="bestfriend", description="اطلب من عضو يكون Best Friend ديالك 🤝 (كيتبعث ليه DM)")
async def bestfriend_cmd(ctx, user: discord.Member):
    """اطلب من عضو يكون Best Friend ديالك 🤝 — كيتبعث ليه طلب فـ DM وخاصو يقبل بزر
    (تقدر يكون عندك بزاف ديال الـ Best Friends فنفس الوقت)"""
    await _propose_relationship(ctx, "bestfriends", user)


@bot.hybrid_command(name="unbestfriend", description="حيد شي صديق مقرب — كتوري ليك لائحة تختار منها")
async def unbestfriend_cmd(ctx):
    """قطع الصداقة مع واحد من الـ Best Friends ديالك — كتوري ليك لائحة (dropdown) تختار منها بالضبط شكون"""
    await unbestfriend_interactive(ctx)


@bot.hybrid_command(name="bestfriendinfo")
async def bestfriendinfo_cmd(ctx, user: Optional[discord.Member] = None):
    """بين لائحة الـ Best Friends ديالك ولا ديال عضو آخر"""
    await _relationship_info_cmd(ctx, "bestfriends", user)


@bot.hybrid_command(name="bestfriends")
async def bestfriends_cmd(ctx):
    """أطول 10 صداقات فالسيرفر (Leaderboard)"""
    await _relationship_leaderboard_cmd(ctx, "bestfriends")


async def check_and_announce_birthdays():
    """كتشيك كل الأعياد المسجلة، كتهني اللي عيد ميلادهم اليوم، وكتحيد الرول
    ديال البارح. كتصاوب فحالها من tasks.loop تحت (birthday_loop)."""
    channel = bot.get_channel(BIRTHDAY_ANNOUNCE_CHANNEL_ID) if BIRTHDAY_ANNOUNCE_CHANNEL_ID else None
    guild = channel.guild if channel else (bot.guilds[0] if bot.guilds else None)
    if not guild:
        return
    now = datetime.now()

    # 1) حيد الرول ديال البارح من اللي بقاو فـ role_holders
    if BIRTHDAY_ROLE_ID and birthdays_db.get("role_holders"):
        role = guild.get_role(BIRTHDAY_ROLE_ID)
        if role:
            for user_id in list(birthdays_db["role_holders"]):
                member = guild.get_member(int(user_id))
                if member and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="عيد الميلاد سالي")
                    except Exception:
                        pass
        birthdays_db["role_holders"] = []

    # 2) شوف شكون عيد ميلادو اليوم
    changed = False
    for user_id, record in birthdays_db.get("birthdays", {}).items():
        if record.get("day") != now.day or record.get("month") != now.month:
            continue
        if record.get("last_announced_year") == now.year:
            continue  # تهنى ديجا هاد العام

        member = guild.get_member(int(user_id))
        record["last_announced_year"] = now.year
        changed = True
        if not member:
            continue

        if channel:
            zodiac_key = record.get("zodiac")
            zodiac_line = ""
            if zodiac_key:
                _, zodiac_label, zodiac_emoji = get_zodiac_sign(record["day"], record["month"])
                if zodiac_label:
                    zodiac_line = f"\n{zodiac_emoji} البرج: **{zodiac_label}**"

            embed = discord.Embed(
                title="🎉🎂 عيد ميلاد سعيد!",
                description=(
                    f"### 🎊 اليوم عيد ميلاد {member.mention}! 🎊\n"
                    f"كاع أعضاء **{SERVER_NAME}** كيهنيوك بهاد اليوم السعيد! 🥳🎈🎁"
                    f"{zodiac_line}"
                ),
                color=discord.Color.pink(),
                timestamp=datetime.now()
            )
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.set_image(url=member.display_avatar.replace(size=512).url)  # الصورة كبيرة وواضحة
            embed.set_footer(text=f"{SERVER_NAME} | Happy Birthday 🎂 | ID: {member.id}")
            try:
                await channel.send(content=f"🎉🎂 {member.mention} عيد ميلادك سعيد! 🎂🎉", embed=embed)
            except Exception:
                pass

        if BIRTHDAY_ROLE_ID:
            role = guild.get_role(BIRTHDAY_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role, reason="عيد ميلاد اليوم")
                    birthdays_db.setdefault("role_holders", []).append(user_id)
                except Exception:
                    pass

    if changed:
        save_birthdays()


@tasks.loop(minutes=60)
async def birthday_loop():
    if not birthdays_db.get("birthdays") and not birthdays_db.get("role_holders"):
        return
    if datetime.now().hour != BIRTHDAY_ANNOUNCE_HOUR:
        return
    await check_and_announce_birthdays()


@birthday_loop.before_loop
async def before_birthday_loop():
    await bot.wait_until_ready()


@birthday_loop.error
async def birthday_loop_error(error):
    print(f"[BIRTHDAYS] خطأ فـ birthday_loop: {error}")


# ═══════════════════════════════════════════════════════
# ║        نظام الصوت — Join to Create + Voice XP           ║
# ═══════════════════════════════════════════════════════
TEMP_VOICE_FILE = os.path.join(DATA_DIR, "temp_voice.json")
temp_voice_channels = {}  # {channel_id (str): owner_id (int)} — الروومات المؤقتة اللي تخلقو


def load_temp_voice_channels():
    global temp_voice_channels
    try:
        with open(TEMP_VOICE_FILE, "r", encoding="utf-8") as f:
            temp_voice_channels = json.load(f)
    except FileNotFoundError:
        temp_voice_channels = {}
    except Exception as e:
        print(f"[VOICE] خطأ فـ تحميل temp_voice.json: {e}")
        temp_voice_channels = {}


def save_temp_voice_channels():
    try:
        with open(TEMP_VOICE_FILE, "w", encoding="utf-8") as f:
            json.dump(temp_voice_channels, f, ensure_ascii=False)
    except Exception as e:
        print(f"[VOICE] خطأ فـ حفظ temp_voice.json: {e}")


load_temp_voice_channels()


def is_temp_voice_owner(member: discord.Member, channel: discord.VoiceChannel) -> bool:
    owner_id = temp_voice_channels.get(str(channel.id))
    if owner_id is not None and int(owner_id) == member.id:
        return True
    return member.guild_permissions.manage_channels  # Admins يقدرو يتحكمو فأي روم برضو


# ═══════════════════════════════════════════════════════
# ║   Room Mute Lock — زر يكتم/يفك كتم كاع اللي فروم صوتي     ║
# ═══════════════════════════════════════════════════════
ROOM_MUTE_FILE = os.path.join(DATA_DIR, "room_mute.json")
# panels: {message_id (str): channel_id (int)} — رسايل البانل المرتبطة بكل روم
# muted_channels: [channel_id, ...] — الروومات اللي دابا "مقفولة" (كاع لي فيها مكتوم، وأي واحد يدخل ليها يتكتم توا)
# manual_mutes: {channel_id (str): [user_id, ...]} — الأعضاء اللي تكتمو يدوياً من الـ Select
#               (بحماية): زر "فك الكل" ما كيمسهمش، خاصك تفك عليهم بيدك من الـ Select
room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}


def load_room_mute():
    global room_mute_db
    try:
        with open(ROOM_MUTE_FILE, "r", encoding="utf-8") as f:
            room_mute_db = json.load(f)
        room_mute_db.setdefault("panels", {})
        room_mute_db.setdefault("muted_channels", [])
        room_mute_db.setdefault("manual_mutes", {})
    except FileNotFoundError:
        room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}
    except Exception as e:
        print(f"[ROOM_MUTE] خطأ فـ التحميل: {e}")
        room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}


def save_room_mute():
    try:
        with open(ROOM_MUTE_FILE, "w", encoding="utf-8") as f:
            json.dump(room_mute_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[ROOM_MUTE] خطأ فـ الحفظ: {e}")


load_room_mute()


def can_toggle_room_mute(member: discord.Member, channel: discord.VoiceChannel) -> bool:
    """شكون يقدر "يستعمل" البانل (يدوس على الأزرار/الـ Select ولا يصاوب بانل جديد)
    — Owner + ROOM_MUTE_PANEL_ALLOWED_USER_IDS بوحدهم، حتى Admin/Moderator
    العاديين ماشي معنيين."""
    if OWNER_ID and member.id == OWNER_ID:
        return True
    return member.id in ROOM_MUTE_PANEL_ALLOWED_USER_IDS


async def apply_room_mute_state(channel: discord.VoiceChannel, muted: bool, protected_ids=None):
    """كتكتم/تفك الكتم على كاع اللي كاينين فالروم دابا — بلا أي استثناء (حتى
    Admin/Moderator/Owner/الأدوار المعفية)، بزربة (concurrent، بلا sleep).
    protected_ids: لائحة IDs ما غاديش تتمس (كيستعملها زر "فك الكل" باش يخلي
    اللي تكتمو يدوياً من الـ Select كيفما هوما)."""
    protected_ids = protected_ids or set()
    targets = [
        m for m in channel.members
        if not m.bot and bool(m.voice and m.voice.mute) != muted and m.id not in protected_ids
    ]

    async def _apply_one(m: discord.Member):
        try:
            await m.edit(mute=muted, reason="Room Mute Panel — كتم/فك الكل")
        except (discord.Forbidden, discord.HTTPException):
            pass

    if targets:
        await asyncio.gather(*(_apply_one(m) for m in targets))
    return len(targets)


def build_room_mute_embed(channel: discord.VoiceChannel, muted: bool) -> discord.Embed:
    embed = discord.Embed(
        title="🔇 الروم مقفولة" if muted else "🔊 الروم محلولة",
        description=(
            f"**Voice Channel:** {channel.mention}\n"
            + ("🔇 كاع اللي فيها مكتومين بلا استثناء، وأي واحد يدخل ليها كيتكتم توا أوتوماتيكياً.\n"
               "💡 تقدر تفك الكتم على شخص معين بوحدو من القائمة تحت، وغادي يبقى محلول حتى تبدل الحالة ديالو يدوياً."
               if muted else
               "🔊 الكل يقدر يهدر عادي فهاد الروم.\n"
               "💡 تقدر تكتم شخص معين بوحدو من القائمة تحت، وغادي يبقى مكتوم حتى تبدل الحالة ديالو يدوياً.")
        ),
        color=discord.Color.red() if muted else discord.Color.green()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Room Mute Panel | {len(channel.members)} عضو دابا فالروم")
    return embed


class RoomMemberSelect(discord.ui.Select):
    """Select كيبين كاع الأعضاء اللي كاينين دابا فالروم — اختيار عضو كيبدل
    (toggle) الحالة ديالو بوحدو (كتم↔فك)، بلا ماتمس الباقي."""

    def __init__(self, channel: Optional[discord.VoiceChannel] = None):
        options = []
        if channel:
            manual_list = room_mute_db.get("manual_mutes", {}).get(str(channel.id), [])
            for m in channel.members:
                if m.bot:
                    continue
                is_muted = bool(m.voice and m.voice.mute)
                is_protected = is_muted and m.id in manual_list
                if is_protected:
                    desc = "🔒 مكتوم يدوياً (محمي من فك الكل) — اختارو باش تفك عليه"
                    emoji = "🔒"
                elif is_muted:
                    desc = "مكتوم دابا — اختارو باش تفك عليه"
                    emoji = "🔇"
                else:
                    desc = "مسموع دابا — اختارو باش تكتمو"
                    emoji = "🎙️"
                options.append(discord.SelectOption(
                    label=m.display_name[:100], value=str(m.id), description=desc, emoji=emoji
                ))
        if not options:
            options = [discord.SelectOption(label="ماكاين حتى عضو (بشري) فالروم دابا", value="none")]

        super().__init__(
            placeholder="🎯 اختار عضو معين باش تبدل الحالة ديالو (كتم/فك كتم)...",
            min_values=1, max_values=1,
            options=options[:25],
            custom_id="room_mute_member_select",
            disabled=(options[0].value == "none"),
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return

        actor = interaction.user
        channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
        guild = interaction.guild
        channel = guild.get_channel(channel_id) if guild and channel_id else None
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
            return
        if not isinstance(actor, discord.Member) or not can_toggle_room_mute(actor, channel):
            await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
            return

        target = guild.get_member(int(self.values[0]))
        if not target or not target.voice or not target.voice.channel or target.voice.channel.id != channel.id:
            await interaction.response.send_message("❌ هاد العضو ماعادش فالروم.", ephemeral=True)
            return

        await interaction.response.defer()
        new_mute = not bool(target.voice.mute)
        try:
            await target.edit(mute=new_mute, reason=f"Room Mute Panel — تبديل يدوي من طرف {actor.display_name}")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send("❌ ما قدرتش نبدل الحالة ديالو (مشكل صلاحيات).", ephemeral=True)
            return

        # كنسجلو/كنحيدو من manual_mutes باش زر "فك الكل" مايمسوش هاد العضو إلا كتمتيه بيدك
        manual_list = room_mute_db.setdefault("manual_mutes", {}).setdefault(str(channel.id), [])
        if new_mute:
            if target.id not in manual_list:
                manual_list.append(target.id)
        else:
            if target.id in manual_list:
                manual_list.remove(target.id)
        save_room_mute()

        muted_state = channel.id in room_mute_db.get("muted_channels", [])
        embed = build_room_mute_embed(channel, muted_state)
        await interaction.message.edit(embed=embed, view=RoomMuteToggleView(muted_state, channel))
        protect_note = " 🔒 (محمي من زر فك الكل)" if new_mute else ""
        await interaction.followup.send(
            f"{'🔇 تكتم' if new_mute else '🔊 تفك عليه الكتم'} {target.mention}.{protect_note}", ephemeral=True
        )
        if guild:
            await log_action(
                guild,
                "🎯 Room Mute Panel — تبديل عضو معين",
                f"**الروم:** {channel.mention}\n**العضو:** {target.mention}\n"
                f"**الحالة الجديدة:** {'🔇 مكتوم (محمي من فك الكل)' if new_mute else '🔊 مسموع'}\n**من طرف:** {actor.mention}",
                discord.Color.orange()
            )


class RoomMuteToggleView(discord.ui.View):
    """بانل كامل: زوج أزرار (كتم الكل بلا استثناء / فك الكل) + Select باش تبدل
    الحالة ديال شخص معين بوحدو. Persistent — كيلقى الروم بواسطة message id
    ديال البانل (room_mute_db['panels'])."""

    def __init__(self, muted: bool = False, channel: Optional[discord.VoiceChannel] = None):
        super().__init__(timeout=None)
        self.add_item(RoomMemberSelect(channel))

    @discord.ui.button(label="🔇 كتم الكل (بلا استثناء)", style=discord.ButtonStyle.danger,
                        custom_id="room_mute_all_button", row=1)
    async def mute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_global(interaction, True)

    @discord.ui.button(label="🔊 فك الكل", style=discord.ButtonStyle.success,
                        custom_id="room_unmute_all_button", row=1)
    async def unmute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_global(interaction, False)

    async def _set_global(self, interaction: discord.Interaction, new_state: bool):
        member = interaction.user
        channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
        if not channel_id:
            await interaction.response.send_message("❌ ماكاينش هاد البانل فالسجل ديالنا.", ephemeral=True)
            return

        guild = interaction.guild
        channel = guild.get_channel(channel_id) if guild else None
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or not can_toggle_room_mute(member, channel):
            await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
            return

        await interaction.response.defer()

        if new_state:
            if channel_id not in room_mute_db.setdefault("muted_channels", []):
                room_mute_db["muted_channels"].append(channel_id)
            protected_ids = set()  # كتم الكل كيمس الجميع، حتى المحميين (باش يبقى فعلاً "الكل")
        else:
            room_mute_db["muted_channels"] = [c for c in room_mute_db.get("muted_channels", []) if c != channel_id]
            # "فك الكل" ما كيمسش اللي تكتمو يدوياً من الـ Select — كيبقاو مكتومين
            protected_ids = set(room_mute_db.get("manual_mutes", {}).get(str(channel.id), []))
        save_room_mute()

        count = await apply_room_mute_state(channel, new_state, protected_ids=protected_ids)
        protected_still_muted = len(protected_ids) if not new_state else 0

        embed = build_room_mute_embed(channel, new_state)
        await interaction.message.edit(embed=embed, view=RoomMuteToggleView(new_state, channel))

        protect_note = f" (🔒 {protected_still_muted} عضو بقاو مكتومين حيت تكتمو يدوياً)" if protected_still_muted else ""
        await interaction.followup.send(
            f"{'🔇 الروم تقفلات، تكتمو' if new_state else '🔊 الروم تحلات، تفك الكتم على'} {count} عضو.{protect_note}",
            ephemeral=True
        )
        if guild:
            await log_action(
                guild,
                "🔇 Room Mute Panel — كتم الكل" if new_state else "🔊 Room Mute Panel — فك الكل",
                f"**الروم:** {channel.mention}\n**العدد المتأثر:** {count}\n**من طرف:** {member.mention}",
                discord.Color.red() if new_state else discord.Color.green()
            )


@bot.hybrid_command(
    name="roommutepanel",
    description="صاوب بانل كامل: كتم الكل بلا استثناء / فك الكل / كتم-فك شخص معين، فروم صوتي معين (Owner فقط)"
)
@app_commands.default_permissions(administrator=True)
async def roommutepanel_cmd(ctx, channel: Optional[discord.VoiceChannel] = None):
    target_channel = channel
    if not target_channel:
        if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
            target_channel = ctx.author.voice.channel
        else:
            await ctx.send("❌ خاصك تكون داخل Voice Channel، ولا تعطي channel كـ parameter.", delete_after=8)
            return

    if not can_toggle_room_mute(ctx.author, target_channel):
        await ctx.send("❌ ماعندكش صلاحية تصاوب هاد البانل.", delete_after=8)
        return

    muted = target_channel.id in room_mute_db.get("muted_channels", [])
    embed = build_room_mute_embed(target_channel, muted)
    view = RoomMuteToggleView(muted, target_channel)
    msg = await ctx.send(embed=embed, view=view)

    room_mute_db.setdefault("panels", {})[str(msg.id)] = target_channel.id
    save_room_mute()

    await log_action(
        ctx.guild,
        "🎛️ Room Mute Panel — تصاوب",
        f"**الروم:** {target_channel.mention}\n**channel البانل:** {ctx.channel.mention}\n**من طرف:** {ctx.author.mention}",
        discord.Color.blue()
    )


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return

    # ═══════ Room Mute Lock: دخل لروم مقفولة → يتكتم توا (بلا استثناء) | خرج منها → يتفك ═══════
    muted_channels = room_mute_db.get("muted_channels", [])
    if muted_channels:
        after_channel_id = after.channel.id if after.channel else None
        before_channel_id = before.channel.id if before.channel else None

        if after_channel_id in muted_channels and after_channel_id != before_channel_id:
            try:
                if not (after.mute):
                    await member.edit(mute=True, reason="دخل لروم مقفولة (Room Mute Lock)")
            except (discord.Forbidden, discord.HTTPException):
                pass
        elif before_channel_id in muted_channels and after_channel_id != before_channel_id:
            try:
                if after.mute:
                    await member.edit(mute=False, reason="خرج من روم مقفولة (Room Mute Lock)")
            except (discord.Forbidden, discord.HTTPException):
                pass

    # ═══════ Join to Create: العضو دخل لـ channel "➕ دير روم" ═══════
    if (bot_settings['join_to_create_enabled'] and JOIN_TO_CREATE_CHANNEL_ID
            and after.channel and after.channel.id == JOIN_TO_CREATE_CHANNEL_ID):
        creator_channel = after.channel
        guild = member.guild
        category = None
        if TEMP_VC_CATEGORY_ID:
            category = guild.get_channel(TEMP_VC_CATEGORY_ID)
        if not category:
            category = creator_channel.category

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
            member: discord.PermissionOverwrite(
                view_channel=True, connect=True, manage_channels=True,
                move_members=True, mute_members=True, deafen_members=True
            ),
        }
        # ═══ رول Unverified ما يشوفش الروومات المؤقتة حتى يوافق على الشروط ═══
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID) if UNVERIFIED_ROLE_ID else None
        if unverified_role:
            overwrites[unverified_role] = discord.PermissionOverwrite(view_channel=False, connect=False)
        try:
            new_channel = await guild.create_voice_channel(
                name=TEMP_VC_NAME_TEMPLATE.format(name=member.display_name)[:100],
                category=category,
                overwrites=overwrites,
                user_limit=TEMP_VC_DEFAULT_LIMIT,
                reason=f"Join to Create — {member.display_name}"
            )
            temp_voice_channels[str(new_channel.id)] = member.id
            save_temp_voice_channels()
            await member.move_to(new_channel, reason="Join to Create")
        except discord.Forbidden:
            print("[VOICE] ⚠️ ماعندش صلاحية Manage Channels باش نخلق الروومات المؤقتة.")
        except Exception as e:
            print(f"[VOICE] خطأ فـ خلق روم مؤقت: {e}")

    # ═══════ تنظيف: العضو خرج من روم مؤقت وبقات فارغة ═══════
    if before.channel and str(before.channel.id) in temp_voice_channels:
        left_channel = before.channel
        if len(left_channel.members) == 0:
            temp_voice_channels.pop(str(left_channel.id), None)
            save_temp_voice_channels()
            try:
                await left_channel.delete(reason="روم مؤقت بقات فارغة")
            except (discord.NotFound, discord.Forbidden):
                pass


@bot.hybrid_command(name="voicerename", description="بدل سمية الروم الصوتي المؤقت ديالك")
async def voicerename_cmd(ctx, *, new_name: str):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت باش تبدل سميتو.", ephemeral=True)
        return
    channel = ctx.author.voice.channel
    if not is_temp_voice_owner(ctx.author, channel):
        await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
        return
    try:
        await channel.edit(name=new_name[:100], reason=f"Renamed by {ctx.author.display_name}")
        await ctx.send(f"✅ تبدلات سمية الروم لـ **{new_name[:100]}**")
    except discord.HTTPException as e:
        await ctx.send(f"❌ ما قدرتش نبدل السمية: {e}", ephemeral=True)


@bot.hybrid_command(name="voicelimit", description="حدد عدد الأعضاء المسموح فالروم الصوتي ديالك (0 = بلا حد)")
async def voicelimit_cmd(ctx, limit: int):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
        return
    channel = ctx.author.voice.channel
    if not is_temp_voice_owner(ctx.author, channel):
        await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
        return
    limit = max(0, min(limit, 99))
    try:
        await channel.edit(user_limit=limit, reason=f"Limit set by {ctx.author.display_name}")
        await ctx.send(f"✅ الحد الأقصى دابا هو **{limit if limit else 'بلا حدود'}**")
    except discord.HTTPException as e:
        await ctx.send(f"❌ خطأ: {e}", ephemeral=True)


@bot.hybrid_command(name="voicelock", description="سد الروم الصوتي المؤقت ديالك (حتى واحد ما يقدر يدخل من بعد)")
async def voicelock_cmd(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
        return
    channel = ctx.author.voice.channel
    if not is_temp_voice_owner(ctx.author, channel):
        await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
        return
    try:
        await channel.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.send("🔒 الروم مسدود دابا — حتى واحد جديد ما يقدر يدخل.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ خطأ: {e}", ephemeral=True)


@bot.hybrid_command(name="voiceunlock", description="حل الروم الصوتي المؤقت ديالك")
async def voiceunlock_cmd(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
        return
    channel = ctx.author.voice.channel
    if not is_temp_voice_owner(ctx.author, channel):
        await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
        return
    try:
        await channel.set_permissions(ctx.guild.default_role, connect=True)
        await ctx.send("🔓 الروم محلول دابا.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ خطأ: {e}", ephemeral=True)


def is_afk_channel(channel: discord.VoiceChannel, guild: discord.Guild) -> bool:
    """واش هاد الروم هي روم AFK؟ (الروم الرسمية ديال السيرفر ولا وحدة من AFK_CHANNEL_IDS)"""
    if guild.afk_channel and channel.id == guild.afk_channel.id:
        return True
    return channel.id in AFK_CHANNEL_IDS


def classify_voice_member(m: discord.Member, channel: discord.VoiceChannel,
                          guild: discord.Guild) -> tuple:
    """كيحدد أشمن درجة ديال XP تستاهل هاد العضو دابا.
    كيرجع (نوع, شحال من XP, واش هو AFK).

    الدرجات:
      stream  🎥 كيدير Go Live / كاميرا      → أكبر XP
      voice   🎤 حال المايك / كيهضر          → XP عادي
      afk_ch  💤 مريح فالروم ديال AFK        → XP مخفض (ولكن أكثر من اللي تحت)
      afk_mut 🔇 سد المايك/Deafen فروم عادية → أصغر XP
    """
    v = m.voice
    if not v:
        return None, 0, False

    # 🎥 لايفستريم ولا كاميرا مشعولة = أعلى درجة، حتى لو المايك مسدود
    if v.self_stream or v.self_video:
        return "stream", int(xp_settings["stream_per_interval"]), False

    in_afk_room = is_afk_channel(channel, guild)
    is_quiet = bool(v.self_mute or v.self_deaf or v.deaf or v.mute)

    # 💤 الروم ديال AFK: مهما كان الحال، هادي درجة AFK ديال الروم
    if in_afk_room:
        return "afk_channel", int(xp_settings["afk_channel_per_interval"]), True

    # 🔇 مايك مسدود / Deafen فروم عادية
    if is_quiet:
        if VOICE_XP_COUNT_MUTED_DEAFENED:
            return "voice", int(xp_settings["voice_per_interval"]), False
        return "afk_muted", int(xp_settings["afk_muted_per_interval"]), True

    # 🎤 المايك محلول = مشارك عادي
    return "voice", int(xp_settings["voice_per_interval"]), False


@tasks.loop(minutes=xp_settings["voice_interval_minutes"])
async def voice_xp_loop():
    if not bot_settings['voice_xp_enabled'] or not bot_settings['leveling_enabled']:
        return
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            # رومات محيدة كامل — حتى XP ديال AFK ماكيتعطاش فيهم
            if channel.id in VOICE_XP_EXCLUDE_CHANNEL_IDS:
                continue
            # روم "دير روم" (Join to Create) ماشي روم حقيقية، غير ممر
            if bot_settings['join_to_create_enabled'] and channel.id == JOIN_TO_CREATE_CHANNEL_ID:
                continue

            humans = [m for m in channel.members if not m.bot]
            if not humans:
                continue
            meets_min_humans = len(humans) >= xp_settings["voice_min_humans"]

            for m in humans:
                kind, amount, is_afk = classify_voice_member(m, channel, guild)
                if not kind or amount <= 0:
                    continue

                # ═══ شرط عدد الناس فالروم (مكافحة الفارمينغ بوحدك) ═══
                if kind == "stream":
                    pass                      # اللايفستريم دايما كيتحسب
                elif is_afk:
                    if not AFK_XP_ENABLED:
                        continue
                    # الروم ديال AFK طبيعي تكون خاوية، علاش الشرط اختياري هنا
                    if AFK_XP_REQUIRE_MIN_HUMANS and not meets_min_humans:
                        continue
                elif not meets_min_humans:
                    continue                  # فويس عادي بوحدو = ماكاين XP

                # ═══ السقف اليومي ديال XP ديال AFK ═══
                if is_afk:
                    amount = afk_xp_allowed(guild.id, m.id, amount)
                    if amount <= 0:
                        continue

                try:
                    await grant_xp_and_announce(m, guild, amount, fallback_channel=channel, source=kind)
                    if is_afk:
                        bump_afk_xp_used(guild.id, m.id, amount)
                except Exception as e:
                    print(f"[VOICE-XP] خطأ فـ إعطاء XP لـ {m}: {e}")


@voice_xp_loop.before_loop
async def before_voice_xp_loop():
    await bot.wait_until_ready()


@voice_xp_loop.error
async def voice_xp_loop_error(error):
    print(f"[VOICE-XP] خطأ كبير وقف الـ loop: {error}")


async def setup_levels_info_message(guild: discord.Guild):
    """كتصاوب رسالة تشرح نظام الـ Leveling كامل + لائحة كاع المستويات
    ورولاتهم، فـ LEVELS_INFO_CHANNEL_ID."""
    if not LEVELS_INFO_CHANNEL_ID:
        return
    channel = bot.get_channel(LEVELS_INFO_CHANNEL_ID)
    if not channel:
        return
    async for message in channel.history(limit=10):
        if message.author == bot.user and message.embeds and message.embeds[0].title and "نظام المستويات" in message.embeds[0].title:
            return

    embed = discord.Embed(
        title="📊 نظام المستويات (Leveling System)",
        description=(
            f"💬 **الشات:** كل ما تهضر، كتربح **XP** ({xp_settings['chat_min']}-{xp_settings['chat_max']} نقطة فكل رسالة)، "
            f"مع فترة انتظار {xp_settings['chat_cooldown']} ثانية بين كل رسالة وأخرى (باش محدش يقدر يسبام باش يربح نقط).\n\n"
            f"🎙️ **الفويس:** كتربح **{xp_settings['voice_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق "
            f"(خاص يكونو على الأقل {xp_settings['voice_min_humans']} ديال البشر فنفس الروم).\n\n"
            f"📡 **اللايفستريم:** ملي تدير Go Live، كتربح **{xp_settings['stream_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق — أكثر من الفويس العادي حيت المجهود أكبر.\n\n"
            f"💤 **الـ AFK:** حتى إلا سديتي المايك ولا درتي Deafen، باقي كتربح XP ولكن أقل:\n"
            f"• مريح فالروم ديال **AFK** → **{xp_settings['afk_channel_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق\n"
            f"• مايك مسدود فروم عادية → **{xp_settings['afk_muted_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق\n"
            f"(علاش الروم ديال AFK كتعطي أكثر؟ باش الرومات النشيطة يبقاو خاوية للي باغي يهضر 😉)\n\n"
            f"كل ما تجمع XP كفاية، كتطلع **Level** جديد. من **Level 30** لفوق، كل مستوى كيصعب أكثر بشكل ملحوظ — "
            f"يعني الوصول لمستويات عالية كيستاهل جهد حقيقي! 💪\n\n"
            f"**الأوامر:**\n"
            f"`/rank [@user]` — شوف المستوى والـ XP ديالك ولا ديال عضو آخر\n"
            f"`/leaderboard` — أفضل 10 أعضاء نشيطين فالسيرفر"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    if LEVEL_ROLES:
        sorted_levels = sorted(LEVEL_ROLES.items(), key=lambda x: int(x[0]))
        lines = []
        for lvl, role_id in sorted_levels:
            role = guild.get_role(role_id) if role_id else None
            role_display = role.mention if role else "⚠️ الرول ماعادش معطي بعد"
            lines.append(f"**Level {lvl}** → {role_display}")
        embed.add_field(name="🎁 الرولات حسب المستوى (تراكمية)", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
    await channel.send(embed=embed)


@bot.hybrid_command(name="setuplevels")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setuplevels_cmd(ctx):
    """كيصاوب/يعاود يصاوب رسالة شرح نظام الـ Leveling فـ LEVELS_INFO_CHANNEL_ID (Admin)"""
    if not LEVELS_INFO_CHANNEL_ID:
        await ctx.send("❌ حط `LEVELS_INFO_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
        return
    await setup_levels_info_message(ctx.guild)
    await ctx.send("✅ رسالة شرح نظام الـ Leveling تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)


@bot.hybrid_command(name="closeticket")
async def closeticket_cmd(ctx):
    """كيسد ticket بأمر (بديل للزر) — خدام غير جوة channel ديال ticket"""
    record = tickets_db.get("open", {}).get(str(ctx.channel.id))
    if not record:
        await ctx.send("❌ هاد الأمر خدام غير جوة channel ديال ticket.", delete_after=6)
        return
    is_opener = ctx.author.id == record.get("opener_id")
    if not (is_opener or _is_ticket_staff(ctx.author)):
        await ctx.send("❌ غير صاحب الـ ticket ولا الإدارة يقدرو يسدوه.", delete_after=6)
        return

    await ctx.send("🔒 غادي نسدو هاد الـ ticket من بعد 5 ثواني...")
    ticket_id = record["id"]
    channel = ctx.channel

    lines = []
    try:
        async for msg in channel.history(limit=500, oldest_first=True):
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = msg.content or "[بلا نص / embed / attachment]"
            lines.append(f"[{ts}] {msg.author}: {content}")
    except Exception as e:
        lines.append(f"[خطأ فـ تجميع transcript: {e}]")

    transcript_text = "\n".join(lines) if lines else "ماكاين حتى رسالة."
    transcript_path = f"/tmp/ticket_{ticket_id}_transcript.txt"
    try:
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
    except Exception:
        transcript_path = None

    log_channel_id = TICKET_LOGS_CHANNEL_ID or MOD_LOGS_CHANNEL_ID
    log_channel = bot.get_channel(log_channel_id) if log_channel_id else None
    if log_channel:
        opener_id = record.get("opener_id")
        claimed_by = record.get("claimed_by")
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} — تسد",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 صاحب الـ Ticket", value=f"<@{opener_id}>" if opener_id else "غير معروف", inline=False)
        embed.add_field(name="🙋 استلمو", value=(f"<@{claimed_by}>" if claimed_by else "محدش استلمو"), inline=False)
        embed.add_field(name="🔒 سداه", value=ctx.author.mention, inline=False)
        embed.add_field(name="🕐 تحلق فـ", value=record.get("opened_at", "—"), inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Ticket #{ticket_id}")
        try:
            if transcript_path:
                await log_channel.send(embed=embed, file=discord.File(transcript_path, filename=f"ticket-{ticket_id}-transcript.txt"))
            else:
                await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[TICKETS] خطأ فـ بعث الـ transcript: {e}")

    if str(channel.id) in tickets_db.get("open", {}):
        del tickets_db["open"][str(channel.id)]
        save_tickets()

    await asyncio.sleep(5)
    try:
        await channel.delete(reason=f"Ticket #{ticket_id} تسد من طرف {ctx.author}")
    except Exception as e:
        print(f"[TICKETS] خطأ فـ حذف الـ channel: {e}")


async def trigger_raid_lockdown(guild: discord.Guild, reason: str, duration_minutes: int = None):
    """كيصعد verification_level ديال السيرفر لأعلى درجة مؤقتاً، وكيبعث تنبيه للإدارة."""
    state = raid_state.setdefault(guild.id, {})
    if state.get("active"):
        return False

    state["active"] = True
    state["previous_verification_level"] = guild.verification_level

    try:
        await guild.edit(verification_level=discord.VerificationLevel.highest, reason="Anti-Raid: Lockdown أوتوماتيكي")
    except Exception as e:
        print(f"[ANTI-RAID] خطأ فـ تصعيد verification level: {e}")

    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        mentions = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
        embed = discord.Embed(
            title="🚨🚨 Anti-Raid: Lockdown مفعل!",
            description=(
                f"{reason}\n\n"
                f"✅ verification level تصعدات مؤقتاً لأعلى درجة.\n"
                f"⚠️ كل عضو جديد غادي يتـ **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** تلقائياً حتى يتسد الـ Lockdown.\n"
                f"استعمل `/unlockdown` باش تسدو يدوياً قبل الوقت، ولا `/raidstatus` باش تشوف الحالة."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )
        try:
            await channel.send(content=mentions or None, embed=embed)
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")

    duration = bot_settings['raid_lockdown_duration_minutes'] if duration_minutes is None else duration_minutes
    if duration and duration > 0:
        async def _auto_revert():
            await asyncio.sleep(duration * 60)
            if raid_state.get(guild.id, {}).get("active"):
                await end_raid_lockdown(guild, reason="انتهت المدة أوتوماتيكياً")
        state["revert_task"] = asyncio.create_task(_auto_revert())

    return True


async def end_raid_lockdown(guild: discord.Guild, reason: str = "يدوي") -> bool:
    state = raid_state.get(guild.id)
    if not state or not state.get("active"):
        return False

    prev_level = state.get("previous_verification_level", discord.VerificationLevel.medium)
    try:
        await guild.edit(verification_level=prev_level, reason="Anti-Raid: رجوع للحالة العادية")
    except Exception as e:
        print(f"[ANTI-RAID] خطأ فـ رجوع verification level: {e}")

    state["active"] = False
    task = state.get("revert_task")
    if task and not task.done():
        task.cancel()

    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="✅ Anti-Raid: Lockdown تسد",
            description=f"**السبب:** {reason}\nverification level رجعت للحالة العادية.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")

    return True


async def _check_and_maybe_trigger_raid(guild: discord.Guild) -> bool:
    """كتزيد join جديد لتتبع الأعضاء الجداد، وكتشوف واش عدد الانضمامات
    الأخيرة وصل للعتبة (bot_settings['raid_join_threshold'] فـ bot_settings['raid_join_interval_seconds']).
    كترجع True إلا Lockdown تفعل دابا بالضبط (أول مرة)."""
    now = datetime.now()
    cutoff = now - timedelta(seconds=bot_settings['raid_join_interval_seconds'])
    joins = [t for t in recent_joins[guild.id] if t > cutoff]
    joins.append(now)
    recent_joins[guild.id] = joins

    if len(joins) >= bot_settings['raid_join_threshold']:
        state = raid_state.get(guild.id, {})
        if not state.get("active"):
            await trigger_raid_lockdown(
                guild,
                reason=f"🚨 {len(joins)} عضو دخلو فـ آخر {bot_settings['raid_join_interval_seconds']} ثانية (العتبة: {bot_settings['raid_join_threshold']})."
            )
            return True
    return False


def _load_font(size: int, bold: bool = True):
    """كتحاول تلقى font جميلة، بالأولوية للفونط اللي حطينا فـ assets/fonts/
    (باش تخدم فأي بيئة، حتى Railway/python-slim اللي ماعندهاش فونطات النظام).
    إلا ماكانتش، كتجرب فونطات النظام، وإلا رجعت للـ font الافتراضي ديال Pillow."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(project_dir, "assets", "fonts", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


async def generate_welcome_card(member: discord.Member, member_count: int, returning: bool = False) -> Optional[io.BytesIO]:
    """كتصاوب صورة ترحيبية مخصصة (Welcome Card) فيها صورة العضو + اسمو + رقمو
    فالسيرفر. كترجع None إلا Pillow ماشي متوفرة أو وقع خطأ (باش الكود اللي
    كيسطاها يرجع للـ embed العادي بلا ما يطيح البوت)."""
    if not PIL_AVAILABLE or not bot_settings['welcome_card_enabled']:
        return None

    try:
        W, H = 1100, 420
        accent = WELCOME_CARD_ACCENT_RGB
        accent2 = WELCOME_CARD_ACCENT2_RGB
        dark = (13, 13, 18)

        # ═══════ الخلفية ═══════
        if WELCOME_CARD_BACKGROUND_PATH and os.path.exists(WELCOME_CARD_BACKGROUND_PATH):
            bg = Image.open(WELCOME_CARD_BACKGROUND_PATH).convert("RGB")
            bg = ImageOps.fit(bg, (W, H), method=Image.LANCZOS).convert("RGBA")
        else:
            # تدرج لوني قطري (diagonal) بين لونين، ممزوج مع الأسود باش يبان depth
            bg = Image.new("RGB", (W, H), dark)
            px = bg.load()
            diag = math.hypot(W, H)
            mix = 0.55
            for y in range(H):
                for x in range(0, W, 2):
                    t = max(0, min(1, (x + y) / diag))
                    r = int((accent[0] * (1 - t) + accent2[0] * t) * mix + dark[0] * (1 - mix))
                    g = int((accent[1] * (1 - t) + accent2[1] * t) * mix + dark[1] * (1 - mix))
                    b = int((accent[2] * (1 - t) + accent2[2] * t) * mix + dark[2] * (1 - mix))
                    px[x, y] = (r, g, b)
                    if x + 1 < W:
                        px[x + 1, y] = (r, g, b)
            bg = bg.convert("RGBA")

            # نقط زخرفية خفيفة (texture) فوق الخلفية
            dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ddraw = ImageDraw.Draw(dots)
            spacing = 34
            for yy in range(0, H, spacing):
                for xx in range(0, W, spacing):
                    ddraw.ellipse((xx, yy, xx + 2, yy + 2), fill=(255, 255, 255, 18))
            bg = Image.alpha_composite(bg, dots)

        # طبقة غامقة شفافة باش النص يبان مزيان فوق أي خلفية
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 60))
        card = Image.alpha_composite(bg, overlay)

        # إطار (frame) خفيف مضيء حول الكارطة
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle((6, 6, W - 6, H - 6), radius=28, outline=(255, 255, 255, 60), width=3)
        card = Image.alpha_composite(card, frame)
        draw = ImageDraw.Draw(card)

        # ═══════ صورة العضو (Avatar) دائرية مع ظل + حلقة بتدرج ═══════
        avatar_size = 200
        avatar_x, avatar_y = 70, (H - avatar_size) // 2

        # ظل ناعم تحت الصورة
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pad = 14
        ImageDraw.Draw(shadow).ellipse(
            (avatar_x - pad, avatar_y - pad + 10, avatar_x + avatar_size + pad, avatar_y + avatar_size + pad + 10),
            fill=(0, 0, 0, 120)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        card = Image.alpha_composite(card, shadow)
        draw = ImageDraw.Draw(card)

        # حلقة بتدرج لوني حول الصورة (رسم أقواس ملونة متدرجة)
        ring_pad = 10
        ring_box = (avatar_x - ring_pad, avatar_y - ring_pad, avatar_x + avatar_size + ring_pad, avatar_y + avatar_size + ring_pad)
        steps = 40
        for i in range(steps):
            t = i / steps
            r = int(accent[0] * (1 - t) + accent2[0] * t)
            g = int(accent[1] * (1 - t) + accent2[1] * t)
            b = int(accent[2] * (1 - t) + accent2[2] * t)
            start = 360 * (i / steps) - 90
            end = 360 * ((i + 1) / steps) - 90
            draw.arc(ring_box, start=start, end=end, fill=(r, g, b, 255), width=8)
        draw.ellipse(ring_box, outline=(255, 255, 255, 90), width=2)

        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            avatar_img = Image.new("RGBA", (256, 256), accent + (255,))
        avatar_img = ImageOps.fit(avatar_img, (avatar_size, avatar_size), method=Image.LANCZOS)

        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        card.paste(avatar_img, (avatar_x, avatar_y), mask)
        draw = ImageDraw.Draw(card)

        # ═══════ badge صغيرة فوق الاسم ═══════
        text_x = avatar_x + avatar_size + 55
        badge_font = _load_font(20, bold=True)
        badge_text = "🔁 رجع للسيرفر" if returning else "✨ عضو جديد"
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        btw, bth = bbox[2] - bbox[0], bbox[3] - bbox[1]
        badge_pad_x, badge_pad_y = 18, 10
        badge_y = 78
        draw.rounded_rectangle(
            (text_x, badge_y, text_x + btw + badge_pad_x * 2, badge_y + bth + badge_pad_y * 2),
            radius=16, fill=(255, 255, 255, 235)
        )
        draw.text((text_x + badge_pad_x, badge_y + badge_pad_y - 2), badge_text, font=badge_font, fill=accent + (255,))

        # ═══════ اسم العضو (كبير، بارز، بظل خفيف) ═══════
        name_font = _load_font(56, bold=True)
        display_name = member.display_name
        if len(display_name) > 18:
            display_name = display_name[:17] + "…"
        name_y = badge_y + bth + badge_pad_y * 2 + 22
        draw.text((text_x + 2, name_y + 2), display_name, font=name_font, fill=(0, 0, 0, 90))
        draw.text((text_x, name_y), display_name, font=name_font, fill=(255, 255, 255, 255))

        # ═══════ subtitle (اسم السيرفر + رقم العضو) ═══════
        sub_font = _load_font(24, bold=False)
        sub_y = name_y + 70
        sub_text = f"{SERVER_NAME}  •  العضو رقم #{member_count}"
        draw.text((text_x, sub_y), sub_text, font=sub_font, fill=(230, 230, 235, 230))

        buffer = io.BytesIO()
        card.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"[WELCOME_CARD] خطأ فـ صنع الصورة: {e}")
        return None


@bot.event
async def on_member_join(member):
    # ═══════════════════════════════════════════════════════
    # ║              Anti-Raid Protection                       ║
    # ═══════════════════════════════════════════════════════
    if bot_settings['anti_raid_enabled']:
        raid_triggered_now = await _check_and_maybe_trigger_raid(member.guild)
        state = raid_state.get(member.guild.id, {})

        if state.get("active"):
            # Raid Mode مفعل → كل عضو جديد كيتطبق عليه bot_settings['raid_action'] مباشرة
            try:
                if bot_settings['raid_action'] == "ban":
                    await member.ban(reason="Anti-Raid: Lockdown مفعل، عضو جديد تلقائياً")
                    action_label = "🚫 حظر تلقائي (Anti-Raid)"
                    color = discord.Color.dark_red()
                else:
                    await member.kick(reason="Anti-Raid: Lockdown مفعل، عضو جديد تلقائياً")
                    action_label = "👢 طرد تلقائي (Anti-Raid)"
                    color = discord.Color.orange()

                await log_case(
                    member.guild, action_label, action_label.split(" ")[0], color,
                    target=member, moderator=None,
                    reason="انضم خلال فترة Anti-Raid Lockdown",
                )
            except discord.Forbidden:
                print(f"[ANTI-RAID] ❌ ماقدرتش نطبق {bot_settings['raid_action']} على {member} — صلاحية ناقصة")
            except Exception as e:
                print(f"[ANTI-RAID] خطأ: {e}")
            return  # ما نكملوش الترحيب/استرجاع الرولات لعضو تفلتر

        # تنبيه بسيط (بلا عقوبة) إلا كان الحساب جديد بزاف — حتى ملي Raid Mode ماشي مفعل
        account_age = datetime.now(member.created_at.tzinfo) - member.created_at
        if account_age < timedelta(hours=RAID_MIN_ACCOUNT_AGE_HOURS):
            await log_action(
                member.guild,
                "⚠️ حساب جديد بزاف",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**عمر الحساب:** {account_age}\n"
                f"غير تنبيه — ماتديرش شي حاجة يدوياً إلا شكيتي فيه.",
                discord.Color.orange()
            )

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
            embed.set_footer(text="GGMW9 | Welcome Back")
            card_buffer = await generate_welcome_card(member, member.guild.member_count, returning=True)
            if card_buffer:
                file = discord.File(card_buffer, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await welcome_channel.send(embed=embed, file=file)
            else:
                embed.set_thumbnail(url=member.display_avatar.url)
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
        embed.set_footer(text="GGMW9 | Verification System")
        card_buffer = await generate_welcome_card(member, member.guild.member_count, returning=False)
        if card_buffer:
            file = discord.File(card_buffer, filename="welcome.png")
            embed.set_image(url="attachment://welcome.png")
            await welcome_channel.send(embed=embed, file=file)
        else:
            embed.set_thumbnail(url=member.display_avatar.url)
            await welcome_channel.send(embed=embed)
    try:
        welcome_dm = discord.Embed(
            title=f"👋 مرحبا بيك | أهلاً بك | Welcome | Bienvenue",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        welcome_dm.add_field(
            name="🇲🇦 بالدارجة",
            value=(
                f"مرحبا بيك فـ **{SERVER_NAME}**!\n"
                f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n"
                f"سير/ي لـ <#{VERIFY_CHANNEL_ID}> وكليك على ✅\n"
                f"شكرا! 🙏"
            ),
            inline=False
        )
        welcome_dm.add_field(
            name="🇸🇦 بالعربية الفصحى",
            value=(
                f"مرحبًا بك في **{SERVER_NAME}**!\n"
                f"قبل أن تتمكن من التحدث في السيرفر، يجب عليك الموافقة على القوانين.\n"
                f"توجّه إلى <#{VERIFY_CHANNEL_ID}> واضغط على ✅\n"
                f"شكرًا لك! 🙏"
            ),
            inline=False
        )
        welcome_dm.add_field(
            name="🇬🇧 In English",
            value=(
                f"Welcome to **{SERVER_NAME}**!\n"
                f"Before you can chat on the server, you need to agree to the rules.\n"
                f"Go to <#{VERIFY_CHANNEL_ID}> and click ✅\n"
                f"Thank you! 🙏"
            ),
            inline=False
        )
        welcome_dm.add_field(
            name="🇫🇷 En Français",
            value=(
                f"Bienvenue sur **{SERVER_NAME}** !\n"
                f"Avant de pouvoir discuter sur le serveur, vous devez accepter les règles.\n"
                f"Rendez-vous dans <#{VERIFY_CHANNEL_ID}> et cliquez sur ✅\n"
                f"Merci ! 🙏"
            ),
            inline=False
        )
        welcome_dm.set_footer(text=f"{SERVER_NAME} | Verification System")
        await member.send(embed=welcome_dm)
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


translated_messages_cache = {}  # {(message_id, lang_en): النص المترجم} — كيفادي إعادة الترجمة إلا رد بزاف ناس بنفس العلم


async def handle_flag_translation(payload: discord.RawReactionActionEvent,
                                   guild: discord.Guild, member: discord.Member):
    """كيترجم الرسالة اللي تحطات عليها reaction بعلم دولة، ويرد بإيمبيد فيه الترجمة."""
    channel = guild.get_channel(payload.channel_id) or bot.get_channel(payload.channel_id)
    if not channel:
        print(f"[AUTO-TRANSLATE] ❌ ما لقيتش channel بـ ID {payload.channel_id}")
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"[AUTO-TRANSLATE] ❌ ما قدرتش نجيب الرسالة (Forbidden/NotFound؟): {e}")
        return

    # ماكاينش نص (رسالة بلا محتوى، صورة وحدها، ولا حتى ترجمة سابقة ديالنا) → ماكاين والو نترجمو
    if message.author.bot or not message.content or not message.content.strip():
        print(f"[AUTO-TRANSLATE] ⏭️ تجاوزت الرسالة (بوت={message.author.bot}, بلا نص={not message.content})")
        return

    lang_display, lang_en = FLAG_TO_LANGUAGE[str(payload.emoji)]
    print(f"[AUTO-TRANSLATE] 🔄 كنترجم رسالة #{message.id} لـ {lang_en}...")
    cache_key = (message.id, lang_en)

    translated = translated_messages_cache.get(cache_key)
    if not translated:
        translated = await translate_text(message.content, lang_en)
        if not translated:
            print(f"[AUTO-TRANSLATE] ❌ translate_text رجع خاوي لـ رسالة #{message.id}")
            return
        translated_messages_cache[cache_key] = translated
        if len(translated_messages_cache) > 500:   # كنخليو الكاش ماكيكبرش بلا حدود
            translated_messages_cache.pop(next(iter(translated_messages_cache)))

    embed = discord.Embed(
        description=translated[:MAX_REPLY_LENGTH],
        color=discord.Color.blurple()
    )
    embed.set_author(
        name=f"🌐 ترجمة لـ {lang_display} — طلب/ات {member.display_name}",
        icon_url=member.display_avatar.url
    )
    try:
        await message.reply(embed=embed, mention_author=False)
    except discord.HTTPException:
        pass


async def maybe_auto_react_translate(message: discord.Message):
    """كيزيد الأعلام ديال AUTO_REACT_FLAGS أوتوماتيك على كل رسالة (إلا فيها نص)،
    باش العضو غير يكليكي على العلم بلا ما يقلب عليه/يكتبو بيدو."""
    if not bot_settings['auto_react_enabled'] or not bot_settings['auto_translate_enabled']:
        return
    if not message.content or not message.content.strip():
        return
    if AUTO_REACT_CHANNEL_IDS and message.channel.id not in AUTO_REACT_CHANNEL_IDS:
        return
    for flag in AUTO_REACT_FLAGS:
        try:
            await message.add_reaction(flag)
        except discord.HTTPException:
            pass


@bot.event
async def on_raw_reaction_add(payload):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    # ═══════ الترجمة التلقائية بالـ Reaction (علم الدولة 🇬🇧🇫🇷) — كتخدم فأي channel ═══════
    if bot_settings['auto_translate_enabled'] and str(payload.emoji) in FLAG_TO_LANGUAGE:
        await handle_flag_translation(payload, guild, member)
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
                f"**الحل:** استعمل `/checkroles` باش تشوف المشكل بالضبط.",
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


async def process_message_xp(message: discord.Message):
    """كتزيد XP للعضو ملي يهضر، وكتشوف واش صعد لمستوى جديد (ممكن أكثر من مستوى
    فمرة وحدة إلا خذا XP كثيرة). كتعطي الرولات ديال LEVEL_ROLES تلقائياً."""
    if not bot_settings['leveling_enabled'] or not message.guild:
        return

    if not isinstance(message.author, discord.Member):
        return

    key = (message.guild.id, message.author.id)
    now = datetime.now()
    last = xp_cooldowns.get(key)
    if last and (now - last).total_seconds() < xp_settings["chat_cooldown"]:
        return
    xp_cooldowns[key] = now

    gained = random.randint(xp_settings["chat_min"], xp_settings["chat_max"])
    await grant_xp_and_announce(message.author, message.guild, gained,
                                fallback_channel=message.channel, source="chat")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.author.bot:
        return
    # ═══════ Prefix Commands (!) معطلين — كاع الأوامر دابا Slash (/) بوحدها ═══════
    # (bot.process_commands ماعادش كيتصاوب، حيت الأوامر ديال ! معطلة نهائياً)
    await process_message_xp(message)
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
                        f"**التحذيرات:** {count} (كتم عند {bot_settings['mute_after_warns']}, طرد عند {bot_settings['kick_after_warns']}, حظر عند {bot_settings['ban_after_warns']})",
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

    await maybe_auto_react_translate(message)

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


@bot.hybrid_command()
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "ما ذكرش سبب"):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    try:
        await member.kick(reason=reason)
        case_id = await log_case(
            ctx.guild, "👢 طرد", "👢", discord.Color.orange(),
            target=member, moderator=ctx.author, reason=reason
        )
        embed = discord.Embed(
            title="👢 طرد",
            description=f"**{member.mention}** تم طرده.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="الطارد", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}")


@bot.hybrid_command()
@app_commands.default_permissions(ban_members=True)
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "ما ذكرش سبب"):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    try:
        await member.ban(reason=reason)
        case_id = await log_case(
            ctx.guild, "🚫 حظر", "🚫", discord.Color.red(),
            target=member, moderator=ctx.author, reason=reason
        )
        embed = discord.Embed(
            title="🚫 حظر",
            description=f"**{member.mention}** تم حظره.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="الحاضر", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}")


@bot.hybrid_command()
@app_commands.default_permissions(ban_members=True)
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        case_id = await log_case(
            ctx.guild, "✅ فك الحظر", "✅", discord.Color.green(),
            target=user, moderator=ctx.author, reason="فك حظر يدوي"
        )
        embed = discord.Embed(
            title="✅ فك الحظر",
            description=f"**{user.name}** تم فك حظره.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.NotFound:
        await ctx.send("❌ ما لقيتش هاد العضو!")
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.hybrid_command()
@app_commands.default_permissions(manage_messages=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(moderate_members=True)
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 5, *, reason: str = "ما ذكرش سبب"):
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
        user_id = str(member.id)
        if user_id in mute_tasks and not mute_tasks[user_id].done():
            mute_tasks[user_id].cancel()
        task = asyncio.create_task(auto_unmute(member, duration, ctx.guild))
        mute_tasks[user_id] = task
        case_id = await log_case(
            ctx.guild, "🔇 كتم", "🔇", discord.Color.yellow(),
            target=member, moderator=ctx.author, reason=reason,
            extra=f"المدة: {duration} دقيقة"
        )
        embed = discord.Embed(
            title="🔇 كتم",
            description=f"**{member.mention}** تم كتم صوته.",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المدة", value=f"{duration} دقيقة", inline=False)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.hybrid_command()
@app_commands.default_permissions(moderate_members=True)
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
        case_id = await log_case(
            ctx.guild, "🔊 فك الكتم", "🔊", discord.Color.green(),
            target=member, moderator=ctx.author, reason="فك كتم يدوي"
        )
        embed = discord.Embed(
            title="🔊 فك الكتم",
            description=f"**{member.mention}** تم فك الكتم.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!")


@bot.hybrid_command()
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


@bot.hybrid_command()
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason: str):
    if OWNER_ID and member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
        return
    if is_exempt(member):
        await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
        return
    count = await add_warn(member, reason)
    case_id = await log_case(
        ctx.guild, "⚠️ تحذير", "⚠️", discord.Color.yellow(),
        target=member, moderator=ctx.author, reason=reason,
        extra=f"عدد التحذيرات الحالي: {count}"
    )
    embed = discord.Embed(
        title="⚠️ تحذير",
        description=f"**{member.mention}** تم تحذيره.",
        color=discord.Color.yellow(),
        timestamp=datetime.now()
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(
        name="عدد التحذيرات",
        value=f"{count} (كتم عند {bot_settings['mute_after_warns']}, طرد عند {bot_settings['kick_after_warns']}, حظر عند {bot_settings['ban_after_warns']})",
        inline=False
    )
    embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
    embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
    await ctx.send(embed=embed)
    action = await apply_warn_escalation(member, ctx.guild, count, reason, channel=ctx.channel)
    if action is None and count >= bot_settings['mute_after_warns']:
        await ctx.send("❌ ما قدرتش نطبق العقوبة (تأكد من صلاحيات وترتيب الأدوار ديال البوت)!")


@bot.hybrid_command()
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def warns(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    user_warns = get_warns(str(member.id))
    embed = discord.Embed(
        title=f"⚠️ تحذيرات {member.display_name}",
        color=discord.Color.yellow(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="العدد",
        value=f"{user_warns['count']} (كتم عند {bot_settings['mute_after_warns']}, طرد عند {bot_settings['kick_after_warns']}, حظر عند {bot_settings['ban_after_warns']})",
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


@bot.hybrid_command()
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def unwarn(ctx, member: discord.Member):
    clear_warns(str(member.id))
    case_id = await log_case(
        ctx.guild, "✅ مسح تحذيرات", "✅", discord.Color.green(),
        target=member, moderator=ctx.author, reason="مسح كاع التحذيرات"
    )
    embed = discord.Embed(
        title="✅ مسح التحذيرات",
        description=f"**{member.mention}** تم مسح تحذيراتو.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"GGMW9 | Moderation | Case #{case_id}")
    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║        /case و /history — تصفح سجل الـ Cases            ║
# ═══════════════════════════════════════════════════════

CASE_ACTION_COLORS = {
    "⚠️": discord.Color.yellow(),
    "🔇": discord.Color.yellow(),
    "🔊": discord.Color.green(),
    "👢": discord.Color.orange(),
    "🚫": discord.Color.red(),
    "✅": discord.Color.green(),
}


@bot.hybrid_command(name="case")
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def case_cmd(ctx, case_id: int):
    """كيبين التفاصيل الكاملة ديال Case معين برقمو"""
    record = get_case(case_id)
    if not record:
        await ctx.send(f"❌ ماكاينش Case #{case_id}.")
        return

    emoji = record["action"].split(" ")[0] if record["action"] else "📋"
    color = CASE_ACTION_COLORS.get(emoji, discord.Color.blurple())

    embed = discord.Embed(
        title=f"📋 Case #{record['id']} — {record['action']}",
        color=color,
        timestamp=datetime.now()
    )
    target_value = f"<@{record['target_id']}> ({record['target_name']})" if record.get("target_id") else record["target_name"]
    mod_value = f"<@{record['moderator_id']}> ({record['moderator_name']})" if record.get("moderator_id") else record["moderator_name"]
    embed.add_field(name="🎯 العضو", value=target_value, inline=False)
    embed.add_field(name="🛡️ نفذ من طرف", value=mod_value, inline=False)
    embed.add_field(name="📝 السبب", value=record["reason"], inline=False)
    if record.get("extra"):
        embed.add_field(name="ℹ️ تفاصيل إضافية", value=record["extra"], inline=False)
    embed.add_field(name="🕐 التاريخ", value=record["timestamp"], inline=False)
    embed.set_footer(text=f"{SERVER_NAME} | Case #{record['id']}")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="history")
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def history_cmd(ctx, member: Optional[discord.Member] = None):
    """كيبين كاع الـ Cases ديال عضو معين، الأحدث فالأول (آخر 15)"""
    member = member or ctx.author
    user_cases = get_cases_for_user(member.id)

    embed = discord.Embed(
        title=f"📋 سجل {member.display_name}",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )

    if not user_cases:
        embed.add_field(name="النتيجة", value="ما كاين حتى Case فسجل هاد العضو ✅", inline=False)
    else:
        lines = []
        for c in user_cases[:15]:
            mod_display = f"<@{c['moderator_id']}>" if c.get("moderator_id") else c["moderator_name"]
            lines.append(
                f"**#{c['id']} — {c['action']}**\n"
                f"السبب: {c['reason']} | نفذ من طرف: {mod_display} | {c['timestamp']}"
            )
        embed.description = "\n\n".join(lines)
        embed.add_field(name="📊 مجموع الـ Cases", value=str(len(user_cases)), inline=False)
        if len(user_cases) > 15:
            embed.set_footer(text=f"{SERVER_NAME} | كيبان غير آخر 15 Case، استعمل /case <رقم> باش تشوف واحد قديم")
        else:
            embed.set_footer(text=f"{SERVER_NAME} | Moderation History")

    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║   OWNER ONLY — إدارة اللائحة الممنوعة (سري، ماشي فالقناة)  ║
# ═══════════════════════════════════════════════════════
# هاد الأوامر خاصة غير بالـ Owner (بواسطة الـ ID فـ OWNER_ID)، حتى
# الـ Admins والـ Moderators ما يقدروش يستعملوها. الرسالة ديال الأمر
# كتمسح مباشرة، والجواب كيوصل بـ DM للـ Owner فقط — باش حتى حد آخر فالسيرفر
# ما يشوف واش تزادت/تحيدت شي كلمة، وواش شكون دارها.

@bot.hybrid_command(name="addword")
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command(name="removeword")
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command(name="addaction", description="زيد عبارة/سلوك ممنوع (Owner)")
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command(name="removeaction")
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command(name="listbanned")
@app_commands.default_permissions(administrator=True)
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
# هاد الأوامر منفصلة على /kick//ban//mute العاديين (اللي خدامين بالصلاحيات
# ديال Discord)، وخاصة غير بالـ Owner بواسطة الـ ID — حتى admin/mod ما
# يقدروش يستعملوها. الـ Admins والـ Moderators كيبقاو خدامين بالأوامر
# العادية فوق حسب الصلاحيات ديال الـ role ديالهم بحال ماكانو.

@bot.hybrid_command(name="ownerkick")
@app_commands.default_permissions(administrator=True)
async def ownerkick_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if not is_owner(ctx):
        return
    if member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
        return
    try:
        await member.kick(reason=reason)
        case_id = await log_case(
            ctx.guild, "👢 طرد (Owner)", "👢", discord.Color.orange(),
            target=member, moderator=ctx.author, reason=reason
        )
        await ctx.send(f"👢 {member.mention} تم طرده من طرف Owner. Case #{case_id}", delete_after=6)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)


@bot.hybrid_command(name="ownerban")
@app_commands.default_permissions(administrator=True)
async def ownerban_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    if not is_owner(ctx):
        return
    if member.id == OWNER_ID:
        await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
        return
    try:
        await member.ban(reason=reason)
        case_id = await log_case(
            ctx.guild, "🚫 حظر (Owner)", "🚫", discord.Color.red(),
            target=member, moderator=ctx.author, reason=reason
        )
        await ctx.send(f"🚫 {member.mention} تم حظره من طرف Owner. Case #{case_id}", delete_after=6)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)


@bot.hybrid_command(name="ownermute")
@app_commands.default_permissions(administrator=True)
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
        case_id = await log_case(
            ctx.guild, "🔇 كتم (Owner)", "🔇", discord.Color.yellow(),
            target=member, moderator=ctx.author, reason=reason,
            extra=f"المدة: {duration} دقيقة"
        )
        await ctx.send(f"🔇 {member.mention} تكتم من طرف Owner ({duration} دقيقة). Case #{case_id}", delete_after=6)
    except discord.Forbidden:
        await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)


@bot.hybrid_command(name="muteall")
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command(name="unmuteall")
@app_commands.default_permissions(administrator=True)
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


# ═══════════════════════════════════════════════════════
# ║        Anti-Raid — أوامر التحكم اليدوي (Admin/Owner)     ║
# ═══════════════════════════════════════════════════════

@bot.hybrid_command(name="lockdown")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def lockdown_cmd(ctx, duration_minutes: int = None):
    """كيفعّل Anti-Raid Lockdown يدوياً (بلا ماتوصل عتبة الانضمامات) — Admin/Owner"""
    started = await trigger_raid_lockdown(
        ctx.guild,
        reason=f"🔒 Lockdown يدوي من طرف {ctx.author.mention}.",
        duration_minutes=duration_minutes
    )
    if started:
        dur_txt = f"{duration_minutes} دقيقة" if duration_minutes else (
            f"{bot_settings['raid_lockdown_duration_minutes']} دقيقة" if bot_settings['raid_lockdown_duration_minutes'] else "حتى `/unlockdown` يدوي"
        )
        await ctx.send(f"🔒 Lockdown تفعل. غادي يدوم: {dur_txt}.")
    else:
        await ctx.send("⚠️ Lockdown مفعل ديجا.", delete_after=6)


@bot.hybrid_command(name="unlockdown")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def unlockdown_cmd(ctx):
    """كيسد Anti-Raid Lockdown يدوياً ويرجع verification level للحالة العادية — Admin/Owner"""
    ended = await end_raid_lockdown(ctx.guild, reason=f"يدوي من طرف {ctx.author.mention}")
    if ended:
        await ctx.send("✅ Lockdown تسد، الوضعية رجعت عادية.")
    else:
        await ctx.send("ℹ️ ماكاين حتى Lockdown مفعل دابا.", delete_after=6)


@bot.hybrid_command(name="raidstatus")
@app_commands.default_permissions(kick_members=True)
@commands.has_permissions(kick_members=True)
async def raidstatus_cmd(ctx):
    """كيبين الحالة ديال Anti-Raid دابا (مفعل ولا لا، عدد الانضمامات الأخيرة)"""
    state = raid_state.get(ctx.guild.id, {})
    now = datetime.now()
    cutoff = now - timedelta(seconds=bot_settings['raid_join_interval_seconds'])
    recent = [t for t in recent_joins.get(ctx.guild.id, []) if t > cutoff]

    embed = discord.Embed(
        title="🚨 Anti-Raid Status",
        color=discord.Color.red() if state.get("active") else discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="الحالة", value="🔒 Lockdown مفعل" if state.get("active") else "✅ عادي", inline=False)
    embed.add_field(
        name="الانضمامات الأخيرة",
        value=f"{len(recent)} / {bot_settings['raid_join_threshold']} (فـ آخر {bot_settings['raid_join_interval_seconds']}ث)",
        inline=False
    )
    embed.add_field(name="العمل ملي يتفعل Lockdown", value="🚫 حظر" if bot_settings['raid_action'] == "ban" else "👢 طرد", inline=False)
    embed.set_footer(text=f"{SERVER_NAME} | Anti-Raid Protection")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="testwelcome", description="بعث Welcome Card تجريبية هنا فالشات (Admin)")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def testwelcome_cmd(ctx, member: Optional[discord.Member] = None, returning: bool = False):
    """كيبعث Welcome Card تجريبية هنا فالشات بلا ما تحتاج عضو يدخل بصح للسيرفر (Admin).
    استعمال: /testwelcome [@عضو] [true/false للـ returning]"""
    member = member or ctx.author
    if not PIL_AVAILABLE:
        await ctx.send("❌ Pillow ماشي مثبتة، الصورة ماغاديش تتصاوب. دير `pip install Pillow`.")
        return
    if not bot_settings['welcome_card_enabled']:
        await ctx.send("⚠️ Welcome Cards معطلة دابا، شعلها من `/botpanel` (زر 🖼️ الترحيب) ولا Admin.")
        return

    card_buffer = await generate_welcome_card(member, ctx.guild.member_count, returning=returning)
    if not card_buffer:
        await ctx.send("❌ وقع خطأ فـ صنع الصورة، شوف الـ logs ديال البوت (`[WELCOME_CARD]`).")
        return

    file = discord.File(card_buffer, filename="welcome.png")
    await ctx.send(content=f"🖼️ هاكذا غادي تبان الكارطة (تجريبي، ماشي رسالة حقيقية):", file=file)


# ═══════════════════════════════════════════════════════
# ║         XP Control Panel — لوحة تحكم فـ XP (Admin)       ║
# ═══════════════════════════════════════════════════════
# لوحة تفاعلية كتخلي الإدارة تبدل شحال ديال XP كياخدو الأعضاء من 3 طرق
# (الشات، الفويس، اللايفستريم) مباشرة من ديسكورد بلا ماتمس الكود — /xppanel
# القيم كتتحفظ فـ xp_settings.json وكتبقى حتى بعد ريستارت البوت.

def _xp_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ لوحة تحكم XP",
        description="بدل شحال ديال XP كياخدو الأعضاء من كل طريقة، بالأزرار تحت. القيم كتتحفظ أوتوماتيك.",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="💬 الشات",
        value=(
            f"**{xp_settings['chat_min']}-{xp_settings['chat_max']}** XP / رسالة\n"
            f"Cooldown: **{xp_settings['chat_cooldown']}** ثانية"
        ),
        inline=True
    )
    embed.add_field(
        name="🎙️ الفويس",
        value=(
            f"**{xp_settings['voice_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق\n"
            f"أدنى بشر فالروم: **{xp_settings['voice_min_humans']}**"
        ),
        inline=True
    )
    embed.add_field(
        name="📡 اللايفستريم",
        value=f"**{xp_settings['stream_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق",
        inline=True
    )
    cap = int(xp_settings.get("afk_daily_cap", 0) or 0)
    embed.add_field(
        name="💤 الـ AFK",
        value=(
            f"فالروم ديال AFK: **{xp_settings['afk_channel_per_interval']}** XP\n"
            f"مايك مسدود فروم عادية: **{xp_settings['afk_muted_per_interval']}** XP\n"
            f"سقف يومي: **{cap if cap > 0 else 'بلا سقف'}**"
        ),
        inline=True
    )
    embed.add_field(
        name="🧠 Trivia",
        value=(
            f"🟢 سهل: **{xp_settings['trivia_easy']}** | 🟡 متوسط: **{xp_settings['trivia_medium']}** | "
            f"🔴 صعيب: **{xp_settings['trivia_hard']}**\n"
            f"سؤال فردي: **{xp_settings['trivia_single']}** XP"
        ),
        inline=True
    )
    mult = xp_settings.get("level_xp_multiplier", 1.0)
    sample_lvl5 = xp_needed_for_level(5)
    sample_lvl20 = xp_needed_for_level(20)
    embed.add_field(
        name="📈 صعوبة المستويات",
        value=(
            f"مضاعف: **×{mult}**\n"
            f"مثال: Level 5 كيحتاج **{sample_lvl5}** XP | Level 20 كيحتاج **{sample_lvl20}** XP"
        ),
        inline=True
    )
    per_hour = 60 / xp_settings["voice_interval_minutes"]
    ratio_voice = (xp_settings["stream_per_interval"] / xp_settings["voice_per_interval"]) if xp_settings["voice_per_interval"] else 0
    embed.add_field(
        name="📐 مقارنة سريعة (تقريبية، فـ الساعة)",
        value=(
            f"اللايفستريم كياخد تقريبا **×{ratio_voice:.1f}** من الفويس العادي.\n"
            f"📡 لايفستريم ≈ **{xp_settings['stream_per_interval'] * per_hour:.0f}** | "
            f"🎙️ فويس ≈ **{xp_settings['voice_per_interval'] * per_hour:.0f}** | "
            f"💤 AFK روم ≈ **{xp_settings['afk_channel_per_interval'] * per_hour:.0f}** | "
            f"🔇 AFK عادي ≈ **{xp_settings['afk_muted_per_interval'] * per_hour:.0f}** XP/ساعة"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | XP Control Panel")
    return embed


class ChatXPModal(discord.ui.Modal, title="💬 إعدادات XP الشات"):
    def __init__(self):
        super().__init__()
        self.min_xp = discord.ui.TextInput(
            label="أدنى XP فكل رسالة", default=str(xp_settings["chat_min"]), max_length=5
        )
        self.max_xp = discord.ui.TextInput(
            label="أقصى XP فكل رسالة", default=str(xp_settings["chat_max"]), max_length=5
        )
        self.cooldown = discord.ui.TextInput(
            label="Cooldown بالثواني بين رسالة ورسالة", default=str(xp_settings["chat_cooldown"]), max_length=6
        )
        self.add_item(self.min_xp)
        self.add_item(self.max_xp)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_min = int(self.min_xp.value)
            new_max = int(self.max_xp.value)
            new_cooldown = int(self.cooldown.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if new_min < 0 or new_max < 0 or new_cooldown < 0:
            await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
            return
        if new_min > new_max:
            await interaction.response.send_message("❌ الأدنى خاصو يكون أصغر ولا يساوي الأقصى.", ephemeral=True)
            return

        xp_settings["chat_min"] = new_min
        xp_settings["chat_max"] = new_max
        xp_settings["chat_cooldown"] = new_cooldown
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class VoiceXPModal(discord.ui.Modal, title="🎙️ إعدادات XP الفويس"):
    def __init__(self):
        super().__init__()
        self.per_interval = discord.ui.TextInput(
            label="XP كل فترة (فويس عادي)", default=str(xp_settings["voice_per_interval"]), max_length=5
        )
        self.interval_minutes = discord.ui.TextInput(
            label="الفترة بالدقايق (مشتركة مع اللايفستريم)",
            default=str(xp_settings["voice_interval_minutes"]), max_length=4
        )
        self.min_humans = discord.ui.TextInput(
            label="أدنى عدد بشر فالروم باش ياخدو XP", default=str(xp_settings["voice_min_humans"]), max_length=3
        )
        self.add_item(self.per_interval)
        self.add_item(self.interval_minutes)
        self.add_item(self.min_humans)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_amount = int(self.per_interval.value)
            new_interval = int(self.interval_minutes.value)
            new_min_humans = int(self.min_humans.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if new_amount < 0 or new_interval <= 0 or new_min_humans < 1:
            await interaction.response.send_message(
                "❌ الفترة خاصها تكون أكبر من 0، وأدنى البشر خاصو يكون 1 ولا أكثر.", ephemeral=True
            )
            return

        interval_changed = new_interval != xp_settings["voice_interval_minutes"]
        xp_settings["voice_per_interval"] = new_amount
        xp_settings["voice_interval_minutes"] = new_interval
        xp_settings["voice_min_humans"] = new_min_humans
        save_xp_settings()

        # الفترة (VOICE_XP_INTERVAL_MINUTES) مشتركة بين الفويس واللايفستريم (نفس الـ loop)،
        # فـ إلا تبدلات خاصنا نبدلو الـ loop نفسو ماشي غير الرقم فالـ dict
        if interval_changed and voice_xp_loop.is_running():
            voice_xp_loop.change_interval(minutes=new_interval)

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class StreamXPModal(discord.ui.Modal, title="📡 إعدادات XP اللايفستريم"):
    def __init__(self):
        super().__init__()
        self.per_interval = discord.ui.TextInput(
            label="XP كل فترة (ملي كيدير Go Live)",
            default=str(xp_settings["stream_per_interval"]), max_length=5
        )
        self.add_item(self.per_interval)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_amount = int(self.per_interval.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص القيمة تكون رقم صحيح.", ephemeral=True)
            return
        if new_amount < 0:
            await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
            return

        xp_settings["stream_per_interval"] = new_amount
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class AfkXPModal(discord.ui.Modal, title="💤 إعدادات XP ديال الـ AFK"):
    def __init__(self):
        super().__init__()
        self.afk_channel_xp = discord.ui.TextInput(
            label="XP كل فترة فالروم ديال AFK",
            default=str(xp_settings["afk_channel_per_interval"]), max_length=5
        )
        self.afk_muted_xp = discord.ui.TextInput(
            label="XP كل فترة (مايك مسدود فروم عادية)",
            default=str(xp_settings["afk_muted_per_interval"]), max_length=5
        )
        self.daily_cap = discord.ui.TextInput(
            label="سقف يومي لـ XP ديال AFK (0 = بلا سقف)",
            default=str(xp_settings.get("afk_daily_cap", 0)), max_length=6
        )
        self.add_item(self.afk_channel_xp)
        self.add_item(self.afk_muted_xp)
        self.add_item(self.daily_cap)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ch_xp = int(self.afk_channel_xp.value)
            mut_xp = int(self.afk_muted_xp.value)
            cap = int(self.daily_cap.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if min(ch_xp, mut_xp, cap) < 0:
            await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
            return
        if ch_xp > xp_settings["voice_per_interval"] or mut_xp > xp_settings["voice_per_interval"]:
            await interaction.response.send_message(
                f"❌ XP ديال AFK خاصو يكون **أقل** من الفويس العادي "
                f"({xp_settings['voice_per_interval']} XP) — وإلا الناس غادي يفرميو وهوما ناعسين 😴",
                ephemeral=True
            )
            return

        xp_settings["afk_channel_per_interval"] = ch_xp
        xp_settings["afk_muted_per_interval"] = mut_xp
        xp_settings["afk_daily_cap"] = cap
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class TriviaXPModal(discord.ui.Modal, title="🧠 إعدادات XP ديال Trivia"):
    def __init__(self):
        super().__init__()
        self.easy = discord.ui.TextInput(
            label="🟢 سهل (بانل Trivia)", default=str(xp_settings["trivia_easy"]), max_length=5
        )
        self.medium = discord.ui.TextInput(
            label="🟡 متوسط (بانل Trivia)", default=str(xp_settings["trivia_medium"]), max_length=5
        )
        self.hard = discord.ui.TextInput(
            label="🔴 صعيب (بانل Trivia)", default=str(xp_settings["trivia_hard"]), max_length=5
        )
        self.single = discord.ui.TextInput(
            label="سؤال فردي (/trivia)", default=str(xp_settings["trivia_single"]), max_length=5
        )
        self.add_item(self.easy)
        self.add_item(self.medium)
        self.add_item(self.hard)
        self.add_item(self.single)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_easy = int(self.easy.value)
            new_medium = int(self.medium.value)
            new_hard = int(self.hard.value)
            new_single = int(self.single.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if min(new_easy, new_medium, new_hard, new_single) < 0:
            await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
            return

        xp_settings["trivia_easy"] = new_easy
        xp_settings["trivia_medium"] = new_medium
        xp_settings["trivia_hard"] = new_hard
        xp_settings["trivia_single"] = new_single
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class LevelXPModal(discord.ui.Modal, title="📈 صعوبة المستويات (Levels)"):
    def __init__(self):
        super().__init__()
        self.multiplier = discord.ui.TextInput(
            label="مضاعف XP المطلوب للمستويات",
            default=str(xp_settings.get("level_xp_multiplier", 1.0)),
            placeholder="1.0 = عادي | 0.5 = نص (أسهل) | 2.0 = ضعف (أصعب)",
            max_length=6
        )
        self.add_item(self.multiplier)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mult = float(self.multiplier.value)
        except ValueError:
            await interaction.response.send_message("❌ خاصها تكون رقم (مثلا 1.0 ولا 0.5).", ephemeral=True)
            return
        if new_mult <= 0:
            await interaction.response.send_message("❌ خاصها تكون أكبر من 0.", ephemeral=True)
            return

        xp_settings["level_xp_multiplier"] = round(new_mult, 3)
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class XPPanelView(discord.ui.View):
    """أزرار لوحة تحكم XP — كل واحد كيحل Modal باش تبدل القيم ديال طريقة معينة.
    خاص Administrator باش يستعملها، حتى ملي تكون الرسالة بانة لكل واحد."""

    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هاد اللوحة خاصة بالإدارة فقط.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="عدل الشات", emoji="💬", style=discord.ButtonStyle.primary)
    async def edit_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChatXPModal())

    @discord.ui.button(label="عدل الفويس", emoji="🎙️", style=discord.ButtonStyle.primary)
    async def edit_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceXPModal())

    @discord.ui.button(label="عدل اللايفستريم", emoji="📡", style=discord.ButtonStyle.primary)
    async def edit_stream(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StreamXPModal())

    @discord.ui.button(label="عدل الـ AFK", emoji="💤", style=discord.ButtonStyle.primary)
    async def edit_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AfkXPModal())

    @discord.ui.button(label="عدل Trivia", emoji="🧠", style=discord.ButtonStyle.primary)
    async def edit_trivia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TriviaXPModal())

    @discord.ui.button(label="صعوبة المستويات", emoji="📈", style=discord.ButtonStyle.primary, row=1)
    async def edit_level_difficulty(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelXPModal())

    @discord.ui.button(label="رجّع الافتراضي", emoji="↩️", style=discord.ButtonStyle.danger, row=1)
    async def reset_defaults(self, interaction: discord.Interaction, button: discord.ui.Button):
        interval_changed = xp_settings["voice_interval_minutes"] != VOICE_XP_INTERVAL_MINUTES
        xp_settings["chat_min"] = XP_MIN_PER_MESSAGE
        xp_settings["chat_max"] = XP_MAX_PER_MESSAGE
        xp_settings["chat_cooldown"] = XP_COOLDOWN_SECONDS
        xp_settings["voice_per_interval"] = VOICE_XP_PER_INTERVAL
        xp_settings["voice_interval_minutes"] = VOICE_XP_INTERVAL_MINUTES
        xp_settings["voice_min_humans"] = VOICE_XP_MIN_HUMANS_IN_CHANNEL
        xp_settings["stream_per_interval"] = STREAM_XP_PER_INTERVAL
        xp_settings["afk_channel_per_interval"] = AFK_CHANNEL_XP_PER_INTERVAL
        xp_settings["afk_muted_per_interval"] = AFK_MUTED_XP_PER_INTERVAL
        xp_settings["afk_daily_cap"] = AFK_XP_DAILY_CAP
        xp_settings["trivia_easy"] = TRIVIA_XP_BY_DIFFICULTY["easy"]
        xp_settings["trivia_medium"] = TRIVIA_XP_BY_DIFFICULTY["medium"]
        xp_settings["trivia_hard"] = TRIVIA_XP_BY_DIFFICULTY["hard"]
        xp_settings["trivia_single"] = TRIVIA_XP_REWARD
        xp_settings["level_xp_multiplier"] = 1.0
        save_xp_settings()
        if interval_changed and voice_xp_loop.is_running():
            voice_xp_loop.change_interval(minutes=VOICE_XP_INTERVAL_MINUTES)
        await interaction.response.edit_message(embed=_xp_panel_embed(), view=self)


@bot.hybrid_command(name="xppanel", description="لوحة تحكم تفاعلية ديال إعدادات XP (Admin)")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def xppanel_cmd(ctx):
    """لوحة تحكم تفاعلية باش تبدل شحال ديال XP كياخدو الأعضاء من الشات، الفويس، اللايفستريم، Trivia، وصعوبة المستويات — Admin"""
    await ctx.send(embed=_xp_panel_embed(), view=XPPanelView())


def recompute_level_from_total_xp(total_xp: int):
    """كتحسب (level, xp_داخل_المستوى) من مجموع XP كلي، حسب صيغة xp_needed_for_level
    الحالية (بحال xp_settings['level_xp_multiplier'] دابا). كتستعمل باش نعاودو نبنيو
    المستوى الصحيح بعد ما نزيدو/ننقصو XP يدوياً."""
    total_xp = max(0, total_xp)
    level = 0
    remaining = total_xp
    while remaining >= xp_needed_for_level(level):
        remaining -= xp_needed_for_level(level)
        level += 1
    return level, remaining


async def adjust_user_xp(member: discord.Member, guild: discord.Guild, amount: int) -> dict:
    """كيزيد/كينقص XP لعضو مباشرة (amount يقدر يكون سالب)، وكيعاود يحسب المستوى
    بالكامل من مجموع XP الكلي — يعني المستوى كيطلع ولا كيهبط تلقائياً حسب
    العدد الجديد (بحال طلبتي: نقصان XP يقدر يرجع العضو لمستوى تحتاني).
    كيعطي الرولات الناقصة إلا صعد لمستوى جديد."""
    data = get_user_level_data(guild.id, member.id)
    old_level = data["level"]
    old_total = total_xp_earned(data)

    new_total = max(0, old_total + amount)
    new_level, new_xp = recompute_level_from_total_xp(new_total)

    data["level"] = new_level
    data["xp"] = new_xp
    save_levels()

    roles_added, roles_removed = [], []
    if new_level != old_level:   # تبدل المستوى (صعد ولا هبط) → نعاودو نظبطو الرول
        roles_added, roles_removed = await sync_level_roles(member, guild, new_level)

    return {
        "old_level": old_level, "new_level": new_level,
        "old_total": old_total, "new_total": new_total,
        "roles_added": roles_added,
        "roles_removed": roles_removed,
    }


@bot.hybrid_command(name="xpadjust")
@app_commands.describe(
    member="العضو اللي بغيتي تبدل ليه XP",
    amount="شحال (رقم موجب باش تزيد، سالب باش تنقص — مثلا -500)",
    reason="السبب (اختياري)"
)
async def xpadjust_cmd(ctx, member: discord.Member, amount: int, *, reason: str = "بلا سبب محدد"):
    """زيد ولا نقص XP لعضو معين مباشرة، والمستوى كيتبدل أوتوماتيكياً حسب المجموع الجديد — Owner بوحدو"""
    if not (OWNER_ID and ctx.author.id == OWNER_ID):
        await ctx.send("❌ هاد الأمر خاص غير بـ Owner.", delete_after=8)
        return
    if amount == 0:
        await ctx.send("❌ عطيني رقم غير صفر (موجب باش تزيد، سالب باش تنقص).", delete_after=8)
        return
    if not ctx.guild:
        return
    if member.bot:
        await ctx.send("❌ ما تقدرش تبدل XP ديال بوت.", delete_after=8)
        return

    result = await adjust_user_xp(member, ctx.guild, amount)

    verb = "زدت" if amount > 0 else "نقصت"
    embed = discord.Embed(
        title="🛠️ تعديل XP يدوي",
        description=f"{verb} **{abs(amount)}** XP لـ {member.mention}",
        color=discord.Color.gold() if amount > 0 else discord.Color.orange()
    )
    level_change = "➡️" if result["old_level"] == result["new_level"] else ("⬆️" if result["new_level"] > result["old_level"] else "⬇️")
    embed.add_field(name="المستوى", value=f"{result['old_level']} {level_change} **{result['new_level']}**", inline=True)
    embed.add_field(name="XP الكلية", value=f"{result['old_total']} → **{result['new_total']}**", inline=True)
    if result["roles_added"]:
        embed.add_field(name="🎁 رول جديد", value=", ".join(result["roles_added"]), inline=False)
    if result["roles_removed"]:
        embed.add_field(name="🗑️ رولات تحيدو", value=", ".join(result["roles_removed"]), inline=False)
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.set_footer(text=f"من طرف {ctx.author.display_name}")
    await ctx.send(embed=embed)

    await log_action(
        ctx.guild, "🛠️ XP Adjustment (Owner)",
        f"**العضو:** {member.mention}\n**التغيير:** {'+' if amount > 0 else ''}{amount} XP\n"
        f"**المستوى:** {result['old_level']} → {result['new_level']}\n"
        f"**السبب:** {reason}\n**من طرف:** {ctx.author.mention}",
        discord.Color.gold() if amount > 0 else discord.Color.orange()
    )


SOURCE_LABELS_AR = {
    "chat": "💬 شات",
    "voice": "🎤 فويس",
    "afk_channel": "💤 AFK (روم AFK)",
    "afk_muted": "🔇 AFK (مايك مسدود)",
    "stream": "🎥 لايفستريم",
    "trivia": "🧠 Trivia (سؤال واحد)",
    "trivia_panel": "🧠 Trivia (panel)",
    "unknown": "❓ ماشي معروف",
}


@bot.hybrid_command(name="xpaudit")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
@app_commands.describe(member="العضو اللي بغيتي تشيك عليه")
async def xpaudit_cmd(ctx, member: discord.Member):
    """كيوري من فين جا كل XP ديال عضو معين (شات/فويس/trivia/afk) وآخر events ديالو — Admin"""
    await ctx.defer()
    summary = get_xp_audit_summary(ctx.guild.id, member.id)

    if summary["total_events"] == 0:
        await ctx.send(f"❌ ماكاينش أي سجل XP لـ {member.mention} حتى دابا (يمكن الميزة ماكانتش مفعلة ملي ربح XP، أو ماشي فهاد السيرفر).")
        return

    embed = discord.Embed(
        title=f"🔍 XP Audit — {member.display_name}",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    data = get_user_level_data(ctx.guild.id, member.id)
    embed.add_field(
        name="📊 الوضع الحالي",
        value=f"Level **{data['level']}** • {data['xp']}/{xp_needed_for_level(data['level'])} XP للمستوى الجاي\n"
              f"مجموع XP إجمالي (منذ البداية): **{total_xp_earned(data)}**",
        inline=False
    )

    dist_lines = []
    for src, info in sorted(summary["by_source"].items(), key=lambda x: -x[1]["total"]):
        label = SOURCE_LABELS_AR.get(src, src)
        dist_lines.append(f"{label}: **{info['total']}** XP ({info['count']} events)")
    embed.add_field(
        name=f"📈 التوزيع حسب المصدر ({summary['total_events']} events مسجلين إجمالي)",
        value="\n".join(dist_lines) if dist_lines else "—",
        inline=False
    )

    recent = summary["recent"][-15:]
    recent_lines = []
    for e in reversed(recent):
        ts = e.get("ts", "")[:16].replace("T", " ")
        label = SOURCE_LABELS_AR.get(e.get("source"), e.get("source"))
        ch = f" <#{e['channel']}>" if e.get("channel") else ""
        recent_lines.append(f"`{ts}` {label} +{e.get('amount')} XP{ch}")
    embed.add_field(
        name="🕒 آخر 15 events",
        value="\n".join(recent_lines) if recent_lines else "—",
        inline=False
    )

    # ═══ كشف سريع: واش الفارقات بين الرسائل قريبة بزاف من cooldown (علامة بوت/سكريبت) ═══
    chat_events = [e for e in summary["recent"] if e.get("source") == "chat"]
    if len(chat_events) >= 5:
        gaps = []
        for i in range(1, len(chat_events)):
            try:
                t1 = datetime.fromisoformat(chat_events[i - 1]["ts"])
                t2 = datetime.fromisoformat(chat_events[i]["ts"])
                gaps.append((t2 - t1).total_seconds())
            except Exception:
                pass
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            tight = sum(1 for g in gaps if xp_settings["chat_cooldown"] <= g <= xp_settings["chat_cooldown"] + 3)
            ratio = tight / len(gaps)
            if ratio >= 0.7 and avg_gap < xp_settings["chat_cooldown"] + 5:
                embed.add_field(
                    name="⚠️ ملاحظة",
                    value=f"{ratio*100:.0f}% من رسائلو الأخيرة جايين بفارق قريب بزاف من cooldown ({xp_settings['chat_cooldown']}ث) "
                          f"— هادشي ممكن يكون نشاط عادي مكثف، ولكن يستاهل تشيك يدوي (سكريبت/أوتو-كليكر).",
                    inline=False
                )

    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║      Bot Control Panel — لوحة تحكم شاملة (Admin)         ║
# ═══════════════════════════════════════════════════════
# لوحة واحدة كتجمع أغلب الحوايج اللي محتاجة تحكم متكرر (تفعيل/تعطيل، عتبات،
# مدد) بلا ماتمس الكود ولا تعاود ريستارت البوت — /botpanel

def _bool_emoji(value: bool) -> str:
    return "✅" if value else "❌"


def _main_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ لوحة تحكم البوت",
        description="اختار قسم من الأزرار تحت باش تشوف/تبدل الإعدادات ديالو. XP ليها لوحة خاصة بيها `/xppanel`.",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="🚨 Anti-Raid",
        value=(
            f"{_bool_emoji(bot_settings['anti_raid_enabled'])} الحالة\n"
            f"عتبة: **{bot_settings['raid_join_threshold']}** فـ **{bot_settings['raid_join_interval_seconds']}**ث\n"
            f"العمل: **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** | Lockdown: **{bot_settings['raid_lockdown_duration_minutes'] or '∞'}**د"
        ),
        inline=True
    )
    embed.add_field(
        name="⚠️ التحذيرات (Warns)",
        value=(
            f"🔇 كتم عند **{bot_settings['mute_after_warns']}** ({bot_settings['mute_duration_minutes']}د)\n"
            f"👢 طرد عند **{bot_settings['kick_after_warns']}**\n"
            f"🚫 حظر عند **{bot_settings['ban_after_warns']}**"
        ),
        inline=True
    )
    embed.add_field(
        name="📰 Auto-Info",
        value=(
            f"{_bool_emoji(bot_settings['auto_info_news'])} أخبار | "
            f"{_bool_emoji(bot_settings['auto_info_games'])} ألعاب | "
            f"{_bool_emoji(bot_settings['auto_info_movies'])} أفلام\n"
            f"{_bool_emoji(bot_settings['auto_info_anime'])} أنمي | "
            f"{_bool_emoji(bot_settings['auto_info_music'])} موسيقى"
        ),
        inline=False
    )
    embed.add_field(
        name="🧩 مميزات عامة",
        value=(
            f"{_bool_emoji(bot_settings['leveling_enabled'])} Leveling/XP | "
            f"{_bool_emoji(bot_settings['voice_xp_enabled'])} Voice XP\n"
            f"{_bool_emoji(bot_settings['join_to_create_enabled'])} Join to Create | "
            f"{_bool_emoji(bot_settings['welcome_card_enabled'])} Welcome Cards\n"
            f"{_bool_emoji(bot_settings['auto_translate_enabled'])} Auto-Translate | "
            f"{_bool_emoji(bot_settings['auto_react_enabled'])} Auto-React"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | Bot Control Panel")
    return embed


class BackToMainButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="رجوع", emoji="🔙", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=_main_panel_embed(), view=MainPanelView())


class PanelPermissionView(discord.ui.View):
    """View بيز فيها فحص الصلاحية (Admin فقط) مشترك بين كل صفحات اللوحة."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هاد اللوحة خاصة بالإدارة فقط.", ephemeral=True)
            return False
        return True


# ───────────── Anti-Raid ─────────────

def _anti_raid_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚨 إعدادات Anti-Raid",
        color=discord.Color.red() if bot_settings["anti_raid_enabled"] else discord.Color.greyple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="الحالة", value=_bool_emoji(bot_settings["anti_raid_enabled"]), inline=True)
    embed.add_field(name="العمل", value="🚫 حظر" if bot_settings["raid_action"] == "ban" else "👢 طرد", inline=True)
    embed.add_field(
        name="مدة Lockdown",
        value=f"{bot_settings['raid_lockdown_duration_minutes']} دقيقة" if bot_settings["raid_lockdown_duration_minutes"] else "حتى /unlockdown يدوي",
        inline=True
    )
    embed.add_field(
        name="العتبة",
        value=f"**{bot_settings['raid_join_threshold']}** عضو جديد فـ **{bot_settings['raid_join_interval_seconds']}** ثانية",
        inline=False
    )
    return embed


class AntiRaidSettingsModal(discord.ui.Modal, title="🚨 إعدادات Anti-Raid"):
    def __init__(self):
        super().__init__()
        self.threshold = discord.ui.TextInput(
            label="عدد الأعضاء الجداد (العتبة)", default=str(bot_settings["raid_join_threshold"]), max_length=4
        )
        self.interval = discord.ui.TextInput(
            label="فـ هاد المدة بالثواني", default=str(bot_settings["raid_join_interval_seconds"]), max_length=5
        )
        self.action = discord.ui.TextInput(
            label="العمل: اكتب kick ولا ban", default=bot_settings["raid_action"], max_length=4
        )
        self.lockdown_minutes = discord.ui.TextInput(
            label="مدة Lockdown بالدقايق (0 = يدوي فقط)",
            default=str(bot_settings["raid_lockdown_duration_minutes"]), max_length=5
        )
        self.add_item(self.threshold)
        self.add_item(self.interval)
        self.add_item(self.action)
        self.add_item(self.lockdown_minutes)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_threshold = int(self.threshold.value)
            new_interval = int(self.interval.value)
            new_lockdown = int(self.lockdown_minutes.value)
        except ValueError:
            await interaction.response.send_message("❌ العتبة/المدة/Lockdown خاصهم يكونو أرقام صحيحة.", ephemeral=True)
            return
        new_action = self.action.value.strip().lower()
        if new_action not in ("kick", "ban"):
            await interaction.response.send_message("❌ العمل خاصو يكون `kick` ولا `ban` فقط.", ephemeral=True)
            return
        if new_threshold < 1 or new_interval < 1 or new_lockdown < 0:
            await interaction.response.send_message("❌ العتبة والمدة خاصهم يكونو أكبر من 0.", ephemeral=True)
            return

        bot_settings["raid_join_threshold"] = new_threshold
        bot_settings["raid_join_interval_seconds"] = new_interval
        bot_settings["raid_action"] = new_action
        bot_settings["raid_lockdown_duration_minutes"] = new_lockdown
        save_bot_settings()

        await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())


class AntiRaidView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    @discord.ui.button(label="تفعيل/تعطيل", emoji="🔌", style=discord.ButtonStyle.primary)
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_settings["anti_raid_enabled"] = not bot_settings["anti_raid_enabled"]
        save_bot_settings()
        await interaction.response.edit_message(embed=_anti_raid_embed(), view=self)

    @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AntiRaidSettingsModal())


# ───────────── Warns Escalation ─────────────

def _warns_embed() -> discord.Embed:
    embed = discord.Embed(title="⚠️ تصعيد التحذيرات (Warns)", color=discord.Color.orange(), timestamp=datetime.now())
    embed.add_field(name="🔇 كتم", value=f"عند **{bot_settings['mute_after_warns']}** تحذيرات، **{bot_settings['mute_duration_minutes']}** دقيقة", inline=False)
    embed.add_field(name="👢 طرد", value=f"عند **{bot_settings['kick_after_warns']}** تحذيرات", inline=False)
    embed.add_field(name="🚫 حظر", value=f"عند **{bot_settings['ban_after_warns']}** تحذيرات", inline=False)
    return embed


class WarnsSettingsModal(discord.ui.Modal, title="⚠️ تصعيد التحذيرات"):
    def __init__(self):
        super().__init__()
        self.mute_after = discord.ui.TextInput(label="كتم عند شحال تحذير", default=str(bot_settings["mute_after_warns"]), max_length=3)
        self.mute_minutes = discord.ui.TextInput(label="مدة الكتم بالدقايق", default=str(bot_settings["mute_duration_minutes"]), max_length=5)
        self.kick_after = discord.ui.TextInput(label="طرد عند شحال تحذير", default=str(bot_settings["kick_after_warns"]), max_length=3)
        self.ban_after = discord.ui.TextInput(label="حظر عند شحال تحذير", default=str(bot_settings["ban_after_warns"]), max_length=3)
        self.add_item(self.mute_after)
        self.add_item(self.mute_minutes)
        self.add_item(self.kick_after)
        self.add_item(self.ban_after)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mute_after = int(self.mute_after.value)
            new_mute_minutes = int(self.mute_minutes.value)
            new_kick_after = int(self.kick_after.value)
            new_ban_after = int(self.ban_after.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if min(new_mute_after, new_mute_minutes, new_kick_after, new_ban_after) < 0:
            await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
            return
        if not (new_mute_after <= new_kick_after <= new_ban_after):
            await interaction.response.send_message(
                "❌ خاص الترتيب يكون منطقي: كتم ≤ طرد ≤ حظر (بعدد التحذيرات).", ephemeral=True
            )
            return

        bot_settings["mute_after_warns"] = new_mute_after
        bot_settings["mute_duration_minutes"] = new_mute_minutes
        bot_settings["kick_after_warns"] = new_kick_after
        bot_settings["ban_after_warns"] = new_ban_after
        save_bot_settings()

        await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())


class WarnsView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WarnsSettingsModal())


# ───────────── Auto-Info Toggles ─────────────

def _auto_info_embed() -> discord.Embed:
    embed = discord.Embed(title="📰 Auto-Info — تفعيل/تعطيل كل فئة", color=discord.Color.teal(), timestamp=datetime.now())
    embed.add_field(name="📰 أخبار", value=_bool_emoji(bot_settings["auto_info_news"]), inline=True)
    embed.add_field(name="🎮 ألعاب", value=_bool_emoji(bot_settings["auto_info_games"]), inline=True)
    embed.add_field(name="🎬 أفلام", value=_bool_emoji(bot_settings["auto_info_movies"]), inline=True)
    embed.add_field(name="📺 أنمي", value=_bool_emoji(bot_settings["auto_info_anime"]), inline=True)
    embed.add_field(name="🎧 موسيقى", value=_bool_emoji(bot_settings["auto_info_music"]), inline=True)
    return embed


class AutoInfoView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    async def _toggle(self, interaction: discord.Interaction, key: str):
        bot_settings[key] = not bot_settings[key]
        save_bot_settings()
        await interaction.response.edit_message(embed=_auto_info_embed(), view=self)

    @discord.ui.button(label="أخبار", emoji="📰", style=discord.ButtonStyle.secondary)
    async def toggle_news(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_news")

    @discord.ui.button(label="ألعاب", emoji="🎮", style=discord.ButtonStyle.secondary)
    async def toggle_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_games")

    @discord.ui.button(label="أفلام", emoji="🎬", style=discord.ButtonStyle.secondary)
    async def toggle_movies(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_movies")

    @discord.ui.button(label="أنمي", emoji="📺", style=discord.ButtonStyle.secondary)
    async def toggle_anime(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_anime")

    @discord.ui.button(label="موسيقى", emoji="🎧", style=discord.ButtonStyle.secondary)
    async def toggle_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_music")


# ───────────── مميزات عامة (Feature Toggles) ─────────────

def _features_embed() -> discord.Embed:
    embed = discord.Embed(title="🧩 مميزات عامة — تفعيل/تعطيل", color=discord.Color.blurple(), timestamp=datetime.now())
    embed.add_field(name="📊 Leveling/XP", value=_bool_emoji(bot_settings["leveling_enabled"]), inline=True)
    embed.add_field(name="🎙️ Voice XP", value=_bool_emoji(bot_settings["voice_xp_enabled"]), inline=True)
    embed.add_field(name="🔊 Join to Create", value=_bool_emoji(bot_settings["join_to_create_enabled"]), inline=True)
    embed.add_field(name="🖼️ Welcome Cards", value=_bool_emoji(bot_settings["welcome_card_enabled"]), inline=True)
    embed.add_field(name="🌐 Auto-Translate", value=_bool_emoji(bot_settings["auto_translate_enabled"]), inline=True)
    embed.add_field(name="⚡ Auto-React", value=_bool_emoji(bot_settings["auto_react_enabled"]), inline=True)
    return embed


class FeaturesView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    async def _toggle(self, interaction: discord.Interaction, key: str):
        bot_settings[key] = not bot_settings[key]
        save_bot_settings()
        await interaction.response.edit_message(embed=_features_embed(), view=self)

    @discord.ui.button(label="Leveling/XP", emoji="📊", style=discord.ButtonStyle.secondary)
    async def toggle_leveling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "leveling_enabled")

    @discord.ui.button(label="Voice XP", emoji="🎙️", style=discord.ButtonStyle.secondary)
    async def toggle_voice_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "voice_xp_enabled")

    @discord.ui.button(label="Join to Create", emoji="🔊", style=discord.ButtonStyle.secondary)
    async def toggle_j2c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "join_to_create_enabled")

    @discord.ui.button(label="Welcome Cards", emoji="🖼️", style=discord.ButtonStyle.secondary)
    async def toggle_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not PIL_AVAILABLE:
            await interaction.response.send_message("❌ Pillow ماشي مثبتة فالسيرفر، Welcome Cards ماغاديش تخدم حتى لو شعلتيها.", ephemeral=True)
            return
        await self._toggle(interaction, "welcome_card_enabled")

    @discord.ui.button(label="Auto-Translate", emoji="🌐", style=discord.ButtonStyle.secondary)
    async def toggle_translate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_translate_enabled")

    @discord.ui.button(label="Auto-React", emoji="⚡", style=discord.ButtonStyle.secondary)
    async def toggle_react(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_react_enabled")


# ───────────── اللوحة الرئيسية ─────────────

class MainPanelView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Anti-Raid", emoji="🚨", style=discord.ButtonStyle.primary)
    async def open_anti_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())

    @discord.ui.button(label="التحذيرات", emoji="⚠️", style=discord.ButtonStyle.primary)
    async def open_warns(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())

    @discord.ui.button(label="Auto-Info", emoji="📰", style=discord.ButtonStyle.primary)
    async def open_auto_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_auto_info_embed(), view=AutoInfoView())

    @discord.ui.button(label="مميزات عامة", emoji="🧩", style=discord.ButtonStyle.primary)
    async def open_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_features_embed(), view=FeaturesView())

    @discord.ui.button(label="XP Panel", emoji="📊", style=discord.ButtonStyle.success, row=1)
    async def open_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


@bot.hybrid_command(name="botpanel")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def botpanel_cmd(ctx):
    """لوحة تحكم شاملة فأغلب إعدادات البوت (Anti-Raid، التحذيرات، Auto-Info، مميزات عامة، وXP) — Admin"""
    await ctx.send(embed=_main_panel_embed(), view=MainPanelView())


# ═══════════════════════════════════════════════════════
# ║              Leveling System — أوامر                     ║
# ═══════════════════════════════════════════════════════

def _progress_bar(current: int, needed: int, length: int = 20) -> str:
    ratio = max(0, min(1, current / needed)) if needed else 0
    filled = int(length * ratio)
    return "🟩" * filled + "⬛" * (length - filled)


@bot.hybrid_command(name="rank")
async def rank_cmd(ctx, member: Optional[discord.Member] = None):
    """كيبين المستوى والـ XP ديال عضو (نتا ولا شخص آخر)"""
    if not bot_settings['leveling_enabled']:
        await ctx.send("❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).", delete_after=6)
        return

    member = member or ctx.author
    data = get_user_level_data(ctx.guild.id, member.id)
    needed = xp_needed_for_level(data["level"])

    # ═══════ حساب الترتيب (Rank) بين كل الأعضاء ═══════
    guild_data = levels_db.get(str(ctx.guild.id), {})
    ranking = sorted(
        guild_data.items(),
        key=lambda item: total_xp_earned(item[1]),
        reverse=True
    )
    rank_position = next((i + 1 for i, (uid, _) in enumerate(ranking) if uid == str(member.id)), None)

    embed = discord.Embed(
        title=f"📊 المستوى ديال {member.display_name}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏆 Level", value=str(data["level"]), inline=True)
    embed.add_field(name="🥇 الترتيب", value=f"#{rank_position}" if rank_position else "—", inline=True)
    embed.add_field(name="✨ XP", value=f"{data['xp']} / {needed}", inline=True)
    embed.add_field(name="التقدم", value=_progress_bar(data["xp"], needed), inline=False)
    embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
    await ctx.send(embed=embed)


def build_leaderboard_embed(guild: discord.Guild) -> Optional[discord.Embed]:
    """كتصاوب embed لائحة الشرف (أفضل 10) لسيرفر معين. كترجع None إلا ماكاين حتى عضو ربح XP بعد."""
    guild_data = levels_db.get(str(guild.id), {})
    if not guild_data:
        return None

    ranking = sorted(
        guild_data.items(),
        key=lambda item: total_xp_earned(item[1]),
        reverse=True
    )[:10]

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (user_id, data) in enumerate(ranking):
        prefix = medals[i] if i < len(medals) else f"#{i + 1}"
        member = guild.get_member(int(user_id))
        name = member.mention if member else f"<@{user_id}> (خرج من السيرفر)"
        lines.append(f"{prefix} {name} — Level {data['level']} ({total_xp_earned(data)} XP)")

    embed = discord.Embed(
        title="🏆 لائحة الشرف (Leaderboard)",
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
    return embed


@bot.hybrid_command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard_cmd(ctx):
    """كيبين أفضل 10 أعضاء نشيطين فالسيرفر (الأكثر XP)"""
    if not bot_settings['leveling_enabled']:
        await ctx.send("❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).", delete_after=6)
        return

    embed = build_leaderboard_embed(ctx.guild)
    if not embed:
        await ctx.send("ماكاين حتى عضو ربح XP دابا.")
        return
    await ctx.send(embed=embed)


@tasks.loop(minutes=LEADERBOARD_UPDATE_MINUTES)
async def update_leaderboard():
    """كتحدث رسالة لائحة الشرف أوتوماتيكياً فـ LEADERBOARD_CHANNEL_ID كل LEADERBOARD_UPDATE_MINUTES
    (كتبدل نفس الرسالة، ماكتبعثش وحدة جديدة كل مرة)."""
    if not bot_settings['leveling_enabled'] or not LEADERBOARD_CHANNEL_ID:
        return
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        print(f"[LEADERBOARD] ❌ ماكاينش channel بـ ID {LEADERBOARD_CHANNEL_ID}")
        return

    guild = channel.guild
    embed = build_leaderboard_embed(guild)
    if not embed:
        return  # ماكاين حتى عضو ربح XP بعد، منتظرين

    msg_id = leaderboard_message_ids.get(str(guild.id))
    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[LEADERBOARD] خطأ فـ التعديل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        leaderboard_message_ids[str(guild.id)] = new_msg.id
        save_leaderboard_message_ids()
    except Exception as e:
        print(f"[LEADERBOARD] خطأ فـ البعث: {e}")


@update_leaderboard.before_loop
async def before_update_leaderboard():
    await bot.wait_until_ready()


@update_leaderboard.error
async def update_leaderboard_error(error):
    print(f"[LEADERBOARD] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_leaderboard.is_running():
        update_leaderboard.restart()


@bot.hybrid_command(name="setlevel")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setlevel_cmd(ctx, member: discord.Member, level: int):
    """كيحط عضو مباشرة فمستوى معين (Admin) — مفيد إلا بغيتي تصحح غلط ولا تعطي مستوى بداية"""
    data = get_user_level_data(ctx.guild.id, member.id)
    data["level"] = max(0, level)
    data["xp"] = 0
    save_levels()
    await ctx.send(f"✅ {member.mention} تحط فـ Level {data['level']}.")


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    await setup_verify_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setupblacklist(ctx):
    """يصاوب رسالة الممنوعات والعقوبات فـ Blacklist channel"""
    if not BLACKLIST_CHANNEL_ID:
        await ctx.send("❌ خاصك تحط `BLACKLIST_CHANNEL_ID` فالـ CONFIG أولاً!")
        return
    await setup_blacklist_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة Blacklist!", delete_after=5)


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
async def setuprules(ctx):
    """يصاوب رسالة القوانين + زرارات كنوافق/كنرفض فـ rules channel"""
    await setup_rules_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة القوانين بالأزرار!", delete_after=5)


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
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


@bot.hybrid_command()
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


@bot.hybrid_command()
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
        value=f"Mute@{bot_settings['mute_after_warns']} / Kick@{bot_settings['kick_after_warns']} / Ban@{bot_settings['ban_after_warns']}",
        inline=True
    )
    embed.add_field(name="🚫 Banned Words", value=f"`{len(get_active_banned_words())}`", inline=True)
    embed.set_footer(text="GGMW9")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="remind", aliases=["تذكير", "reminder"],
                     description="صاوب تذكير ليك: /remind [#شانيل] 10m/21:00 الرسالة")
async def remind_cmd(ctx, channel: Optional[discord.TextChannel] = None, *, rest: str):
    """
    كل واحد يصاوب تذكير لراسو، فأي وقت وأي شانيل بغى:
    /remind 10m اشرب الما                     ← بعد 10 دقايق، فنفس الشانيل
    /remind 21:00 نوض                         ← اليوم/غدا فـ 21:00، فنفس الشانيل
    /remind #general 2h30m سلام              ← بعد ساعتين ونص، فـ #general
    /remind #announcements 2026-07-25-18:00 حدث ← نهار محدد بالضبط
    """
    parts = rest.strip().split(maxsplit=1)
    if len(parts) < 2:
        await ctx.send(
            "❌ خاصك تحط الوقت والرسالة. مثال: `/remind 10m اشرب الما`\n"
            "استعمل `/help` باش تشوف كاع الصيغ الممكنة.",
            delete_after=15
        )
        return

    وقت, رسالة = parts[0], parts[1]
    target_channel = channel or ctx.channel

    if ctx.guild and target_channel.guild and target_channel.guild.id != ctx.guild.id:
        await ctx.send("❌ الشانيل خاصو يكون فنفس السيرفر.", delete_after=10)
        return

    if ctx.guild:
        perms = target_channel.permissions_for(ctx.guild.me)
        if not perms.send_messages:
            await ctx.send(f"❌ ما عنديش صلاحية نبعث فـ {target_channel.mention}.", delete_after=10)
            return

    target_dt = parse_time_input(وقت)
    if not target_dt:
        embed = discord.Embed(
            title="❌ الوقت ماشي صحيح!",
            description=(
                "استعمل شي صيغة من هادو:\n"
                "`10m` / `2h` / `1h30m` / `1d` — بعد مدة من دابا\n"
                "`21:00` — اليوم فهاد الساعة (وإلا غدا إلا فاتت)\n"
                "`2026-07-25-21:00` — نهار محدد بالضبط\n\n"
                "مثال كامل: `/remind #general 2h30m سلام`"
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=25)
        return

    if target_dt <= datetime.now():
        await ctx.send("❌ الوقت لي حطيتي فات! حط وقت فالمستقبل.", delete_after=10)
        return

    if target_dt > datetime.now() + timedelta(days=90):
        await ctx.send("❌ ما نقدرش نحط تذكير فوق 90 يوم.", delete_after=10)
        return

    global next_reminder_id
    reminder = {
        "id": next_reminder_id,
        "user_id": str(ctx.author.id),
        "channel_id": target_channel.id,
        "guild_id": ctx.guild.id if ctx.guild else None,
        "message": رسالة,
        "remind_at": target_dt.isoformat(),
        "created_at": datetime.now().isoformat(),
    }
    reminders.append(reminder)
    next_reminder_id += 1
    save_reminders()

    ts = int(target_dt.timestamp())
    embed = discord.Embed(
        title="⏰ تسجل التذكير!",
        description=f"غادي نذكرك بـ:\n> {رسالة}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📅 وقت التذكير", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
    embed.add_field(name="📍 الشانيل", value=target_channel.mention, inline=False)
    embed.set_footer(text=f"GGMW9 | ID: {reminder['id']}")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="reminders", aliases=["تذكيراتي"])
async def reminders_cmd(ctx):
    """كيبين التذكيرات المبرمجة ديال الشخص اللي طلب الأمر"""
    user_id = str(ctx.author.id)
    user_reminders = sorted(
        (r for r in reminders if r["user_id"] == user_id),
        key=lambda r: r["remind_at"]
    )
    if not user_reminders:
        await ctx.send("📭 ماعندكش أي تذكير مبرمج دابا.", delete_after=10)
        return

    embed = discord.Embed(title="⏰ التذكيرات ديالك", color=discord.Color.blue(), timestamp=datetime.now())
    for r in user_reminders[:15]:
        ts = int(datetime.fromisoformat(r["remind_at"]).timestamp())
        text = r["message"] if len(r["message"]) <= 200 else r["message"][:200] + "..."
        chan_txt = f"<#{r['channel_id']}>"
        embed.add_field(name=f"#{r['id']}", value=f"{text}\n<t:{ts}:R> — {chan_txt}", inline=False)
    embed.set_footer(text="/delreminder <ID> باش تلغي وحدة")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="delreminder", aliases=["حذف_تذكير"])
async def delreminder_cmd(ctx, reminder_id: int):
    """كيحيد تذكير (غير ديال الشخص اللي صاوبو)"""
    user_id = str(ctx.author.id)
    target = next((r for r in reminders if r["id"] == reminder_id and r["user_id"] == user_id), None)
    if not target:
        await ctx.send("❌ ماكاينش هاد التذكير عندك (تأكد من الـ ID).", delete_after=10)
        return
    reminders.remove(target)
    save_reminders()
    await ctx.send(f"✅ تحذاف التذكير #{reminder_id}.", delete_after=10)


@bot.hybrid_command()
async def help(ctx):
    embed = discord.Embed(
        title="📋 قائمة أوامر GGMW9",
        description=(
            "**GGMW9** — بوت AI مغربي + Moderation + Verification + Auto-Info\n"
            "💡 كاع الأوامر دابا Slash Commands (`/`) بوحدها — اكتب `/` باش تشوف اللائحة ديال Discord."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    ai_cmds = (
        "`/chat <رسالة>` — هضر مع GGMW9\n"
        "`/نسيني` — امسح ذاكرتك\n"
        "`/ذاكرة` — شحال من رسالة فالذاكرة\n"
        "`/انعلمك <حاجة>` — علم GGMW9 شي حاجة"
    )
    embed.add_field(name="🤖 AI & ذاكرة", value=ai_cmds, inline=False)
    mod_cmds = (
        "`/kick @user [سبب]` — طرد عضو\n"
        "`/ban @user [سبب]` — حظر عضو\n"
        "`/unban <user_id>` — فك الحظر\n"
        "`/mute @user <دقائق> [سبب]` — كتم\n"
        "`/unmute @user` — فك الكتم\n"
        "`/warn @user <سبب>` — تحذير\n"
        "`/warns [@user]` — عرض التحذيرات\n"
        "`/unwarn @user` — مسح التحذيرات\n"
        "`/case <رقم>` — تفاصيل Case معين\n"
        "`/history [@user]` — سجل الـ Cases ديال عضو\n"
        "`/clear <عدد>` — حذف رسائل (1-100)"
    )
    embed.add_field(name="🛡️ موديراتورز", value=mod_cmds, inline=False)
    verif_cmds = (
        "`/setupverify` — صاوب رسالة التفعيل بـ ✅ (Admin)\n"
        "`/setuprules` — صاوب رسالة القوانين بـ أزرار كنوافق/كنرفض (Admin)\n"
        "`/verify @user` — يفعّل عضو يدوياً (Admin)\n"
        "`/unverify @user` — يرجعو @Unverified (Admin)"
    )
    embed.add_field(name="✅ تفعيل", value=verif_cmds, inline=False)
    ticket_cmds = (
        "`/setuptickets` — صاوب/عاود صاوب لوحة الـ Tickets (Admin)\n"
        "🎫 ضغط على الزر فاللوحة → كيتحلق channel خاص\n"
        "`/closeticket` — سد ticket بأمر (بديل للزر، جوة channel الـ ticket)"
    )
    embed.add_field(name="🎫 Tickets", value=ticket_cmds, inline=False)
    application_cmds = (
        "📋 ضغط على الزر فاللوحة → عمر الاستمارة (Modal)\n"
        "`/setupapplications` — صاوب/عاود صاوب لوحة الـ Applications (Admin)\n"
        "`/applications` — بين الطلبات المعلقة (Admin)\n"
        "✅/❌ أزرار قبول/رفض فـ channel المراجعة (Staff)"
    )
    embed.add_field(name="📋 Applications", value=application_cmds, inline=False)
    suggestion_cmds = (
        "`/suggest <فكرة>` — بعث اقتراح جديد\n"
        "👍/👎 صوّت على الاقتراحات ديال الآخرين\n"
        "✅/❌ أزرار قبول/رفض (Staff)"
    )
    embed.add_field(name="💡 Suggestions", value=suggestion_cmds, inline=False)
    birthday_cmds = (
        "`/setbirthday <يوم> <شهر>` — سجل عيد ميلادك (كيعطيك رول البرج أوتوماتيكياً ♈)\n"
        "`/birthday [@عضو]` — بين عيد ميلادك ولا ديال عضو (والبرج)\n"
        "`/birthdays` — أقرب 10 أعياد ميلاد جاية\n"
        "`/removebirthday` — حيد عيد ميلادك من السجل (وحيد رول البرج)"
    )
    embed.add_field(name="🎂 Birthdays", value=birthday_cmds, inline=False)
    relationship_cmds = (
        "`/marry @عضو` — اطلب زواج 💍 (خاصو يقبل بزر)\n"
        "`/divorce` — طلق الزوج/الزوجة ديالك\n"
        "`/marriage [@عضو]` — بين معلومات الزواج\n"
        "`/marriages` — أطول 10 علاقات فالسيرفر\n"
        "`/bestfriend @عضو` — اطلب Best Friend 🤝\n"
        "`/unbestfriend` — قطع الصداقة\n"
        "`/bestfriendinfo [@عضو]`, `/bestfriends` — معلومات و Leaderboard"
    )
    embed.add_field(name="💌 Marry / Bestfriend", value=relationship_cmds, inline=False)
    voice_room_cmds = (
        "`/roommutepanel [روم]` — بانل كامل للتحكم فروم صوتي (Staff/صاحب الروم):\n"
        "🔇 **كتم الكل** — كيكتم كاع اللي فالروم بلا استثناء (حتى Admin/Mod) + أي واحد يدخل من بعد كيتكتم توا\n"
        "🔊 **فك الكل** — كيفك الكتم على الجميع ويحل الروم عادي\n"
        "🎯 **Select عضو معين** — بدل الحالة (كتم/فك) ديال شخص وحدو بوحدو، بلا ماتمس الباقي\n"
        "`/voicerename`, `/voicelimit`, `/voicelock`, `/voiceunlock` — تحكم فالروم المؤقت ديالك"
    )
    embed.add_field(name="🎙️ Voice Rooms", value=voice_room_cmds, inline=False)
    raid_cmds = (
        "`/lockdown [دقائق]` — فعّل Anti-Raid Lockdown يدوياً (Admin)\n"
        "`/unlockdown` — سد الـ Lockdown يدوياً (Admin)\n"
        "`/raidstatus` — شوف الحالة دابا"
    )
    embed.add_field(name="🚨 Anti-Raid", value=raid_cmds, inline=False)
    embed.add_field(
        name="🖼️ Welcome Card",
        value="`/testwelcome [@عضو]` — جرب شكل الكارطة الترحيبية هنا فالشات (Admin)",
        inline=False
    )
    level_cmds = (
        "`/rank [@user]` — شوف المستوى والـ XP ديالك ولا ديال عضو آخر\n"
        "`/leaderboard` — أفضل 10 أعضاء نشيطين\n"
        "`/setlevel @user <رقم>` — حط عضو فمستوى معين يدوياً (Admin)\n"
        "`/setuplevels` — صاوب/عاود صاوب رسالة شرح النظام (Admin)"
    )
    embed.add_field(name="📊 Leveling", value=level_cmds, inline=False)
    roles_cmds = (
        "`/setuproles` — صاوب رسالة اختيار الأدوار (Admin)\n"
        "`/listroles` — بين رسائل Reaction Roles الفعّالة (Admin)"
    )
    embed.add_field(name="🎭 Reaction Roles", value=roles_cmds, inline=False)
    util_cmds = (
        "`/ping` — سرعة البوت\n"
        "`/info` — معلومات البوت\n"
        "`/help` — هاد القائمة\n"
        "`/testinfo` — جرب Auto-Info فوراً (Admin)"
    )
    embed.add_field(name="🔧 أدوات", value=util_cmds, inline=False)
    reminder_cmds = (
        "`/remind [#شانيل] <وقت> <رسالة>` — صاوب تذكير\n"
        "`/remind 10m اشرب الما` — بعد 10 دقايق، فنفس الشانيل\n"
        "`/remind 21:00 نوض` — اليوم فـ 21:00 (وإلا غدا إلا فاتت)\n"
        "`/remind #general 2h30m سلام` — بعد ساعتين ونص، فـ #general\n"
        "`/remind #الشانيل 2026-07-25-18:00 حدث` — نهار محدد بالضبط\n"
        "`/reminders` — التذكيرات ديالك المبرمجة\n"
        "`/delreminder <ID>` — لغي تذكير"
    )
    embed.add_field(name="⏰ تذكيرات", value=reminder_cmds, inline=False)
    auto_mod = (
        "✅ كلمات ممنوعة\n"
        "✅ كشف السبام (5 msg/5s)\n"
        "✅ Auto-mute\n"
        "✅ Auto-kick (3 warns)\n"
        "✅ Logs كاملة فـ #mod-logs بـ Case ID (`/case`, `/history`)"
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
    embed.set_footer(text="GGMW9 | Slash Commands: /")
    await ctx.send(embed=embed)


@bot.hybrid_command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    response = await ask_ai(user_id, ctx.author.name, ctx.author.display_name, message)
    await ctx.send(response[:MAX_REPLY_LENGTH])


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@owner_only()
async def نسيني(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@owner_only()
async def ذاكرة(ctx):
    user_id = str(ctx.author.id)
    count = len(user_memory.get(user_id, [])) // 2
    await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@owner_only()
async def انعلمك(ctx, *, knowledge: str):
    learned_knowledge.append(knowledge)
    gender = detect_gender(ctx.author.name, ctx.author.display_name)
    if gender == "female":
        await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
    else:
        await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")


@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@owner_only()
async def انعلمك_شي_حاجة_جديدة(ctx, *, knowledge: str):
    await انعلمك(ctx, knowledge=knowledge)


# ═══════════════════════════════════════════════════════
# ║        COMMAND TEST INFO (جديد!)                      ║
# ═══════════════════════════════════════════════════════

@bot.hybrid_command()
@app_commands.default_permissions(administrator=True)
@owner_only()
async def testinfo(ctx, category: str = "all"):
    """
    جرب Auto-Info فوراً!
    الاستخدام: /testinfo [news|games|movies|anime|music|all]
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
        await ctx.send("❌ الاستخدام: `/testinfo [news|games|movies|anime|music|all]`")
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
    if bot_settings['auto_info_news']:
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
    if bot_settings['auto_info_games']:
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
    if bot_settings['auto_info_movies']:
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
    if bot_settings['auto_info_anime']:
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
    if bot_settings['auto_info_music']:
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


# ═══════════════════════════════════════════════════════
# ║      لائحة الإدارة (Administrators) — كل 30 دقيقة       ║
# ═══════════════════════════════════════════════════════

async def build_admin_list_embed(guild: discord.Guild) -> discord.Embed:
    """يبني embed فيه Owner + Admins + Mods مرتبين بالـ roles، باش لي بغا
    يدير report يعرف بسرعة شكون يدير ليه tag."""
    embed = discord.Embed(
        title="👑 لائحة الإدارة",
        description=(
            "هادي لائحة الـ Owner والـ Admins والـ Moderators ديال السيرفر.\n"
            "إلا بغيتي تدير report، دير tag لواحد من هادو حسب الحالة ديالك."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    already_listed_ids = set()

    # Owner فوق بوحدو
    owner_member = guild.get_member(OWNER_ID) if OWNER_ID else None
    if OWNER_ID:
        already_listed_ids.add(OWNER_ID)
    embed.add_field(
        name="👑 Owner",
        value=owner_member.mention if owner_member else (f"<@{OWNER_ID}>" if OWNER_ID else "—"),
        inline=False
    )

    # باقي الأدوار بالترتيب المحدد فـ STAFF_ROLES_ORDER
    for entry in STAFF_ROLES_ORDER:
        role = guild.get_role(entry["role_id"])
        if not role:
            embed.add_field(name=entry["label"], value="⚠️ هاد الرول ماكاينش فالسيرفر (تأكد من role_id)", inline=False)
            continue

        members = [m for m in role.members if m.id not in already_listed_ids]
        already_listed_ids.update(m.id for m in members)

        value = "\n".join(m.mention for m in members) if members else "— محدش دابا"
        embed.add_field(name=f"{entry['label']} ({len(members)})", value=value, inline=False)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"{SERVER_NAME} | آخر تحديث")
    return embed


@tasks.loop(minutes=ADMIN_LIST_UPDATE_MINUTES)
async def update_admin_list():
    if not ADMINISTRATORS_CHANNEL_ID:
        return
    channel = bot.get_channel(ADMINISTRATORS_CHANNEL_ID)
    if not channel:
        print(f"[ADMIN_LIST] ❌ ماكاينش channel بـ ID {ADMINISTRATORS_CHANNEL_ID}")
        return

    guild = channel.guild
    embed = await build_admin_list_embed(guild)
    msg_id = admin_list_message_ids.get(str(guild.id))

    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[ADMIN_LIST] خطأ فـ التعديل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        admin_list_message_ids[str(guild.id)] = new_msg.id
        save_admin_list_message_ids()
    except Exception as e:
        print(f"[ADMIN_LIST] خطأ فـ البعث: {e}")


@update_admin_list.before_loop
async def before_update_admin_list():
    await bot.wait_until_ready()


@update_admin_list.error
async def update_admin_list_error(error):
    print(f"[ADMIN_LIST] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_admin_list.is_running():
        update_admin_list.restart()


@auto_info.error
async def auto_info_error(error):
    """إلا وقع خطأ ما تصيدوش try/except ديال الفئات، هادي كنسجلوه، وكنعاودو نشغلو
    الـ loop (بلا هاد الشي، tasks.loop كيوقف نهائيا بصمت ملي يطيح خطأ ما تصيدش)."""
    print(f"[AUTO_INFO] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not auto_info.is_running():
        auto_info.restart()


# ═══════════════════════════════════════════════════════
# ║           Loop: كيتحقق من التذكيرات كل 30 ثانية        ║
# ═══════════════════════════════════════════════════════
@tasks.loop(seconds=30)
async def check_reminders():
    if not reminders:
        return

    now = datetime.now()
    due = [r for r in reminders if datetime.fromisoformat(r["remind_at"]) <= now]
    if not due:
        return

    for r in due:
        try:
            channel = bot.get_channel(r["channel_id"])
            if channel:
                embed = discord.Embed(
                    title="⏰ تذكير!",
                    description=r["message"],
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"GGMW9 | ID: {r['id']}")
                await channel.send(content=f"<@{r['user_id']}>", embed=embed)
            else:
                print(f"[REMINDERS] ❌ ماكاينش channel بـ ID {r['channel_id']} (تذكير #{r['id']})")
        except Exception as e:
            print(f"[REMINDERS] خطأ فـ بعث التذكير #{r['id']}: {e}")
        reminders.remove(r)

    save_reminders()


@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()


@check_reminders.error
async def check_reminders_error(error):
    print(f"[REMINDERS] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not check_reminders.is_running():
        check_reminders.restart()


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
            description=f"استخدم `/help` باش تشوف كيفاش تستخدم الأمر.",
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
    print(f"📰 News: {'نشط' if bot_settings['auto_info_news'] else 'معطل مؤقتا'} {NEWS_CHANNEL_IDS}")
    print(f"🎮 Games: {'نشط' if bot_settings['auto_info_games'] else 'معطل مؤقتا'} {GAMES_CHANNEL_IDS}")
    print(f"🎬 Movies: {'نشط' if bot_settings['auto_info_movies'] else 'معطل مؤقتا'} {MOVIES_CHANNEL_IDS}")
    print(f"📺 Anime: {'نشط' if bot_settings['auto_info_anime'] else 'معطل مؤقتا'} {ANIME_CHANNEL_IDS}")
    print(f"🎧 Music: {'نشط' if bot_settings['auto_info_music'] else 'معطل مؤقتا'} {MUSIC_CHANNEL_IDS}")
    print(f"⏱️ Timeout: {API_TIMEOUT}s")
    print(f"🛡️ Moderation: نشط")
    print(f"✅ Verification: نشط")
    print(f"📰 Auto-Info: نشط (5 channels + APIs حقيقية)")
    print(f"⚠️ Warn Escalation: Mute@{bot_settings['mute_after_warns']} / Kick@{bot_settings['kick_after_warns']} / Ban@{bot_settings['ban_after_warns']}")
    print(f"📊 Stats Channel: {STATS_CHANNEL_ID if STATS_CHANNEL_ID else 'ماشي معطي بعد'} (كل {STATS_UPDATE_MINUTES} د)")
    print(f"🏆 Leaderboard أوتوماتيكي: {LEADERBOARD_CHANNEL_ID if LEADERBOARD_CHANNEL_ID else 'ماشي معطي بعد'} (كل {LEADERBOARD_UPDATE_MINUTES} د)")
    print(f"👑 Administrators Channel: {ADMINISTRATORS_CHANNEL_ID if ADMINISTRATORS_CHANNEL_ID else 'ماشي معطي بعد'} (كل {ADMIN_LIST_UPDATE_MINUTES} د)")
    print(f"🎫 Tickets: Panel={TICKETS_PANEL_CHANNEL_ID or 'ماشي معطي'} | Category={TICKETS_CATEGORY_ID or 'ماشي معطي'} | Logs={TICKET_LOGS_CHANNEL_ID or 'MOD_LOGS_CHANNEL_ID'}")
    print(f"📋 Applications: Panel={APPLICATIONS_PANEL_CHANNEL_ID or 'ماشي معطي'} | Review={APPLICATIONS_REVIEW_CHANNEL_ID or 'MOD_LOGS_CHANNEL_ID'} | Cooldown={APPLICATIONS_COOLDOWN_HOURS}h")
    print(f"💡 Suggestions: Channel={SUGGESTIONS_CHANNEL_ID or 'ماشي معطي'}")
    print(f"🎂 Birthdays: Channel={BIRTHDAY_ANNOUNCE_CHANNEL_ID or 'ماشي معطي'} | Role={BIRTHDAY_ROLE_ID or 'بلا رول'} | Hour={BIRTHDAY_ANNOUNCE_HOUR}:00 UTC")
    print(f"🚨 Anti-Raid: {'نشط' if bot_settings['anti_raid_enabled'] else 'معطل'} (عتبة: {bot_settings['raid_join_threshold']} فـ {bot_settings['raid_join_interval_seconds']}ث | عمل: {bot_settings['raid_action']})")
    print(f"🖼️ Welcome Cards: {'نشط' if (bot_settings['welcome_card_enabled'] and PIL_AVAILABLE) else ('معطل (Pillow ماشي مثبت)' if not PIL_AVAILABLE else 'معطل')}")
    print(f"📊 Leveling: {'نشط' if bot_settings['leveling_enabled'] else 'معطل'} (شات: {xp_settings['chat_min']}-{xp_settings['chat_max']} XP/رسالة، cooldown {xp_settings['chat_cooldown']}ث)")
    print(f"⏰ Reminders: {len(reminders)} مبرمجين (كيتفقّد كل 30 ثانية)")
    print(f"🌐 Auto-Translate: {'نشط' if bot_settings['auto_translate_enabled'] else 'معطل'} ({len(FLAG_TO_LANGUAGE)} علم مدعوم) | Auto-React: {'نشط' if bot_settings['auto_react_enabled'] else 'معطل'} ({', '.join(AUTO_REACT_FLAGS) if AUTO_REACT_FLAGS else 'بلا أعلام'})")
    print(f"🔊 Join to Create: {'نشط' if (bot_settings['join_to_create_enabled'] and JOIN_TO_CREATE_CHANNEL_ID) else 'معطل'} | Voice XP: {'نشط' if bot_settings['voice_xp_enabled'] else 'معطل'} (فويس: {xp_settings['voice_per_interval']} / لايفستريم: {xp_settings['stream_per_interval']} XP كل {xp_settings['voice_interval_minutes']}د)")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"/help | {len(bot.guilds)} سيرفرات"
        )
    )

    if not auto_info.is_running():
        auto_info.start()

    if STATS_CHANNEL_ID and not update_stats.is_running():
        update_stats.start()

    if LEADERBOARD_CHANNEL_ID and not update_leaderboard.is_running():
        update_leaderboard.start()

    if ADMINISTRATORS_CHANNEL_ID and not update_admin_list.is_running():
        update_admin_list.start()

    if not check_reminders.is_running():
        check_reminders.start()

    if not birthday_loop.is_running():
        birthday_loop.start()

    if not voice_xp_loop.is_running():
        voice_xp_loop.start()

    if TRIVIA_ENABLED and TRIVIA_AUTO_CHANNEL_IDS and not trivia_auto_loop.is_running():
        trivia_auto_loop.start()

    bot.add_view(RulesVerifyView())  # باش الأزرار يبقاو خدامين حتى بعد ريستارت البوت
    bot.add_view(RolePickerView())   # باش الـ Dropdown ديال الأدوار يبقى خدام حتى بعد ريستارت البوت
    bot.add_view(TicketPanelView())    # باش زر "دير Ticket" يبقى خدام حتى بعد ريستارت البوت
    bot.add_view(TicketControlView())  # باش أزرار Claim/Close يبقاو خدامين فكاع الـ tickets المفتوحة
    bot.add_view(ApplicationPanelView())   # باش زر "قدم طلب Staff" يبقى خدام حتى بعد ريستارت البوت
    bot.add_view(ApplicationReviewView())  # باش أزرار قبول/رفض الطلبات يبقاو خدامين
    bot.add_view(SuggestionReviewView())   # باش أزرار قبول/رفض الاقتراحات يبقاو خدامين
    bot.add_view(RoomMuteToggleView())     # باش زر كتم/فك كتم الروم يبقى خدام حتى بعد ريستارت البوت
    bot.add_view(TriviaGamePanelView())    # باش زر "🎮 ابدأ اللعب" ديال Trivia يبقى خدام حتى بعد ريستارت البوت

    for guild in bot.guilds:
        # ملاحظة: ماعادش كنبعثو رسالة "تفعيل العضوية" القديمة (بالريأكشن ✅)
        # باش ما تبقاش مكررة مع رسالة القوانين الجديدة بالأزرار (setup_rules_message)
        await setup_rules_message(guild)
        if BLACKLIST_CHANNEL_ID:
            await setup_blacklist_message(guild)
        if TICKETS_PANEL_CHANNEL_ID:
            await setup_tickets_panel(guild)
        if APPLICATIONS_PANEL_CHANNEL_ID:
            await setup_applications_panel(guild)
        if LEVELS_INFO_CHANNEL_ID:
            await setup_levels_info_message(guild)
        if SUGGESTIONS_CHANNEL_ID:
            await setup_suggestions_info(guild)
        if TRIVIA_CHANNEL_ID:
            await setup_trivia_panel(guild)

        problems = check_role_hierarchy(guild)
        if problems:
            print(f"[ROLE CHECK] ⚠️ {guild.name}: مشاكل فترتيب الرولات:")
            for p in problems:
                print(f"  - {p}")
            await log_action(
                guild,
                "⚠️ مشكل فترتيب الرولات",
                "نظام التفعيل ممكن ما يخدمش مزيان:\n\n" + "\n\n".join(problems) +
                "\n\nاستعمل `/checkroles` بعد ما تصلح باش تتأكد.",
                discord.Color.orange()
            )

    # ═══════ Slash Commands (/) — sync مرة وحدة فقط (on_ready يقدر يتكرر عند reconnect) ═══════
    global _slash_synced
    if not _slash_synced:
        try:
            for guild in bot.guilds:
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
            print(f"✅ Slash Commands (/) تزامنو مع {len(bot.guilds)} سيرفر (فوريين).")
        except discord.HTTPException as e:
            print(f"⚠️ خطأ فـ sync ديال Slash Commands: {e}")
            print(f"[SYNC-DEBUG] status={e.status} code={e.code}")
            print(f"[SYNC-DEBUG] تفاصيل دقيقة من Discord:\n{e.text}")
        except Exception as e:
            print(f"⚠️ خطأ فـ sync ديال Slash Commands: {e}")
        _slash_synced = True


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
