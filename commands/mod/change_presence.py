from enum import Enum
import discord
from typing import Optional


class PresenceType(Enum):
    PLAYING = 'playing'
    WATCHING = 'watching'
    STREAMING = 'streaming'
    LISTENING = 'listening'
    COMPETING = 'competing'
    CUSTOM = 'custom'


async def change_presence(bot, presence: PresenceType, name: str) -> int:
    """Change the bot's presence based on the specified type and name."""
    activity = _create_activity(presence, name)

    if activity:
        await bot.change_presence(status=discord.Status.online, activity=activity)
        return 1
    return -1


def _create_activity(presence: PresenceType, name: str) -> Optional[discord.ActivityType]:
    """Create the appropriate activity object based on presence type."""
    activity_map = {
        PresenceType.PLAYING: discord.Game(name=name),
        PresenceType.WATCHING: discord.Activity(type=discord.ActivityType.watching, name=name),
        PresenceType.STREAMING: discord.Streaming(name=name, url="https://www.twitch.tv/edek"),
        PresenceType.LISTENING: discord.Activity(type=discord.ActivityType.listening, name=name),
        PresenceType.COMPETING: discord.Activity(type=discord.ActivityType.competing, name=name),
        PresenceType.CUSTOM: discord.CustomActivity(name=name)
    }

    return activity_map.get(presence)
