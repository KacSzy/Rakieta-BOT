import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

from commands.unbany.tickets import TicketButton

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD")
UNBAN_GUILD_ID = os.getenv("UNBAN_GUILD")
TICKET_CHANNEL_ID = os.getenv("TICKET_CHANNEL_ID")

GUILD = discord.Object(id=GUILD_ID)
UNBAN_GUILD = discord.Object(id=UNBAN_GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="_", intents=intents)


@bot.event
async def on_ready():
    # activity = discord.Game(name="Zwróć rangę za 50% jej wartości :)")
    # await bot.change_presence(status=discord.Status.online, activity=activity)
    await bot.change_presence(activity=discord.CustomActivity(name='Zwróć rangę za 50% jej wartości.'))
    print(f"Logged as {bot.user}")
    await bot.tree.sync(guild=GUILD)
    await bot.tree.sync(guild=UNBAN_GUILD)

    channel = bot.get_channel(int(TICKET_CHANNEL_ID))
    if channel:
        embed = discord.Embed(
            title="🎟 System Ticketów",
            description="Aby napisać skargę kliknij poniższy przycisk",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed, view=TicketButton())


async def load_extensions():
    await bot.load_extension("events")
    await bot.load_extension("slash_commands")


async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


asyncio.run(main())
