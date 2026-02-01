import sqlite3
import asyncio
from typing import List, Any

# Mock/Adapter for libsql_client to use sqlite3 locally
class MockResult:
    def __init__(self, rows, rows_affected=0):
        self.rows = rows
        self.rows_affected = rows_affected

class MockClient:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        if params is None:
            params = []
        try:
            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()
            # Convert sqlite3.Row to tuple or accessible by index/name
            # libsql returns rows that can be accessed by index
            rows_list = [tuple(r) for r in rows]
            self.conn.commit()
            return MockResult(rows_list, cursor.rowcount)
        except Exception as e:
            self.conn.rollback()
            raise e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

# We will import the migration function from database (once implemented)
# from database import check_and_migrate_tables

async def test_migration():
    db_path = "test_migration.db"
    # Setup "bad" state
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create Leaderboard with INTEGER user_id
    c.execute('CREATE TABLE Leaderboard (user_id INTEGER PRIMARY KEY, "1v1_W" INTEGER)')
    c.execute('INSERT INTO Leaderboard (user_id, "1v1_W") VALUES (?, ?)', (123456789012345678, 5))

    # Create MatchParticipants with INTEGER user_id
    c.execute('CREATE TABLE Matches (match_id INTEGER PRIMARY KEY)')
    c.execute('CREATE TABLE MatchParticipants (id INTEGER PRIMARY KEY, match_id INTEGER, user_id INTEGER, team TEXT, result TEXT)')
    c.execute('INSERT INTO Matches (match_id) VALUES (1)')
    c.execute('INSERT INTO MatchParticipants (match_id, user_id, team, result) VALUES (1, ?, "Blue", "WIN")', (123456789012345678,))

    conn.commit()
    conn.close()

    print("DB Setup Complete. Running Migration...")

    # Run migration (mocking the client creation)
    # We need to monkeypatch or pass the client to the migration function
    # For now, let's assume we can pass the client explicitly or use the mock

    client = MockClient(db_path)

    # Call migration function (simulated import)
    from database import migrate_tables_to_text
    await migrate_tables_to_text(client)

    # Verify schema
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check Leaderboard user_id type
    # In SQLite, checking type in PRAGMA table_info
    c.execute("PRAGMA table_info(Leaderboard)")
    columns = {row[1]: row[2] for row in c.fetchall()}
    print("Leaderboard Columns:", columns)
    if columns['user_id'] != 'TEXT':
        print("FAILURE: Leaderboard user_id is NOT TEXT")
    else:
        print("SUCCESS: Leaderboard user_id is TEXT")

    # Check data preserved
    c.execute("SELECT user_id FROM Leaderboard")
    uid = c.fetchone()[0]
    print(f"Leaderboard user_id value: {uid} (Type: {type(uid)})")

    # Check MatchParticipants
    c.execute("PRAGMA table_info(MatchParticipants)")
    columns = {row[1]: row[2] for row in c.fetchall()}
    print("MatchParticipants Columns:", columns)
    if columns['user_id'] != 'TEXT':
        print("FAILURE: MatchParticipants user_id is NOT TEXT")
    else:
        print("SUCCESS: MatchParticipants user_id is TEXT")

    c.execute("SELECT user_id FROM MatchParticipants")
    uid = c.fetchone()[0]
    print(f"MatchParticipants user_id value: {uid} (Type: {type(uid)})")

    conn.close()

    # Cleanup
    import os
    os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(test_migration())
