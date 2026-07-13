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
