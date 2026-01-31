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
