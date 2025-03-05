from discord.ext import commands
from const import BLOCKED_WORDS, LOG_CHANNEL_ID


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
            await message.channel.send(f'{message.author.mention} banned.')
            await log_channel.send(f'🚨 {message.author.mention} scam: `{message.content}`')
            await message.guild.ban(message.author, reason=f'Rakietowy scam: {message.content}')


async def setup(bot):
    await bot.add_cog(Events(bot))
