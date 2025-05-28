from enum import Enum
import discord
import os
import requests
from typing import List, Optional

from commands.rocket.match_result_view import ResultView
from commands.unbelievable_API.add_money import add_money_unbelievable

UNBELIEVABOAT_API_KEY = os.getenv("UNBELIEVABOAT_API_KEY")
GUILD_ID = os.getenv("GUILD")
MATCH_CHANNEL_ID = 1342099575732965376
MATCH_TIMEOUT_SECONDS = 1800  # 30 min

RANK_ROLES = ["Brąz", "Srebro", "Złoto", "Platyna", "Diament", "Champion", "GC1", "GC2", "GC3", "SSL"]
GC_RANKS = {
    "GC1": ["GC1", "GC2"],
    "GC2": ["GC1", "GC2", "GC3"],
    "GC3": ["GC2", "GC3", "SSL"],
    "SSL": ["GC3", "SSL"]
}


class MatchType(Enum):
    BO3 = "Best of 3"
    ONE_GAME = "One game"


def get_rank(member: discord.Member) -> Optional[str]:
    """Extract player's rank from their Discord roles."""
    for role in member.roles:
        if role.name in RANK_ROLES:
            return role.name
    return None


def get_user_balance(user_id: int) -> int:
    """Fetch user balance from UnbelievaBoat API."""
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
    headers = {"accept": "application/json", "Authorization": f"{UNBELIEVABOAT_API_KEY}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get("bank", 0)
    return 0


def take_bet(player: discord.Member, stake: int) -> None:
    """Deduct stake from each player's balance."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"{UNBELIEVABOAT_API_KEY}"
    }
    payload = {"cash": 0, "bank": -stake}

    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{player.id}"
    requests.patch(url, json=payload, headers=headers)


class MatchView(discord.ui.View):
    def __init__(self, stake: int, match_type: MatchType, creator: discord.Member):
        super().__init__(timeout=MATCH_TIMEOUT_SECONDS)
        self.stake = stake
        self.match_type = match_type
        self.creator = creator
        self.players = [creator]
        self.max_players = 2
        self.message = None
        self.required_role = get_rank(creator)

        take_bet(self.creator, self.stake)

    async def on_timeout(self):
        """Handle view timeout by removing interactive components."""
        await add_money_unbelievable(self.creator.id, 0, self.stake)
        self.clear_items()
        if self.message:
            await self.message.edit(view=None)

    async def send_initial_message(self, interaction: discord.Interaction):
        """Send the initial match invitation message."""
        embed = self._create_match_embed()
        channel = interaction.guild.get_channel(MATCH_CHANNEL_ID)
        self.message = await channel.send(embed=embed, view=self)

    def _create_match_embed(self) -> discord.Embed:
        """Create the match information embed."""
        embed = discord.Embed(
            title=f"🔹 1V1 MATCH 🔹",
            description=(
                f"**Stawka:** {self.stake} 💰\n"
                f"**Tryb:** {self.match_type.value}\n"
                f"**Ranga:** {self.required_role}\n"
                f"**Organizator:** {self.creator.mention}"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Kliknij przycisk, aby dołączyć!")
        return embed

    @discord.ui.button(label="Dołącz", style=discord.ButtonStyle.green, custom_id="join_match")
    async def join_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle join match button click."""
        user = interaction.user

        # Check if user is already in the match
        if user in self.players:
            await interaction.response.send_message("Już jesteś w meczu!", ephemeral=True)
            return

        # Validate rank requirements
        if not self._validate_user_rank(user):
            await interaction.response.send_message(
                "Nie możesz dołączyć, ponieważ Twoja ranga nie spełnia wymagań.", ephemeral=True)
            return

        # Check if user has enough balance
        if not self._validate_user_balance(user):
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        # Add user to players and update
        self.players.append(user)
        await interaction.response.send_message(f"{user.mention} dołączył do meczu!", ephemeral=True)

        # Start match if max players reached
        if len(self.players) == self.max_players:
            await self.start_match()

    def _validate_user_rank(self, user: discord.Member) -> bool:
        """Check if user's rank meets the requirements."""
        user_rank = get_rank(user)

        if self.required_role in GC_RANKS:
            return user_rank in GC_RANKS[self.required_role]
        else:
            return user_rank == self.required_role

    def _validate_user_balance(self, user: discord.Member) -> bool:
        """Check if user has sufficient balance for the match stake."""
        user_balance = get_user_balance(user.id)
        return user_balance >= self.stake

    async def start_match(self):
        """Start the match after enough players have joined."""
        # Create discussion thread
        thread = await self._create_match_thread()

        # Remove join button
        self.clear_items()
        await self.message.edit(view=self)

        # Take a bet from the player
        second_player = self.players[1]
        take_bet(second_player, self.stake)

        # Add result submission view
        view = ResultView(self.players, self.stake)
        await thread.send("🔹 Potwierdź wynik meczu:", view=view)

    async def _create_match_thread(self):
        """Create a thread for match discussion."""
        thread = await self.message.create_thread(
            name=f'Mecz 1V1 - {self.creator.name}',
            auto_archive_duration=1440
        )

        await thread.set_permissions(thread.guild.default_role, send_messages=False)

        for player in self.players:
            await thread.set_permissions(player, send_messages=True)

        # Send info message
        participants = ', '.join(player.mention for player in self.players)
        await thread.send(
            f"Mecz rozpoczęty! Uczestnicy: {participants}\n"
            f"Tryb: {self.match_type.value}"
        )

        return thread
