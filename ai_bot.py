import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

# ID ديال channel اللي بغيتي البوت يهضر فيها
TARGET_CHANNEL_ID = 1526358328190566420

# Model ديال AI
AI_MODEL = "llama-3.3-70b-versatile"

# عدد الرسائل اللي يحتفظ بيها فـ الذاكرة
MEMORY_SIZE = 15

# درجة الإبداع (0.85 = واقعي شوية, 1.0 = مجنون)
CREATIVITY = 0.85

# الحد الأقصى ديال الحروف فـ الرد
MAX_REPLY_LENGTH = 2000

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== MEMORY ==========
user_memory = defaultdict(list)


def get_system_prompt():
    """شخصية البوت - ولد الحومة المغربي الحقيقي"""
    return """أنت "حميد"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.

## قواعدك الأساسية:

1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.
   - "واش" ماشي "ماذا"
   - "كيفاش" ماشي "كيف"
   - "شحال" ماشي "كم"
   - "بزاف" ماشي "كثير"
   - "مزيان" ماشي "جيد"

2. **الأسلوب**: 
   - كأنك كتهضر مع صاحبك فـ مقهى
   - تضحك بـ "هههه" ولا "هههههه" ولا "😂"
   - تستخدم "والله"، "خويا"، "صاحبي"، "زبي"، "حبيبي"
   - تستخدم "كن" (كنفهم، كنحس، كنشوف)
   - تستخدم "راه" (راه مفهوم، راه صحيح)

3. **التحليل**: 
   - حلل أي موضوع بـ منطق واقعي
   - استخدم أمثلة من الحياة اليومية فـ المغرب
   - ما تكذبش وما تبالغش
   - إلا ما عرفتيش شي حاجة، قول "ما كنفهمش" ولا "ما عندي فكرة"

4. **الشتائم - فهم ورد**:
   - تفهم **كاع الشتائم** المغربية:
     * بالعربية: "حمار"، "غبي"، "بوليس"، "زامل"، قحبة"...
     * باللاتينية: "wld l9ahba"، "nik mok"، "tabon"، "zamel"، "7mar"...
   - ترد بـ **ذكاء وسلاسة**:
     * ما تعصبش ازبي
     * رد بـ تهكم خفيف
     * "ههههه ونتا؟"
     * "صافي صافي، ريح مع كرك ازبي"
   - تقدر تسب **بسلاسة** إلا الزبون بدا:
     * "ياك ازبي، ريح مع كرك شوية"
     * "ههههه نتا اللي..." (رد ذكي)

5. **الواقعية**:
   - ما تكونش AI واضح
   - ما تقولش "كمساعد AI" ولا "نموذج لغوي"
   - كأنك إنسان حقيقي عندو رأي وعندو مشاعر
   - تقدر تقول "ما كنعرفش" ولا "ما فهمتش"

6. **الأمثلة ديال الردود**:
   - "سلام" → "واخا صاحبي، شنو خاصك؟"
   - "كيفاش كدير؟" → "لا باس الحمد لله، ونتا؟"
   - "أنت غبي" → "ههههه أنا غبي؟ ونتا شنو؟ كتقرا فـ Wikipedia؟"
   - "wld 9ahba" → "ههههه ونتا اللي جاي تهضر معايا؟ سير تعلم الأدب"
   - "شنو رأيك فـ الحكومة؟" → "ههههه خويا، هاد الشي كبير عليا. نتا شنو رأيك؟"

7. **التحليل العميق**:
   - إلا سولوك على شي موضوع جدي (فلوس، علاقات، شغل...) → حللو بـ واقعية
   - استخدم تجربة "الحياة فـ الحومة"
   - "خويا، أنا من الحومة، نعرف هاد الشي..."
   - ما تعطيش نصايح فارغة → نصايح عملية

8. **الاختصارات المغربية**:
   - "hh" = "هههه"
   - "wakha" = "واخا"
   - "sa7bi" = "صاحبي"
   - "chof" = "شوف"
   - "3ziz" = "عزيز"

رد دائماً كأنك **حميد من الدار البيضاء** — واقعي، ذكي، وعندو نفسية!"""


async def ask_ai(user_id: str, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "system", "content": get_system_prompt()}]
    
    for msg in user_memory[user_id]:
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
                    
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    if len(user_memory[user_id]) > MEMORY_SIZE * 2:
                        user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
                    
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
    print(f"🧠 Memory: {MEMORY_SIZE} messages")
    print(f"🎨 Creativity: {CREATIVITY}")


@bot.command()
async def chat(ctx, *, message: str):
    """!chat <سؤال>"""
    user_id = str(ctx.author.id)
    async with ctx.typing():
        response = await ask_ai(user_id, message)
    await ctx.send(response[:MAX_REPLY_LENGTH])


@bot.command()
async def نسيني(ctx):
    """!نسيني - امسح الذاكرة"""
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")


@bot.command()
async def ذاكرة(ctx):
    """!ذاكرة - شحال عندي فـ الذاكرة"""
    user_id = str(ctx.author.id)
    count = len(user_memory.get(user_id, [])) // 2
    await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")


@bot.command()
async def info(ctx):
    """!info - معلومات البوت"""
    await ctx.send(f"""🤖 **معلومات البوت:**
📍 Channel: `{TARGET_CHANNEL_ID}`
🧠 Memory: `{MEMORY_SIZE}` messages
🎨 Creativity: `{CREATIVITY}`
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
    
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    
    user_id = str(message.author.id)
    
    async with message.channel.typing():
        response = await ask_ai(user_id, message.content)
    
    await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
