import discord
from discord.ext import commands
import os
import google.generativeai as genai

# إعداد الـ Intents الجديدة
intents = discord.Intents.default()
intents.message_content = True 

# تعريف البوت
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# إعداد Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

@bot.event
async def on_ready():
    print(f'البوت {bot.user} خدام دابا!')

@bot.command(name='ask')
async def ask(ctx, *, question: str):
    response = model.generate_content(question)
    await ctx.send(response.text)

# تشغيل البوت
bot.run(os.getenv('DISCORD_TOKEN'))
