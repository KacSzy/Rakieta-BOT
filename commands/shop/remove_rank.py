import re

import discord

from commands.shop.items_const import COLORS_PRICES_DICT, ICONS_PRICES_DICT


def normalize_role_name(role_name: str) -> str:
    return re.sub(r'[^\w\s]', '', role_name).strip().lower()


async def check_and_remove_role(member: discord.Member, role_name: str) -> int | None:
    """
    Checks if `member` has a role named `role_name`.
    If yes - it removes the role and returns 50% of money.
    If no - func does nothing.

    :param member: Discord member to check.
    :param role_name: The name of the role we are looking for.

    :return: If `role_name` is found and can be returned, returns the amount of money user will receive.
    If '`role_name` is found but can't be returned, returns -1.
    Otherwise, returns None.
    """

    if role_name not in COLORS_PRICES_DICT and role_name not in ICONS_PRICES_DICT:
        return -1

    for role in member.roles:

        if role_name == normalize_role_name(role.name):
            price = COLORS_PRICES_DICT.get(role_name) or ICONS_PRICES_DICT.get(role_name)

            await member.remove_roles(role)
            return price

    return None
