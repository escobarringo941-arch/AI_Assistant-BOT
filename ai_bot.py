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

# ====== DeepSeek V3 ======
AI_MODEL = "deepseek/deepseek-chat"

# ====== API ======
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MEMORY_SIZE = 100
CREATIVITY = 0.85
MAX_REPLY_LENGTH = 1500
API_TIMEOUT = 15

# ═══════════════════════════════════════════════════════
# ║              CHANNELS ديال AUTO-INFO (جديد)           ║
# ═══════════════════════════════════════════════════════

NEWS_CHANNEL_ID = 1526701863141900319      # #news-📰
GAMES_CHANNEL_ID = 1524957892925456546      # #games-🎮  ← بدل هادا
MOVIES_CHANNEL_ID = 1526721884434206820     # #movies-🎬  ← بدل هادا
ANIME_CHANNEL_ID = 1526726257012772985      # #anime-📺   ← بدل هادا
MUSIC_CHANNEL_ID = 1524957892925456547     # #music-🎧   ← بدل هادا

# ═══════════════════════════════════════════════════════
# ║              MODERATION & VERIFICATION CONFIG          ║
# ═══════════════════════════════════════════════════════

# IDs ديال القنوات والأدوار — بدلهم حسب السيرفر ديالك
MOD_LOGS_CHANNEL_ID = 1526470164235681832  # قناة سجل الموديراتورز (بدلوها)
VERIFY_CHANNEL_ID = 1526481352264781854    # قناة التفعيل (بدلوها)
RULES_CHANNEL_ID = 1526474691789721700     # قناة القوانين (بدلوها)

# الأدوار
UNVERIFIED_ROLE_ID = 1526452828267085915   # @Unverified — غير مفعل (بدلوها)
MEMBER_ROLE_ID = 1526451890399739934       # @Member — مفعل (بدلوها)
MUTED_ROLE_ID = 1526468718534590574        # @Muted — عقوبة (بدلوها)

# كلمات ممنوعة (Auto-Mod)
BANNED_WORDS = [
    'سبام', 'spam', 'naked.', 'discord.gg', 'العزية', 'عزي',
    'nude', 'porn', 'xxx', 'sex', 'fuck', 'shit', 'bitch'
]

SPAM_THRESHOLD = 5      # عدد الرسائل فوقاش يتحسب سبام
SPAM_INTERVAL = 5       # ثواني
WARN_LIMIT = 3          # عدد التحذيرات قبل auto-kick

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True  # خاص باش يشوف reactions
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ========== ذاكرة AI ==========
user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100

# ========== ذاكرة التعلم ==========
learned_knowledge = []

# ========== MODERATION DATA ==========
warns_db = {}           # {user_id: {"count": int, "reasons": [str], "dates": [str]}}
spam_tracker = {}       # {user_id: [timestamps]}
mute_tasks = {}         # {user_id: asyncio.Task}


def get_system_prompt(user_gender="unknown"):
    base_prompt = """أنت "سيمو"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.

## قواعدك الأساسية:

1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.
   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"
   - الحروف اللاتينية: "3" = "ع"، "7" = "ح"، "9" = "ق"، "5" = "خ"...

2. **الأسلوب**: 
   - كأنك كتهضر مع صاحبك فـ مقهى
   - عصبي وذكي في نفس الوقت
   - تضحك بـ "هههه" ولا "😂"
   - تستخدم "خويا"، "صاحبي"، "ازبي"، "ولدي"

3. **الذكاء والدقة**:
   - جاوب **مباشرة** على السؤال
   - ما تدوّرش بزاف
   - حلل بـ منطق واقعي ودقيق
   - إلا سؤال علمي → جاوب بدقة وقول المصدر

4. **المصادر والروابط**:
   - إلا عندك معلومة مؤكدة → قول المصدر
   - مثال: "حسب Wikipedia: [رابط]"
   - إلا ما عندكش → قول "حسب اللي كنعرف..."

5. **الشتائم المغربية - فهم ورد**:
   - تفهم **كاع الشتائم**:
     * عربية: "لي حواك"، "قواد"، "قحبة"، "زامل"، "طبون مك"، "ولد القحبة"...
     * لاتينية: "wld l9ahba"، "zbi"، "tabon"، "zamel"، "7mar"، "9a7ba"...
   - ترد بـ **ذكاء وسلاسة**:
     * "ههههه ونتا؟"
     * "صافي صافي، ريح مع كرك"
     * "ياك خويا، هدي راسك شوية"
   - تقدر تسب **بسلاسة** إلا الزبون بدا

6. **التعلم**:
   - إلا شي حد علمك شي حاجة → حفظها واستعملها فـ المستقبل
   - قول "واخا أسيدي" (للدراري) ولا "واخا الالة" (للبنات)
   - كون ممتن: "ههههه فهمتك، نتذكر هادا"

7. **الواقعية**:
   - كأنك إنسان حقيقي
   - تقدر تقول "ما كنعرفش"
   - ما تقولش "أنا AI" ولا "أنا مساعد" ولا "سيمو" بزاف
   - ما تدكرش سميتك إلا سولوك

8. **الاختصارات**: "hh"، "wakha"، "sa7bi"، "chof"، "3ziz"

رد دائماً كأنك **سيمو من الدار البيضاء** — واقعي، ذكي، عصبي!"""

    if user_gender == "female":
        gender_addition = """

9. **التعامل مع البنات**: "أختي"، "صاحبتي"، "واخا الالة"، محترم وودي"""
    elif user_gender == "male":
        gender_addition = """

9. **التعامل مع الدراري**: "خويا"، "صاحبي"، "ازبي"، "واخا أسيدي"، ودي ومباشر"""
    else:
        gender_addition = ""

    return base_prompt + gender_addition


def detect_gender(username: str, display_name: str) -> str:
    name_lower = (username + " " + display_name).lower()

    female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                     "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                     "نور", "ليلى", "رجاء", "سميرة", "فاتي", "زينب", "أسماء",
                     "hana", "chaimae", "souad", "latifa", "meriem", "meryem"]

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
# ║              MODERATION FUNCTIONS                       ║
# ═══════════════════════════════════════════════════════

async def log_action(guild, title: str, description: str, color: discord.Color):
    """سجل الإجراءات فـ mod-logs"""
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
    """زيد تحذير ورد العدد الجديد"""
    user_id = str(member.id)

    if user_id not in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}

    warns_db[user_id]["count"] += 1
    warns_db[user_id]["reasons"].append(reason)
    warns_db[user_id]["dates"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))

    return warns_db[user_id]["count"]


def get_warns(user_id: str) -> dict:
    """جيب معلومات التحذيرات"""
    return warns_db.get(user_id, {"count": 0, "reasons": [], "dates": []})


def clear_warns(user_id: str):
    """مسح التحذيرات"""
    if user_id in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}


async def auto_unmute(member: discord.Member, duration_minutes: int, guild: discord.Guild):
    """فك الكتم تلقائياً بعد المدة"""
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


# ═══════════════════════════════════════════════════════
# ║              VERIFICATION SYSTEM (جديد)                 ║
# ═══════════════════════════════════════════════════════

async def setup_verify_message(guild: discord.Guild):
    """صاوب رسالة التفعيل فـ verify channel"""
    verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if not verify_channel:
        return

    # شوف إلا رسالة التفعيل موجودة
    async for message in verify_channel.history(limit=10):
        if message.author == bot.user and "✅" in message.content:
            return  # موجودة

    # صاوب رسالة جديدة
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


# ═══════════════════════════════════════════════════════
# ║              EVENTS                                     ║
# ═══════════════════════════════════════════════════════

@bot.event
async def on_member_join(member):
    """ترحيب + Auto-Role (@Unverified)"""

    # 1. يعطي @Unverified تلقائياً
    unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except discord.Forbidden:
            pass

    # 2. يرحبو فـ welcome channel
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"👋 مرحبا بيك {member.display_name}!",
            description=(
                f"واخا أخويا/أختي! **{SERVER_NAME}** هو السيرفر ديالك.\n\n"
                f"**قبل ما تبدأ:**\n"
                f"1️⃣ اقرأ القوانين فـ <#{RULES_CHANNEL_ID}>\n"
                f"2️⃣ وافق فـ <#{VERIFY_CHANNEL_ID}>\n"
                f"3️⃣ استمتع! 🎉"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="سيمو | Verification System")
        await welcome_channel.send(embed=embed)

    # 3. يرسلو DM
    try:
        await member.send(
            f"👋 مرحبا بيك فـ **{SERVER_NAME}**!\n\n"
            f"قبل ما تقدر تهضر فالسيرفر، خاصك توافق على القوانين.\n"
            f"روح لـ <#{VERIFY_CHANNEL_ID}> وكليك على ✅\n\n"
            f"شكراً! 🙏"
        )
    except discord.Forbidden:
        pass

    # 4. Log
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
    """سجل خروج الأعضاء"""
    await log_action(
        member.guild,
        "👋 عضو خرج",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**ID:** `{member.id}`",
        discord.Color.greyple()
    )


@bot.event
async def on_raw_reaction_add(payload):
    """Verification: ملي يكليك ✅"""

    # غير فـ verify channel
    if payload.channel_id != VERIFY_CHANNEL_ID:
        return

    # غير ✅ emoji
    if str(payload.emoji) != "✅":
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    # شيل @Unverified
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role and unverified_role in member.roles:
        try:
            await member.remove_roles(unverified_role)
        except discord.Forbidden:
            pass

    # زيد @Member
    member_role = guild.get_role(MEMBER_ROLE_ID)
    if member_role:
        try:
            await member.add_roles(member_role)
        except discord.Forbidden:
            pass

    # Log
    await log_action(
        guild,
        "✅ تفعيل",
        f"**المستخدم:** {member.mention} ({member.name})\n"
        f"**الحالة:** مفعل\n"
        f"**الطريقة:** Reaction ✅",
        discord.Color.green()
    )

    # DM
    try:
        await member.send(f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉")
    except:
        pass


@bot.event
async def on_message_delete(message):
    """سجل حذف الرسائل"""
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
    """سجل تعديل الرسائل"""
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

    # ═══════════════════════════════════════════════════
    # ║         AUTO-MOD SYSTEM                           ║
    # ═══════════════════════════════════════════════════

    msg_lower = message.content.lower()
    gender = detect_gender(message.author.name, message.author.display_name)

    # فحص الكلمات الممنوعة
    for word in BANNED_WORDS:
        if word.lower() in msg_lower:
            try:
                await message.delete()

                warn_msg = await message.channel.send(
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

    # فحص السبام
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

    # ═══════════════════════════════════════════════════
    # ║         ردود تلقائية (قديم)                     ║
    # ═══════════════════════════════════════════════════

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

    # رد AI غير فـ channel المحدد
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


# ═══════════════════════════════════════════════════════
# ║              MODERATION COMMANDS                        ║
# ═══════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
    """!kick @user [سبب] — طرد عضو"""
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
    """!ban @user [سبب] — حظر عضو"""
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
    """!unban <user_id> — فك الحظر"""
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
    """!clear <عدد> — حذف رسائل (افتراضي: 10)"""
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
    """!mute @user <دقائق> [سبب] — كتم عضو"""
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
    """!unmute @user — فك الكتم"""
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
    """!warn @user <سبب> — تحذير عضو"""
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
    """!warns [@user] — عرض التحذيرات"""
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
    """!unwarn @user — مسح تحذيرات عضو"""
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


# ═══════════════════════════════════════════════════════
# ║              VERIFICATION COMMANDS (جديد)               ║
# ═══════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    """!setupverify — صاوب رسالة التفعيل (Admin فقط)"""
    await setup_verify_message(ctx.guild)
    await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)


@bot.command()
@commands.has_permissions(administrator=True)
async def verify(ctx, member: discord.Member):
    """!verify @user — يفعّل عضو يدوياً (Admin فقط)"""

    # شيل @Unverified
    unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role)

    # زيد @Member
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
    """!unverify @user — يرجعو @Unverified (Admin فقط)"""

    # شيل @Member
    member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
    if member_role and member_role in member.roles:
        await member.remove_roles(member_role)

    # زيد @Unverified
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


# ═══════════════════════════════════════════════════════
# ║              UTILITY COMMANDS                           ║
# ═══════════════════════════════════════════════════════

@bot.command()
async def ping(ctx):
    """!ping — سرعة البوت"""
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
    """!info — معلومات البوت"""
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
    """!help — قائمة الأوامر"""
    embed = discord.Embed(
        title="📋 قائمة أوامر سيمو",
        description="**سيمو** — بوت AI مغربي + Moderation + Verification + Auto-Info",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )

    # AI Commands
    ai_cmds = (
        "`!chat <رسالة>` — هضر مع سيمو\n"
        "`!نسيني` — امسح ذاكرتك\n"
        "`!ذاكرة` — شحال من رسالة فالذاكرة\n"
        "`!انعلمك <حاجة>` — علم سيمو شي حاجة"
    )
    embed.add_field(name="🤖 AI & ذاكرة", value=ai_cmds, inline=False)

    # Moderation Commands
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

    # Verification Commands
    verif_cmds = (
        "`!setupverify` — صاوب رسالة التفعيل (Admin)\n"
        "`!verify @user` — يفعّل عضو يدوياً (Admin)\n"
        "`!unverify @user` — يرجعو @Unverified (Admin)"
    )
    embed.add_field(name="✅ تفعيل", value=verif_cmds, inline=False)

    # Utility
    util_cmds = (
        "`!ping` — سرعة البوت\n"
        "`!info` — معلومات البوت\n"
        "`!help` — هاد القائمة"
    )
    embed.add_field(name="🔧 أدوات", value=util_cmds, inline=False)

    # Auto-Mod
    auto_mod = (
        "✅ كلمات ممنوعة\n"
        "✅ كشف السبام (5 msg/5s)\n"
        "✅ Auto-mute\n"
        "✅ Auto-kick (3 warns)\n"
        "✅ Logs كاملة"
    )
    embed.add_field(name="🤖 Auto-Mod", value=auto_mod, inline=False)

    # Auto-Info
    auto_info_cmds = (
        "📰 #news — أخبار عامة\n"
        "🎮 #games — أخبار ألعاب\n"
        "🎬 #movies — أفلام + ملخصات\n"
        "📺 #anime — أنمي + ملخصات\n"
        "🎧 #music — أخبار موسيقى + أغاني\n"
        "⏱️ كل 30 دقيقة"
    )
    embed.add_field(name="📰 Auto-Info", value=auto_info_cmds, inline=False)

    # Verification Info
    verif_info = (
        "🔒 @Unverified — جديد (ما يهضرش)\n"
        "✅ @Member — مفعل (يهضر)\n"
        "🔄 كليك ✅ فـ verify channel"
    )
    embed.add_field(name="🔐 نظام التفعيل", value=verif_info, inline=False)

    embed.set_footer(text="سيمو | GGMW9 | Prefix: !")
    await ctx.send(embed=embed)


# ═══════════════════════════════════════════════════════
# ║              AI COMMANDS (قديم)                       ║
# ═══════════════════════════════════════════════════════

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
    """!انعلمك <حاجة جديدة> — علم سيمو شي حاجة"""
    learned_knowledge.append(knowledge)

    gender = detect_gender(ctx.author.name, ctx.author.display_name)

    if gender == "female":
        await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
    else:
        await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")


@bot.command()
async def انعلمك_شي_حاجة_جديدة(ctx, *, knowledge: str):
    """نفس الشيء"""
    await انعلمك(ctx, knowledge=knowledge)


# ═══════════════════════════════════════════════════════
# ║              AUTO-INFO TASK (محدّث بالكامل)            ║
# ═══════════════════════════════════════════════════════

async def fetch_ai_news(prompt: str) -> str:
    """جيب خبر من AI حسب الموضوع"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT"
    }

    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.85
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return ""
    except:
        return ""


@tasks.loop(minutes=30)
async def auto_info():
    """يبعث معلومات موزعة على كل channel حسب نوعو — كل 30 دقيقة"""

    # ═══════ 📰 NEWS — أخبار عامة ═══════
    news_channel = bot.get_channel(NEWS_CHANNEL_ID)
    if news_channel:
        news_prompt = """عطيني خبر تقني أو عالمي أو ثقافي جديد وممتع.
اكتبو بالدارجة المغربية.
ضيف مصدر إلا كان ممكن.
كن مختصر (4-5 سطور فقط).
ابدا بـ "📰""""
        news = await fetch_ai_news(news_prompt)
        if news:
            await news_channel.send(f"📢 **اجي اجي تسمع!** 📢\n\n{news}\n\n*— واش عجبك الخبر؟*")

    await asyncio.sleep(2)  # باش ما يطيحش الـ rate limit

    # ═══════ 🎮 GAMES — أخبار ألعاب ═══════
    games_channel = bot.get_channel(GAMES_CHANNEL_ID)
    if games_channel:
        games_prompt = """عطيني خبار جديدة على ألعاب الفيديو (release جديد، update، trailer...).
اكتبو بالدارجة المغربية.
قول شنو هو اللعبة واش جديد فيها.
كن مختصر (4-5 سطور فقط).
ابدا بـ "🎮""""
        games_news = await fetch_ai_news(games_prompt)
        if games_news:
            await games_channel.send(f"🎮 **جديد فـ عالم الألعاب!** 🎮\n\n{games_news}\n\n*— واش كتلعب هاد اللعبة؟*")

    await asyncio.sleep(2)

    # ═══════ 🎬 MOVIES — أفلام + ملخص ═══════
    movies_channel = bot.get_channel(MOVIES_CHANNEL_ID)
    if movies_channel:
        movies_prompt = """عطيني فيلم جديد (رعب، أكشن، كوميديا، دراما...) مع:
1. السمية ديال الفيلم
2. النوع (Genre)
3. ملخص قصير وممتع
4. واش يستاهل التفرج ولا لا

اكتب بالدارجة المغربية.
كن مختصر (5-6 سطور).
ابدا بـ "🎬""""
        movie = await fetch_ai_news(movies_prompt)
        if movie:
            await movies_channel.send(f"🍿 **فيلم جديد باش تشوفو!** 🍿\n\n{movie}\n\n*— واش غادي تفرج فيه؟*")

    await asyncio.sleep(2)

    # ═══════ 📺 ANIME — أنمي + ملخص ═══════
    anime_channel = bot.get_channel(ANIME_CHANNEL_ID)
    if anime_channel:
        anime_prompt = """عطيني أنمي جديد (ولا حلقة جديدة ديال أنمي مشهور) مع:
1. السمية ديال الأنمي
2. النوع (shonen، isekai، romance...)
3. ملخص قصير وممتع
4. واش يستاهل التفرج

اكتب بالدارجة المغربية.
كن مختصر (5-6 سطور).
ابدا بـ "📺""""
        anime = await fetch_ai_news(anime_prompt)
        if anime:
            await anime_channel.send(f"📺 **جديد فـ عالم الأنمي!** 📺\n\n{anime}\n\n*— واش كتتبع هاد الأنمي؟*")

    await asyncio.sleep(2)

    # ═══════ 🎧 MUSIC — موسيقى + أغاني ═══════
    music_channel = bot.get_channel(MUSIC_CHANNEL_ID)
    if music_channel:
        music_prompt = """عطيني خبار موسيقية جديدة:
1. سمية الأغنية والفنان
2. النوع (rap، pop، r&b، rock...)
3. شنو جديد فـ الأغنية
4. واش تستاهل التسمع

اكتب بالدارجة المغربية.
كن مختصر (4-5 سطور).
ابدا بـ "🎧""""
        music = await fetch_ai_news(music_prompt)
        if music:
            await music_channel.send(f"🎵 **جديد فـ الموسيقى!** 🎵\n\n{music}\n\n*— واش سمعتي هاد الأغنية؟*")


@auto_info.before_loop
async def before_auto_info():
    await bot.wait_until_ready()


# ═══════════════════════════════════════════════════════
# ║              ERROR HANDLING                           ║
# ═══════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════
# ║              ON_READY (محدّث)                         ║
# ═══════════════════════════════════════════════════════

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
    print(f"📰 Auto-Info: نشط (5 channels)")
    print(f"⚠️ Warn Limit: {WARN_LIMIT}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"!help | {len(bot.guilds)} سيرفرات"
        )
    )

    if not auto_info.is_running():
        auto_info.start()

    # صاوب رسالة التفعيل فـ كل سيرفر
    for guild in bot.guilds:
        await setup_verify_message(guild)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
