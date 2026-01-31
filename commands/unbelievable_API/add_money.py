import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = os.getenv('GUILD')
UNBELIEVABOAT_API_KEY = os.getenv("UNBELIEVABOAT_API_KEY")


async def add_money_unbelievable(user_id: int, cash: int, bank: int) -> None:
    """
    Adds or deletes money from user's account asynchronously.

    :param user_id: Discord user's ID
    :param cash: Value to add (if >0) or remove (<0) to hand
    :param bank: Value to add (if >0) or remove (<0) to bank
    """
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"

    payload = {
        "cash": cash,
        "bank": bank
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"{UNBELIEVABOAT_API_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json=payload, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to update balance for {user_id}: {response.status}")
