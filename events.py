import discord
from discord.ext import commands
from const import BLOCKED_WORDS, LOG_CHANNEL_ID


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Skip processing for logs channels, bot messages
        if message.author.bot or 'logi' in str(message.channel):
            return

        if 'ustawienia' in str(message.content):
            await message.reply('[Ustawienia Edka](<https://www.youtube.com/watch?v=PeMm2dlzF3k>)')

        # Check for blocked words
        message_content = message.content.lower()
        if any(blocked_word in message_content for blocked_word in BLOCKED_WORDS):
            await self._handle_blocked_message(message)

    async def _handle_blocked_message(self, message: discord.Message):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        # Check if user is already banned
        try:
            await message.guild.fetch_ban(message.author)
            await message.delete()
            return
        except discord.NotFound:
            pass  # User not banned -> continue processing

        # Delete message and notify channel
        await message.delete()
        await message.channel.send(f'{message.author.mention} banned.')

        # Log
        await log_channel.send(f'🚨 {message.author.mention} scam: `{message.content}`')

        # Send DM to user
        try:
            await self._send_ban_dm(message)
        except discord.Forbidden:
            await log_channel.send(f'⚠️ Nie udało się wysłać DM do {message.author.mention}.')

        # Ban the user
        await message.guild.ban(message.author, reason=f'Rakietowy scam: {message.content}')

    async def _send_ban_dm(self, message: discord.Message):
        await message.author.send(
            f"Zostałeś zbanowany na serwerze **{message.guild.name}** za wiadomość ze scamem.\n"
            f"Twoja wiadomość: `{message.content}`"
        )
        await message.author.send(
            "W celu odwołania się dołącz na [serwer](<https://discord.com/invite/v4fQDbAZQw>) i napisz podanie."
        )
        await message.author.send(
            "Jeżeli z jakiegoś powodu nie możesz dołączyć, wyślij wiadomość do <@567984269516079104>"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
