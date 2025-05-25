import asyncio
import discord
from commands.unbelievable_API.add_money import add_money_unbelievable

ADMIN_ID = 567984269516079104


class ResultView(discord.ui.View):
    def __init__(self, players, stake):
        super().__init__(timeout=None)
        self.players = players
        self.stake = stake
        self.results = {}

    async def check_results(self, interaction: discord.Interaction):
        """Check if both players submitted results and handle match outcome."""
        if len(self.results) < 2:
            return

        player_ids = list(self.results.keys())
        player_results = list(self.results.values())

        if player_results.count("win") == 1 and player_results.count("lose") == 1:
            await self._handle_match_agreement(interaction, player_ids, player_results)
        else:
            await interaction.channel.send(f"🚨 Brak zgodności wyników! <@{ADMIN_ID}>.")

        self.stop()

    async def _handle_match_agreement(self, interaction: discord.Interaction, player_ids, player_results):
        """Process match when players agree on the result."""
        winner_id = player_ids[player_results.index("win")]
        await add_money_unbelievable(winner_id, 0, (self.stake * 2))
        await interaction.channel.send(f"🎉 <@{winner_id}> wygrywa {self.stake * 2} 💰!")

        await asyncio.sleep(5)
        await interaction.channel.edit(archived=True, locked=True)

    async def _validate_player(self, interaction: discord.Interaction):
        """Check if user is a player in this match."""
        if interaction.user.id not in (player.id for player in self.players):
            await interaction.response.send_message("Nie jesteś graczem tego meczu!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Wygrana", style=discord.ButtonStyle.green)
    async def win_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle win button click."""
        if not await self._validate_player(interaction):
            return

        self.results[interaction.user.id] = "win"
        await interaction.response.send_message(f"{interaction.user.mention} zgłosił wygraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="❌ Przegrana", style=discord.ButtonStyle.red)
    async def lose_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle lose button click."""
        if not await self._validate_player(interaction):
            return

        self.results[interaction.user.id] = "lose"
        await interaction.response.send_message(f"{interaction.user.mention} zgłosił przegraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="x", style=discord.ButtonStyle.grey)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle thread deletion button (admin only)."""
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("Nie masz uprawnień!", ephemeral=True)
            return

        await interaction.response.send_message('Zamykanie...')
        await asyncio.sleep(3)
        await interaction.channel.edit(archived=True, locked=True)
