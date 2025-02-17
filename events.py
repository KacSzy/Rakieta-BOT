from discord.ext import commands
from const import BLOCKED_WORDS, BLOCKED_LINKS, LOG_CHANNEL_ID


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if 'logi' in str(message.channel):
            return

        if message.author.bot:
            return

        if 'ustawienia' in str(message.content):
            await message.reply('[Ustawienia Edka](<https://www.youtube.com/watch?v=PeMm2dlzF3k>)')

        message_str: str = message.content.lower()
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        if any(blocked_word in message_str for blocked_word in BLOCKED_WORDS):
            await message.delete()
            await message.guild.ban(message.author, reason="Scam serwer (rakieta)")
            await message.channel.send(f'{message.author.mention} banned.')
            await log_channel.send(f'🚨 {message.author.mention} scam serwer: `{message.content}`')

        elif any(blocked_link in message_str for blocked_link in BLOCKED_LINKS):
            await message.delete()
            await message.guild.ban(message.author, reason="Scam link (rakieta)")
            await message.channel.send(f'{message.author.mention} banned.')
            await log_channel.send(f'🚨 {message.author.mention} scam link: `{message.content}`')


async def setup(bot):
    await bot.add_cog(Events(bot))
