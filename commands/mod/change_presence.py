from enum import Enum

import discord


class PresenceType(Enum):
    PLAYING = 'playing',
    WATCHING = 'watching',
    STREAMING = 'streaming',
    LISTENING = 'listening',
    COMPETING = 'competing',
    CUSTOM = 'custom'


async def change_presence(bot, presence: PresenceType, name: str) -> int:

    activity = None

    if presence == PresenceType.PLAYING:
        activity = discord.Game(name=name)

    elif presence == PresenceType.WATCHING:
        activity = discord.Activity(type=discord.ActivityType.watching, name=name)

    elif presence == PresenceType.STREAMING:
        activity = discord.Streaming(name=name, url="https://www.twitch.tv/edek")

    elif presence == PresenceType.LISTENING:
        activity = discord.Activity(type=discord.ActivityType.listening, name=name)

    elif presence == PresenceType.COMPETING:
        activity = discord.Activity(type=discord.ActivityType.competing, name=name)

    elif presence == PresenceType.CUSTOM:
        activity = discord.CustomActivity(name=name)

    if activity:
        await bot.change_presence(status=discord.Status.online, activity=activity)
        return 1
    else:
        return -1
