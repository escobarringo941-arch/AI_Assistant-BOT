import os
import discord
import aiohttp
from discord.ext import commands

# ========== CONFIG ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Models مجانية فـ Groq:
# "llama-3.1-8b-instant"  - سريع وقوي ⭐
# "llama-3.1-70b-versatile" - أقوى شوية
# "mixtral-8x7b-32768" - متعدد اللغات مزيان
# "gemma-7b-it" - خفيف
MODEL = "llama-3.1-8b-instant"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def ask_ai(prompt: str) -> str:
    """نرسل السؤال للـ AI ونرجع الجواب"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Reply in the same language the user writes in."
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
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
    """!chat <سؤال>"""
    async with ctx.typing():
        response = await ask_ai(message)
    # Discord limit: 2000 char
    await ctx.send(response[:2000])

@bot.event
async def on_message(message):
    # ما نردش على رسائل البوت نفسو
    if message.author == bot.user:
        return
    
    # نرد إلا منشونا فـ channel ولا DM
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            # نحيد الـ mention من الرسالة
            clean = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if clean:
                response = await ask_ai(clean)
                await message.reply(response[:2000])
    
    await bot.process_commands(message)

# ========== RUN ==========
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
