from enum import Enum
import discord
import os
import aiohttp
from typing import Optional, List

from commands.rocket.match_result_view import ResultView
from commands.unbelievable_API.add_money import add_money_unbelievable
from const import MATCH_CHANNEL_ID, ADMIN_USER_ID

UNBELIEVABOAT_API_KEY = os.getenv("UNBELIEVABOAT_API_KEY")
GUILD_ID = os.getenv("GUILD")
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


async def get_user_balance(user_id: int) -> int:
    """Fetch user balance from UnbelievaBoat API."""
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
    headers = {"accept": "application/json", "Authorization": f"{UNBELIEVABOAT_API_KEY}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("bank", 0)
    return 0


async def take_bet(player: discord.Member, stake: int) -> None:
    """Deduct stake from each player's balance."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"{UNBELIEVABOAT_API_KEY}"
    }
    payload = {"cash": 0, "bank": -stake}

    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{player.id}"

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json=payload, headers=headers) as response:
             # Consume the response
            await response.text()


class MatchView(discord.ui.View):
    def __init__(self, stake: int, match_type: MatchType, creator: discord.Member, team_size: int = 1):
        super().__init__(timeout=MATCH_TIMEOUT_SECONDS)
        self.stake = stake
        self.match_type = match_type
        self.creator = creator
        self.team_size = team_size
        self.blue_team: List[discord.Member] = [creator]
        self.orange_team: List[discord.Member] = []
        self.message = None
        self.required_role = get_rank(creator)
        # Note: take_bet is called in send_initial_message for the creator

    async def on_timeout(self):
        """Handle view timeout by refunding everyone and removing components."""
        # Refund everyone currently in the teams
        all_players = self.blue_team + self.orange_team
        for player in all_players:
            await add_money_unbelievable(player.id, 0, self.stake)

        self.clear_items()
        if self.message:
            await self.message.edit(content="⏰ Mecz anulowany (timeout). Środki zwrócone.", view=None, embed=None)

    async def send_initial_message(self, interaction: discord.Interaction):
        """Send the initial match invitation message."""
        # Take the bet from the creator here
        await take_bet(self.creator, self.stake)

        embed = self._create_match_embed()
        channel = interaction.guild.get_channel(MATCH_CHANNEL_ID)
        self.message = await channel.send(embed=embed, view=self)

    def _create_match_embed(self) -> discord.Embed:
        """Create the match information embed."""
        match_title = f"🔹 {self.team_size}v{self.team_size} MATCH 🔹"

        embed = discord.Embed(
            title=match_title,
            description=(
                f"**Stawka:** {self.stake} 💰\n"
                f"**Tryb:** {self.match_type.value}\n"
                f"**Ranga:** {self.required_role}\n"
                f"**Organizator:** {self.creator.mention}"
            ),
            color=discord.Color.blue()
        )

        blue_mentions = "\n".join([p.mention for p in self.blue_team]) or "Oczekiwanie..."
        orange_mentions = "\n".join([p.mention for p in self.orange_team]) or "Oczekiwanie..."

        embed.add_field(name=f"🔵 Blue Team ({len(self.blue_team)}/{self.team_size})", value=blue_mentions, inline=True)
        embed.add_field(name=f"🟠 Orange Team ({len(self.orange_team)}/{self.team_size})", value=orange_mentions, inline=True)

        embed.set_footer(text="Wybierz drużynę, aby dołączyć!")
        return embed

    async def _handle_join(self, interaction: discord.Interaction, team_color: str):
        """Generic handler for joining a team."""
        user = interaction.user

        # Check if user is already in any team
        if user in self.blue_team or user in self.orange_team:
            await interaction.response.send_message("Już jesteś w meczu!", ephemeral=True)
            return

        target_team = self.blue_team if team_color == "blue" else self.orange_team

        # Check if team is full
        if len(target_team) >= self.team_size:
            await interaction.response.send_message("Ta drużyna jest już pełna!", ephemeral=True)
            return

        # Validate rank requirements
        if not self._validate_user_rank(user):
            await interaction.response.send_message(
                "Nie możesz dołączyć, ponieważ Twoja ranga nie spełnia wymagań.", ephemeral=True)
            return

        # Check if user has enough balance
        if not await self._validate_user_balance(user):
            await interaction.response.send_message("Masz za mało kasy!", ephemeral=True)
            return

        # Deduct stake
        await take_bet(user, self.stake)

        # Add to team
        target_team.append(user)

        await interaction.response.send_message(f"Dołączyłeś do {team_color.capitalize()} Team!", ephemeral=True)
        await self._update_message()

        # Check if match is ready
        if len(self.blue_team) == self.team_size and len(self.orange_team) == self.team_size:
            await self.start_match()

    @discord.ui.button(label="Dołącz do Blue", style=discord.ButtonStyle.primary, custom_id="join_blue")
    async def join_blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_join(interaction, "blue")

    @discord.ui.button(label="Dołącz do Orange", style=discord.ButtonStyle.danger, custom_id="join_orange")
    async def join_orange(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_join(interaction, "orange")

    @discord.ui.button(label="Opuść", style=discord.ButtonStyle.secondary, custom_id="leave_match")
    async def leave_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user not in self.blue_team and user not in self.orange_team:
            await interaction.response.send_message("Nie jesteś w tym meczu.", ephemeral=True)
            return

        # Remove user and refund
        if user in self.blue_team:
            self.blue_team.remove(user)
        elif user in self.orange_team:
            self.orange_team.remove(user)

        await add_money_unbelievable(user.id, 0, self.stake)
        await interaction.response.send_message("Opuściłeś mecz. Środki zwrócone.", ephemeral=True)

        # If everyone left, maybe cancel? But for now just update embed.
        await self._update_message()

    async def _update_message(self):
        """Update the match embed with current teams."""
        if self.message:
            embed = self._create_match_embed()
            await self.message.edit(embed=embed)

    def _validate_user_rank(self, user: discord.Member) -> bool:
        """Check if user's rank meets the requirements."""
        user_rank = get_rank(user)

        if self.required_role in GC_RANKS:
            return user_rank in GC_RANKS[self.required_role]
        else:
            return user_rank == self.required_role

    async def _validate_user_balance(self, user: discord.Member) -> bool:
        """Check if user has sufficient balance for the match stake."""
        user_balance = await get_user_balance(user.id)
        return user_balance >= self.stake

    async def start_match(self):
        """Start the match after enough players have joined."""
        # Create discussion thread
        thread = await self._create_match_thread()

        # Remove buttons/view from invitation message
        self.clear_items()
        await self.message.edit(view=None) # Or keep view with disabled buttons? Removing is cleaner.

        # Add result submission view
        # Passing teams to ResultView
        view = ResultView(self.blue_team, self.orange_team, self.stake)
        await thread.send("🔹 Potwierdź wynik meczu:", view=view)

    async def _create_match_thread(self):
        """Create a thread for match discussion."""
        thread = await self.message.create_thread(
            name=f'Mecz {self.team_size}v{self.team_size} - {self.creator.name}',
            auto_archive_duration=1440
        )

        # Send info message
        blue_mentions = ', '.join(p.mention for p in self.blue_team)
        orange_mentions = ', '.join(p.mention for p in self.orange_team)

        info_message = (
            f"Mecz rozpoczęty!\n"
            f"🔵 **Blue Team:** {blue_mentions}\n"
            f"🟠 **Orange Team:** {orange_mentions}\n"
            f"Tryb: {self.match_type.value}\n\n"
            f"⏰ **UWAGA:** Jeżeli przeciwnik nie odpowie w ciągu 15 minut, "
            f"prosimy o kontakt z administracją <@{ADMIN_USER_ID}>."
        )

        await thread.send(info_message)
        # Ping players? Mentions in message should ping them.

        return thread
