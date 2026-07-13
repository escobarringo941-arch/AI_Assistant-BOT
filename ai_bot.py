import os
import discord
import aiohttp
from discord.ext import commands
from collections import defaultdict

# ========== CONFIG ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Models خدامين فـ Groq (2026):
# "llama-3.3-70b-versatile" - أقوى ⭐ (أحسن بالعربية)
# "llama-3.1-8b-instant" - سريع
# "mixtral-8x7b-32768" - متعدد اللغات
MODEL = "llama-3.3-70b-versatile"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== MEMORY ==========
user_memory = defaultdict(list)
MAX_MEMORY = 10

def get_system_prompt():
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

5. **الاحترافية**: 
   - لا تستخدم لغة نابية
   - كن مهذب دائماً
   - اعترف إلا ما عرفتيش شي حاجة

مثال على رد: "واخا أخويا، فهمتك المشكلة. خاصك تدير هاد الخطوات..." """

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
        "temperature": 0.8
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
        bot.run(DISCORD_TOKEN)
