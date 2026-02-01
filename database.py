import os
import libsql_client
import time
from typing import List, Dict, Optional, Any

def get_db_config():
    url = os.getenv("CONNECTION_URL")
    token = os.getenv("CONNECTION_TOKEN")
    if not url:
        print("Database CONNECTION_URL not set.")
        return None, None
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")
    return url, token

async def init_system_tables():
    """Initializes the SystemConfig and new tables (Matches, Achievements) if they don't exist."""
    url, token = get_db_config()
    if not url: return

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
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            game_mode INTEGER,
            stake INTEGER,
            winner_team TEXT,
            blue_score_sets INTEGER,
            orange_score_sets INTEGER,
            score_details TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS MatchParticipants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            user_id INTEGER,
            team TEXT,
            result TEXT,
            FOREIGN KEY(match_id) REFERENCES Matches(match_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS UserAchievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_id TEXT,
            unlocked_at INTEGER,
            UNIQUE(user_id, achievement_id)
        );
        """
    ]

    async with libsql_client.create_client(url, auth_token=token) as client:
        for q in queries:
            try:
                await client.execute(q)
            except Exception as e:
                print(f"Error initializing table with query: {q[:50]}... -> {e}")

        # Migration for Leaderboard columns
        goal_cols = ["1v1_GS", "1v1_GC", "2v2_GS", "2v2_GC", "3v3_GS", "3v3_GC"]
        for col in goal_cols:
            try:
                # Attempt to add column. Will fail if exists.
                await client.execute(f'ALTER TABLE Leaderboard ADD COLUMN "{col}" INTEGER DEFAULT 0')
            except Exception:
                pass

async def update_match_history(user_id: int, team_size: int, is_win: bool, goals_scored: int = 0, goals_conceded: int = 0):
    """
    Updates the match history for a user in the Leaderboard table.
    Increments the win or loss count and updates goal stats.
    """
    if team_size not in [1, 2, 3]:
        print(f"Unsupported team size for stats: {team_size}")
        return

    url, token = get_db_config()
    if not url: return

    # Determine columns
    result_type = "W" if is_win else "L"
    win_loss_col = f"{team_size}v{team_size}_{result_type}"
    gs_col = f"{team_size}v{team_size}_GS"
    gc_col = f"{team_size}v{team_size}_GC"

    # Upsert query
    query = f"""
        INSERT INTO Leaderboard (user_id, "{win_loss_col}", "{gs_col}", "{gc_col}")
        VALUES (?, 1, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            "{win_loss_col}" = "{win_loss_col}" + 1,
            "{gs_col}" = "{gs_col}" + ?,
            "{gc_col}" = "{gc_col}" + ?
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, [user_id, goals_scored, goals_conceded, goals_scored, goals_conceded])
    except Exception as e:
        print(f"Error updating match history for user {user_id}: {e}")

async def save_match_record(
    timestamp: int,
    game_mode: int,
    stake: int,
    winner_team: str,
    blue_score_sets: int,
    orange_score_sets: int,
    score_details: str,
    participants: List[Dict[str, Any]]
) -> int:
    """
    Saves a match record and its participants.
    participants: List of dicts with keys 'user_id', 'team', 'result'
    Returns match_id
    """
    url, token = get_db_config()
    if not url: return -1

    insert_match_sql = """
        INSERT INTO Matches (timestamp, game_mode, stake, winner_team, blue_score_sets, orange_score_sets, score_details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING match_id
    """

    insert_participant_sql = """
        INSERT INTO MatchParticipants (match_id, user_id, team, result)
        VALUES (?, ?, ?, ?)
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            # Insert Match
            match_res = await client.execute(insert_match_sql, [
                timestamp, game_mode, stake, winner_team, blue_score_sets, orange_score_sets, score_details
            ])

            # Get match_id from RETURNING or last_insert_rowid if needed (libsql returns rows for RETURNING)
            match_id = match_res.rows[0][0] if match_res.rows else None

            # If RETURNING didn't work (depending on driver/db version), fetch max id (less safe but fallback)
            # But Turso/libsql usually supports RETURNING

            if match_id:
                for p in participants:
                    await client.execute(insert_participant_sql, [
                        match_id, p['user_id'], p['team'], p['result']
                    ])
                return match_id
            return -1
    except Exception as e:
        print(f"Error saving match record: {e}")
        return -1

async def get_user_matches_history(user_id: int, limit: int = 10):
    """Fetches recent matches for a user."""
    url, token = get_db_config()
    if not url: return []

    query = """
        SELECT m.match_id, m.timestamp, m.game_mode, m.stake, m.winner_team,
               m.blue_score_sets, m.orange_score_sets, m.score_details, mp.result, mp.team
        FROM MatchParticipants mp
        JOIN Matches m ON mp.match_id = m.match_id
        WHERE mp.user_id = ?
        ORDER BY m.timestamp DESC
        LIMIT ?
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id, limit])
            return res.rows
    except Exception as e:
        print(f"Error fetching user history: {e}")
        return []

async def get_match_participants(match_id: int):
    """Fetches all participants for a given match."""
    url, token = get_db_config()
    if not url: return []

    query = "SELECT user_id, team, result FROM MatchParticipants WHERE match_id = ?"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [match_id])
            return res.rows
    except Exception as e:
        print(f"Error fetching match participants: {e}")
        return []

async def get_user_leaderboard_stats(user_id: int):
    """Fetches all stats for a user from Leaderboard."""
    url, token = get_db_config()
    if not url: return None

    # We need to select all relevant columns
    cols = [
        "1v1_W", "1v1_L", "1v1_GS", "1v1_GC",
        "2v2_W", "2v2_L", "2v2_GS", "2v2_GC",
        "3v3_W", "3v3_L", "3v3_GS", "3v3_GC"
    ]
    cols_quoted = [f'"{c}"' for c in cols]

    query = f"SELECT {', '.join(cols_quoted)} FROM Leaderboard WHERE user_id = ?"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id])
            if res.rows:
                row = res.rows[0]
                # Map back to a nice dict
                stats = {}
                for i, col in enumerate(cols):
                    stats[col] = row[i]
                return stats
            return None
    except Exception as e:
        print(f"Error fetching user stats: {e}")
        return None

async def add_user_achievement(user_id: int, achievement_id: str):
    """Records a new achievement for a user. Returns True if newly added."""
    url, token = get_db_config()
    if not url: return False

    query = """
        INSERT INTO UserAchievements (user_id, achievement_id, unlocked_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, achievement_id) DO NOTHING
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id, achievement_id, int(time.time())])
            return res.rows_affected > 0
    except Exception as e:
        print(f"Error adding achievement: {e}")
        return False

async def get_user_achievements(user_id: int):
    """Fetches all achievements for a user."""
    url, token = get_db_config()
    if not url: return []

    query = "SELECT achievement_id, unlocked_at FROM UserAchievements WHERE user_id = ?"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query, [user_id])
            return res.rows
    except Exception as e:
        print(f"Error fetching achievements: {e}")
        return []

# --- Existing functions preserved below (get_leaderboard_data, get_all_winners, bonus stuff) ---

async def get_leaderboard_data(team_size: int):
    """
    Retrieves the top 3 players by Wins and Top 3 by Calculated Score for a given team size.
    Score = (Wins * 3) - (Losses * 1).
    Returns a dictionary: {'wins': [...], 'score': [...]}
    Each list contains tuples: (user_id, wins, losses, score)
    """
    if team_size not in [1, 2, 3]:
        return {'wins': [], 'score': []}

    url, token = get_db_config()
    if not url: return {'wins': [], 'score': []}

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

    url, token = get_db_config()
    if not url: return []

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

async def get_bonus_count() -> int:
    """Fetches the number of lucky bonuses awarded so far."""
    url, token = get_db_config()
    if not url: return 50

    query = "SELECT value FROM SystemConfig WHERE key = 'lucky_bonus_count'"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            res = await client.execute(query)
            if res.rows:
                return res.rows[0][0]
            return 0
    except Exception as e:
        print(f"Error fetching bonus count: {e}")
        return 50

async def increment_bonus_count(amount: int):
    """Increments the lucky bonus counter."""
    url, token = get_db_config()
    if not url: return

    query = "UPDATE SystemConfig SET value = value + ? WHERE key = 'lucky_bonus_count'"

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(query, [amount])
    except Exception as e:
        print(f"Error incrementing bonus count: {e}")
