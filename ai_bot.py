import discord
from discord.ext import commands
import os
from google import genai

Setup intents
intents = discord.Intents.default()
intents.message_content = True 

Setup bot
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

Setup Gemini client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print('Bot is ready and running!')

@bot.command(name='ask')
async def ask(ctx, *, question: str = "Hello"):
    async with ctx.typing():
        try:
            # Using the correct modern method for google-genai
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=question
            )
            await ctx.send(response.text)
        except Exception as e:
            print(f"Error: {e}")
            await ctx.send("An error occurred while processing the request.")

bot.run(os.getenv('DISCORD_TOKEN'))
