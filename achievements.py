from datetime import datetime, time
from typing import List, Dict, Set, Callable, Optional

# Achievement Definition
class Achievement:
    def __init__(self, id: str, name: str, description: str, condition: Callable[[List[Dict], Dict], bool]):
        self.id = id
        self.name = name
        self.description = description
        self.condition = condition

# Condition Helpers
def has_played_count(matches: List[Dict], count: int) -> bool:
    return len(matches) >= count

def has_won_count(matches: List[Dict], count: int) -> bool:
    wins = [m for m in matches if m['result'] == 'WIN']
    return len(wins) >= count

def has_lost_count(matches: List[Dict], count: int) -> bool:
    losses = [m for m in matches if m['result'] == 'LOSS']
    return len(losses) >= count

def has_won_mode_count(matches: List[Dict], mode: int, count: int) -> bool:
    wins = [m for m in matches if m['result'] == 'WIN' and m['match_type'] == mode]
    return len(wins) >= count

def current_win_streak(matches: List[Dict], count: int) -> bool:
    # Matches are assumed to be sorted desc (newest first)
    streak = 0
    for m in matches:
        if m['result'] == 'WIN':
            streak += 1
        else:
            break
    return streak >= count

def broken_loss_streak(matches: List[Dict], min_loss_streak: int) -> bool:
    # Recent match (index 0) must be a WIN
    if not matches or matches[0]['result'] != 'WIN':
        return False

    # Previous matches must be losses
    loss_streak = 0
    for m in matches[1:]:
        if m['result'] == 'LOSS':
            loss_streak += 1
        else:
            break
    return loss_streak >= min_loss_streak

def won_all_modes_today(matches: List[Dict], current_match: Dict) -> bool:
    # Check if user has won 1v1, 2v2, 3v3 today
    if not matches: return False

    current_ts = current_match.get('timestamp')
    if not isinstance(current_ts, datetime):
        # Fallback or try to parse if string
        try:
            current_ts = datetime.fromisoformat(str(current_ts))
        except:
            current_ts = datetime.now() # Fallback

    today = current_ts.date()

    wins_today = {1: False, 2: False, 3: False}

    for m in matches:
        m_ts = m['timestamp']
        if not isinstance(m_ts, datetime):
             try:
                m_ts = datetime.fromisoformat(str(m_ts))
             except:
                 continue

        if m_ts.date() != today:
            continue

        if m['result'] == 'WIN' and m['match_type'] in wins_today:
            wins_today[m['match_type']] = True

    return all(wins_today.values())

def played_count_today(matches: List[Dict], count: int) -> bool:
    if not matches: return False

    today = datetime.now().date()

    played_today = 0
    for m in matches:
        m_ts = m['timestamp']
        if not isinstance(m_ts, datetime):
             try:
                m_ts = datetime.fromisoformat(str(m_ts))
             except:
                 continue

        if m_ts.date() == today:
            played_today += 1

    return played_today >= count

def played_at_night(current_match: Dict, start_hour: int, end_hour: int) -> bool:
    # Check current match time
    ts = current_match.get('timestamp')
    if not isinstance(ts, datetime):
        try:
            ts = datetime.fromisoformat(str(ts))
        except:
            return False

    # 2:00 to 5:00
    t = ts.time()
    return time(start_hour, 0) <= t <= time(end_hour, 0)

def played_weekend_count(matches: List[Dict], count: int) -> bool:
    if not matches: return False

    current_ts = matches[0]['timestamp']
    if not isinstance(current_ts, datetime):
        try:
            current_ts = datetime.fromisoformat(str(current_ts))
        except:
            return False

    # 5 = Saturday, 6 = Sunday
    if current_ts.weekday() not in [5, 6]:
        return False

    count_weekend = 0
    current_iso_year, current_week, _ = current_ts.isocalendar()

    for m in matches:
        ts = m['timestamp']
        if not isinstance(ts, datetime):
            try:
                ts = datetime.fromisoformat(str(ts))
            except:
                continue

        iso_year, week, _ = ts.isocalendar()
        if iso_year == current_iso_year and week == current_week:
            if ts.weekday() in [5, 6]:
                count_weekend += 1
        else:
            # Assumes sorted desc
            pass

    return count_weekend >= count


# List of Achievements
ACHIEVEMENTS_LIST = [
    Achievement("first_blood", "Pierwsza Krew", "Wygraj swój pierwszy mecz.",
                lambda history, curr: has_won_count(history, 1)),

    Achievement("debut", "Debiutant", "Zagraj swój pierwszy mecz.",
                lambda history, curr: has_played_count(history, 1)),

    Achievement("humility", "Lekcja Pokory", "Przegraj swój pierwszy mecz.",
                lambda history, curr: history and history[-1]['result'] == 'LOSS'),

    Achievement("warmup", "Rozgrzewka", "Zagraj 5 meczy w dowolnym trybie.",
                lambda history, curr: has_played_count(history, 5)),

    Achievement("heating_up", "Heating Up (Rozgrzany)", "Wygraj 3 mecze z rzędu.",
                lambda history, curr: current_win_streak(history, 3)),

    Achievement("on_fire", "On Fire", "Wygraj 5 meczy z rzędu.",
                lambda history, curr: current_win_streak(history, 5)),

    Achievement("unstoppable", "Nie do zatrzymania", "Wygraj 10 meczy z rzędu.",
                lambda history, curr: current_win_streak(history, 10)),

    Achievement("breakthrough", "Przełamanie", "Wygraj mecz po serii przynajmniej 3 porażek.",
                lambda history, curr: broken_loss_streak(history, 3)),

    Achievement("lone_wolf", "Samotny Wilk", "Wygraj 10 meczy w trybie 1v1.",
                lambda history, curr: has_won_mode_count(history, 1, 10)),

    Achievement("king_1v1", "Król 1v1", "Wygraj 50 meczy w trybie 1v1.",
                lambda history, curr: has_won_mode_count(history, 1, 50)),

    Achievement("perfect_duo", "Idealny Duet", "Wygraj 10 meczy w trybie 2v2.",
                lambda history, curr: has_won_mode_count(history, 2, 10)),

    Achievement("team_play", "Gra Zespołowa", "Wygraj 10 meczy w trybie 3v3.",
                lambda history, curr: has_won_mode_count(history, 3, 10)),

    Achievement("versatile", "Wszechstronny", "Wygraj w jednym dniu przynajmniej jeden mecz w każdym trybie (1v1, 2v2 i 3v3).",
                lambda history, curr: won_all_modes_today(history, curr)),

    Achievement("regular", "Stały Bywalec", "Zagraj łącznie 50 scrimów.",
                lambda history, curr: has_played_count(history, 50)),

    Achievement("veteran", "Weteran", "Zagraj łącznie 100 scrimów.",
                lambda history, curr: has_played_count(history, 100)),

    Achievement("legend", "Legenda", "Zagraj łącznie 500 scrimów.",
                lambda history, curr: has_played_count(history, 500)),

    Achievement("no_life", "No-Life", "Zagraj 10 scrimów w ciągu jednego dnia.",
                lambda history, curr: played_count_today(history, 10)),

    Achievement("night_owl", "Nocny Marek", "Zagraj scrim między 2:00 a 5:00 rano.",
                lambda history, curr: played_at_night(curr, 2, 5)),

    Achievement("weekend_warrior", "Weekendowy Wojownik", "Zagraj przynajmniej 5 meczy w sobotę lub niedzielę.",
                lambda history, curr: played_weekend_count(history, 5)),
]

# Map for easy access
ACHIEVEMENTS = {a.id: a for a in ACHIEVEMENTS_LIST}

def check_new_achievements(user_history: List[Dict], unlocked_ids: Set[str]) -> List[Achievement]:
    """
    Checks if any new achievements are unlocked based on the latest match history.
    Returns a list of newly unlocked achievements.
    """
    if not user_history:
        return []

    # Newest match is at index 0
    current_match = user_history[0]

    newly_unlocked = []

    for ach in ACHIEVEMENTS_LIST:
        if ach.id in unlocked_ids:
            continue

        try:
            if ach.condition(user_history, current_match):
                newly_unlocked.append(ach)
        except Exception as e:
            print(f"Error checking achievement {ach.id}: {e}")

    return newly_unlocked
