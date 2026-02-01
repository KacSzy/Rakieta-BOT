import datetime
from typing import List, Dict, Any, Tuple
from commands.rocket.achievements_config import ACHIEVEMENTS
from database import (
    get_user_leaderboard_stats,
    get_user_matches_history,
    add_user_achievement,
    get_user_achievements
)

async def check_achievements(user_id: int, current_match: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Checks and awards achievements for a user after a match.
    current_match expects: {'result': 'WIN'/'LOSS', 'timestamp': int, 'game_mode': int}
    Returns a list of unlocked achievement objects (name, description).
    """
    unlocked = []

    # Fetch data
    stats = await get_user_leaderboard_stats(user_id) # Dict of stats
    history = await get_user_matches_history(user_id, limit=50) # List of rows
    existing_achievements = await get_user_achievements(user_id) # List of (id, date)
    existing_ids = set(r[0] for r in existing_achievements)

    if not stats:
        # Should at least have current match stats if updated correctly
        return []

    # Calculate Totals from Leaderboard (Reliable for lifetime counts)
    total_wins = sum(stats[k] for k in stats if k.endswith('_W'))
    total_losses = sum(stats[k] for k in stats if k.endswith('_L'))
    total_games = total_wins + total_losses

    # Parse current match info
    is_win = current_match['result'] == 'WIN'
    mode = current_match['game_mode'] # 1, 2, 3
    current_ts = current_match['timestamp']

    # --- Checks ---

    # 1. First Match Checks
    if total_games == 1:
        if "rookie" not in existing_ids:
            if await _grant(user_id, "rookie", unlocked): existing_ids.add("rookie")

        if is_win and "first_blood" not in existing_ids:
             if await _grant(user_id, "first_blood", unlocked): existing_ids.add("first_blood")

        if not is_win and "humble" not in existing_ids:
             if await _grant(user_id, "humble", unlocked): existing_ids.add("humble")

    # 2. Counts
    if total_games >= 5 and "warmup" not in existing_ids:
        await _grant(user_id, "warmup", unlocked)
    if total_games >= 50 and "regular" not in existing_ids:
        await _grant(user_id, "regular", unlocked)
    if total_games >= 100 and "veteran" not in existing_ids:
        await _grant(user_id, "veteran", unlocked)
    if total_games >= 500 and "legend" not in existing_ids:
        await _grant(user_id, "legend", unlocked)

    # 3. Streaks (Need history)
    # History from DB: 0:id, 1:ts, 2:mode, 3:stake, 4:winner, 5:b_s, 6:o_s, 7:det, 8:result, 9:team
    streak = 0
    if history:
        for match in history:
            # match[8] is result ('WIN'/'LOSS')
            if match[8] == 'WIN':
                streak += 1
            else:
                break

    if is_win:
        if streak >= 3 and "heating_up" not in existing_ids: await _grant(user_id, "heating_up", unlocked)
        if streak >= 5 and "on_fire" not in existing_ids: await _grant(user_id, "on_fire", unlocked)
        if streak >= 10 and "unstoppable" not in existing_ids: await _grant(user_id, "unstoppable", unlocked)

    # Breakthrough: Win after >= 3 losses
    # We need to look at history BEFORE the current win (which is history[0])
    if is_win and len(history) >= 2:
        loss_streak = 0
        for match in history[1:]: # Skip current match (index 0)
            if match[8] == 'LOSS':
                loss_streak += 1
            else:
                break
        if loss_streak >= 3 and "breakthrough" not in existing_ids:
            await _grant(user_id, "breakthrough", unlocked)

    # 4. Mode Specific (from Leaderboard)
    mode_wins = stats.get(f"{mode}v{mode}_W", 0)

    if mode == 1:
        if mode_wins >= 10 and "lone_wolf" not in existing_ids: await _grant(user_id, "lone_wolf", unlocked)
        if mode_wins >= 50 and "king_1v1" not in existing_ids: await _grant(user_id, "king_1v1", unlocked)
    elif mode == 2:
        if mode_wins >= 10 and "perfect_duo" not in existing_ids: await _grant(user_id, "perfect_duo", unlocked)
    elif mode == 3:
        if mode_wins >= 10 and "team_player" not in existing_ids: await _grant(user_id, "team_player", unlocked)

    # 5. Time Based
    now = datetime.datetime.fromtimestamp(current_ts)

    # Night Owl (2:00 - 5:00)
    if 2 <= now.hour < 5 and "night_owl" not in existing_ids:
        await _grant(user_id, "night_owl", unlocked)

    # Weekend Warrior
    if now.weekday() in [5, 6]: # Sat, Sun
        weekend_count = 0
        for match in history:
            m_time = datetime.datetime.fromtimestamp(match[1])
            if m_time.weekday() in [5, 6]:
                weekend_count += 1

        if weekend_count >= 5 and "weekend_warrior" not in existing_ids:
             await _grant(user_id, "weekend_warrior", unlocked)

    # No-Life (10 games in one day) & Versatile
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today_matches = [m for m in history if m[1] >= today_start]

    if len(today_matches) >= 10 and "no_life" not in existing_ids:
        await _grant(user_id, "no_life", unlocked)

    # Versatile: Win in 1v1, 2v2, 3v3 in one day
    if is_win:
        modes_won = set()
        for m in today_matches:
            if m[8] == 'WIN':
                modes_won.add(m[2]) # game_mode

        if {1, 2, 3}.issubset(modes_won) and "versatile" not in existing_ids:
             await _grant(user_id, "versatile", unlocked)

    return unlocked

async def _grant(user_id: int, achievement_id: str, unlocked_list: list) -> bool:
    """Helper to add achievement and append to list if successful."""
    if await add_user_achievement(user_id, achievement_id):
        unlocked_list.append(ACHIEVEMENTS[achievement_id])
        return True
    return False
