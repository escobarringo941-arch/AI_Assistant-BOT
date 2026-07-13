import discord, os, google.generativeai as genai
from discord.ext import commands

genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-1.5-flash')
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default() | discord.Intents.message_content)

@bot.event
async def on_message(message):
    if message.author != bot.user and bot.user.mentioned_in(message):
        response = model.generate_content(message.content)
        await message.channel.send(response.text)

bot.run(os.environ['DISCORD_TOKEN'])
