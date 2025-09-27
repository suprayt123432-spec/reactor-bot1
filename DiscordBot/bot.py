import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os

# === SETTINGS ===
TOKEN = os.getenv("DISCORD_TOKEN")  # Your bot token in Replit Secrets
GUILD_ID = int(os.getenv("GUILD_ID", "1419636162162589773"))
OWNER_ID = int(os.getenv("OWNER_ID", "1184517618749669510"))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "1419655166411538572"))
TICKET_CATEGORY_NAME = "tickets"

# Allowed roles for bot commands
ALLOWED_ROLES = {
    1419661398790639728,  # Owner
    1419659627578134630,
    1419640962136674396,
    1419667020752093244
}

# Memory storage
usernames = {}
links = {}
ticket_counter = 0

# === BOT SETUP ===
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# === ROLE CHECK ===
def is_allowed(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    return any(role.id in ALLOWED_ROLES for role in interaction.user.roles)


# === USERNAME COMMANDS ===
@tree.command(name="username_set", description="Set your Roblox username", guild=discord.Object(id=GUILD_ID))
async def username_set(interaction: discord.Interaction, roblox_username: str):
    usernames[interaction.user.id] = roblox_username
    await interaction.response.send_message(f"✅ Your Roblox username has been set to: **{roblox_username}**", ephemeral=True)


@tree.command(name="username_get", description="Get your Roblox username", guild=discord.Object(id=GUILD_ID))
async def username_get(interaction: discord.Interaction):
    username = usernames.get(interaction.user.id, "Not set yet.")
    await interaction.response.send_message(f"🎮 Your Roblox username: **{username}**", ephemeral=True)


# === LINK COMMANDS ===
@tree.command(name="link_set", description="Set your Roblox server link", guild=discord.Object(id=GUILD_ID))
async def link_set(interaction: discord.Interaction, server_link: str):
    links[interaction.user.id] = server_link
    await interaction.response.send_message(f"✅ Your Roblox server link has been set to: {server_link}", ephemeral=True)


@tree.command(name="link_get", description="Get your Roblox server link", guild=discord.Object(id=GUILD_ID))
async def link_get(interaction: discord.Interaction):
    link = links.get(interaction.user.id, "Not set yet.")
    await interaction.response.send_message(f"🔗 Your Roblox server link: {link}", ephemeral=True)


# === HANDLE TICKET BUTTON ===
class HandleTicketView(discord.ui.View):
    def __init__(self, ticket_owner_id: int):
        super().__init__(timeout=None)
        self.ticket_owner_id = ticket_owner_id

    @discord.ui.button(label="🔧 Handle Ticket", style=discord.ButtonStyle.primary, custom_id="handle_ticket")
    async def handle_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.ticket_owner_id:
            await interaction.response.send_message("❌ You cannot handle your own ticket.", ephemeral=True)
            return

        ticket_owner = interaction.guild.get_member(self.ticket_owner_id)
        if ticket_owner:
            await interaction.response.send_message(
                f"{ticket_owner.mention}, your ticket is now being handled by {interaction.user.mention} ✅"
            )
        else:
            await interaction.response.send_message("⚠️ Could not find the ticket creator.", ephemeral=True)


# === CREATE TICKET BUTTON ===
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Create Ticket", style=discord.ButtonStyle.blurple, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global ticket_counter
        ticket_counter += 1
        ticket_number = str(ticket_counter).zfill(3)

        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_number}",
            overwrites=overwrites,
            category=category
        )

        await ticket_channel.edit(topic=f"Ticket Owner ID: {interaction.user.id}")

        embed = discord.Embed(
            title="⏳ Waiting for Payout Manager",
            description=(
                "Please wait for a payout manager to be assigned to your **Withdrawal** ticket.\n\n"
                "🕐 Your withdrawal request is pending.\n\n"
                "**Next Steps**\nA payout manager will be assigned to assist you shortly."
            ),
            color=discord.Color.blurple()
        )

        await ticket_channel.send(
            content=f"{interaction.user.mention}",
            embed=embed,
            view=HandleTicketView(interaction.user.id)
        )

        await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)


# === SHOW TICKET PANEL ===
@tree.command(name="tickets_show", description="Show the ticket panel (Admins only)", guild=discord.Object(id=GUILD_ID))
async def tickets_show(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎟️ Ticket Panel",
        description="Click below to create a ticket.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, view=TicketView())


# === CLOSE TICKET COMMAND ===
@tree.command(name="close", description="Close a ticket channel with options", guild=discord.Object(id=GUILD_ID))
async def close(interaction: discord.Interaction):
    topic = interaction.channel.topic
    if not topic or "Ticket Owner ID:" not in topic:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    ticket_owner_id = int(topic.split(":")[1].strip())

    class CloseView(discord.ui.View):
        @discord.ui.button(label="🗑️ Delete Ticket", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
        async def delete_ticket(self, interaction2: discord.Interaction, button: discord.ui.Button):
            await interaction.channel.send("🗑️ Ticket will be deleted in **3 seconds**...")
            await asyncio.sleep(3)
            await interaction.channel.delete()

        @discord.ui.button(label="🔓 Reopen Ticket", style=discord.ButtonStyle.success, custom_id="reopen_ticket")
        async def reopen_ticket(self, interaction2: discord.Interaction, button: discord.ui.Button):
            ticket_owner = interaction.guild.get_member(ticket_owner_id)
            if ticket_owner:
                await interaction2.channel.set_permissions(ticket_owner, view_channel=True, send_messages=True)
            await interaction2.response.send_message("🔓 Ticket reopened.")

    await interaction.response.send_message("⚙️ Choose an option:", view=CloseView())


# === SHECKLES COMMAND ===
notation_map = {
    "k": 3, "m": 6, "b": 9, "t": 12,
    "qa": 15, "qi": 18, "sx": 21, "sp": 24, "oc": 27,
}

def expand_notation(value: str) -> str:
    value = value.lower().strip()
    for notation, zeros in notation_map.items():
        if value.endswith(notation):
            try:
                base = int(value[:-len(notation)])
                return str(base * (10 ** zeros))
            except ValueError:
                return None
    if value.isdigit():
        return value
    return None

@tree.command(name="sheckles", description="Convert number notation (e.g. 1sx → full number)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(value="Enter a number like 1t, 2sx, 5qa")
async def sheckles(interaction: discord.Interaction, value: str):
    expanded = expand_notation(value)
    if expanded:
        await interaction.response.send_message(f"💰 **{value.upper()}** = `{expanded}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid value format.", ephemeral=True)


# === EVENTS ===
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(TicketView())
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if channel:
        await channel.send("✅ Reactor bot is **online**.")
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_disconnect():
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if channel:
        try:
            await channel.send("⚠️ Reactor bot is **offline**.")
        except:
            pass


# === RUN BOT ===
bot.run(TOKEN)
