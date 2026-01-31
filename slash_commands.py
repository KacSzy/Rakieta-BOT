import os

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from commands.gemini.ask_gemini import handle_gemini_command
from commands.mod.change_presence import PresenceType, change_presence
from commands.rocket.match import MatchView, get_user_balance, MatchType
from commands.shop.remove_rank import check_and_remove_role
from commands.unbelievable_API.add_money import add_money_unbelievable
from const import EDEK_USER_ID

GUILD_ID = os.getenv("GUILD")
UNBAN_GUILD_ID = os.getenv("UNBAN_GUILD")


class SlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------------------------------------------------------------------------

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

        user_balance = await get_user_balance(interaction.user.id)

        if user_balance < stake:
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        match_view = MatchView(stake, match_type, interaction.user)
        await match_view.send_initial_message(interaction)
        await interaction.followup.send('Match created!', ephemeral=True)

    @app_commands.command(name="return_role", description="Zwróć rangę kupioną w serwerowym sklepie za 50% ceny.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def return_role(self, interaction: discord.Interaction, role: str):

        await interaction.response.defer(ephemeral=True)
        price = await check_and_remove_role(interaction.user, role)

        if price:
            if price == -1:
                await interaction.followup.send(
                    f'Ta ranga nie może zostać zwrócona lub źle napisałeś jej nazwę. Spróbuj ponownie', ephemeral=True)
            else:
                await interaction.followup.send(f'Zwrot uznany. Przelewam {price // 2} na konto.', ephemeral=True)
                await add_money_unbelievable(interaction.user.id, 0, (price // 2))

        else:
            await interaction.followup.send('Nie masz tej rangi.', ephemeral=True)

    @app_commands.command(name='change_presence', description="Change bot's rich presence.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    async def change_presence(self, interaction: Interaction, presence: PresenceType, name: str):
        await interaction.response.defer(ephemeral=True)
        result = await change_presence(self.bot, presence, name)

        if result == 1:
            await interaction.followup.send('Done!', ephemeral=True)

        else:
            await interaction.followup.send('Coś poszło nie tak. Spróbuj ponownie!', ephemeral=True)

    @app_commands.command(name='clear_invites',
                          description="Usuwa wszystkie zaproszenia użyte < 5 razy (z wyjątkiem Edka).")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    async def clear_invites(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        invites = await guild.invites()

        for invite in invites:
            if invite.inviter.id != EDEK_USER_ID:

                if invite.uses < 5:
                    await invite.delete()

        await interaction.followup.send('Wszystkie zaproszenia zostały usunięte.', ephemeral=True)

    @app_commands.command(name='ask', description='Zadaj pytanie sztucznej inteligencji.')
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ask_ai(self, interaction: Interaction, question: str):
        await interaction.response.defer()
        await handle_gemini_command(interaction, question)


    # -----------------------------------------------------------------------------------------------


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))
