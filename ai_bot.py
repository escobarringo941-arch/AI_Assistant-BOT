import os
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

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

TARGET_CHANNEL_ID = 1526384339670270012
WELCOME_CHANNEL_ID = 1524957892925456545
SERVER_NAME = "GGMW9"

AI_MODEL = "deepseek/deepseek-chat"

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

NEWS_CHANNEL_ID = 1526701863141900319
GAMES_CHANNEL_ID = 1524957892925456546
MOVIES_CHANNEL_ID = 1526721884434206820
ANIME_CHANNEL_ID = 1526726257012772985
MUSIC_CHANNEL_ID = 1524957892925456547

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
    "1️⃣ الاحترام واجب بين كاع الأعضاء — ممنوع السب، العنصرية، والتنمر.\n"
    "2️⃣ ممنوع السبام والإعلانات بلا إذن من الإدارة.\n"
    "3️⃣ ممنوع المحتوى ديال +18 ولا العنيف ولا الصادم.\n"
    "4️⃣ هضر فـ الشات المخصص ليه (بحال #games للألعاب).\n"
    "5️⃣ احترم القرارات ديال الأدمن والمشرفين.\n"
    "6️⃣ ممنوع مشاركة معلومات شخصية ديال الآخرين (Doxxing).\n"
    "7️⃣ عدم الالتزام بالقوانين غادي يأدي لعقوبة (تحذير، كتم، طرد)."
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

SPAM_THRESHOLD = 5
SPAM_INTERVAL = 5
WARN_LIMIT = 3

# ═══════════════════════════════════════════════════════
# ║              REACTION ROLES CONFIG                     ║
# ═══════════════════════════════════════════════════════
# حط هنا الإيموجي ↔ ID ديال الرول (كليك يمين على الرول فـ Discord → Copy ID)
# خاصك تفعّل "Developer Mode" فـ Discord Settings > Advanced باش يبان ليك Copy ID
REACTION_ROLES = {
    "🎮": 1526800480007880845,  # ← حط ID دور Gamer
    "📺": 1526800623419523072,  # ← حط ID دور Anime Fan
    "🎬": 1526801019458158642,  # ← حط ID دور Movie Fan
    "🎧": 1526801165692702842,  # ← حط ID دور Music Fan
}

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100
learned_knowledge = []
warns_db = {}
spam_tracker = {}
mute_tasks = {}
reaction_role_messages = {}  # {message_id: {emoji: role_id}}

# ═══════════════════════════════════════════════════════
# ║   سجل المحتوى المنشور (باش ما يتعاودش تا شي حاجة)      ║
# ═══════════════════════════════════════════════════════
POSTED_HISTORY_FILE = "posted_history.json"

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
    "anime": 800,
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

REACTION_ROLES_FILE = "reaction_roles.json"


def load_reaction_role_messages():
    """يقرا رسائل Reaction Roles المحفوظة من ملف JSON (باش ما تتمسحش عند restart)"""
    global reaction_role_messages
    try:
        with open(REACTION_ROLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # الـ keys فـ JSON دايما strings، خاصنا نرجعوهم int (message_id)
        reaction_role_messages = {int(msg_id): roles_map for msg_id, roles_map in data.items()}
        print(f"[REACTION ROLES] تحمل {len(reaction_role_messages)} رسالة محفوظة")
    except FileNotFoundError:
        print("[REACTION ROLES] ماكاينش سجل سابق، غادي نبداو من الصفر")
    except Exception as e:
        print(f"[REACTION ROLES] خطأ فـ التحميل: {e}")


def save_reaction_role_messages():
    """يحفظ رسائل Reaction Roles فـ ملف JSON"""
    try:
        with open(REACTION_ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in reaction_role_messages.items()}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[REACTION ROLES] خطأ فـ الحفظ: {e}")


load_reaction_role_messages()


def get_system_prompt(user_gender="unknown"):
    base_prompt = 'أنت "سيمو"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.'
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
    base_prompt += 'رد دائماً كأنك **سيمو من الدار البيضاء** — واقعي، ذكي، عصبي!'

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


async def ask_ai(user_id: str, username: str, display_name: str, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT"
    }
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
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "max_tokens": MAX_REPLY_LENGTH,
        "temperature": CREATIVITY
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    if len(user_memory[user_id]) > MEMORY_SIZE * 2:
                        user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
                    server_memory.append({"role": "user", "content": f"[{username}]: {prompt}"})
                    server_memory.append({"role": "assistant", "content": reply})
                    if len(server_memory) > MAX_SERVER_MEMORY * 2:
                        server_memory[:] = server_memory[-MAX_SERVER_MEMORY * 2:]
                    return reply
                else:
                    error = await resp.text()
                    return f"❌ Error {resp.status}: {error[:200]}"
    except asyncio.TimeoutError:
        return "⏳ تعطل شوية... عاود سولني!"
    except Exception as e:
        return f"❌ Exception: {str(e)[:200]}"


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
        html = await fetch_html(page_url, headers={"User-Agent": "Mozilla/5.0 (compatible; SimoBot/1.0)"})
        if not html:
            return ""
        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
        return match.group(1) if match else ""
    except Exception as e:
        print(f"[OG_IMAGE] خطأ فـ جلب الصورة من {page_url}: {e}")
        return ""


async def translate_to_darija(text: str) -> str:
    """يترجم نص من الانجليزية للدارجة المغربية عبر نفس الـ AI (DeepSeek)"""
    if not text or not OPENROUTER_API_KEY:
        return text
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT"
    }
    payload = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "نتا مترجم محترف. ترجم النص التالي من الانجليزية للدارجة المغربية "
                    "بطريقة طبيعية وسلسة ومفهومة. غير الترجمة، بلا مقدمات، بلا تعليقات، "
                    "بلا علامات تنصيص."
                )
            },
            {"role": "user", "content": text}
        ],
        "max_tokens": 700,
        "temperature": 0.3
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated = data["choices"][0]["message"]["content"].strip()
                    return translated if translated else text
                else:
                    print(f"[TRANSLATE] status {resp.status}")
                    return text
    except Exception as e:
        print(f"[TRANSLATE] Exception: {e}")
        return text


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
                "genre": omdb_data.get("Genre", "N/A"),
                "plot": plot_ar,
                "rating": rating,
                "poster": poster,
                "imdb": f"https://www.imdb.com/title/{imdb_id}/"
            }

    return {}


async def get_anime_from_jikan() -> dict:
    """
    اكتشاف عشوائي حقيقي للأنمي عبر Jikan /random/anime (بلا لائحة ثابتة).
    كنفلتراو بـ score و members باش نضمنو أنمي معروف ومزيان، وكنحترمو rate-limit
    ديال Jikan بـ sleep بين كل محاولة.
    """
    jikan_headers = {"User-Agent": "Mozilla/5.0 (compatible; SimoBot/1.0)"}

    for attempt in range(8):  # يجرب حتى 8 مرات قبل ما يستسلم
        if attempt > 0:
            await asyncio.sleep(1.2)  # نحترمو rate-limit ديال Jikan

        data = await fetch_json("https://api.jikan.moe/v4/random/anime", headers=jikan_headers)
        anime = data.get("data") if data else None
        if not anime:
            continue

        mal_id = anime.get("mal_id")
        if not mal_id or is_posted("anime", str(mal_id)):
            continue

        score = anime.get("score") or 0
        members = anime.get("members") or 0
        if score < 6.5 or members < 30000:  # نفلترو الحوايج المغمورة بزاف
            continue

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
            "genres": ", ".join([g["name"] for g in anime.get("genres", [])]),
            "synopsis": synopsis_ar,
            "score": anime.get("score", 0),
            "poster": poster,
            "url": anime.get("url", "")
        }

    return {}


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
                "genres": ", ".join([g["name"] for g in detail.get("genres", [])]),
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
        embed.set_footer(text=f"سيمو | {datetime.now().strftime('%H:%M:%S')}")
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


async def add_warn(member: discord.Member, reason: str) -> int:
    user_id = str(member.id)
    if user_id not in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}
    warns_db[user_id]["count"] += 1
    warns_db[user_id]["reasons"].append(reason)
    warns_db[user_id]["dates"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    return warns_db[user_id]["count"]


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
    embed.set_footer(text="سيمو | Verification System")
    msg = await verify_channel.send(embed=embed)
    await msg.add_reaction("✅")


# ═══════════════════════════════════════════════════════
# ║   نظام القوانين + التفعيل بالأزرار (Buttons)           ║
# ║   (كيبان مباشرة تحت القوانين، بحال المواقع)              ║
# ═══════════════════════════════════════════════════════

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


class RulesVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # باش يبقى خدام للأبد (persistent view)

    def _is_exempt(self, member: discord.Member) -> bool:
        if member.id == OWNER_ID:
            return True
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)

    @discord.ui.button(label="كنوافق", style=discord.ButtonStyle.success, emoji="✅", custom_id="rules_agree_button")
    async def agree_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return

        member_role = guild.get_role(MEMBER_ROLE_ID)
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)

        if member_role and member_role in member.roles:
            await interaction.response.send_message("✅ راك مفعل من قبل، مرحبا بيك!", ephemeral=True)
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
                    "❌ ما قدرتش نفعلك، بلغ الإدارة (البوت ماعندوش صلاحية كافية — "
                    "غالبا role ديال البوت تحت فـ ترتيب الرولات، خاصو يكون فوق role ديال Member).",
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
            f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك، استمتع/ي 🎉", ephemeral=True
        )

        await log_action(
            guild,
            "✅ تفعيل (زر القوانين)",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الحالة:** وافق على القوانين وتفعل",
            discord.Color.green()
        )

        gender_embed = discord.Embed(
            title="🚻 واش نتا/نتي ولد ولا بنت؟",
            description="ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
            color=discord.Color.blurple()
        )
        await interaction.followup.send(
            embed=gender_embed,
            view=GenderSelectView(target_user_id=member.id, guild_id=guild.id),
            ephemeral=True
        )

    @discord.ui.button(label="كنرفض", style=discord.ButtonStyle.danger, emoji="❌", custom_id="rules_refuse_button")
    async def refuse_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return

        if self._is_exempt(member):
            await interaction.response.send_message(
                "⚠️ راك أدمن/مشرف، ماغاديش نطردك، ولكن هاد الزر معناه رفض القوانين للأعضاء العاديين.",
                ephemeral=True
            )
            return

        try:
            await interaction.response.send_message(
                "❌ رفضتي القوانين، غادي تتطرد من السيرفر...", ephemeral=True
            )
        except Exception:
            pass

        try:
            await member.send(f"❌ رفضتي القوانين ديال **{SERVER_NAME}**، تم طردك من السيرفر تلقائياً.")
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
        title="📜 قوانين السيرفر",
        description=(
            f"{SERVER_RULES}\n\n"
            f"⚠️ **باش تقدر/ي تهضر/ي وتفاعل/ي فالسيرفر، خاصك توافق/ي على هاد القوانين بالضغط على ✅ تحت.**\n"
            f"إلا ضغطتي على ❌ (رفض)، غادي تتطرد من السيرفر تلقائياً."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="سيمو | Rules & Verification")
    await rules_channel.send(embed=embed, view=RulesVerifyView())


async def setup_blacklist_message(guild: discord.Guild):
    """كيبعث embed فـ channel 'Blacklist things' فيه الممنوعات والعقوبات المتدرجة بالتفصيل"""
    channel = bot.get_channel(BLACKLIST_CHANNEL_ID)
    if not channel:
        return
    async for message in channel.history(limit=10):
        if message.author == bot.user and "Blacklist" in (message.embeds[0].title if message.embeds else ""):
            return

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
            f"1️⃣ **تحذير** — كل مخالفة خفيفة كتبان تحذير أوتوماتيكي ({WARN_LIMIT} تحذيرات = طرد)\n"
            f"2️⃣ **كتم (Mute)** — إلا بعتي {SPAM_THRESHOLD} رسايل فـ {SPAM_INTERVAL} ثواني (سبام)، كتتكتم أوتوماتيك\n"
            f"3️⃣ **طرد (Kick)** — عند الوصول لـ {WARN_LIMIT}/{WARN_LIMIT} تحذيرات\n"
            f"4️⃣ **حظر (Ban) مباشر** — Doxxing، محتوى +18، تهديد خطير، أو تكرار الطرد"
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
                "مثال: `!report @Simo بعث رابط ديال سيرفر آخر فـ #general`\n\n"
                "**2) بلاغ عام (بلا ما تحدد عضو):**\n"
                "`!report وصف المشكل`\n"
                "مثال: `!report كاين ناس كيهضرو بزربة فـ #announcements`\n\n"
                "💡 **نصيحة:** إلا عندك سكرين شوت ديال المخالفة، بعثو مباشرة للمشرفين ولا فـ نفس الرسالة معاك (mention العضو بحال Ahmed)\n"
                "⚠️ الرسالة ديالك كتمسح أوتوماتيك من الشات العام والبلاغ كيوصل مباشرة للإدارة، حتى حد ماغاديش يشوف بلي بلغتي."
            ),
            inline=False
        )

    embed.set_footer(text="سيمو | Auto-Moderation System")
    await channel.send(embed=embed)


@bot.event
async def on_member_join(member):
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
        embed.set_footer(text="سيمو | Verification System")
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

    # ═══════ Reaction Roles ═══════
    if payload.message_id in reaction_role_messages:
        emoji = str(payload.emoji)
        role_id = reaction_role_messages[payload.message_id].get(emoji)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass
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
async def on_raw_reaction_remove(payload):
    """كينزع الرول إلا نزع العضو الـ reaction ديالو"""
    if payload.message_id not in reaction_role_messages:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    emoji = str(payload.emoji)
    role_id = reaction_role_messages[payload.message_id].get(emoji)
    if role_id:
        role = guild.get_role(role_id)
        if role:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
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
        for word in BANNED_WORDS:
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
                        f"**التحذيرات:** {count}/{WARN_LIMIT}",
                        discord.Color.red()
                    )
                    if count >= WARN_LIMIT:
                        try:
                            await message.author.kick(reason=f"3 تحذيرات (Auto-Mod)")
                            await message.channel.send(
                                f"🚫 {message.author.mention} تم طرده تلقائياً (3 تحذيرات)!",
                                delete_after=10
                            )
                            await log_action(
                                message.guild,
                                "🚫 Auto-Kick",
                                f"**المستخدم:** {message.author.mention}\n"
                                f"**السبب:** 3 تحذيرات (Auto-Mod)",
                                discord.Color.dark_red()
                            )
                            clear_warns(str(message.author.id))
                        except discord.Forbidden:
                            pass
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

    if "سيمو" in msg_lower or "simo" in msg_lower:
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
        embed.set_footer(text="سيمو | Moderation")
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
        embed.set_footer(text="سيمو | Moderation")
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
        embed.set_footer(text="سيمو | Moderation")
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
        embed.set_footer(text="سيمو | Moderation")
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
        embed.set_footer(text="سيمو | Moderation")
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
    embed.set_footer(text="سيمو | Report System")

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
    embed.add_field(name="عدد التحذيرات", value=f"{count}/{WARN_LIMIT}", inline=False)
    embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
    embed.set_footer(text="سيمو | Moderation")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "⚠️ تحذير",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**السبب:** {reason}\n"
        f"**العدد:** {count}/{WARN_LIMIT}\n"
        f"**المنفذ:** {ctx.author.mention}",
        discord.Color.yellow()
    )
    if count >= WARN_LIMIT:
        try:
            await member.kick(reason=f"3 تحذيرات: {reason}")
            await ctx.send(f"🚫 {member.mention} تم طرده تلقائياً (3 تحذيرات)!")
            await log_action(
                ctx.guild,
                "🚫 Auto-Kick",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**السبب:** 3 تحذيرات\n"
                f"**آخر تحذير:** {reason}",
                discord.Color.dark_red()
            )
            clear_warns(str(member.id))
        except discord.Forbidden:
            await ctx.send("❌ ما قدرتش نطردو!")


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
    embed.add_field(name="العدد", value=f"{user_warns['count']}/{WARN_LIMIT}", inline=False)
    if user_warns["reasons"]:
        reasons_text = "\n".join([
            f"{i+1}. {r} ({user_warns['dates'][i]})" 
            for i, r in enumerate(user_warns["reasons"])
        ])
        embed.add_field(name="الأسباب والتواريخ", value=reasons_text, inline=False)
    else:
        embed.add_field(name="الأسباب", value="ما كاين والو ✅", inline=False)
    embed.set_footer(text="سيمو | Moderation")
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
    embed.set_footer(text="سيمو | Moderation")
    await ctx.send(embed=embed)
    await log_action(
        ctx.guild,
        "✅ مسح تحذيرات",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**المنفذ:** {ctx.author.mention}",
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
    """يصاوب رسالة اختيار الأدوار بالـ Reactions (خاصك تعمر REACTION_ROLES فـ config أولاً)"""
    valid_roles = {}
    for emoji, role_id in REACTION_ROLES.items():
        if not role_id:
            continue
        role = ctx.guild.get_role(role_id)
        if role:
            valid_roles[emoji] = role_id

    if not valid_roles:
        await ctx.send(
            "❌ ماكاين حتى رول صالح فـ `REACTION_ROLES`!\n"
            "خاصك تحط IDs ديال الأدوار فـ config (فعّل Developer Mode فـ Discord، "
            "بعدها كليك يمين على الرول → Copy ID)."
        )
        return

    description = "كليك على الإيموجي باش تاخد الرول، وكليك عليه مرة أخرى باش تنزعو 🔄\n\n"
    description += "\n".join([
        f"{emoji} — <@&{role_id}>" for emoji, role_id in valid_roles.items()
    ])

    embed = discord.Embed(
        title="🎭 اختار الأدوار ديالك",
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="سيمو | Reaction Roles")

    msg = await ctx.send(embed=embed)
    for emoji in valid_roles:
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            pass

    reaction_role_messages[msg.id] = valid_roles
    save_reaction_role_messages()
    await ctx.send("✅ تصاوبات رسالة الأدوار!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def listroles(ctx):
    """يبين شحال من رسالة Reaction Roles فعّالة دابا"""
    if not reaction_role_messages:
        await ctx.send("ماكاين حتى رسالة Reaction Roles فعّالة دابا. استعمل `!setuproles`.")
        return
    lines = []
    for msg_id, roles_map in reaction_role_messages.items():
        roles_text = ", ".join([f"{e} → <@&{r}>" for e, r in roles_map.items()])
        lines.append(f"**Message ID:** `{msg_id}`\n{roles_text}")
    embed = discord.Embed(
        title="🎭 رسائل Reaction Roles الفعّالة",
        description="\n\n".join(lines),
        color=discord.Color.blue()
    )
    embed.set_footer(text="سيمو | Reaction Roles")
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
    embed.set_footer(text="سيمو | Verification")
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
    embed.set_footer(text="سيمو | Role Hierarchy Check")
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
    embed.set_footer(text="سيمو | Verification")
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
    embed.set_footer(text="سيمو")
    await ctx.send(embed=embed)


@bot.command()
async def info(ctx):
    embed = discord.Embed(
        title="🤖 معلومات سيمو",
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
    embed.add_field(name="⚠️ Warn Limit", value=f"`{WARN_LIMIT}`", inline=True)
    embed.add_field(name="🚫 Banned Words", value=f"`{len(BANNED_WORDS)}`", inline=True)
    embed.set_footer(text="سيمو | GGMW9")
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📋 قائمة أوامر سيمو",
        description="**سيمو** — بوت AI مغربي + Moderation + Verification + Auto-Info",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    ai_cmds = (
        "`!chat <رسالة>` — هضر مع سيمو\n"
        "`!نسيني` — امسح ذاكرتك\n"
        "`!ذاكرة` — شحال من رسالة فالذاكرة\n"
        "`!انعلمك <حاجة>` — علم سيمو شي حاجة"
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
    embed.set_footer(text="سيمو | GGMW9 | Prefix: !")
    await ctx.send(embed=embed)


@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    response = await ask_ai(user_id, ctx.author.name, ctx.author.display_name, message)
    await ctx.send(response[:MAX_REPLY_LENGTH])


@bot.command()
async def نسيني(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")


@bot.command()
async def ذاكرة(ctx):
    user_id = str(ctx.author.id)
    count = len(user_memory.get(user_id, [])) // 2
    await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")


@bot.command()
async def انعلمك(ctx, *, knowledge: str):
    learned_knowledge.append(knowledge)
    gender = detect_gender(ctx.author.name, ctx.author.display_name)
    if gender == "female":
        await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
    else:
        await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")


@bot.command()
async def انعلمك_شي_حاجة_جديدة(ctx, *, knowledge: str):
    await انعلمك(ctx, knowledge=knowledge)


# ═══════════════════════════════════════════════════════
# ║        COMMAND TEST INFO (جديد!)                      ║
# ═══════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(administrator=True)
async def testinfo(ctx, category: str = "all"):
    """
    جرب Auto-Info فوراً!
    الاستخدام: !testinfo [news|games|movies|anime|music|all]
    """
    categories = {
        "news": ("📰 News", NEWS_CHANNEL_ID, get_news_from_api, "NewsAPI"),
        "games": ("🎮 Games", GAMES_CHANNEL_ID, get_game_from_rawg, "RAWG.io"),
        "movies": ("🎬 Movies", MOVIES_CHANNEL_ID, get_movie_from_omdb, "TMDb+OMDb"),
        "anime": ("📺 Anime", ANIME_CHANNEL_ID, get_anime_from_jikan, "Jikan"),
        "music": ("🎧 Music", MUSIC_CHANNEL_ID, get_music_from_lastfm, "Last.fm")
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
        name, channel_id, func, api_name = categories[cat]
        channel = bot.get_channel(channel_id)
        
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
    """يبعث معلومات من APIs حقيقية — كل 30 دقيقة"""

    # ═══════ 📰 NEWS — أخبار عامة ═══════
    news_channel = bot.get_channel(NEWS_CHANNEL_ID)
    if news_channel:
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
            embed.set_footer(text="سيمو | NewsAPI")
            await news_channel.send(embed=embed)

    await asyncio.sleep(2)

    # ═══════ 🎮 GAMES — أخبار ألعاب ═══════
    games_channel = bot.get_channel(GAMES_CHANNEL_ID)
    if games_channel:
        game = await get_game_from_rawg()
        if game:
            embed = discord.Embed(
                title=f"🎮 {game['name']}",
                description=game['description'][:400] + "...",
                color=discord.Color.green(),
                url=game['url'],
                timestamp=datetime.now()
            )
            embed.add_field(name="📅 Release", value=game['released'], inline=True)
            embed.add_field(name="⭐ Rating", value=game['rating'], inline=True)
            embed.add_field(name="🎭 Genre", value=game['genres'], inline=False)
            if game['poster']:
                embed.set_image(url=game['poster'])
            embed.set_footer(text="سيمو | RAWG.io")
            await games_channel.send(embed=embed)

    await asyncio.sleep(2)

    # ═══════ 🎬 MOVIES — أفلام + ملخص ═══════
    movies_channel = bot.get_channel(MOVIES_CHANNEL_ID)
    if movies_channel:
        movie = await get_movie_from_omdb()
        if movie:
            embed = discord.Embed(
                title=f"🎬 {movie['title']} ({movie['year']})",
                description=movie['plot'][:500] + "...",
                color=discord.Color.gold(),
                url=movie['imdb'],
                timestamp=datetime.now()
            )
            embed.add_field(name="🎭 Genre", value=movie['genre'], inline=True)
            embed.add_field(name="⭐ IMDB Rating", value=f"{movie['rating']}/10", inline=True)
            if movie['poster'] and movie['poster'] != "N/A":
                embed.set_image(url=movie['poster'])
            embed.set_footer(text="سيمو | IMDB via OMDb")
            await movies_channel.send(embed=embed)

    await asyncio.sleep(2)

    # ═══════ 📺 ANIME — أنمي + ملخص ═══════
    anime_channel = bot.get_channel(ANIME_CHANNEL_ID)
    if anime_channel:
        anime = await get_anime_from_jikan()
        if anime:
            embed = discord.Embed(
                title=f"📺 {anime['title']}",
                description=anime['synopsis'][:500] + "...",
                color=discord.Color.purple(),
                url=anime['url'],
                timestamp=datetime.now()
            )
            if anime['title_jp']:
                embed.add_field(name="🇯🇵 Japanese", value=anime['title_jp'], inline=False)
            embed.add_field(name="📺 Type", value=anime['type'], inline=True)
            embed.add_field(name="📊 Episodes", value=str(anime['episodes']), inline=True)
            embed.add_field(name="⭐ MAL Score", value=f"{anime['score']}/10", inline=True)
            embed.add_field(name="🎭 Genres", value=anime['genres'], inline=False)
            if anime['poster']:
                embed.set_image(url=anime['poster'])
            embed.set_footer(text="سيمو | MyAnimeList via Jikan")
            await anime_channel.send(embed=embed)

    await asyncio.sleep(2)

    # ═══════ 🎧 MUSIC — موسيقى + أغاني ═══════
    music_channel = bot.get_channel(MUSIC_CHANNEL_ID)
    if music_channel:
        music = await get_music_from_lastfm()
        if music:
            embed = discord.Embed(
                title=f"🎵 {music['name']}",
                description=f"أغنية جديدة من **{music['artist']}**",
                color=discord.Color.red(),
                url=music['url'],
                timestamp=datetime.now()
            )
            embed.add_field(name="🎤 Artist", value=music['artist'], inline=True)
            embed.add_field(name="👥 Listeners", value=f"{music['listeners']:,}", inline=True)
            if music['poster']:
                embed.set_image(url=music['poster'])
            embed.set_footer(text="سيمو | Last.fm")
            await music_channel.send(embed=embed)


@auto_info.before_loop
async def before_auto_info():
    await bot.wait_until_ready()


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
    else:
        print(f"[ERROR] {error}")


@bot.event
async def on_ready():
    print(f"✅ سيمو شغال!")
    print(f"🤖 Model: {AI_MODEL}")
    print(f"💬 AI Channel: {TARGET_CHANNEL_ID}")
    print(f"👋 Welcome: {WELCOME_CHANNEL_ID}")
    print(f"✅ Verify: {VERIFY_CHANNEL_ID}")
    print(f"🛡️ Mod Logs: {MOD_LOGS_CHANNEL_ID}")
    print(f"📰 News: {NEWS_CHANNEL_ID}")
    print(f"🎮 Games: {GAMES_CHANNEL_ID}")
    print(f"🎬 Movies: {MOVIES_CHANNEL_ID}")
    print(f"📺 Anime: {ANIME_CHANNEL_ID}")
    print(f"🎧 Music: {MUSIC_CHANNEL_ID}")
    print(f"⏱️ Timeout: {API_TIMEOUT}s")
    print(f"🛡️ Moderation: نشط")
    print(f"✅ Verification: نشط")
    print(f"📰 Auto-Info: نشط (5 channels + APIs حقيقية)")
    print(f"⚠️ Warn Limit: {WARN_LIMIT}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"!help | {len(bot.guilds)} سيرفرات"
        )
    )

    if not auto_info.is_running():
        auto_info.start()

    bot.add_view(RulesVerifyView())  # باش الأزرار يبقاو خدامين حتى بعد ريستارت البوت

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
