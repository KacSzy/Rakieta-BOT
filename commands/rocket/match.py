from enum import Enum

import discord
import os
import requests

from commands.rocket.match_result_view import ResultView

UNBELIEVABOAT_API_KEY = os.getenv("UNBELIEVABOAT_API_KEY")
GUILD_ID = os.getenv("GUILD")


def get_rank(member: discord.Member):
    rank_roles = ["Brąz", "Srebro", "Złoto", "Platyna", "Diament", "Champion", "GC1", "GC2", "GC3", "SSL"]
    for role in member.roles:
        if role.name in rank_roles:
            return role.name
    return None


class MatchType(Enum):
    BO3 = "Best of 3"
    ONE_GAME = "One game"


class MatchView(discord.ui.View):
    def __init__(self, stake: int, match_type: MatchType, creator: discord.Member):
        super().__init__(timeout=1800) # 30 min
        self.stake = stake
        self.match_type = match_type
        self.creator = creator
        self.players = [creator]
        self.max_players = 2
        self.message = None

        self.required_role = get_rank(creator)

    async def on_timeout(self):
        self.clear_items()
        if self.message:
            await self.message.edit(view=self)

    async def send_initial_message(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"🔹 1V1 MATCH 🔹",
            description=f"**Stawka:** {self.stake} 💰\n"
                        f"**Tryb:** {self.match_type.value}\n"
                        f"**Ranga:** {self.required_role}\n"
                        f"**Organizator:** {self.creator.mention}",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Kliknij przycisk, aby dołączyć!")

        channel = interaction.guild.get_channel(1342099575732965376)
        self.message = await channel.send(embed=embed, view=self)

    @discord.ui.button(label="Dołącz", style=discord.ButtonStyle.green, custom_id="join_match")
    async def join_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.players:
            await interaction.response.send_message("Już jesteś w meczu!", ephemeral=True)
            return

        if get_rank(user) != self.required_role:
            await interaction.response.send_message("Nie możesz dołączyć bo masz inną rangę.", ephemeral=True)
            return

        user_balance = get_user_balance(user.id)
        if user_balance < self.stake:
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        self.players.append(user)
        await interaction.response.send_message(f"{user.mention} dołączył do meczu!", ephemeral=True)

        if len(self.players) == self.max_players:
            await self.start_match()

    async def start_match(self):
        thread = await self.message.create_thread(
            name=f'Mecz 1V1 - {self.creator.name}',
            auto_archive_duration=1440
        )

        await thread.send(
            f"Mecz rozpoczęty! Uczestnicy: {', '.join(player.mention for player in self.players)}\n"
            f"Tryb: {self.match_type.value}"
        )

        self.clear_items()
        await self.message.edit(view=self)

        take_bets(self.players, self.stake)

        view = ResultView(self.players, self.stake)
        await thread.send("🔹 Potwierdź wynik meczu:", view=view)


def get_user_balance(user_id: int) -> int:
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
    headers = {"accept": "application/json", "Authorization": f"{UNBELIEVABOAT_API_KEY}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get("bank", 0)

    return 0


def take_bets(players: list, stake: int) -> None:
    for player in players:
        url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{player.id}"

        payload = {
            "cash": 0,
            "bank": -stake
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"{UNBELIEVABOAT_API_KEY}"
        }

        requests.patch(url, json=payload, headers=headers)
