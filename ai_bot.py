import discord
from discord.ext import commands
import os
import google.generativeai as genai

إعداد الـ Intents الجديدة
intents = discord.Intents.default()
intents.message_content = True 

تعريف البوت
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

إعداد Gemini API بالموديل الجديد
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

@bot.event
async def on_ready():
    print(f'البوت {bot.user} خدام دابا!')

@bot.command(name='ask')
async def ask(ctx, *, question: str = "مرحبا، كيف يمكنني مساعدتك؟"):
    try:
        response = model.generate_content(question)
        await ctx.send(response.text)
    except Exception as e:
        await ctx.send("عفواً، حدث خطأ أثناء الاتصال بـ Gemini.")
        print(f"Error: {e}")

تشغيل البوت
bot.run(os.getenv('DISCORD_TOKEN'))
