import discord
from const import ROLE_ID_1V1_LEADER, ROLE_ID_2V2_LEADER, ROLE_ID_3V3_LEADER
from database import get_all_winners, get_role_holders, update_role_holders

async def update_leader_role(guild: discord.Guild, team_size: int):
    """
    Updates the leader role for the given team size based on match history.
    """
    if team_size == 1:
        role_id = ROLE_ID_1V1_LEADER
        max_leaders = 1
    elif team_size == 2:
        role_id = ROLE_ID_2V2_LEADER
        max_leaders = 2
    elif team_size == 3:
        role_id = ROLE_ID_3V3_LEADER
        max_leaders = 3
    else:
        return

    role = guild.get_role(role_id)
    if not role:
        print(f"Role with ID {role_id} not found in guild {guild.name}")
        return

    # Fetch all winners sorted by Wins DESC, Score DESC
    all_winners = await get_all_winners(team_size)

    # If no winners exist, clear everything
    if not all_winners:
        # Try to clear from DB holders
        old_holders = await get_role_holders(team_size)
        for uid in old_holders:
            try:
                member = await guild.fetch_member(uid)
                if role in member.roles:
                    await member.remove_roles(role)
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"Failed to remove role from {uid}: {e}")

        await update_role_holders(team_size, [])
        return

    # 1. Determine New Leaders
    max_wins = all_winners[0][1]
    candidates = [row for row in all_winners if row[1] == max_wins]
    candidate_ids = [int(c[0]) for c in candidates]

    # Get incumbents from DB (persistent state)
    incumbent_ids = await get_role_holders(team_size)
    valid_incumbents = [uid for uid in candidate_ids if uid in incumbent_ids]

    final_leader_ids = []

    if len(candidates) <= max_leaders:
        final_leader_ids = candidate_ids
    else:
        # Priority: Incumbents -> Highest Score
        leaders_selected = []

        # Add valid incumbents first
        for uid in valid_incumbents:
            if len(leaders_selected) < max_leaders:
                leaders_selected.append(uid)

        # Fill with remaining candidates (sorted by Score DESC)
        for row in candidates:
            if len(leaders_selected) >= max_leaders:
                break
            uid = int(row[0])
            if uid not in leaders_selected:
                leaders_selected.append(uid)

        final_leader_ids = leaders_selected

    # 2. Identify Users to Remove Role From
    users_to_remove = set()

    # A. Users who were in DB but lost the spot
    for uid in incumbent_ids:
        if uid not in final_leader_ids:
            users_to_remove.add(uid)

    # B. Safety Sweep (Top 25)
    # Check top players to see if they hold the role erroneously (e.g. from before DB tracking)
    # This fixes the bug where "previous person dropped to top 2 but kept role" if DB was empty/desync.
    top_candidates = all_winners[:25]
    for row in top_candidates:
        uid = int(row[0])
        if uid not in final_leader_ids:
            # We must check if they have the role.
            # We can't rely on users_to_remove logic alone if they weren't in DB.
            try:
                member = guild.get_member(uid)
                if not member:
                    member = await guild.fetch_member(uid)

                if role in member.roles:
                    users_to_remove.add(uid)
            except discord.NotFound:
                pass # User left server
            except Exception as e:
                print(f"Safety sweep check failed for {uid}: {e}")

    # Execute Removal
    for uid in users_to_remove:
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)

            # Double check (redundant but safe)
            if role in member.roles:
                await member.remove_roles(role)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Failed to remove role from {uid}: {e}")

    # 3. Identify Users to Add Role To
    # We iterate final_leader_ids and ensure they have the role.
    for uid in final_leader_ids:
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)

            if role not in member.roles:
                await member.add_roles(role)
        except discord.NotFound:
            print(f"Leader {uid} not found in guild.")
        except Exception as e:
            print(f"Failed to add role to {uid}: {e}")

    # 4. Update DB State
    await update_role_holders(team_size, final_leader_ids)
