import asyncio
import os

import discord
import requests

UNBELIEVABOAT_API_KEY = os.getenv("UNBELIEVABOAT_API_KEY")
GUILD_ID = os.getenv("GUILD")
ADMIN_ID = 567984269516079104


class ResultView(discord.ui.View):
    def __init__(self, players, stake):
        super().__init__()
        self.players = players
        self.stake = stake
        self.results = {}

    async def check_results(self, interaction: discord.Interaction):

        if len(self.results) < 2:
            return

        player_ids = list(self.results.keys())
        player_results = list(self.results.values())

        if player_results.count("win") == 1 and player_results.count("lose") == 1:

            winner_id = player_ids[player_results.index("win")]
            await self.give_winnings(winner_id)
            await interaction.channel.send(f"🎉 <@{winner_id}> wygrywa {self.stake * 2} 💰!")

            await asyncio.sleep(5)
            await interaction.channel.edit(archived=True, locked=True)

        else:
            await interaction.channel.send(f"🚨 Brak zgodności wyników! <@{ADMIN_ID}>.")

        self.stop()

    async def give_winnings(self, winner_id):
        url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{winner_id}"

        payload = {
            "cash": 0,
            "bank": (self.stake * 2)
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"{UNBELIEVABOAT_API_KEY}"
        }

        requests.patch(url, json=payload, headers=headers)

    @discord.ui.button(label="✅ Wygrana", style=discord.ButtonStyle.green)
    async def win_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id not in (player.id for player in self.players):
            return await interaction.response.send_message("Nie jesteś graczem tego meczu!", ephemeral=True)

        self.results[interaction.user.id] = "win"
        await interaction.response.send_message(f"{interaction.user.mention} zgłosił wygraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="❌ Przegrana", style=discord.ButtonStyle.red)
    async def lose_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id not in (player.id for player in self.players):
            return await interaction.response.send_message("Nie jesteś graczem tego meczu!", ephemeral=True)

        self.results[interaction.user.id] = "lose"
        await interaction.response.send_message(f"{interaction.user.mention} zgłosił przegraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="x", style=discord.ButtonStyle.grey)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("Nie masz uprawnień!", ephemeral=True)

        else:
            await interaction.response.send_message('Zamykanie...')
            await asyncio.sleep(3)
            await interaction.channel.edit(archived=True, locked=True)
