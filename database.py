import os
import libsql_client
import json
from datetime import datetime

async def update_match_history(user_id: int, team_size: int, is_win: bool):
    """
    Updates the match history for a user in the Leaderboard table.
    Increments the win or loss count for the specific team size.
    """
    if team_size not in [1, 2, 3]:
        # Only 1v1, 2v2, 3v3 are supported
        print(f"Unsupported team size for stats: {team_size}")
        return

    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")

    if not url:
        print("Database CONNECTION_URL not set.")
        return

    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")

    # Determine column to update
    result_type = "W" if is_win else "L"
    column_name = f"{team_size}v{team_size}_{result_type}"

    # Upsert query: Insert if not exists (with 1), else update (increment by 1)
    # We assume other columns default to 0 in the schema.
    # Note: Column names starting with numbers must be double-quoted.
    query = f"""
        INSERT INTO Leaderboard (user_id, "{column_name}")
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET "{column_name}" = "{column_name}" + 1
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, [user_id])
    except Exception as e:
        print(f"Error updating match history for user {user_id}: {e}")

async def get_leaderboard_data(team_size: int):
    """
    Retrieves the top 3 players by Wins and Top 3 by Calculated Score for a given team size.
    Score = (Wins * 3) - (Losses * 1).
    Returns a dictionary: {'wins': [...], 'score': [...]}
    Each list contains tuples: (user_id, wins, losses, score)
    """
    if team_size not in [1, 2, 3]:
        return {'wins': [], 'score': []}

    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")

    if not url:
        print("Database CONNECTION_URL not set.")
        return {'wins': [], 'score': []}

    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")

    wins_col = f"{team_size}v{team_size}_W"
    losses_col = f"{team_size}v{team_size}_L"

    # 1. Top Wins
    query_wins = f"""
        SELECT user_id, "{wins_col}", "{losses_col}", ("{wins_col}" * 3 - "{losses_col}") as score
        FROM Leaderboard
        WHERE "{wins_col}" > 0
        ORDER BY "{wins_col}" DESC, score DESC
        LIMIT 3
    """

    # 2. Top Score (filtered >= 0)
    query_score = f"""
        SELECT user_id, "{wins_col}", "{losses_col}", ("{wins_col}" * 3 - "{losses_col}") as score
        FROM Leaderboard
        WHERE ("{wins_col}" > 0 OR "{losses_col}" > 0)
          AND ("{wins_col}" * 3 - "{losses_col}") >= 0
        ORDER BY score DESC, "{wins_col}" DESC
        LIMIT 3
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res_wins = await client.execute(query_wins)
            res_score = await client.execute(query_score)

            return {
                'wins': res_wins.rows,
                'score': res_score.rows
            }
    except Exception as e:
        print(f"Error fetching leaderboard for {team_size}v{team_size}: {e}")
        return {'wins': [], 'score': []}

async def get_all_winners(team_size: int):
    """
    Retrieves ALL players sorted by wins (desc) and then score (desc).
    Used for role assignment logic to find ties.
    """
    if team_size not in [1, 2, 3]:
        return []

    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return []
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    wins_col = f"{team_size}v{team_size}_W"
    losses_col = f"{team_size}v{team_size}_L"

    # Fetch users with at least 1 win
    query = f"""
        SELECT user_id, "{wins_col}", "{losses_col}", ("{wins_col}" * 3 - "{losses_col}") as score
        FROM Leaderboard
        WHERE "{wins_col}" > 0
        ORDER BY "{wins_col}" DESC, score DESC
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query)
            return res.rows
    except Exception as e:
        print(f"Error fetching winners for {team_size}v{team_size}: {e}")
        return []


async def init_system_tables():
    """Initializes the SystemConfig table if it doesn't exist."""
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    queries = [
        """
        CREATE TABLE IF NOT EXISTS SystemConfig (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        );
        """,
        """
        INSERT INTO SystemConfig (key, value)
        VALUES ('lucky_bonus_count', 0)
        ON CONFLICT(key) DO NOTHING;
        """,
        """
        CREATE TABLE IF NOT EXISTS Matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            match_type INTEGER,
            result TEXT,
            stake INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            teammates TEXT,
            opponents TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS UserAchievements (
            user_id INTEGER,
            achievement_id TEXT,
            unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, achievement_id)
        );
        """
    ]

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            for q in queries:
                await client.execute(q)
    except Exception as e:
        print(f"Error initializing system tables: {e}")


async def get_bonus_count() -> int:
    """Fetches the number of lucky bonuses awarded so far."""
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return 50 # Fail safe to max to prevent overflow if DB down
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = "SELECT value FROM SystemConfig WHERE key = 'lucky_bonus_count'"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query)
            if res.rows:
                return res.rows[0][0]
            return 0
    except Exception as e:
        print(f"Error fetching bonus count: {e}")
        return 50 # Fail safe


async def increment_bonus_count(amount: int):
    """Increments the lucky bonus counter."""
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = "UPDATE SystemConfig SET value = value + ? WHERE key = 'lucky_bonus_count'"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, [amount])
    except Exception as e:
        print(f"Error incrementing bonus count: {e}")

# ---------------- Match History & Achievements ----------------

async def log_match(user_id: int, match_data: dict):
    """
    Logs a match to the Matches table.
    match_data expects: match_type (int), result (str), stake (int), teammates (list/str), opponents (list/str)
    """
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = """
    INSERT INTO Matches (user_id, match_type, result, stake, teammates, opponents, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    # Format teammates/opponents as string if list
    teammates = match_data.get('teammates', "")
    if isinstance(teammates, list):
        teammates = ", ".join(teammates)

    opponents = match_data.get('opponents', "")
    if isinstance(opponents, list):
        opponents = ", ".join(opponents)

    params = [
        user_id,
        match_data.get('match_type'),
        match_data.get('result'),
        match_data.get('stake'),
        teammates,
        opponents,
        datetime.now().isoformat()
    ]

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, params)
    except Exception as e:
        print(f"Error logging match for {user_id}: {e}")


async def get_user_matches(user_id: int, limit: int = 20):
    """
    Fetches the last N matches for a user.
    Returns a list of dictionaries.
    """
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return []
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = """
    SELECT match_type, result, stake, teammates, opponents, timestamp
    FROM Matches
    WHERE user_id = ?
    ORDER BY timestamp DESC
    LIMIT ?
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id, limit])
            matches = []
            for row in res.rows:
                matches.append({
                    'match_type': row[0],
                    'result': row[1],
                    'stake': row[2],
                    'teammates': row[3],
                    'opponents': row[4],
                    'timestamp': row[5] # String ISO format
                })
            return matches
    except Exception as e:
        print(f"Error fetching matches for {user_id}: {e}")
        return []


async def unlock_achievement(user_id: int, achievement_id: str):
    """
    Unlocks an achievement for a user.
    """
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = """
    INSERT INTO UserAchievements (user_id, achievement_id, unlocked_at)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, achievement_id) DO NOTHING
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, [user_id, achievement_id, datetime.now().isoformat()])
    except Exception as e:
        print(f"Error unlocking achievement {achievement_id} for {user_id}: {e}")


async def get_user_achievements(user_id: int):
    """
    Fetches all unlocked achievements for a user.
    Returns a list of dicts: {'id': ..., 'unlocked_at': ...}
    """
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return []
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    query = """
    SELECT achievement_id, unlocked_at
    FROM UserAchievements
    WHERE user_id = ?
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id])
            achievements = []
            for row in res.rows:
                achievements.append({
                    'id': row[0],
                    'unlocked_at': row[1]
                })
            return achievements
    except Exception as e:
        print(f"Error fetching achievements for {user_id}: {e}")
        return []

async def get_user_stats(user_id: int):
    """
    Calculates aggregated stats for a user across all matches.
    """
    # We can calculate this from Matches table or Leaderboard table.
    # Leaderboard table has summary. Matches table allows recalculation.
    # For simplicity, let's use Leaderboard table data if available, or just aggregate Matches?
    # Leaderboard table is split by team size.
    # Let's fetch from Leaderboard for now as it persists total wins/losses.

    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url: return None
    if url.startswith("libsql://"): url = url.replace("libsql://", "https://")

    # We want total wins and losses across all modes.
    # Schema: user_id, "1v1_W", "1v1_L", "2v2_W", ...

    query = """
    SELECT "1v1_W", "1v1_L", "2v2_W", "2v2_L", "3v3_W", "3v3_L"
    FROM Leaderboard
    WHERE user_id = ?
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id])
            if res.rows:
                row = res.rows[0]
                # row is tuple
                stats = {
                    '1v1': {'W': row[0] or 0, 'L': row[1] or 0},
                    '2v2': {'W': row[2] or 0, 'L': row[3] or 0},
                    '3v3': {'W': row[4] or 0, 'L': row[5] or 0}
                }

                total_w = stats['1v1']['W'] + stats['2v2']['W'] + stats['3v3']['W']
                total_l = stats['1v1']['L'] + stats['2v2']['L'] + stats['3v3']['L']

                return {
                    'wins': total_w,
                    'losses': total_l,
                    'details': stats
                }
            return None
    except Exception as e:
        print(f"Error fetching stats for {user_id}: {e}")
        return None
