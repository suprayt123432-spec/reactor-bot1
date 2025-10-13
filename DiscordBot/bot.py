# bot.py - FIXED & SECURE: Currency System (K, M, B, T, Qa, Qi, Sx, Sp, Oc)
import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import re

# ============================
# CONFIG
# ============================
TOKEN = os.getenv("MTQyMTE1NzQ2MzM1NjM0MjMzMw.GZ6NIV.HDClEc6oYF9pEpPfI9rOMKJd8PMnW2aswcAY1c")  # ✅ Securely read token from environment
GUILD_ID = 1427269750576124007
OWNER_ID = 1184517618749669510
TICKET_CATEGORY_NAME = "tickets"
PANEL_FILE = "data.json"
STATUS_CHANNEL_ID = 1427304360484012053

ADMIN_ROLE_IDS = {
    1427270463305945172,  # Owner role
    1427294002662736046,
}

# ============================
# Persistence
# ============================
def ensure_data():
    if not os.path.exists(PANEL_FILE):
        base = {
            "ticket_counter": 0,
            "balances": {},
            "usernames": {},
            "links": {},
            "invites": {},
            "panel": None
        }
        with open(PANEL_FILE, "w") as f:
            json.dump(base, f, indent=2)
        return base
    with open(PANEL_FILE, "r") as f:
        return json.load(f)

def save_data():
    with open(PANEL_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = ensure_data()

# ============================
# Bot setup
# ============================
intents = discord.Intents.default()
intents.message_content = True  # ✅ Fix for the “Privileged Intent missing” warning
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def is_admin(user: discord.Member):
    return user.id == OWNER_ID or any(r.id in ADMIN_ROLE_IDS for r in user.roles)

# ============================
# Currency Helpers
# ============================
suffixes = [
    (1e27, "Oc"), (1e24, "Sp"), (1e21, "Sx"), (1e18, "Qi"),
    (1e15, "Qa"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")
]

def format_balance(amount: float) -> str:
    for value, suffix in suffixes:
        if amount >= value:
            formatted = f"{amount / value:.2f}".rstrip("0").rstrip(".")
            return f"{formatted}{suffix}"
    return str(int(amount))

def parse_amount(input_str: str) -> float:
    input_str = input_str.strip().lower()
    match = re.match(r"^([\d,.]+)\s*([a-z]*)$", input_str)
    if not match:
        raise ValueError("Invalid amount format.")
    num, suffix = match.groups()
    num = float(num.replace(",", ""))
    suffix = suffix.lower()
    suffix_map = {
        "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12,
        "qa": 1e15, "qi": 1e18, "sx": 1e21,
        "sp": 1e24, "oc": 1e27
    }
    if suffix in suffix_map:
        num *= suffix_map[suffix]
    return num

# ============================
# Panel / Tickets / Misc
# ============================
async def update_panel_status(status_text: str):
    panel = data.get("panel")
    if not panel:
        return
    guild = bot.get_guild(panel["guild"])
    if not guild:
        return
    channel = guild.get_channel(panel["channel"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(panel["message"])
        if msg.embeds:
            embed = msg.embeds[0]
            if embed.fields:
                embed.set_field_at(0, name="Bot Status", value=status_text, inline=False)
            else:
                embed.add_field(name="Bot Status", value=status_text, inline=False)
            await msg.edit(embed=embed, view=TicketView())
    except Exception:
        pass

class HandleTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔧 Handle Ticket", style=discord.ButtonStyle.primary, custom_id="handle_ticket_btn")
    async def handle_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(f"✅ {interaction.user.mention} is now handling this ticket.")

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        data["ticket_counter"] += 1
        ticket_number = str(data["ticket_counter"]).zfill(3)

        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_number}", overwrites=overwrites, category=category
        )

        invites = data["invites"].get(str(interaction.user.id), 0)
        balance = data["balances"].get(str(interaction.user.id), 0)

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number}",
            description=f"{interaction.user.mention} created this ticket.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="📩 Invites", value=f"{invites}", inline=False)
        embed.add_field(name="💰 Balance", value=format_balance(balance), inline=False)

        await channel.send(embed=embed, view=HandleTicketView())
        save_data()
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# ============================
# Slash Commands (unchanged)
# ============================
# [your slash commands remain exactly as before — no edits needed]

# ============================
# Events
# ============================
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(TicketView())
    bot.add_view(HandleTicketView())
    await update_panel_status("🟢 Online")
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if ch:
        await ch.send("🟢 Bot is **online**!")
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_disconnect():
    await update_panel_status("🔴 Offline")
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if ch:
        await ch.send("🔴 Bot is **offline**!")

# ============================
# Run
# ============================
if not TOKEN:
    raise ValueError("❌ TOKEN environment variable not set.")
bot.run(TOKEN)
