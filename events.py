import discord
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
            try:
                await message.guild.fetch_ban(message.author)
                await message.delete()
                return
            except discord.NotFound:
                pass  # User not banned -> continue

            await message.delete()
            await message.channel.send(f'{message.author.mention} banned.')
            await log_channel.send(f'🚨 {message.author.mention} scam: `{message.content}`')

            try:
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

            except discord.Forbidden:  # jeśli użytkownik ma zablokowane DM
                await log_channel.send(f'⚠️ Nie udało się wysłać DM do {message.author.mention}.')

            await message.guild.ban(message.author, reason=f'Rakietowy scam: {message.content}')


async def setup(bot):
    await bot.add_cog(Events(bot))
