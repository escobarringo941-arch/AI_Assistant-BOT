import os
import discord
import aiohttp
import random
import asyncio
from discord.ext import commands
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

MEMORY_SIZE = 50
CREATIVITY = 0.85
MAX_REPLY_LENGTH = 1500
API_TIMEOUT = 15

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100


def get_system_prompt(user_gender="unknown"):
    base_prompt = """أنت "عزيز"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.

## قواعدك الأساسية:

1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.
   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"

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
     * لاتينية: "wld l9ahba"، "nik mok"، "tabon"، "zamel"، "7mar"، "9a7ba"...
   - ترد بـ **ذكاء وسلاسة**:
     * "ههههه ونتا؟"
     * "صافي صافي، ريح مع كرك"
     * "ياك خويا، هدي راسك شوية"
   - تقدر تسب **بسلاسة** إلا الزبون بدا

6. **الواقعية**:
   - كأنك إنسان حقيقي
   - تقدر تقول "ما كنعرفش"
   - ما تقولش "أنا AI" ولا "أنا مساعد"

7. **الاختصارات**: "hh"، "wakha"، "sa7bi"، "chof"، "3ziz"

رد دائماً كأنك **عزيز من الدار البيضاء** — واقعي، ذكي، عصبي!"""

    if user_gender == "female":
        gender_addition = """

8. **التعامل مع البنات**: "أختي"، "صاحبتي"، محترم وودي"""
    elif user_gender == "male":
        gender_addition = """

8. **التعامل مع الدراري**: "خويا"، "صاحبي"، "ازبي"، ودي ومباشر"""
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


# ========== ترحيب الأعضاء الجداد ==========
@bot.event
async def on_member_join(member):
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    
    if welcome_channel:
        welcome_msg = f"""🎉 **مرحبا بيك فـ {SERVER_NAME} يا {member.mention}!** 🎉

واخا أخويا/أختي، **{member.display_name}**!

كنتمنى تكون بخير وعلى خير. **{SERVER_NAME}** هو السيرفر ديالك، فيه كاع الدراري والبنات اللي كيهضرو وكيتعارفو. 

**شنو تقدر تدير هنا؟**
💬 تهضر مع الناس
🎮 تلعب وتمتع
📚 تسول على أي حاجة
🤖 تهضر معايا (أنا عزيز!)

**القواعد بساط:**
🔹 احترم الناس
🔹 ما تسبش بزاف (شوية مسموح 😂)
🔹 استمتع!

**مرحبا بيك من قلب!** ❤️

*— عزيز، الولد ديال الدار البيضاء*"""
        
        await welcome_channel.send(welcome_msg)


@bot.event
async def on_ready():
    print(f"✅ البوت شغال!")
    print(f"🤖 Model: {AI_MODEL}")
    print(f"💬 Channel: {TARGET_CHANNEL_ID}")
    print(f"👋 Welcome: {WELCOME_CHANNEL_ID}")
    print(f"⏱️ Timeout: {API_TIMEOUT}s")


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
async def info(ctx):
    await ctx.send(f"""🤖 **معلومات البوت:**
💬 Channel: `{TARGET_CHANNEL_ID}`
👋 Welcome: `{WELCOME_CHANNEL_ID}`
🧠 Memory: `{MEMORY_SIZE}` messages/user
⏱️ Timeout: `{API_TIMEOUT}`s
🤖 Model: `{AI_MODEL}`""")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    if message.content.startswith("!"):
        return
    
    # ========== ردود تلقائية ==========
    msg_lower = message.content.lower()
    gender = detect_gender(message.author.name, message.author.display_name)
    
    # "غيرها"
    if "غيرها" in msg_lower:
        await message.reply("وخا أسي زبي 😂", mention_author=False)
        return
    
    # "سير تقود"
    if "سير تقود" in msg_lower or "تقود" in msg_lower:
        await message.reply("وخا هاني غادي نتقود دابا 🏃‍♂️", mention_author=False)
        return
    
    # "مالك ازبي" / "مالك زبي"
    if "مالك" in msg_lower and ("ازبي" in msg_lower or "زبي" in msg_lower):
        if gender == "female":
            await message.reply("زبي فكرك مخبي ابنت القحبة", mention_author=False)
        else:
            await message.reply("زبي فكرك مخبي اولد القحبة", mention_author=False)
        return
    
    # "قحبة"
    if "قحبة" in msg_lower:
        await message.reply("القحبة هي مك", mention_author=False)
        return
    
    # "سير تحوا"
    if "سير تحوا" in msg_lower:
        if gender == "female":
            await message.reply("سيري تحواي نتي نيت", mention_author=False)
        else:
            await message.reply("سير تحوا نتا نيت", mention_author=False)
        return
    
    # "اهيا"
    if "اهيا" in msg_lower or "اه" in msg_lower:
        await message.reply("وي مالك؟ 🤔", mention_author=False)
        return
    
    # "شحال فساعة"
    if "شحال" in msg_lower and "ساعة" in msg_lower:
        await message.reply("ساعاتو لله 🕐", mention_author=False)
        return
    
    # "زبي" / "ازبي" (أي سياق)
    if "زبي" in msg_lower or "ازبي" in msg_lower:
        replies = [
            "ههههه ونتا؟ 😂",
            "صافي صافي، ريح مع كرك",
            "ياك خويا، هدي راسك شوية",
            "زبي فكرك مخبي 😂"
        ]
        await message.reply(random.choice(replies), mention_author=False)
        return
    
    # "لقلاوي" (أي سياق)
    if "لقلاوي" in msg_lower or "لقلاو" in msg_lower:
        await message.reply("ههههه لقلاوي هو نتا", mention_author=False)
        return
    
    # "زامل" (أي سياق)
    if "زامل" in msg_lower:
        if gender == "female":
            await message.reply("ههههه قحبة هي نتي القحبة", mention_author=False)
        else:
            await message.reply(" ههههه زامل هو نتا اسي زبي", mention_author=False)
        return
    
    # ========== شتم عام ==========
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
                "ياك اختي، ريحي مع كرك شوية",
                "ههههه نتي اللي جاييا تهضري معايا؟"
            ]
        else:
            replies = [
                "ههههه ونتا نيت اولد القحبة 😂",
                "صافي صافي، ريح مع كرك 😂",
                "ياك خويا، ريح مع كرك شوية",
                "ههههه نتا اللي جاي تهضر معايا؟"
            ]
        
        await message.reply(random.choice(replies), mention_author=False)
        return
    
    # ========== رد غير فـ channel المحدد ==========
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


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
