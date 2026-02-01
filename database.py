import os
import libsql_client

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

    create_table_query = """
    CREATE TABLE IF NOT EXISTS SystemConfig (
        key TEXT PRIMARY KEY,
        value INTEGER DEFAULT 0
    );
    """

    # Initialize lucky_bonus_count if not present
    init_value_query = """
    INSERT INTO SystemConfig (key, value)
    VALUES ('lucky_bonus_count', 0)
    ON CONFLICT(key) DO NOTHING;
    """

    try:
        async with libsql_client.create_client(url, auth_token=token) as client:
            await client.execute(create_table_query)
            await client.execute(init_value_query)
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
