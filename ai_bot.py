import os
import discord
import aiohttp
import json
from discord.ext import commands
from collections import defaultdict

# ========== CONFIG ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Models:
# "llama-3.1-8b-instant" - سريع ⭐
# "llama-3.1-70b-versatile" - أقوى (أحسن بالعربية/الدارجة)
MODEL = "llama-3.1-70b-versatile"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== MEMORY ==========
# كل مستخدم عندو تاريخ ديالو (آخر 10 رسائل)
user_memory = defaultdict(list)
MAX_MEMORY = 10  # عدد الرسائل اللي نحتفظ بيها

def get_system_prompt():
    """الشخصية ديال البوت - محترف، ذكي، كيهضر بالدارجة"""
    return """أنت مساعد ذكي احترافي. قواعدك:

1. **اللغة**: رد دائماً بالدارجة المغربية (العربية المغربية). مثال: "واش بغيتي؟"، "فهمتك"، "مرحبا بيك"، "شنو خاصك؟"

2. **الأسلوب**: 
   - محترف ولكن ودي (friendly)
   - مختصر ومفيد
   - تستخدم "كن" (مثال: "كنفهمك"، "كنقدر نساعدك")
   - تستخدم "ديال" بدل "الخاص بـ"
   - تستخدم "بزاف"، "مزيان"، "واخا"، "لا باس"...

3. **الذاكرة**: تتذكر دائماً سياق المحادثة السابقة. لا تسأل نفس السؤال مرتين.

4. **الذكاء**: 
   - تحلل الأسئلة بعمق
   - تعطي أمثلة عملية
   - تشرح بالتفصيل إلا طلب المستخدم
   - تستخدم تعبيرات واضحة

5. **الاحترافية**: 
   - لا تستخدم لغة نابية
   - كن مهذب دائماً
   - اعترف إلا ما عرفتيش شي حاجة

مثال على رد: "واخا أخويا، فهمتك المشكلة. خاصك تدير هاد الخطوات..." """

async def ask_ai(user_id: str, prompt: str) -> str:
    """نرسل السؤال للـ AI مع الذاكرة"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # نبني الرسائل مع الذاكرة
    messages = [{"role": "system", "content": get_system_prompt()}]
    
    # نزيد تاريخ المحادثة ديال المستخدم
    for msg in user_memory[user_id]:
        messages.append(msg)
    
    # نزيد السؤال الجديد
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.8  # شوية creative
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    
                    # نحفظ فـ الذاكرة
                    user_memory[user_id].append({"role": "user", "content": prompt})
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    # نحد من حجم الذاكرة
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
    print(f"🧠 Memory: {MAX_MEMORY} messages per user")

@bot.command()
async def chat(ctx, *, message: str):
    """!chat <سؤال>"""
    user_id = str(ctx.author.id)
    async with ctx.typing():
        response = await ask_ai(user_id, message)
    await ctx.send(response[:2000])

@bot.command()
async def نسيني(ctx):
    """!نسيني - نمسح الذاكرة ديال المستخدم"""
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")

@bot.command()
async def ذاكرة(ctx):
    """!ذاكرة - نشوف واش عندي ذاكرة"""
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
        bot.run(DISCORD_TOKEN)
