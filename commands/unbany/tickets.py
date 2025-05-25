import asyncio
from typing import Final

import discord
from discord import ui, ButtonStyle

ADMIN_ROLE_ID: Final[int] = 779479259487928360
CATEGORY_ID: Final[int] = 1350532455752405074


class TicketButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create ticket", style=ButtonStyle.grey, emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button) -> None:
        guild = interaction.guild
        user = interaction.user

        admin_role = guild.get_role(ADMIN_ROLE_ID)

        settings_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        category = guild.get_channel(CATEGORY_ID)
        ticket_channel = await guild.create_text_channel(name=f"ticket-{user.name}", category=category,
                                                         overwrites=settings_overwrites)

        await interaction.response.send_message(f"Twój ticket został utworzony: {ticket_channel.mention}",
                                                ephemeral=True)

        message: str = (f'{user.mention} dziękujemy za stworzenie ticketa!\n'
                        f'Napisz podanie zgodne ze wzorem.\n'
                        f'Administracja wkrótce się z Tobą skontaktuje.')

        await ticket_channel.send(
            message,
            view=CloseTicketButton(user, admin_role)
        )


class CloseTicketButton(ui.View):
    def __init__(self, user, admin_role):
        super().__init__(timeout=None)
        self.user = user
        self.admin_role = admin_role

    @ui.button(label="Close Ticket", style=ButtonStyle.red, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if self.admin_role not in interaction.user.roles:
            await interaction.followup.send("Nie masz uprawnień do zamknięcia tego ticketa.", ephemeral=True)
            return

        await interaction.followup.send('Ok!', ephemeral=True)
        await interaction.channel.send('Zamykanie...')
        await asyncio.sleep(3)
        await interaction.channel.delete()
