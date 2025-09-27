# bot.py - FULL merged bot (tickets, persistence, invites, banlist, sheckles, status)
# IMPORTANT: Replace TOKEN, GUILD_ID, OWNER_ID below before running.

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import json
import datetime
import traceback

# ============================
# CONFIG - EDIT THESE
# ============================
TOKEN = "MTQyMTE1NzQ2MzM1NjM0MjMzMw.Gg2oTW.YlT9gBDzU7ib-1T5Ri5xbdAZAgEhckssUXFgdE"
GUILD_ID = 1419636162162589773   # int
OWNER_ID = 1184517618749669510   # int
TICKET_CATEGORY_NAME = "tickets"
PANEL_FILE = "data.json"                # single persistence file used for everything
STATUS_CHANNEL_ID = 1419655166411538572 # where online/offline messages are sent
MIN_ACCOUNT_AGE_HOURS = 6               # heuristic: auto-ban accounts younger than this (0 = disabled)

# ============================
# Persistence helpers
# ============================
def ensure_data():
    if not os.path.exists(PANEL_FILE):
        base = {
            "ticket_counter": 0,
            "usernames": {},    # str(user_id) -> username
            "links": {},        # str(user_id) -> link
            "inviter_map": {},  # str(member_id) -> inviter_id
            "cached_invites": {},# str(guild_id) -> {code: uses}
            "panel": None,       # {"guild": id, "channel": id, "message": id}
            "banlist": []        # list of user ids (ints)
        }
        with open(PANEL_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=2)
        return base
    with open(PANEL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d):
    with open(PANEL_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

data = ensure_data()
ticket_counter = int(data.get("ticket_counter", 0))
usernames = data.get("usernames", {})
links = data.get("links", {})
inviter_map = data.get("inviter_map", {})
cached_invites = data.get("cached_invites", {})
panel_info = data.get("panel")
banlist = set(int(x) for x in data.get("banlist", []))

def persist_all():
    global ticket_counter, usernames, links, inviter_map, cached_invites, panel_info, banlist
    data["ticket_counter"] = ticket_counter
    data["usernames"] = usernames
    data["links"] = links
    data["inviter_map"] = inviter_map
    data["cached_invites"] = cached_invites
    data["panel"] = panel_info
    data["banlist"] = list(banlist)
    save_data(data)

# ============================
# Bot setup
# ============================
intents = discord.Intents.default()
intents.members = True      # required; enable in dev portal
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ----------------------------
# Utility helpers
# ----------------------------
async def fetch_member_safe(guild: discord.Guild, user_id: int):
    try:
        m = guild.get_member(user_id)
        if m:
            return m
        return await guild.fetch_member(user_id)
    except Exception:
        return None

async def update_guild_invite_cache(guild: discord.Guild):
    try:
        invites = await guild.invites()
    except Exception:
        invites = []
    d = {inv.code: inv.uses for inv in invites}
    cached_invites[str(guild.id)] = d
    persist_all()

def get_ticket_owner_from_topic(channel: discord.TextChannel):
    topic = channel.topic or ""
    if "Ticket Owner ID:" not in topic:
        return None
    try:
        part = topic.split("Ticket Owner ID:")[1].split("|")[0].strip()
        return int(part)
    except Exception:
        return None

# ============================
# USERNAME / LINK commands (persistent)
# ============================
@tree.command(name="username_set", description="Set your Roblox username", guild=discord.Object(id=GUILD_ID))
async def username_set(interaction: discord.Interaction, roblox_username: str):
    usernames[str(interaction.user.id)] = roblox_username
    persist_all()
    await interaction.response.send_message(f"✅ Roblox username saved: **{roblox_username}**", ephemeral=True)

@tree.command(name="username_get", description="Get your Roblox username", guild=discord.Object(id=GUILD_ID))
async def username_get(interaction: discord.Interaction):
    u = usernames.get(str(interaction.user.id))
    if u:
        await interaction.response.send_message(f"🎮 Your Roblox username: **{u}**", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ No username set. Use `/username_set <name>`.", ephemeral=True)

@tree.command(name="link_set", description="Set your Roblox server link", guild=discord.Object(id=GUILD_ID))
async def link_set(interaction: discord.Interaction, server_link: str):
    links[str(interaction.user.id)] = server_link
    persist_all()
    await interaction.response.send_message("✅ Roblox server link saved.", ephemeral=True)

@tree.command(name="link_get", description="Get your Roblox server link", guild=discord.Object(id=GUILD_ID))
async def link_get(interaction: discord.Interaction):
    l = links.get(str(interaction.user.id))
    if l:
        await interaction.response.send_message(f"🔗 Your server link: {l}", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ No link set. Use `/link_set <link>`.", ephemeral=True)

# ============================
# Persistent Ticket Views & Buttons (custom_id + timeout=None)
# ============================
class HandleTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔧 Handle Ticket", style=discord.ButtonStyle.primary, custom_id="handle_ticket_btn")
    async def handle_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer so we avoid "interaction failed"
        await interaction.response.defer(ephemeral=True)
        owner_id = get_ticket_owner_from_topic(interaction.channel)
        if owner_id is None:
            await interaction.followup.send("❌ This is not a ticket channel.", ephemeral=True)
            return
        if interaction.user.id == owner_id:
            await interaction.followup.send("🚫 You cannot handle your own ticket.", ephemeral=True)
            return
        owner_member = await fetch_member_safe(interaction.guild, owner_id)
        owner_mention = owner_member.mention if owner_member else f"<@{owner_id}>"
        # Public note in ticket channel
        try:
            await interaction.channel.send(f"{owner_mention}, your ticket is being handled by {interaction.user.mention}")
        except Exception:
            pass
        await interaction.followup.send("✅ You are now handling this ticket.", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer to avoid timeouts while creating channel
        await interaction.response.defer(ephemeral=True)
        global ticket_counter
        ticket_counter += 1
        ticket_number = str(ticket_counter).zfill(3)

        # ensure category
        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            try:
                category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)
            except Exception:
                category = None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=f"ticket-{ticket_number}",
                overwrites=overwrites,
                category=category
            )
        except Exception as e:
            ticket_counter -= 1
            persist_all()
            await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
            return

        # persist owner in channel topic (durable)
        try:
            await ticket_channel.edit(topic=f"Ticket Owner ID: {interaction.user.id} | Ticket Number: {ticket_number}")
        except Exception:
            pass

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number}",
            description=(
                f"{interaction.user.mention} — Please wait for staff to handle your request.\n\n"
                "A staff member will press **Handle Ticket** to claim this ticket."
            ),
            color=discord.Color.blurple()
        )

        try:
            await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=HandleTicketView())
        except Exception:
            pass

        persist_all()
        await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

# ============================
# Panel commands and persistence
# ============================
@tree.command(name="tickets_show", description="Post (or refresh) the ticket panel (owner/admin)", guild=discord.Object(id=GUILD_ID))
async def tickets_show(interaction: discord.Interaction):
    # permission: server owner or configured owner id
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return

    embed = discord.Embed(title="🎟️ Ticket Panel", description="Click below to create a ticket.", color=discord.Color.blue())
    # send a persistent panel message
    await interaction.response.defer(ephemeral=True)
    try:
        msg = await interaction.channel.send(embed=embed, view=TicketView())
        # save panel info
        global panel_info
        panel_info = {"guild": interaction.guild.id, "channel": interaction.channel.id, "message": msg.id}
        persist_all()
        # register view instances so buttons work after restart
        bot.add_view(TicketView())
        bot.add_view(HandleTicketView())
        await interaction.followup.send("✅ Ticket panel posted and saved.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to post panel: {e}", ephemeral=True)

@tree.command(name="reset_panel", description="Reset the saved ticket panel (owner/admin)", guild=discord.Object(id=GUILD_ID))
async def reset_panel(interaction: discord.Interaction):
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return
    global panel_info
    panel_info = None
    persist_all()
    await interaction.response.send_message("✅ Panel cleared from memory. Use /tickets_show to post a new panel.", ephemeral=True)

# ============================
# Close / Delete / Reopen
# ============================
@tree.command(name="close", description="Close this ticket (Delete or Reopen)", guild=discord.Object(id=GUILD_ID))
async def close(interaction: discord.Interaction):
    owner_id = get_ticket_owner_from_topic(interaction.channel)
    if owner_id is None:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    class CloseView(discord.ui.View):
        def __init__(self, owner_id_inner):
            super().__init__(timeout=None)
            self.owner_id_inner = owner_id_inner

        @discord.ui.button(label="🗑️ Delete Ticket", style=discord.ButtonStyle.danger, custom_id="close_delete_btn")
        async def delete_ticket(self, interaction2: discord.Interaction, button: discord.ui.Button):
            await interaction2.response.defer(ephemeral=True)
            # public message and 3 second delay
            try:
                await interaction2.channel.send("🗑️ Ticket will be deleted in **3 seconds**...")
            except Exception:
                pass
            await asyncio.sleep(3)
            try:
                await interaction2.channel.delete()
            except Exception:
                await interaction2.followup.send("❌ Failed to delete channel.", ephemeral=True)

        @discord.ui.button(label="🔓 Reopen Ticket", style=discord.ButtonStyle.success, custom_id="close_reopen_btn")
        async def reopen_ticket(self, interaction2: discord.Interaction, button: discord.ui.Button):
            await interaction2.response.defer(ephemeral=True)
            owner_member = await fetch_member_safe(interaction2.guild, self.owner_id_inner)
            if owner_member:
                try:
                    await interaction2.channel.set_permissions(owner_member, view_channel=True, send_messages=True)
                except Exception:
                    pass
            await interaction2.followup.send("✅ Ticket reopened (owner can view again).", ephemeral=False)

    await interaction.response.send_message("⚙️ Choose an option:", view=CloseView(owner_id), ephemeral=True)

# ============================
# Manual handle / delete commands (admin)
# ============================
@tree.command(name="handle", description="Assign a handler to the ticket (Admin only)", guild=discord.Object(id=GUILD_ID))
async def handle_cmd(interaction: discord.Interaction, member: discord.Member):
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission to use /handle.", ephemeral=True)
        return
    owner = get_ticket_owner_from_topic(interaction.channel)
    if owner is None:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return
    if member.id == owner:
        await interaction.response.send_message("🚫 Can't set the ticket creator as handler.", ephemeral=True)
        return
    owner_member = await fetch_member_safe(interaction.guild, owner)
    owner_mention = owner_member.mention if owner_member else f"<@{owner}>"
    await interaction.response.send_message(f"{owner_mention}, your ticket is now being handled by {member.mention}", ephemeral=False)

@tree.command(name="delete", description="Delete ticket channel (Admin only)", guild=discord.Object(id=GUILD_ID))
async def delete_cmd(interaction: discord.Interaction):
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    owner = get_ticket_owner_from_topic(interaction.channel)
    if owner is None:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.channel.send("🗑️ Ticket will be deleted in **3 seconds**...")
    except Exception:
        pass
    await asyncio.sleep(3)
    try:
        await interaction.channel.delete()
    except Exception:
        await interaction.followup.send("❌ Failed to delete channel.", ephemeral=True)

# ============================
# SHECKLES converter
# ============================
notation_map = {
    "k": 3, "m": 6, "b": 9, "t": 12,
    "qa": 15, "qi": 18, "sx": 21, "sp": 24, "oc": 27,
}

def expand_notation(value: str) -> str:
    v = value.lower().strip()
    for notation, zeros in notation_map.items():
        if v.endswith(notation):
            try:
                base = int(v[:-len(notation)])
                return str(base * (10 ** zeros))
            except Exception:
                return None
    if v.isdigit():
        return v
    return None

@tree.command(name="sheckles", description="Convert shorthand money notation (e.g. 1sx)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(value="Enter a number like 1t, 2sx, 5qa")
async def sheckles(interaction: discord.Interaction, value: str = None):
    if value:
        expanded = expand_notation(value)
        if expanded is None:
            await interaction.response.send_message("❌ Invalid format. Example: `1sx`, `5qa`", ephemeral=True)
            return
        await interaction.response.send_message(f"💰 **{value.upper()}** = `{expanded}`", ephemeral=True)
    else:
        await interaction.response.send_message("🎟️ Use `/sheckles <value>` to convert (e.g. `/sheckles 1sx`).", ephemeral=True)

# ============================
# Invite tracking (on_member_join)
# ============================
@bot.event
async def on_ready():
    # sync commands
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
    except Exception:
        pass

    # Register persistent views so Discord routes button interactions to our callbacks
    bot.add_view(TicketView())
    bot.add_view(HandleTicketView())

    # Restore panel if saved
    global panel_info
    if panel_info:
        try:
            g = bot.get_guild(panel_info["guild"])
            ch = g.get_channel(panel_info["channel"]) if g else None
            if ch:
                try:
                    msg = await ch.fetch_message(panel_info["message"])
                    await msg.edit(view=TicketView())
                    print("✅ Ticket panel restored after restart")
                except Exception:
                    # Panel may have been deleted - clear it
                    panel_info = None
                    persist_all()
        except Exception:
            panel_info = None
            persist_all()

    # cache invites for the guild to detect which invite was used
    try:
        g = bot.get_guild(GUILD_ID)
        if g:
            invites = await g.invites()
            cached_invites[str(GUILD_ID)] = {inv.code: inv.uses for inv in invites}
            persist_all()
    except Exception:
        pass

    # online status
    try:
        ch = bot.get_channel(STATUS_CHANNEL_ID)
        if ch:
            await ch.send("🟢 Reactor Bot is **online**!")
    except Exception:
        pass

    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_member_join(member: discord.Member):
    # auto-ban if in persistent banlist
    if member.id in banlist:
        try:
            await member.guild.ban(member, reason="Persistent banlist auto-ban")
        except Exception:
            pass
        return

    # anti-alt heuristic: ban if account age < MIN_ACCOUNT_AGE_HOURS (if >0)
    if MIN_ACCOUNT_AGE_HOURS and MIN_ACCOUNT_AGE_HOURS > 0:
        now = datetime.datetime.utcnow()
        created = member.created_at
        age_hours = (now - created).total_seconds() / 3600.0
        if age_hours < MIN_ACCOUNT_AGE_HOURS:
            try:
                await member.guild.ban(member, reason=f"Account too new ({age_hours:.1f}h) - auto-ban heuristic")
            except Exception:
                pass
            return

    # detect invites used
    try:
        new_invites = await member.guild.invites()
    except Exception:
        new_invites = []
    old = cached_invites.get(str(member.guild.id), {})
    used = None
    for inv in new_invites:
        old_use = old.get(inv.code, 0)
        if inv.uses > old_use:
            used = inv
            break

    # update cache
    try:
        cached_invites[str(member.guild.id)] = {inv.code: inv.uses for inv in new_invites}
        persist_all()
    except Exception:
        pass

    if used:
        inviter_map[str(member.id)] = str(used.inviter.id)
        persist_all()

@bot.event
async def on_member_remove(member: discord.Member):
    # keep inviter_map as-is (optional cleanup could be done here)
    pass

# ============================
# Persistent banlist commands
# ============================
@tree.command(name="ban_record", description="Add user to persistent banlist and ban them", guild=discord.Object(id=GUILD_ID))
async def ban_record(interaction: discord.Interaction, user: discord.User, reason: str = None):
    if not (interaction.user.guild_permissions.ban_members or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return
    banlist.add(int(user.id))
    persist_all()
    try:
        await interaction.guild.ban(user, reason=reason or "Added to persistent banlist")
    except Exception:
        pass
    await interaction.response.send_message(f"✅ {user} added to persistent banlist and banned (if in guild).", ephemeral=True)

@tree.command(name="unban_record", description="Remove user from persistent banlist", guild=discord.Object(id=GUILD_ID))
async def unban_record(interaction: discord.Interaction, user_id: int):
    if not (interaction.user.guild_permissions.ban_members or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return
    banlist.discard(int(user_id))
    persist_all()
    await interaction.response.send_message(f"✅ Removed {user_id} from persistent banlist.", ephemeral=True)

@tree.command(name="banlist", description="Show persistent banlist", guild=discord.Object(id=GUILD_ID))
async def banlist_cmd(interaction: discord.Interaction):
    if not (interaction.user.guild_permissions.ban_members or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return
    if not banlist:
        await interaction.response.send_message("Banlist is empty.", ephemeral=True)
        return
    ids = "\n".join(str(x) for x in sorted(banlist))
    await interaction.response.send_message(f"**Persistent banlist**:\n{ids}", ephemeral=True)

# ============================
# Inviter commands
# ============================
@tree.command(name="inviter", description="Check who invited a user (if recorded)", guild=discord.Object(id=GUILD_ID))
async def inviter_cmd(interaction: discord.Interaction, user: discord.Member):
    inv = inviter_map.get(str(user.id))
    if inv:
        try:
            inv_member = await fetch_member_safe(interaction.guild, int(inv))
            if inv_member:
                await interaction.response.send_message(f"{user.mention} was invited by {inv_member.mention}", ephemeral=True)
                return
        except Exception:
            pass
        await interaction.response.send_message(f"{user.mention} was invited by <@{inv}>", ephemeral=True)
    else:
        await interaction.response.send_message(f"No inviter info recorded for {user.mention}.", ephemeral=True)

@tree.command(name="invites_check", description="Check invite uses for a user", guild=discord.Object(id=GUILD_ID))
async def invites_check(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    try:
        invites = await interaction.guild.invites()
    except Exception:
        invites = []
    total = sum(inv.uses for inv in invites if inv.inviter and inv.inviter.id == user.id)
    await interaction.response.send_message(f"{user.mention} has {total} invite uses (current invites).", ephemeral=True)

# ============================
# /say (DM) command
# ============================
@tree.command(name="say", description="Send a DM to a user (Admin only)", guild=discord.Object(id=GUILD_ID))
async def say_cmd(interaction: discord.Interaction, user: discord.Member, message: str):
    if not (interaction.user.guild_permissions.manage_guild or interaction.user.id == OWNER_ID):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    try:
        await user.send(message)
        await interaction.response.send_message(f"✅ Sent DM to {user.mention}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to send DM: {e}", ephemeral=True)

# ============================
# /help
# ============================
@tree.command(name="help", description="Show available commands", guild=discord.Object(id=GUILD_ID))
async def help_cmd(interaction: discord.Interaction):
    e = discord.Embed(title="Bot Commands", color=discord.Color.green())
    e.add_field(name="/username_set <name>", value="Save username", inline=False)
    e.add_field(name="/username_get", value="Show username", inline=False)
    e.add_field(name="/link_set <link>", value="Save server link", inline=False)
    e.add_field(name="/link_get", value="Show server link", inline=False)
    e.add_field(name="/tickets_show", value="Post ticket panel (owner/admin)", inline=False)
    e.add_field(name="/reset_panel", value="Clear saved panel (owner/admin)", inline=False)
    e.add_field(name="/close", value="Close ticket (delete or reopen)", inline=False)
    e.add_field(name="/handle <member>", value="Assign handler (admin)", inline=False)
    e.add_field(name="/delete", value="Delete ticket (admin)", inline=False)
    e.add_field(name="/sheckles <value>", value="Convert notation (e.g. 1sx)", inline=False)
    e.add_field(name="/ban_record <user>", value="Add user to persistent banlist (admin)", inline=False)
    e.add_field(name="/unban_record <id>", value="Remove user from banlist (admin)", inline=False)
    e.add_field(name="/banlist", value="Show banlist (admin)", inline=False)
    e.add_field(name="/inviter <user>", value="Who invited this user (if recorded)", inline=False)
    e.add_field(name="/invites_check [user]", value="Check current invite uses", inline=False)
    e.add_field(name="/say <user> <message>", value="Send DM (admin)", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

# ============================
# Online / Offline messages
# ============================
@bot.event
async def on_disconnect():
    try:
        ch = bot.get_channel(STATUS_CHANNEL_ID)
        if ch:
            await ch.send("🔴 Reactor Bot is **offline**!")
    except Exception:
        pass

# ============================
# Startup & run
# ============================
if TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("ERROR: Edit TOKEN, GUILD_ID, OWNER_ID at the top of bot.py before running.")
else:
    try:
        bot.run(TOKEN)
    except Exception:
        traceback.print_exc()
