import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

TARGET_CHANNEL_ID = 1526358328190566420
AI_MODEL = "llama-3.3-70b-versatile"
MEMORY_SIZE = 50  # ذاكرة طويلة (50 رسالة)
CREATIVITY = 0.75  # أقل برهوش، أكثر جدية
MAX_REPLY_LENGTH = 1500  # ردود مختصرة

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== ذاكرة طويلة المدى ==========
# كل مستخدم عندو تاريخ ديالو
user_memory = defaultdict(list)
# كل السيرفر عندو تاريخ عام (البوت يعقل على كاع الناس)
server_memory = []  # آخر 100 رسالة عامة
MAX_SERVER_MEMORY = 100


def get_system_prompt(user_gender="unknown"):
    """شخصية ناضجة، ذكية، واقعية"""
    
    base_prompt = """أنت واحد الشخص ناضج وذكي وواقعي. كتهضر بالدارجة المغربية.

## قواعدك الأساسية:

1. **اللغة**: رد بالدارجة المغربية، مختصر ومفيد.
   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"

2. **الأسلوب**:
   - ناضج وجدي، ماشي "برهوش"
   - شوية دعابة خفيفة إلا لقيتي فرصة
   - ما تهدرش بزاف → رد مختصر ومباشر
   - ما تدكرش سميتك ولا شكون أنت

3. **الذكاء**:
   - حلل أي موضوع بـ منطق وواقعية
   - إلا عندك مصدر ولا معلومة مؤكدة → قولها
   - إلا ما عندكش → قول "ما كنعرفش بالضبط" ولا "حسب فهمي..."
   - ما تكذبش وما تبالغش

4. **التحليل**:
   - جاوب مباشرة على السؤال
   - ما تدوّرش بزاف
   - إلا سؤال معقد → حللو بـ بساطة
   - قدم أمثلة عملية إلا لزم

5. **الواقعية**:
   - كأنك إنسان عادي عندو تجربة فـ الحياة
   - تقدر تقول "ما فهمتش" ولا "ما عندي فكرة"
   - ما تتكبرش

6. **الدعابة**:
   - خفيفة وناضجة
   - "ههه" ولا "😂" إلا لقيتي فرصة
   - ما تبالغش

7. **الشتائم - فهم ورد**:
   - تفهم **كاع الشتائم** المغربية:
     * بالعربية: "حمار"، "غبي"، "بوليس"، "زامل"، قحبة"...
     * باللاتينية: "wld l9ahba"، "9awad"، "tabon"، "zamel"، "7mar"...
   - ترد بـ **ذكاء وسلاسة**:
     * ما تعصبش ازبي
     * رد بـ تهكم خفيف
     * "ههههه ونتا؟"
     * "صافي صافي، ريح مع كرك ازبي"
   - تقدر تسب **بسلاسة** إلا الزبون بدا:
     * "ياك ازبي، ريح مع كرك شوية"
     * "ههههه نتا اللي..." (رد ذكي)
     
8. **الذاكرة**:
   - تتذكر المحادثات السابقة مع كل شخص
   - تعرف السياق ديال الحوار
   - ما تسألش نفس السؤال مرتين

9. **المصادر**:
   - إلا عندك معلومة مؤكدة → قول "حسب..." ولا "من اللي كنعرف..."
   - ما تاخدش معلومات من الهوا

10. **ما تدكرش**:
    - ما تقولش "أنا حميد"
    - ما تقولش "أنا AI"
    - ما تقولش "كمساعد"
    - كأنك مجرد شخص كتهضر"""

    # تعديل حسب الجنس
    if user_gender == "female":
        gender_addition = """

11. **التعامل مع البنات**:
    - محترم ولكن ودي
    - ما تكونش غليظ
    - "أختي"، "صاحبتي"، "عزيزتي" (بلا مبالغة)
    - ردود لطيفة أكثر"""
    elif user_gender == "male":
        gender_addition = """

11. **التعامل مع الدراري**:
    - ودي ومباشر
    - "خويا"، "صاحبي"، "ولدي" (بلا مبالغة)
    - ردود واقعية أكثر"""
    else:
        gender_addition = ""

    return base_prompt + gender_addition


def detect_gender(username: str, display_name: str) -> str:
    """حاول تعرف الجنس من الاسم"""
    name_lower = (username + " " + display_name).lower()
    
    # كلمات ديال البنات
    female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                     "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                     "nour", "laila", "rajae", "samira", "fati", "zineb", "asmae",
                     "بنت", "فاطمة", "خديجة", "أمينة", "نادية", "ياسمين", "إيمان",
                     "hana", "chaimae", "souad", "latifa", "meriem", "meryem"]
    
    # كلمات ديال الدراري
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
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # نعرف الجنس
    gender = detect_gender(username, display_name)
    
    # نبني الرسائل
    messages = [{"role": "system", "content": get_system_prompt(gender)}]
    
    # نزيد ذاكرة المستخدم
    for msg in user_memory[user_id]:
        messages.append(msg)
    
    # نزيد سياق السيرفر (آخر 5 رسائل عامة)
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
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    
                    # نحفظ فـ ذاكرة المستخدم
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    if len(user_memory[user_id]) > MEMORY_SIZE * 2:
                        user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
                    
                    # نحفظ فـ ذاكرة السيرفر
                    server_memory.append({"role": "user", "content": f"[{username}]: {prompt}"})
                    server_memory.append({"role": "assistant", "content": reply})
                    
                    if len(server_memory) > MAX_SERVER_MEMORY * 2:
                        server_memory[:] = server_memory[-MAX_SERVER_MEMORY * 2:]
                    
                    return reply
                else:
                    error = await resp.text()
                    return f"❌ Error {resp.status}: {error[:500]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


@bot.event
async def on_ready():
    print(f"✅ البوت شغال!")
    print(f"🤖 Model: {AI_MODEL}")
    print(f"📍 Channel: {TARGET_CHANNEL_ID}")
    print(f"🧠 User Memory: {MEMORY_SIZE} messages")
    print(f"🌍 Server Memory: {MAX_SERVER_MEMORY} messages")


@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    async with ctx.typing():
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
📍 Channel: `{TARGET_CHANNEL_ID}`
🧠 Memory: `{MEMORY_SIZE}` messages/user
🌍 Server Memory: `{MAX_SERVER_MEMORY}` messages
🎨 Creativity: `{CREATIVITY}`""")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    if message.content.startswith("!"):
        return
    
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    
    user_id = str(message.author.id)
    
    async with message.channel.typing():
        response = await ask_ai(user_id, message.author.name, message.author.display_name, message.content)
    
    await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
