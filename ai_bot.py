import discord
from discord.ext import commands
import os
import google.generativeai as genai

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.command(name='ask')
async def ask(ctx, *, question: str = "How can I help you?"):
    try:
        response = model.generate_content(question)
        await ctx.send(response.text)
    except Exception as e:
        await ctx.send("Error processing request.")
        print(f"Error: {e}")

bot.run(os.getenv('DISCORD_TOKEN'))
