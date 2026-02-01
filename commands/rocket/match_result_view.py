import asyncio
import random
import discord
from commands.unbelievable_API.add_money import add_money_unbelievable
from const import ADMIN_USER_ID, MATCH_LOGS_CHANNEL_ID
from database import update_match_history
from commands.rocket.leader_roles import update_leader_role


class ResultView(discord.ui.View):
    def __init__(self, blue_team, orange_team, stake, team_size):
        super().__init__(timeout=None)
        self.blue_team = blue_team
        self.orange_team = orange_team
        self.stake = stake
        self.team_size = team_size
        # Track confirmed result for each team
        self.blue_vote = None
        self.orange_vote = None

    def _get_player_team(self, user_id):
        if user_id in [p.id for p in self.blue_team]:
            return "blue"
        if user_id in [p.id for p in self.orange_team]:
            return "orange"
        return None

    async def check_results(self, interaction: discord.Interaction):
        """Check if both teams submitted compatible results."""
        if not self.blue_vote or not self.orange_vote:
            return

        if self.blue_vote == "win" and self.orange_vote == "lose":
            await self._handle_win(interaction, "blue")
        elif self.blue_vote == "lose" and self.orange_vote == "win":
            await self._handle_win(interaction, "orange")
        else:
            # Conflict: e.g. both claim win, or both claim lose
            await interaction.channel.send(f"🚨 Brak zgodności wyników! (Blue: {self.blue_vote}, Orange: {self.orange_vote}) <@{ADMIN_USER_ID}>.")
            self.stop()

    async def _handle_win(self, interaction: discord.Interaction, winning_team_name):
        """Process payout for the winning team."""
        if winning_team_name == "blue":
            winning_team = self.blue_team
            losing_team = self.orange_team
        else:
            winning_team = self.orange_team
            losing_team = self.blue_team

        # Prepare for logging
        from commands.rocket.match import get_user_balance
        log_data = []

        # Calculate Payout & Bonus
        bonus_awarded = False
        bonus_amount = 0

        # 10% chance for bonus
        if random.random() < 0.10:
            bonus_awarded = True
            bonus_amount = int(self.stake * 0.5)

        total_payout = (self.stake * 2) + bonus_amount

        payout_list = []

        # Process winners
        for player in winning_team:
            # Fetch 'old' balance (which is balance AFTER bet was taken)
            old_balance = await get_user_balance(player.id)

            await add_money_unbelievable(player.id, 0, total_payout)
            await update_match_history(player.id, self.team_size, is_win=True)
            payout_list.append(player.mention)

            # Record for log (New balance = Old + Total Payout)
            log_data.append({
                "user": player,
                "status": "WIN",
                "old": old_balance,
                "new": old_balance + total_payout
            })

        # Process losers
        for player in losing_team:
            # Fetch 'old' balance
            old_balance = await get_user_balance(player.id)

            await update_match_history(player.id, self.team_size, is_win=False)

            # Record for log (New balance = Old, as stake was already lost)
            log_data.append({
                "user": player,
                "status": "LOSS",
                "old": old_balance,
                "new": old_balance
            })

        winners_str = ", ".join(payout_list)

        message = f"🎉 Zwycięzcy: {winners_str} zgarniają po {self.stake * 2} 💰!"

        if bonus_awarded:
            message += f"\n🍀 **LUCKY!** Wylosowano dodatkowy bonus {bonus_amount} 💰 (50% stawki)! Łącznie otrzymują po {total_payout} 💰."

        await interaction.channel.send(message)

        # Send Logs
        try:
            await self._send_logs(interaction.guild, log_data, bonus_awarded, bonus_amount, total_payout)
        except Exception as e:
            print(f"Failed to send logs: {e}")

        # Update Leader Roles
        try:
            await update_leader_role(interaction.guild, self.team_size)
        except Exception as e:
            print(f"Failed to update leader roles: {e}")

        await asyncio.sleep(5)
        await interaction.channel.edit(archived=True, locked=True)
        self.stop()

    @discord.ui.button(label="✅ Wygrana", style=discord.ButtonStyle.green)
    async def win_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        team = self._get_player_team(interaction.user.id)
        if not team:
            await interaction.response.send_message("Nie jesteś graczem tego meczu!", ephemeral=True)
            return

        if team == "blue":
            self.blue_vote = "win"
        else:
            self.orange_vote = "win"

        await interaction.response.send_message(f"{interaction.user.mention} ({team.capitalize()}) zgłosił wygraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="❌ Przegrana", style=discord.ButtonStyle.red)
    async def lose_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        team = self._get_player_team(interaction.user.id)
        if not team:
            await interaction.response.send_message("Nie jesteś graczem tego meczu!", ephemeral=True)
            return

        if team == "blue":
            self.blue_vote = "lose"
        else:
            self.orange_vote = "lose"

        await interaction.response.send_message(f"{interaction.user.mention} ({team.capitalize()}) zgłosił przegraną!")
        await self.check_results(interaction)

    @discord.ui.button(label="x", style=discord.ButtonStyle.grey)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("Nie masz uprawnień!", ephemeral=True)
            return

        await interaction.response.send_message('Zamykanie...')
        await asyncio.sleep(3)
        await interaction.channel.edit(archived=True, locked=True)
        self.stop()

    async def _send_logs(self, guild, log_data, bonus_awarded, bonus_amount, total_payout):
        channel = guild.get_channel(MATCH_LOGS_CHANNEL_ID)
        if not channel:
            return

        title = f"📝 Match Result Log ({self.team_size}v{self.team_size})"
        desc = (
            f"**Stake:** {self.stake} 💰\n"
            f"**Bonus:** {'✅ Tak (+ ' + str(bonus_amount) + ')' if bonus_awarded else '❌ Nie'}\n"
            f"**Payout per Winner:** {total_payout} 💰"
        )

        embed = discord.Embed(title=title, description=desc, color=discord.Color.gold() if bonus_awarded else discord.Color.green())

        balance_log = ""
        for entry in log_data:
            user = entry["user"]
            status = entry["status"]
            old_b = entry["old"]
            new_b = entry["new"]

            icon = "🏆" if status == "WIN" else "💀"
            balance_log += f"{icon} **{user.display_name}**: {old_b} ➡ **{new_b}**\n"

        embed.add_field(name="Balance Updates", value=balance_log, inline=False)
        embed.set_footer(text=f"Match ID: {self.blue_team[0].id if self.blue_team else 'Unknown'}")

        await channel.send(embed=embed)
