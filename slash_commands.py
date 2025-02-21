import os

import discord
from discord import Interaction, app_commands
from discord.ext import commands
from commands.rocket.match import MatchView, get_user_balance, MatchType

GUILD_ID = os.getenv("GUILD")


class SlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Slash commands loaded!")

    @app_commands.command(name='ping', description='Tests connection.')
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ping(self, interaction: Interaction):
        await interaction.response.send_message(f'{round(self.bot.latency * 1000)}ms', ephemeral=True)

    @app_commands.command(name="match_1v1", description="Rozpocznij mecz 1v1 o wybraną stawkę.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def match_start_1s(self, interaction: discord.Interaction, stake: int, match_type: MatchType):
        if stake < 200:
            await interaction.response.send_message("Minimalna stawka to 200.", ephemeral=True)
            return

        user_balance = get_user_balance(interaction.user.id)

        if user_balance < stake:
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        match_view = MatchView(stake, match_type, interaction.user)
        await match_view.send_initial_message(interaction)
        await interaction.followup.send('Match created!', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))
