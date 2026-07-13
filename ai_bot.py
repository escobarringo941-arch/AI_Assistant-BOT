import discord
from discord.ext import commands
import os
import google.generativeai as genai

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.command(name='ask')
async def ask(ctx, *, question: str):
    response = model.generate_content(question)
    await ctx.send(response.text)

bot.run(os.getenv('DISCORD_TOKEN'))
