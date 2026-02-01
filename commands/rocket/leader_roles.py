import discord
from const import ROLE_ID_1V1_LEADER, ROLE_ID_2V2_LEADER, ROLE_ID_3V3_LEADER
from database import get_all_winners

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
    # rows are tuples: (user_id, wins, losses, score)
    all_winners = await get_all_winners(team_size)
    if not all_winners:
        # No winners at all? Remove role from everyone
        for member in role.members:
            try:
                await member.remove_roles(role)
            except Exception as e:
                print(f"Failed to remove role from {member}: {e}")
        return

    # Determine max wins
    max_wins = all_winners[0][1]

    # Identify candidates: everyone with max_wins
    candidates = [row for row in all_winners if row[1] == max_wins]
    candidate_ids = [int(c[0]) for c in candidates]

    # Identify incumbents (current role holders)
    # We only care about incumbents who are ALSO candidates (still have max wins)
    # because if they lost max wins status, they lose role anyway.
    incumbent_ids = [m.id for m in role.members]
    valid_incumbents = [uid for uid in candidate_ids if uid in incumbent_ids]

    final_leader_ids = []

    # Logic:
    # 1. If number of candidates <= max_leaders, ALL candidates get the role.
    if len(candidates) <= max_leaders:
        final_leader_ids = candidate_ids
    else:
        # 2. If number of candidates > max_leaders, we must select subset.
        # Priority: Incumbents -> Highest Score.

        # Step A: Keep valid incumbents (up to max_leaders)
        # Assuming incumbents are already sorted by Score DESC in `candidates` list?
        # `get_all_winners` returns sorted by Wins DESC, Score DESC.
        # But `candidates` respects that order.

        # Actually, "Incumbents first".
        # Let's take valid incumbents.
        leaders_selected = []

        # Add valid incumbents first
        for uid in valid_incumbents:
            if len(leaders_selected) < max_leaders:
                leaders_selected.append(uid)

        # Step B: If spots remaining, fill with remaining candidates (highest score first)
        # `candidates` is already sorted by Score DESC because of SQL `ORDER BY ..., score DESC`
        for row in candidates:
            if len(leaders_selected) >= max_leaders:
                break
            uid = row[0]
            if uid not in leaders_selected:
                leaders_selected.append(uid)

        final_leader_ids = leaders_selected

    # Apply changes
    # 1. Remove role from those who have it but are NOT in final_leader_ids
    for member in role.members:
        if member.id not in final_leader_ids:
            try:
                await member.remove_roles(role)
            except Exception as e:
                print(f"Failed to remove role from {member}: {e}")

    # 2. Add role to final_leader_ids who don't have it
    for uid in final_leader_ids:
        member = guild.get_member(uid)
        if not member:
            try:
                member = await guild.fetch_member(uid)
            except Exception as e:
                print(f"Failed to fetch member {uid}: {e}")
                continue

        if member and role not in member.roles:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"Failed to add role to {member}: {e}")
