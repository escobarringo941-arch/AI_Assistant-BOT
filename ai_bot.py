import discord
from discord.ext import commands
import os
from google import genai

إعداد الـ Intents
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

إعداد الـ Client الجديد
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.command(name='ask')
async def ask(ctx, *, question: str = "How can I help you?"):
    try:
        # استخدام الطريقة الجديدة للمكتبة الجديدة
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=question
        )
        await ctx.send(response.text)
    except Exception as e:
        await ctx.send("Error processing request.")
        print(f"Error: {e}")

bot.run(os.getenv('DISCORD_TOKEN'))
