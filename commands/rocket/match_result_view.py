import asyncio
import random
import time
import discord
from commands.unbelievable_API.add_money import add_money_unbelievable
from const import ADMIN_USER_ID, MATCH_LOGS_CHANNEL_ID
from database import (
    update_match_history,
    get_bonus_count,
    increment_bonus_count,
    save_match_record
)
from commands.rocket.leader_roles import update_leader_role
from commands.rocket.achievements import check_achievements


class MatchScoreModal(discord.ui.Modal):
    def __init__(self, view: 'ResultView', team_name: str, label: str, is_bo3: bool):
        super().__init__(title=f"Zgłoś wynik dla {team_name}")
        self.view_ref = view
        self.team_name = team_name
        self.is_bo3 = is_bo3

        if self.is_bo3:
            self.game1 = discord.ui.TextInput(
                label="Mecz 1 (Blue-Orange)",
                placeholder="np. 2-1",
                required=True,
                max_length=10
            )
            self.game2 = discord.ui.TextInput(
                label="Mecz 2 (Blue-Orange)",
                placeholder="np. 1-3",
                required=True,
                max_length=10
            )
            self.game3 = discord.ui.TextInput(
                label="Mecz 3 (Blue-Orange) (jeśli był)",
                placeholder="np. 4-2",
                required=False,
                max_length=10
            )
            self.add_item(self.game1)
            self.add_item(self.game2)
            self.add_item(self.game3)
        else:
            self.game1 = discord.ui.TextInput(
                label="Wynik (Blue-Orange)",
                placeholder="np. 4-1",
                required=True,
                max_length=10
            )
            self.add_item(self.game1)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate and Normalize Inputs
        scores = []
        inputs = [self.game1]
        if self.is_bo3:
            inputs.append(self.game2)
            inputs.append(self.game3)

        for i, inp in enumerate(inputs):
            val = inp.value.strip()
            if not val:
                # If optional game3 is empty, skip
                if self.is_bo3 and i == 2:
                    continue
                # If required is empty (shouldn't happen due to required=True but strictly speaking)
                continue

            # Normalize separators
            val = val.replace(':', '-').replace(' ', '-')
            parts = val.split('-')

            if len(parts) != 2:
                 await interaction.response.send_message(f"🚨 Błędny format wyniku w polu '{inp.label}': '{val}'. Użyj formatu '3-2'.", ephemeral=True)
                 return
            try:
                b = int(parts[0])
                o = int(parts[1])
                scores.append((b, o))
            except ValueError:
                await interaction.response.send_message(f"🚨 Wynik musi składać się z liczb! Błąd w: '{val}'", ephemeral=True)
                return

        if not scores:
            await interaction.response.send_message("🚨 Nie podano żadnego wyniku!", ephemeral=True)
            return

        # Format report string: "2:1, 1:3"
        report_str = ", ".join([f"{b}:{o}" for b, o in scores])

        if self.team_name == "Blue":
            self.view_ref.blue_report = report_str
            await interaction.response.send_message(f"✅ Zgłoszono wynik (Blue): **{report_str}**")
        else:
            self.view_ref.orange_report = report_str
            await interaction.response.send_message(f"✅ Zgłoszono wynik (Orange): **{report_str}**")

        await self.view_ref.check_results(interaction)


class ResultView(discord.ui.View):
    def __init__(self, blue_team, orange_team, stake, team_size, match_type):
        super().__init__(timeout=None)
        self.blue_team = blue_team
        self.orange_team = orange_team
        self.stake = stake
        self.team_size = team_size
        self.match_type = match_type # Enum MatchType or string

        # Reports format "2:1, 1:3"
        self.blue_report = None
        self.orange_report = None

    def _get_captain(self, team_list):
        return team_list[0] if team_list else None

    def _parse_scores(self, report_str):
        # returns list of (blue_goals, orange_goals)
        games = []
        parts = report_str.split(',')
        for p in parts:
            b, o = map(int, p.strip().split(':'))
            games.append((b, o))
        return games

    async def check_results(self, interaction: discord.Interaction):
        """Check if both captains submitted compatible results."""
        if not self.blue_report or not self.orange_report:
            return

        if self.blue_report == self.orange_report:
            score_str = self.blue_report
            games = self._parse_scores(score_str)

            blue_wins = 0
            orange_wins = 0

            for b, o in games:
                if b > o: blue_wins += 1
                elif o > b: orange_wins += 1

            if blue_wins > orange_wins:
                await self._handle_win(interaction, "blue", score_str, games, blue_wins, orange_wins)
            elif orange_wins > blue_wins:
                await self._handle_win(interaction, "orange", score_str, games, blue_wins, orange_wins)
            else:
                await interaction.channel.send("🚨 Remis w serii? Coś jest nie tak. Zgłoście wynik ponownie.")
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

    async def _handle_win(self, interaction: discord.Interaction, winning_team_name, score_str, games, b_wins, o_wins):
        """Process payout, db updates, and achievements."""

        # Determine Teams
        if winning_team_name == "blue":
            winning_team = self.blue_team
        else:
            winning_team = self.orange_team

        # Calculate Totals
        total_blue_goals = sum(g[0] for g in games)
        total_orange_goals = sum(g[1] for g in games)

        # Prepare for Payout
        from commands.rocket.match import get_user_balance
        log_data = []
        payout_list = []

        # Bonus Logic
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

        # 1. Update DB: Save Match Record first
        # Participants Data
        participants_data = []
        for p in self.blue_team:
            participants_data.append({
                'user_id': p.id,
                'team': 'Blue',
                'result': 'WIN' if winning_team_name == 'blue' else 'LOSS'
            })
        for p in self.orange_team:
            participants_data.append({
                'user_id': p.id,
                'team': 'Orange',
                'result': 'WIN' if winning_team_name == 'orange' else 'LOSS'
            })

        match_timestamp = int(time.time())
        saved_match_id = await save_match_record(
            timestamp=match_timestamp,
            game_mode=self.team_size,
            stake=self.stake,
            winner_team=winning_team_name.capitalize(),
            blue_score_sets=b_wins,
            orange_score_sets=o_wins,
            score_details=score_str,
            participants=participants_data
        )

        # Common Achievement / Update Logic
        async def process_player(player, is_winner, team_color):
            # Money
            old_balance = await get_user_balance(player.id)
            if is_winner:
                await add_money_unbelievable(player.id, 0, total_payout)
                payout_list.append(player.mention)
                new_balance = old_balance + total_payout
                status_str = "WIN"
            else:
                new_balance = old_balance
                status_str = "LOSS"

            log_data.append({
                "user": player,
                "status": status_str,
                "old": old_balance + self.stake, # Stake was deducted at start
                "new": new_balance
            })

            # Stats Update (Leaderboard)
            # Goals for this player's team
            if team_color == "blue":
                gs = total_blue_goals
                gc = total_orange_goals
            else:
                gs = total_orange_goals
                gc = total_blue_goals

            await update_match_history(player.id, self.team_size, is_winner, gs, gc)

            # Check Achievements
            match_info = {
                'result': 'WIN' if is_winner else 'LOSS',
                'timestamp': match_timestamp,
                'game_mode': self.team_size
            }
            new_achievements = await check_achievements(player.id, match_info)

            if new_achievements:
                # Announce
                for ach in new_achievements:
                    await interaction.channel.send(f"🏆 **{player.display_name}** zdobył osiągnięcie: **{ach['name']}** - {ach['description']}")

        # Process All Players
        for p in self.blue_team:
            await process_player(p, winning_team_name == "blue", "blue")

        for p in self.orange_team:
            await process_player(p, winning_team_name == "orange", "orange")

        # Result Message
        winners_str = ", ".join(payout_list)
        message = f"🎉 **Koniec Meczu!** Wynik: **{score_str}** dla {winning_team_name.capitalize()}!\n" \
                  f"💰 Zwycięzcy: {winners_str} zgarniają po {self.stake * 2} 💰!"

        if bonus_awarded:
            message += f"\n🍀 **LUCKY!** Wylosowano dodatkowy bonus {bonus_amount} 💰 (50% stawki)! Łącznie otrzymują po {total_payout} 💰."

        await interaction.channel.send(message)

        # Logs & Roles
        try:
            await self._send_logs(interaction.guild, log_data, bonus_awarded, bonus_amount, total_payout, score_str)
            await update_leader_role(interaction.guild, self.team_size)
        except Exception as e:
            print(f"Post-match error: {e}")

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

            # Determine if BO3
            # match_type might be Enum or Str
            is_bo3 = "Best of 3" in str(self.match_type)

            modal = MatchScoreModal(self, team_name, is_bo3)
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
