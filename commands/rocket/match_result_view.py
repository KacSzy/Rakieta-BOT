import asyncio
import random
import discord
from commands.unbelievable_API.add_money import add_money_unbelievable
from const import ADMIN_USER_ID, MATCH_LOGS_CHANNEL_ID
from database import update_match_history, get_bonus_count, increment_bonus_count
from commands.rocket.leader_roles import update_leader_role


class MatchScoreModal(discord.ui.Modal):
    def __init__(self, view: 'ResultView', team_name: str, label: str):
        super().__init__(title=f"Zgłoś wynik dla {team_name}")
        self.view_ref = view
        self.team_name = team_name

        self.blue_score = discord.ui.TextInput(
            label=f"Wynik BLUE ({label})",
            placeholder="np. 2",
            min_length=1,
            max_length=2,
            required=True
        )
        self.orange_score = discord.ui.TextInput(
            label=f"Wynik ORANGE ({label})",
            placeholder="np. 1",
            min_length=1,
            max_length=2,
            required=True
        )
        self.add_item(self.blue_score)
        self.add_item(self.orange_score)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            b_score = int(self.blue_score.value)
            o_score = int(self.orange_score.value)
        except ValueError:
            await interaction.response.send_message("Wynik musi być liczbą!", ephemeral=True)
            return

        # Store result in parent view
        # Format "BlueScore:OrangeScore" e.g. "2:1"
        report_str = f"{b_score}:{o_score}"

        if self.team_name == "Blue":
            self.view_ref.blue_report = report_str
            await interaction.response.send_message(f"✅ Zgłoszono wynik: Blue **{b_score}** - **{o_score}** Orange.")
        else:
            self.view_ref.orange_report = report_str
            await interaction.response.send_message(f"✅ Zgłoszono wynik: Blue **{b_score}** - **{o_score}** Orange.")

        await self.view_ref.check_results(interaction)


class ResultView(discord.ui.View):
    def __init__(self, blue_team, orange_team, stake, team_size, match_type):
        super().__init__(timeout=None)
        self.blue_team = blue_team
        self.orange_team = orange_team
        self.stake = stake
        self.team_size = team_size
        self.match_type = match_type # Enum MatchType

        # Reports format "BlueScore:OrangeScore"
        self.blue_report = None
        self.orange_report = None

    def _get_captain(self, team_list):
        return team_list[0] if team_list else None

    async def check_results(self, interaction: discord.Interaction):
        """Check if both captains submitted compatible results."""
        if not self.blue_report or not self.orange_report:
            return

        if self.blue_report == self.orange_report:
            # Parse scores
            try:
                b_s, o_s = map(int, self.blue_report.split(':'))
            except:
                await interaction.channel.send("🚨 Błąd formatu wyniku. Zresetujcie zgłoszenia.")
                self.blue_report = None
                self.orange_report = None
                return

            if b_s > o_s:
                await self._handle_win(interaction, "blue", self.blue_report)
            elif o_s > b_s:
                await self._handle_win(interaction, "orange", self.blue_report)
            else:
                await interaction.channel.send("🚨 Remis? W Rocket League nie ma remisów! Zgłoście poprawny wynik.")
                self.blue_report = None
                self.orange_report = None
        else:
            # Conflict
            await interaction.channel.send(
                f"🚨 **KONFLIKT!**\n"
                f"🔵 Blue zgłasza: {self.blue_report}\n"
                f"🟠 Orange zgłasza: {self.orange_report}\n"
                f"Ustalcie poprawny wynik i wyślijcie ponownie lub zawołajcie admina <@{ADMIN_USER_ID}>."
            )
            self.blue_report = None
            self.orange_report = None

    async def _handle_win(self, interaction: discord.Interaction, winning_team_name, score_str):
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

        # Check global limit
        current_bonus_count = await get_bonus_count()
        winners_count = len(winning_team)

        # Only try if limit not reached
        if current_bonus_count + winners_count <= 50:
            # 10% chance for bonus
            if random.random() < 0.10:
                bonus_awarded = True
                bonus_amount = int(self.stake * 0.5)
                # Increment DB counter
                await increment_bonus_count(winners_count)

        total_payout = (self.stake * 2) + bonus_amount

        payout_list = []

        # Process winners
        for player in winning_team:
            old_balance = await get_user_balance(player.id)
            await add_money_unbelievable(player.id, 0, total_payout)
            await update_match_history(player.id, self.team_size, is_win=True)
            payout_list.append(player.mention)

            log_data.append({
                "user": player,
                "status": "WIN",
                "old": old_balance,
                "new": old_balance + total_payout
            })

        # Process losers
        for player in losing_team:
            old_balance = await get_user_balance(player.id)
            await update_match_history(player.id, self.team_size, is_win=False)

            log_data.append({
                "user": player,
                "status": "LOSS",
                "old": old_balance,
                "new": old_balance
            })

        winners_str = ", ".join(payout_list)
        message = f"🎉 **Koniec Meczu!** Wynik: **{score_str}** dla {winning_team_name.capitalize()}!\n" \
                  f"💰 Zwycięzcy: {winners_str} zgarniają po {self.stake * 2} 💰!"

        if bonus_awarded:
            message += f"\n🍀 **LUCKY!** Wylosowano dodatkowy bonus {bonus_amount} 💰 (50% stawki)! Łącznie otrzymują po {total_payout} 💰."

        await interaction.channel.send(message)

        # Send Logs
        try:
            await self._send_logs(interaction.guild, log_data, bonus_awarded, bonus_amount, total_payout, score_str)
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

    @discord.ui.button(label="📝 Zgłoś Wynik", style=discord.ButtonStyle.success)
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = interaction.user
            captain_blue = self._get_captain(self.blue_team)
            captain_orange = self._get_captain(self.orange_team)

            if user != captain_blue and user != captain_orange:
                await interaction.response.send_message("Tylko kapitanowie drużyn mogą zgłaszać wynik!", ephemeral=True)
                return

            is_blue = (user == captain_blue)
            team_name = "Blue" if is_blue else "Orange"

            # self.match_type is now a string value, so we can check it directly
            label = "Mapy" if "Best of 3" in str(self.match_type) else "Gole"

            modal = MatchScoreModal(self, team_name, label)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error in report_button: {e}")
            await interaction.response.send_message("Wystąpił błąd przy otwieraniu formularza. Spróbuj ponownie.", ephemeral=True)

    @discord.ui.button(label="x", style=discord.ButtonStyle.grey)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("Nie masz uprawnień!", ephemeral=True)
            return

        await interaction.response.send_message('Zamykanie...')
        await asyncio.sleep(3)
        await interaction.channel.edit(archived=True, locked=True)
        self.stop()

    async def _send_logs(self, guild, log_data, bonus_awarded, bonus_amount, total_payout, score_str):
        channel = guild.get_channel(MATCH_LOGS_CHANNEL_ID)
        if not channel:
            return

        title = f"📝 Match Result Log ({self.team_size}v{self.team_size})"
        desc = (
            f"**Wynik:** {score_str}\n"
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
