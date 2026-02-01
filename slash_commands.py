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
from database import get_leaderboard_data

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

    @app_commands.command(name="match", description="Rozpocznij mecz (1v1, 2v2, 3v3) o wybraną stawkę.")
    @app_commands.describe(
        stake="Stawka meczu (min. 200)",
        match_type="Tryb gry (BO3 lub One Game)",
        team_size="Rozmiar drużyny (1v1, 2v2, 3v3)"
    )
    @app_commands.choices(team_size=[
        app_commands.Choice(name="1v1", value=1),
        app_commands.Choice(name="2v2", value=2),
        app_commands.Choice(name="3v3", value=3)
    ])
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def match_start(self, interaction: discord.Interaction, stake: int, match_type: MatchType, team_size: int = 1):
        if stake < 200:
            await interaction.response.send_message("Minimalna stawka to 200.", ephemeral=True)
            return

        user_balance = await get_user_balance(interaction.user.id)

        if user_balance < stake:
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        match_view = MatchView(stake, match_type, interaction.user, team_size)
        await match_view.send_initial_message(interaction)
        await interaction.followup.send(f'Utworzono mecz {team_size}v{team_size}!', ephemeral=True)

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

    @app_commands.command(name='leaderboard', description='Wyświetla ranking graczy Rocket League (1v1, 2v2, 3v3).')
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def leaderboard(self, interaction: Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="✨ Leaderzy Rankingów ✨",
            color=discord.Color.teal()
        )
        embed.set_footer(text="Statystyki odświeżane po każdym meczu.")

        for team_size in [1, 2, 3]:
            data = await get_leaderboard_data(team_size)
            wins_list = data['wins']
            score_list = data['score']

            # Format Wins
            wins_str = ""
            for i, row in enumerate(wins_list, 1):
                user_id = row[0]
                wins = row[1]
                # Try to resolve user
                user = interaction.guild.get_member(user_id)
                name = user.display_name if user else f"<@{user_id}>"
                wins_str += f"`{i}.` **{name}** • {wins} W\n"

            if not wins_str:
                wins_str = "*Brak danych*"

            # Format Score
            score_str = ""
            for i, row in enumerate(score_list, 1):
                user_id = row[0]
                score = row[3] # (user_id, wins, losses, score)
                user = interaction.guild.get_member(user_id)
                name = user.display_name if user else f"<@{user_id}>"
                score_str += f"`{i}.` **{name}** • {score} pkt\n"

            if not score_str:
                score_str = "*Brak danych*"

            embed.add_field(
                name=f"🏆 {team_size}v{team_size} | Najwięcej Wygranych",
                value=wins_str,
                inline=True
            )
            embed.add_field(
                name=f"🚀 {team_size}v{team_size} | Najwyższy Wynik",
                value=score_str,
                inline=True
            )
            # Add empty field for spacing/formatting if needed, but 2 cols per row is fine for 3 rows
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------------------------------


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))
