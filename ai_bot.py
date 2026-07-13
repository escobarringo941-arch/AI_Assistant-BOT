import discord
from discord.ext import commands
import os
import google.generativeai as genai

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
تغيير الموديل لموديل مضمون
model = genai.GenerativeModel('gemini-1.5-pro')

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.command(name='ask')
async def ask(ctx, *, question: str):
    try:
        response = model.generate_content(question)
        await ctx.send(response.text)
    except Exception as e:
        await ctx.send("Error.")
        print(e)

bot.run(os.getenv('DISCORD_TOKEN'))
