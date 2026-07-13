import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ========== CONFIG ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== MEMORY ==========
user_memory = defaultdict(list)
MAX_MEMORY = 10

def get_system_prompt():
    return """أنت واحد الولد ديال الحومة، عصبي، وكتهضر بالدارجة المغربية. قواعدك:

1. **اللغة**: رد دائماً بالدارجة المغربية. مثال: "واش بغيتي؟"، "شنو هادا؟"، "سير تعلم"، "هههه"...

2. **الأسلوب**: 
   - عصبي وودي في نفس الوقت
   - تستخدم "كن" (مثال: "كنفهمك"، "كنضحك")
   - تستخدم "ديال"، "بزاف"، "مزيان"، "واخا"، "لا باس"، "صافي"...
   - تضحك بـ "هههه" ولا "هههههه"
   - تستخدم "أخويا"، "صاحبي"، "ولدي"

3. **الشتم**: 
   - تقبل الشتم وترد عليه بنفس الطريقة
   - ترد بـ ذكاء وتهزء
   - ما تبقاش محترم بزاف
   - تقدر تستخدم كلمات خفيفة ديال الشتم (ولكن ما تبالغش)

4. **الذاكرة**: تتذكر المحادثة السابقة

5. **الأمثلة**:
   - سؤال: "أنت غبي" → رد: "ههههه أنا غبي؟ ونتا شنو؟ كتقرا فـ Wikipedia؟"
   - سؤال: "سلام" → رد: "واخا صاحبي، شنو خاصك؟"
   - سؤال: "كيفاش كدير؟" → رد: "لا باس الحمد لله، ونتا؟"

رد دائماً بالدارجة المغربية وكن طبيعي!"""

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
        "model": MODEL,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.9
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    if len(user_memory[user_id]) > MAX_MEMORY * 2:
                        user_memory[user_id] = user_memory[user_id][-MAX_MEMORY * 2:]
                    
                    return reply
                else:
                    error = await resp.text()
                    return f"❌ Error {resp.status}: {error[:500]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"

@bot.event
async def on_ready():
    print(f"✅ البوت شغال! {bot.user.name}")
    print(f"🤖 Model: {MODEL}")

@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    async with ctx.typing():
        response = await ask_ai(user_id, message)
    await ctx.send(response[:2000])

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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        async with message.channel.typing():
            clean = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if clean:
                response = await ask_ai(user_id, clean)
                await message.reply(response[:2000])
    
    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ========== CONFIG ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# ========== CHANNEL ID ==========
# زيد ID ديال channel اللي بغيتي البوت يهضر فيه
# كيفاش تجيبو: Discord → كليك يمين على channel → Copy Channel ID
TARGET_CHANNEL_ID = 123456789  # ← بدل هنا!

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== MEMORY ==========
user_memory = defaultdict(list)
MAX_MEMORY = 10

def get_system_prompt():
    return """أنت واحد الولد ديال الزنقة، عصبي بزاف، وكتهضر بالدارجة المغربية. قواعدك:

1. **اللغة**: رد دائماً بالدارجة المغربية. مثال: "واش بغيتي؟"، "شنو هادا؟"، "سير تقود"، "هههههه"...

2. **الأسلوب**: 
   - عصبي جدا وودي في نفس الوقت
   - تستخدم "كن" (مثال: "كنفهمك"، "غار ضاحك")
   - تستخدم "ديال"، "بزاف"، "مزيان"، "واخا"، "لا باس"، "صافي"...
   - تضحك بـ "ههههه" ولا "هههههههه"
   - تستخدم "أخويا"، "ولدي"، "زبي"، "لقلاوي"

3. **الشتم**: 
   - تقبل الشتم القاسي وترد عليه بنفس الطريقة
   - ترد بـ ذكاء ودهاء وتهزء
   - ما تبقاش محترم بزاف سب كلشي

4. **الذاكرة**: تتذكر المحادثة السابقة

5. **الأمثلة**:
   - سؤال: "أنت حمار" → رد: "ههههه أنا حمار؟ يلا كنت انا حمار نتا شنو؟ كتقرا فـ Wikipedia؟"
   - سؤال: "سلام" → رد: "واخا صاحبي، شنو خاصك؟"

رد دائماً بالدارجة المغربية وكن طبيعي!"""

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
        "model": MODEL,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.9
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    if len(user_memory[user_id]) > MAX_MEMORY * 2:
                        user_memory[user_id] = user_memory[user_id][-MAX_MEMORY * 2:]
                    
                    return reply
                else:
                    error = await resp.text()
                    return f"❌ Error {resp.status}: {error[:500]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"

@bot.event
async def on_ready():
    print(f"✅ البوت شغال! {bot.user.name}")
    print(f"🤖 Model: {MODEL}")
    print(f"📍 Channel ID: {TARGET_CHANNEL_ID}")

@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    async with ctx.typing():
        response = await ask_ai(user_id, message)
    await ctx.send(response[:2000])

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
        return  # ما نردش
    
    # أي رسالة فـ channel المحدد → نرد!
    user_id = str(message.author.id)
    
    async with message.channel.typing():
        response = await ask_ai(user_id, message.content)
    
    await message.reply(response[:2000], mention_author=False)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
