import os
import discord
import aiohttp
import random
import asyncio
import json
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
OMDB_API_KEY = os.getenv("OMDB_API_KEY")           # ← سجل فـ omdbapi.com
NEWS_API_KEY = os.getenv("NEWS_API_KEY")           # ← سجل فـ newsapi.org
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")       # ← سجل فـ last.fm/api
RAWG_API_KEY = os.getenv("RAWG_API_KEY")           # ← سجل فـ rawg.io/apidocs

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

UNVERIFIED_ROLE_ID = 1526452828267085915
MEMBER_ROLE_ID = 1526451890399739934
MUTED_ROLE_ID = 1526468718534590574

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
    """جيب فيلم عشوائي من IMDB عبر OMDb API (مع retry + ترجمة للدارجة)"""
    if not OMDB_API_KEY:
        print("[OMDB] OMDB_API_KEY ماكاينش! خاصك تزيدو فـ Railway Variables.")
        return {}

    # أفلام كلاسيكية معروفة
    classic_movies = [
        "tt0111161", "tt0068646", "tt0468569", "tt0071562", "tt0167260",
        "tt0110912", "tt0050083", "tt0137523", "tt0109830", "tt1375666",
        "tt0816692", "tt1853728", "tt1345836", "tt0482571", "tt0407887",
        "tt0172495", "tt0364569", "tt0253474", "tt0910970", "tt0435761",
        "tt0268978", "tt0120338", "tt0102926", "tt0080684", "tt0076759",
        "tt0120689", "tt0209144", "tt0169547", "tt0180093", "tt0120586",
        "tt0108052"
    ]
    # أفلام جداد (2019-2024)
    recent_movies = [
        "tt1160419",  # Dune (2021)
        "tt15239678", # Dune: Part Two (2024)
        "tt15398776", # Oppenheimer (2023)
        "tt1517268",  # Barbie (2023)
        "tt1745960",  # Top Gun: Maverick (2022)
        "tt6710474",  # Everything Everywhere All at Once (2022)
        "tt1877830",  # The Batman (2022)
        "tt10872600", # Spider-Man: No Way Home (2021)
        "tt9362722",  # Spider-Man: Across the Spider-Verse (2023)
        "tt5537002",  # Killers of the Flower Moon (2023)
        "tt6791350",  # Guardians of the Galaxy Vol. 3 (2023)
        "tt10366206", # John Wick: Chapter 4 (2023)
        "tt6263850",  # Deadpool & Wolverine (2024)
        "tt22022452", # Inside Out 2 (2024)
        "tt8946378",  # Knives Out (2019)
        "tt11564570", # Glass Onion (2022)
        "tt2382320",  # No Time to Die (2021)
        "tt10954600", # Nope (2022)
        "tt7286456",  # Joker (2019)
        "tt4154796"   # Avengers: Endgame (2019)
    ]

    candidates = random.sample(classic_movies, len(classic_movies)) + random.sample(recent_movies, len(recent_movies))
    random.shuffle(candidates)
    url = "https://www.omdbapi.com/"

    for movie_id in candidates[:8]:  # يجرب حتى 8 أفلام (قديم وجديد مخلوطين) قبل ما يستسلم
        params = {
            "i": movie_id,
            "apikey": OMDB_API_KEY,
            "plot": "full"
        }
        data = await fetch_json(url, params)

        if data.get("Response") != "True":
            print(f"[OMDB] {movie_id} فشل: {data.get('Error', 'unknown error')}")
            continue

        rating = data.get("imdbRating", "0")
        try:
            if rating in ("N/A", None) or float(rating) < 6.0:
                continue
        except ValueError:
            continue

        plot = data.get("Plot", "No plot available.")
        plot_ar = await translate_to_darija(plot)

        return {
            "title": data.get("Title", "Unknown"),
            "year": data.get("Year", "N/A"),
            "genre": data.get("Genre", "N/A"),
            "plot": plot_ar,
            "rating": rating,
            "poster": data.get("Poster", ""),
            "imdb": f"https://www.imdb.com/title/{movie_id}/"
        }

    return {}


async def get_anime_from_jikan() -> dict:
    """
    جيب أنمي (قديم ولا جديد) من Jikan API — عشوائي بين:
    - الموسم الحالي (أنميات جداد كيخرجو دابا)
    - توب الأنمي (خلطة قديم وجديد بتقييم عالي)
    كل مرة كيبدل المصدر، فما كيبقاش دايما كيرجع لنفس الحوايج القديمة.
    """
    jikan_headers = {"User-Agent": "Mozilla/5.0 (compatible; SimoBot/1.0)"}

    source = random.choice(["seasonal", "top", "top", "seasonal"])  # توازن خفيف نحو top (أكثر استقرار)
    if source == "seasonal":
        url = "https://api.jikan.moe/v4/seasons/now"
    else:
        page = random.randint(1, 8)
        url = f"https://api.jikan.moe/v4/top/anime?page={page}"

    data = await fetch_json(url, headers=jikan_headers)
    anime_list = data.get("data", []) if data else []

    # فلتر: نبقاو غير على الأنميات اللي عندها score مزيان ونوعها TV/Movie
    anime_list = [
        a for a in anime_list
        if a.get("score") and a.get("score") >= 6.5 and a.get("type") in ("TV", "Movie")
    ]

    if not anime_list:
        print(f"[JIKAN] ماكاينش نتائج صالحة من {url}")
        return {}

    random.shuffle(anime_list)

    for i, anime in enumerate(anime_list[:6]):
        if i > 0:
            await asyncio.sleep(1.0)  # نحترمو rate-limit ديال Jikan

        synopsis = anime.get("synopsis") or "No synopsis available."
        synopsis_ar = await translate_to_darija(synopsis)

        return {
            "title": anime.get("title", "Unknown"),
            "title_jp": anime.get("title_japanese", ""),
            "type": anime.get("type", "TV"),
            "episodes": anime.get("episodes", "N/A"),
            "genres": ", ".join([g["name"] for g in anime.get("genres", [])]),
            "synopsis": synopsis_ar,
            "score": anime.get("score", 0),
            "poster": anime.get("images", {}).get("jpg", {}).get("large_image_url", ""),
            "url": anime.get("url", "")
        }

    return {}


async def get_game_from_rawg() -> dict:
    """جيب لعبة عشوائية من RAWG API (مع ترجمة الوصف للدارجة)"""
    if not RAWG_API_KEY:
        print("[RAWG] RAWG_API_KEY ماكاينش!")
        return {}

    popular_games = [
        "gta-v", "the-witcher-3-wild-hunt", "red-dead-redemption-2",
        "god-of-war", "elden-ring", "the-last-of-us-part-ii",
        "horizon-zero-dawn", "ghost-of-tsushima", "spider-man",
        "cyberpunk-2077", "assassins-creed-valhalla", "call-of-duty-warzone",
        "fortnite", "minecraft", "valorant", "league-of-legends",
        "counter-strike-global-offensive", "apex-legends", "overwatch-2",
        "rocket-league", "fall-guys", "among-us", "genshin-impact",
        "pokemon-go", "clash-of-clans", "pubg", "free-fire"
    ]

    candidates = random.sample(popular_games, len(popular_games))

    for game_slug in candidates[:6]:  # يجرب حتى 6 ألعاب قبل ما يستسلم
        url = f"https://api.rawg.io/api/games/{game_slug}"
        params = {"key": RAWG_API_KEY}
        data = await fetch_json(url, params)

        if not data or not data.get("name"):
            print(f"[RAWG] {game_slug} ما رجعش داتا صحيحة")
            continue

        rating = data.get("rating", 0)
        if rating < 3.0:  # RAWG rating out of 5
            continue

        description = data.get("description_raw", "No description available.")[:500]
        description_ar = await translate_to_darija(description)

        return {
            "name": data.get("name", "Unknown"),
            "released": data.get("released", "N/A"),
            "genres": ", ".join([g["name"] for g in data.get("genres", [])]),
            "description": description_ar,
            "rating": f"{rating}/5",
            "poster": data.get("background_image", ""),
            "url": f"https://rawg.io/games/{game_slug}"
        }

    return {}


async def get_music_from_lastfm() -> dict:
    """جيب أغنية عشوائية من Last.fm API"""
    if not LASTFM_API_KEY:
        return {}
    
    popular_artists = [
        "The Weeknd", "Drake", "Taylor Swift", "Ed Sheeran", "Ariana Grande",
        "Billie Eilish", "Post Malone", "Dua Lipa", "Bruno Mars", "Rihanna",
        "Kendrick Lamar", "Travis Scott", "Eminem", "Jay-Z", "Beyoncé",
        "Coldplay", "Maroon 5", "Imagine Dragons", "OneRepublic", "Shawn Mendes",
        "Justin Bieber", "Selena Gomez", "Miley Cyrus", "Doja Cat", "Lil Nas X",
        "Olivia Rodrigo", "Harry Styles", "Bad Bunny", "J Balvin", "Karol G"
    ]
    
    artist = random.choice(popular_artists)
    url = "http://ws.audioscrobbler.com/2.0/"
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
        if tracks:
            track = random.choice(tracks)
            # حول listeners لـ int باش نقدرو نستعملو :, format
            listeners_str = track.get("listeners", "0")
            try:
                listeners = int(listeners_str)
            except (ValueError, TypeError):
                listeners = 0
            
            return {
                "name": track.get("name", "Unknown"),
                "artist": artist,
                "listeners": listeners,  # دابا رقم (int)
                "url": track.get("url", ""),
                "poster": ""  # Last.fm ما كيعطيش posters مباشرة
            }
    return {}


async def get_news_from_api() -> dict:
    """جيب خبر من NewsAPI"""
    if not NEWS_API_KEY:
        return {}
    
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NEWS_API_KEY,
        "category": random.choice(["technology", "entertainment", "science", "sports"]),
        "language": "en",
        "pageSize": 20
    }
    
    data = await fetch_json(url, params)
    
    if data and "articles" in data and data["articles"]:
        # يفلتر المقالات اللي عندها عنوان ووصف حقيقيين (NewsAPI كترجع بزاف [Removed])
        valid_articles = [
            a for a in data["articles"]
            if a.get("title") and a.get("title") != "[Removed]"
        ]
        if not valid_articles:
            return {}
        article = random.choice(valid_articles)
        title_ar = await translate_to_darija(article.get("title", "Unknown"))
        desc_ar = await translate_to_darija(article.get("description", "No description."))
        return {
            "title": title_ar,
            "description": desc_ar,
            "url": article.get("url", ""),
            "source": article.get("source", {}).get("name", "Unknown"),
            "image": article.get("urlToImage", "")
        }
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
            f"قبل ما تقدر تهضر فالسيرفر، خاصك توافق على القوانين.\n\n"
            f"**الخطوات:**\n"
            f"1️⃣ اقرأ القوانين فـ <#{RULES_CHANNEL_ID}>\n"
            f"2️⃣ كليك على ✅ تحت\n\n"
            f"**ملاحظة:** إلا ما وافقتش، ما غاديش تقدر تهضر ولا تفاعل!"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="سيمو | Verification System")
    msg = await verify_channel.send(embed=embed)
    await msg.add_reaction("✅")


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
                f"1️⃣ قرأ/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
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
            f"روح لـ <#{VERIFY_CHANNEL_ID}> وكليك على ✅\n\n"
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
            pass
    await log_action(
        guild,
        "✅ تفعيل",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**الحالة:** مفعل\n"
        f"**الطريقة:** Reaction ✅",
        discord.Color.green()
    )
    try:
        await member.send(f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉")
    except:
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
async def setupverify(ctx):
    await setup_verify_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)


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
        await member.send(f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉")
    except:
        pass


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
        "`!setupverify` — صاوب رسالة التفعيل (Admin)\n"
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
        "🔄 كليك ✅ فـ verify channel"
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
        "movies": ("🎬 Movies", MOVIES_CHANNEL_ID, get_movie_from_omdb, "OMDb"),
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
                preview = str(data)[:100]
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

    for guild in bot.guilds:
        await setup_verify_message(guild)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
