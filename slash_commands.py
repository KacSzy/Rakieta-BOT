import os

import discord
from discord import Interaction
from discord.ext import commands

GUILD_ID = os.getenv("GUILD")

class SlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Slash commands loaded!")

    @discord.app_commands.command(name='ping', description='Tests connection.')
    @discord.app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ping(self, interaction: Interaction):
        await interaction.response.send_message(f'{round(self.bot.latency * 1000)}ms', ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))
