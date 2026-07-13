import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('Bot is online and ready!')

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

bot.run(os.getenv('DISCORD_TOKEN'))
import discord
from discord.ext import commands
import os
import google.generativeai as genai

Setup intents
intents = discord.Intents.default()
intents.message_content = True 

Setup bot
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

@bot.event
async def on_ready():
    print('Bot is online and ready to answer!')

@bot.command(name='ask')
async def ask(ctx, *, question: str = "Hello"):
    try:
        response = model.generate_content(question)
        await ctx.send(response.text)
    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("I'm sorry, I couldn't process that.")

bot.run(os.getenv('DISCORD_TOKEN'))
