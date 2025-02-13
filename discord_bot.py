import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD")
GUILD = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="_", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged as {bot.user}")
    await bot.tree.sync(guild=GUILD)

async def load_extensions():
    await bot.load_extension("events")
    await bot.load_extension("slash_commands")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

asyncio.run(main())
