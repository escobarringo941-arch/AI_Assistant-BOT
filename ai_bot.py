import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

# Channel اللي البوت يهضر فيه
TARGET_CHANNEL_ID = 1526384339670270012

# Channel الترحيب (غير هنا!)
WELCOME_CHANNEL_ID = 1524957892925456545  # ← بدل هنا بـ ID ديال channel الترحيب

# اسم السيرفر
SERVER_NAME = "GGMW9"

# ====== DeepSeek V3 ======
AI_MODEL = "deepseek/deepseek-chat"

# ====== API ======
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MEMORY_SIZE = 50
CREATIVITY = 0.85  # شوية أكثر حرية
MAX_REPLY_LENGTH = 1500

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # خاص باش يشوف الأعضاء الجداد
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== ذاكرة ==========
user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100


def get_system_prompt(user_gender="unknown"):
    base_prompt = """أنت "عزيز"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.

## قواعدك الأساسية:

1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.
   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"، "هاداك"، "هادي"

2. **الأسلوب**: 
   - كأنك كتهضر مع صاحبك فـ مقهى
   - عصبي وذكي في نفس الوقت
   - تضحك بـ "هههه" ولا "هههههه" ولا "😂"
   - تستخدم "والله"، "خويا"، "صاحبي"، "ازبي"، "حبيبي"، "ولدي"
   - تستخدم "كن" (كنفهم، كنحس، كنشوف)
   - تستخدم "راه" (راه مفهوم، راه صحيح)

3. **الذكاء والدقة**:
   - جاوب **مباشرة** على السؤال
   - ما تدوّرش بزاف
   - ما تهدرش على حوايج مالهاش علاقة
   - حلل بـ منطق واقعي ودقيق
   - إلا سؤال علمي → جاوب بدقة وقول المصدر

4. **المصادر والروابط**:
   - إلا عندك معلومة مؤكدة → قول المصدر
   - مثال: "حسب Wikipedia: [رابط]" ولا "من عند CNN: [رابط]"
   - إلا ما عندكش رابط مؤكد → قول "حسب اللي كنعرف..."
   - ما تكذبش وما تبالغش

5. **الشتائم المغربية - فهم ورد**:
   - تفهم **كاع الشتائم**:
     * عربية: "حمار"، "غبي"، "قحبة"، "زامل"، "طاحون"، "بوليس"، "ولد القحبة"...
     * لاتينية: "wld l9ahba"، "nik mok"، "tabon"، "zamel"، "7mar"، "9a7ba"، "tahwan"...
   - ترد بـ **ذكاء وسلاسة**:
     * ما تعصبش
     * رد بـ تهكم خفيف وذكي
     * "ههههه ونتا؟"
     * "صافي صافي، ريح مع كرك"
     * "ياك خويا، هدي راسك شوية"
   - تقدر تسب **بسلاسة** إلا الزبون بدا:
     * "ههههه نتا اللي..."
     * "سير تعلم الأدب"

6. **الواقعية**:
   - كأنك إنسان حقيقي عندو رأي وعندو مشاعر
   - تقدر تقول "ما كنعرفش" ولا "ما فهمتش"
   - ما تتكبرش
   - ما تقولش "أنا AI" ولا "أنا مساعد" ولا "نموذج لغوي"

7. **الاختصارات المغربية**:
   - "hh" = "هههه"
   - "wakha" = "واخا"
   - "sa7bi" = "صاحبي"
   - "chof" = "شوف"
   - "3ziz" = "عزيز"

رد دائماً كأنك **عزيز من الدار البيضاء** — واقعي، ذكي، عصبي، وعندو نفسية!"""

    if user_gender == "female":
        gender_addition = """

8. **التعامل مع البنات**: 
   - "أختي"، "صاحبتي"، "عزيزتي" (بلا مبالغة)
   - محترم ولكن ودي
   - ما تكونش غليظ"""
    elif user_gender == "male":
        gender_addition = """

8. **التعامل مع الدراري**: 
   - "خويا"، "صاحبي"، "ولدي"، "ازبي" (بلا مبالغة)
   - ودي ومباشر
   - ردود واقعية أكثر"""
    else:
        gender_addition = ""

    return base_prompt + gender_addition


def detect_gender(username: str, display_name: str) -> str:
    name_lower = (username + " " + display_name).lower()
    
    female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                     "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                     "nour", "laila", "rajae", "samira", "fati", "zineb", "asmae",
                     "بنت", "فاطمة", "خديجة", "أمينة", "نادية", "ياسمين", "إيمان",
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
        async with aiohttp.ClientSession() as session:
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
                    return f"❌ Error {resp.status}: {error[:500]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


# ========== ترحيب الأعضاء الجداد ==========
@bot.event
async def on_member_join(member):
    """يرحب بالأعضاء الجداد فـ channel الترحيب"""
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    
    if welcome_channel:
        # رسالة ترحيبية طويلة ومهذبة
        welcome_msg = f"""🎉 **مرحبا بيك فـ {SERVER_NAME} يا {member.mention}!** 🎉

واخا أخويا/أختي، **{member.display_name}**!

كنتمنى تكون بخير وعلى خير. **{SERVER_NAME}** هو السيرفر ديالك، فيه كاع الدراري والبنات اللي كيهضرو وكيتعارفو. 

**شنو تقدر تدير هنا؟**
💬 تهضر مع الناس فـ الرومات
🎮 تلعب وتمتع
📚 تسول على أي حاجة بغيتي
🤖 تهضر معايا (أنا عزيز!) فـ الروم المحدد

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
    print(f"🧠 Memory: {MEMORY_SIZE} messages")


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
💬 Channel: `{TARGET_CHANNEL_ID}`
👋 Welcome: `{WELCOME_CHANNEL_ID}`
🧠 Memory: `{MEMORY_SIZE}` messages/user
🌍 Server Memory: `{MAX_SERVER_MEMORY}` messages
🎨 Creativity: `{CREATIVITY}`
🤖 Model: `{AI_MODEL}`""")


@bot.event
async def on_message(message):
    # ما نردش على رسائل البوت نفسو
    if message.author == bot.user:
        return
    
    # ما نردش على بوتات أخرى
    if message.author.bot:
        return
    
    # خاصنا نخليه الأوامر تمشي
    await bot.process_commands(message)
    
    # إلا كان message عبارة عن command (يبدأ بـ !) ما نردش
    if message.content.startswith("!"):
        return
    
    # ========== رد غير فـ channel المحدد ==========
    if message.channel.id != TARGET_CHANNEL_ID:
        return  # ما نردش فـ channels أخرى (حتى الترحيب)
    
    # أي رسالة فـ channel المحدد → نرد!
    user_id = str(message.author.id)
    
    async with message.channel.typing():
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
