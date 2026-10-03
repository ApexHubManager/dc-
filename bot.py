import os
import re
import json
import random
import string
import asyncio
import secrets
import ipaddress
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    from proxmoxer import ProxmoxAPI
except ImportError:
    ProxmoxAPI = None


# ============================================================
# APEX CLOULD
# COMPLETE DISCORD BOT
# ============================================================

load_dotenv()

BRAND = os.getenv("BRAND", "APEX CLOULD")
TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "1373911333455659038"))
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

DATA_FILE = os.getenv("DATA_FILE", "data.json")
REGIMENT_FILE = os.getenv("REGIMENT_FILE", "regiment.txt")

DISCORD_INVITE = os.getenv(
    "DISCORD_INVITE",
    "https://discord.gg/6Vwvgf9Haw"
)

TICKET_CATEGORY_NAME = os.getenv(
    "TICKET_CATEGORY_NAME",
    "APEX CLOULD TICKETS"
)

APPLICATION_CATEGORY_NAME = os.getenv(
    "APPLICATION_CATEGORY_NAME",
    "APEX CLOULD APPLICATIONS"
)

MAX_TIMEOUT_DAYS = 28


# ============================================================
# PROXMOX CONFIG
# ============================================================

PROXMOX_HOST = os.getenv("PROXMOX_HOST", "")
PROXMOX_PORT = int(os.getenv("PROXMOX_PORT", "8006"))
PROXMOX_USER = os.getenv("PROXMOX_USER", "")
PROXMOX_TOKEN_NAME = os.getenv("PROXMOX_TOKEN_NAME", "")
PROXMOX_TOKEN_VALUE = os.getenv("PROXMOX_TOKEN_VALUE", "")
PROXMOX_VERIFY_SSL = os.getenv(
    "PROXMOX_VERIFY_SSL",
    "false"
).lower() == "true"

PROXMOX_NODE = os.getenv("PROXMOX_NODE", "")
PROXMOX_STORAGE = os.getenv("PROXMOX_STORAGE", "local-lvm")
PROXMOX_BRIDGE = os.getenv("PROXMOX_BRIDGE", "vmbr0")

PROXMOX_VM_TEMPLATE = os.getenv(
    "PROXMOX_VM_TEMPLATE",
    ""
)

PROXMOX_CT_TEMPLATE = os.getenv(
    "PROXMOX_CT_TEMPLATE",
    ""
)


# ============================================================
# PLANS
# ============================================================

PLANS = {
    "1": {
        "name": "Plan 1",
        "ram": 4096,
        "cores": 2,
        "disk": 50
    },
    "2": {
        "name": "Plan 2",
        "ram": 8192,
        "cores": 4,
        "disk": 80
    },
    "3": {
        "name": "Plan 3",
        "ram": 16384,
        "cores": 6,
        "disk": 120
    },
    "4": {
        "name": "Plan 4",
        "ram": 32768,
        "cores": 8,
        "disk": 200
    }
}


# ============================================================
# DEFAULT DATA
# ============================================================

DEFAULT_DATA = {
    "admins": [],
    "vps_managers": [],

    "promotion_roles": {},
    "member_roles": [],

    "config": {
        "logs_channel": None,
        "welcome_channel": None,
        "leave_channel": None,
        "application_channel": None,
        "application_review_channel": None
    },

    "automod": {
        "links_enabled": False,
        "badwords_enabled": False,
        "bypass_roles": [],
        "badwords": []
    },

    "warnings": {},
    "tickets": {},
    "applications": {},
    "giveaways": {},
    "vps": {},

    "lockdown": {
        "active": False,
        "channel": None
    },

    "counter": {
        "vps": 1000,
        "ticket": 0,
        "application": 0
    }
}


# ============================================================
# DATA FUNCTIONS
# ============================================================

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        merged = json.loads(json.dumps(DEFAULT_DATA))

        for key, value in data.items():
            if isinstance(value, dict) and isinstance(
                merged.get(key),
                dict
            ):
                merged[key].update(value)
            else:
                merged[key] = value

        return merged

    except Exception:
        return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data):
    temp_file = DATA_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    os.replace(temp_file, DATA_FILE)


data = load_data()


# ============================================================
# REGIMENT
# ============================================================

def load_regiment():
    if not os.path.exists(REGIMENT_FILE):
        with open(
            REGIMENT_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(
                "# APEX CLOULD REGIMENT\n"
                "# Add your regiment information here.\n"
            )

    try:
        with open(
            REGIMENT_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return file.read().strip()
    except Exception:
        return ""


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True


class ApexBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        restore_persistent_views()

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)

            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(
                    f"[APEX CLOULD] Synced commands to {GUILD_ID}"
                )
            except Exception as error:
                print(
                    f"[APEX CLOULD] Guild sync error: {error}"
                )
        else:
            try:
                await self.tree.sync()
                print("[APEX CLOULD] Global commands synced")
            except Exception as error:
                print(
                    f"[APEX CLOULD] Global sync error: {error}"
                )

        if not expiry_checker.is_running():
            expiry_checker.start()

        if not giveaway_checker.is_running():
            giveaway_checker.start()

    async def on_ready(self):
        print("=" * 55)
        print(f"{BRAND} ONLINE")
        print(f"Bot: {self.user}")
        print(f"ID: {self.user.id}")
        print("=" * 55)


bot = ApexBot()


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)


def timestamp():
    return now().isoformat()


def parse_timestamp(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return now()


def owner_only(user):
    return user.id == OWNER_ID


def is_admin(member):
    if member.id == OWNER_ID:
        return True

    return member.id in data["admins"]


def is_vps_manager(member):
    if member.id == OWNER_ID:
        return True

    if member.id in data["vps_managers"]:
        return True

    return is_admin(member)


def is_staff(member):
    return is_admin(member) or is_vps_manager(member)


def has_bypass_role(member):
    for role in member.roles:
        if role.id in data["automod"]["bypass_roles"]:
            return True

    return False


def mention(user):
    return f"<@{user.id}>"


def random_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(
        secrets.choice(chars)
        for _ in range(length)
    )


def random_vps_id():
    data["counter"]["vps"] += 1
    save_data(data)

    return f"APX-{data['counter']['vps']}"


def random_ticket_id():
    data["counter"]["ticket"] += 1
    save_data(data)

    return f"T-{data['counter']['ticket']:04d}"


def random_application_id():
    data["counter"]["application"] += 1
    save_data(data)

    return f"APP-{data['counter']['application']:04d}"


def make_embed(
    title,
    description="",
    color=discord.Color.blurple()
):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now()
    )

    embed.set_footer(
        text=BRAND
    )

    return embed


async def send_log(guild, title, description):
    channel_id = data["config"].get("logs_channel")

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)

    if not channel:
        return

    try:
        await channel.send(
            embed=make_embed(
                title,
                description,
                discord.Color.dark_grey()
            )
        )
    except Exception:
        pass


async def safe_dm(user, embed):
    try:
        await user.send(embed=embed)
        return True
    except Exception:
        return False


async def require_staff(interaction):
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this.",
            ephemeral=True
        )
        return False

    return True


async def require_admin(interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Admin permission required.",
            ephemeral=True
        )
        return False

    return True


async def require_owner(interaction):
    if not owner_only(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return False

    return True


# ============================================================
# DURATION
# ============================================================

DURATION_PATTERN = re.compile(
    r"^(?P<number>\d+)(?P<unit>[smhdw])$",
    re.IGNORECASE
)


def parse_duration(value):
    match = DURATION_PATTERN.match(
        value.strip().lower()
    )

    if not match:
        return None

    number = int(match.group("number"))
    unit = match.group("unit")

    if unit == "s":
        return timedelta(seconds=number)

    if unit == "m":
        return timedelta(minutes=number)

    if unit == "h":
        return timedelta(hours=number)

    if unit == "d":
        return timedelta(days=number)

    if unit == "w":
        return timedelta(weeks=number)

    return None


# ============================================================
# ADMIN
# ============================================================

admin_group = app_commands.Group(
    name="admin",
    description="APEX CLOULD admin management"
)


@admin_group.command(
    name="add",
    description="Add an admin"
)
@app_commands.describe(user="User to make admin")
async def admin_add(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The owner cannot be changed.",
            ephemeral=True
        )
        return

    if user.id in data["admins"]:
        await interaction.response.send_message(
            "⚠️ That user is already an admin.",
            ephemeral=True
        )
        return

    data["admins"].append(user.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} is now an admin."
    )

    await send_log(
        interaction.guild,
        "Admin Added",
        f"{user.mention} was added by {interaction.user.mention}."
    )


@admin_group.command(
    name="remove",
    description="Remove an admin"
)
@app_commands.describe(user="Admin to remove")
async def admin_remove(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The owner cannot be removed.",
            ephemeral=True
        )
        return

    if user.id not in data["admins"]:
        await interaction.response.send_message(
            "⚠️ That user is not an admin.",
            ephemeral=True
        )
        return

    data["admins"].remove(user.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} is no longer an admin."
    )


bot.tree.add_command(admin_group)


# ============================================================
# VPS MANAGERS
# ============================================================

vps_manager_group = app_commands.Group(
    name="vpsmanager",
    description="APEX CLOULD VPS manager management"
)


@vps_manager_group.command(
    name="add",
    description="Add a VPS manager"
)
@app_commands.describe(user="User to add")
async def vpsmanager_add(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id in data["vps_managers"]:
        await interaction.response.send_message(
            "⚠️ Already a VPS manager.",
            ephemeral=True
        )
        return

    data["vps_managers"].append(user.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} is now a VPS manager."
    )


@vps_manager_group.command(
    name="remove",
    description="Remove a VPS manager"
)
@app_commands.describe(user="User to remove")
async def vpsmanager_remove(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id not in data["vps_managers"]:
        await interaction.response.send_message(
            "⚠️ That user is not a VPS manager.",
            ephemeral=True
        )
        return

    data["vps_managers"].remove(user.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} was removed from VPS managers."
    )


bot.tree.add_command(vps_manager_group)


# ============================================================
# CONFIG
# ============================================================

config_group = app_commands.Group(
    name="config",
    description="APEX CLOULD configuration"
)

config_role_group = app_commands.Group(
    name="role",
    description="Configure member roles",
    parent=config_group
)


@config_group.command(
    name="logs",
    description="Set the logging channel"
)
@app_commands.describe(channel="Logging channel")
async def config_logs(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not await require_admin(interaction):
        return

    data["config"]["logs_channel"] = channel.id
    save_data(data)

    await interaction.response.send_message(
        f"✅ Logs channel set to {channel.mention}."
    )


@config_group.command(
    name="welcome",
    description="Set welcome channel"
)
@app_commands.describe(channel="Welcome channel")
async def config_welcome(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not await require_admin(interaction):
        return

    data["config"]["welcome_channel"] = channel.id
    save_data(data)

    await interaction.response.send_message(
        f"✅ Welcome channel set to {channel.mention}."
    )


@config_group.command(
    name="leave",
    description="Set leave channel"
)
@app_commands.describe(channel="Leave channel")
async def config_leave(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not await require_admin(interaction):
        return

    data["config"]["leave_channel"] = channel.id
    save_data(data)

    await interaction.response.send_message(
        f"✅ Leave channel set to {channel.mention}."
    )


@config_role_group.command(
    name="add",
    description="Add an automatic member role"
)
@app_commands.describe(role="Role to give new members")
async def config_role_add(
    interaction: discord.Interaction,
    role: discord.Role
):
    if not await require_admin(interaction):
        return

    if role.id in data["member_roles"]:
        await interaction.response.send_message(
            "⚠️ That role is already configured.",
            ephemeral=True
        )
        return

    data["member_roles"].append(role.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {role.mention} will now be given to new members."
    )


@config_role_group.command(
    name="remove",
    description="Remove an automatic member role"
)
@app_commands.describe(role="Role to remove")
async def config_role_remove(
    interaction: discord.Interaction,
    role: discord.Role
):
    if not await require_admin(interaction):
        return

    if role.id not in data["member_roles"]:
        await interaction.response.send_message(
            "⚠️ That role is not configured.",
            ephemeral=True
        )
        return

    data["member_roles"].remove(role.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ {role.mention} removed from automatic roles."
    )


@config_role_group.command(
    name="list",
    description="List automatic member roles"
)
async def config_role_list(
    interaction: discord.Interaction
):
    if not await require_admin(interaction):
        return

    roles = []

    for role_id in data["member_roles"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    description = (
        "\n".join(roles)
        if roles
        else "No automatic roles configured."
    )

    await interaction.response.send_message(
        embed=make_embed(
            "Automatic Roles",
            description
        ),
        ephemeral=True
    )


bot.tree.add_command(config_group)


# ============================================================
# MODERATION
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.describe(
    user="Member to kick",
    reason="Reason"
)
async def kick(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):
    if not await require_staff(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The owner cannot be kicked.",
            ephemeral=True
        )
        return

    dm = make_embed(
        "You have been kicked",
        f"**Server:** {interaction.guild.name}\n"
        f"**Reason:** {reason}",
        discord.Color.orange()
    )

    await safe_dm(user, dm)

    try:
        await user.kick(reason=reason)

        await interaction.response.send_message(
            f"👢 {user.mention} has been kicked."
        )

        await send_log(
            interaction.guild,
            "Member Kicked",
            f"{user.mention}\n"
            f"Moderator: {interaction.user.mention}\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot kick that member.",
            ephemeral=True
        )


@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    user="Member to ban",
    reason="Reason"
)
async def ban(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):
    if not await require_staff(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The owner cannot be banned.",
            ephemeral=True
        )
        return

    await safe_dm(
        user,
        make_embed(
            "You have been banned",
            f"**Server:** {interaction.guild.name}\n"
            f"**Reason:** {reason}",
            discord.Color.red()
        )
    )

    try:
        await user.ban(
            reason=reason,
            delete_message_days=0
        )

        await interaction.response.send_message(
            f"🔨 {user.mention} has been banned."
        )

        await send_log(
            interaction.guild,
            "Member Banned",
            f"{user.mention}\n"
            f"Moderator: {interaction.user.mention}\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot ban that member.",
            ephemeral=True
        )


@bot.tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.describe(
    user="Member",
    duration="Examples: 10m, 2h, 1d",
    reason="Reason"
)
async def timeout(
    interaction: discord.Interaction,
    user: discord.Member,
    duration: str,
    reason: str = "No reason provided"
):
    if not await require_staff(interaction):
        return

    delta = parse_duration(duration)

    if not delta:
        await interaction.response.send_message(
            "❌ Invalid duration. Example: `10m`, `2h`, `1d`.",
            ephemeral=True
        )
        return

    if delta > timedelta(days=MAX_TIMEOUT_DAYS):
        await interaction.response.send_message(
            "❌ Discord timeout cannot exceed 28 days.",
            ephemeral=True
        )
        return

    try:
        await user.timeout(
            delta,
            reason=reason
        )

        await interaction.response.send_message(
            f"⏳ {user.mention} timed out for `{duration}`."
        )

        await safe_dm(
            user,
            make_embed(
                "You have been timed out",
                f"**Duration:** {duration}\n"
                f"**Reason:** {reason}",
                discord.Color.orange()
            )
        )

        await send_log(
            interaction.guild,
            "Member Timed Out",
            f"{user.mention}\n"
            f"Duration: {duration}\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot timeout that member.",
            ephemeral=True
        )


@bot.tree.command(
    name="un",
    description="Remove a timeout"
)
@app_commands.describe(user="Member")
async def untimeout(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_staff(interaction):
        return

    try:
        await user.timeout(None)

        await interaction.response.send_message(
            f"✅ Timeout removed from {user.mention}."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot remove that timeout.",
            ephemeral=True
        )


# ============================================================
# WARNINGS
# ============================================================

@bot.tree.command(
    name="warn",
    description="Warn a member"
)
@app_commands.describe(
    user="Member",
    reason="Reason"
)
async def warn(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):
    if not await require_staff(interaction):
        return

    uid = str(user.id)

    if uid not in data["warnings"]:
        data["warnings"][uid] = []

    warning = {
        "reason": reason,
        "moderator": interaction.user.id,
        "time": timestamp()
    }

    data["warnings"][uid].append(warning)

    count = len(data["warnings"][uid])

    if count >= 3:
        try:
            await user.timeout(
                timedelta(days=1),
                reason="Reached 3 warnings"
            )

            await safe_dm(
                user,
                make_embed(
                    "Automatic Timeout",
                    "You reached **3 warnings** and have been "
                    "timed out for **1 day**.",
                    discord.Color.red()
                )
            )

        except discord.Forbidden:
            pass

    save_data(data)

    await interaction.response.send_message(
        f"⚠️ {user.mention} warned.\n"
        f"Warnings: **{count}**"
    )

    await safe_dm(
        user,
        make_embed(
            "You have been warned",
            f"**Reason:** {reason}\n"
            f"**Warnings:** {count}",
            discord.Color.orange()
        )
    )

    await send_log(
        interaction.guild,
        "Warning",
        f"{user.mention} received a warning.\n"
        f"Reason: {reason}\n"
        f"Total: {count}"
    )


@bot.tree.command(
    name="warnings",
    description="View member warnings"
)
@app_commands.describe(user="Member")
async def warnings(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_staff(interaction):
        return

    warning_list = data["warnings"].get(
        str(user.id),
        []
    )

    if not warning_list:
        description = "No warnings."
    else:
        lines = []

        for index, warning in enumerate(
            warning_list,
            start=1
        ):
            lines.append(
                f"**{index}.** {warning['reason']}"
            )

        description = "\n".join(lines)

    await interaction.response.send_message(
        embed=make_embed(
            f"Warnings — {user}",
            description,
            discord.Color.orange()
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="clearwarnings",
    description="Clear member warnings"
)
@app_commands.describe(user="Member")
async def clearwarnings(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_staff(interaction):
        return

    data["warnings"].pop(
        str(user.id),
        None
    )

    save_data(data)

    await interaction.response.send_message(
        f"✅ Warnings cleared for {user.mention}."
    )


# ============================================================
# CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Delete messages"
)
@app_commands.describe(
    amount="Number of messages, 1-100"
)
async def clear(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):
    if not await require_staff(interaction):
        return

    if not isinstance(
        interaction.channel,
        discord.TextChannel
    ):
        await interaction.response.send_message(
            "❌ This command can only be used in text channels.",
            ephemeral=True
        )
        return

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=amount
    )

    await interaction.followup.send(
        f"🧹 Deleted **{len(deleted)}** messages.",
        ephemeral=True
    )


# ============================================================
# MSG
# ============================================================

@bot.tree.command(
    name="msg",
    description="Send an embed message"
)
@app_commands.describe(
    channel="Channel",
    text="Message text",
    title="Optional title"
)
async def msg(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    text: str,
    title: str = ""
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ Owner or VPS Manager permission required.",
            ephemeral=True
        )
        return

    embed = make_embed(
        title if title else BRAND,
        text
    )

    await channel.send(embed=embed)

    await interaction.response.send_message(
        f"✅ Message sent to {channel.mention}.",
        ephemeral=True
    )


# ============================================================
# SERVER INFO
# ============================================================

@bot.tree.command(
    name="serverinfo",
    description="Show server information"
)
async def serverinfo(
    interaction: discord.Interaction
):
    guild = interaction.guild

    owner = guild.owner.mention if guild.owner else "Unknown"

    embed = make_embed(
        f"{guild.name}",
        f"Information about **{guild.name}**"
    )

    embed.add_field(
        name="Owner",
        value=owner,
        inline=True
    )

    embed.add_field(
        name="Members",
        value=str(guild.member_count),
        inline=True
    )

    embed.add_field(
        name="Boosts",
        value=str(guild.premium_subscription_count),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# TICKET SYSTEM
# ============================================================

class TicketCategoryView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(
        self,
        interaction,
        ticket_type
    ):
        guild = interaction.guild
        user = interaction.user

        for ticket in data["tickets"].values():
            if (
                ticket.get("user_id") == user.id
                and ticket.get("open") is True
            ):
                channel = guild.get_channel(
                    ticket.get("channel_id")
                )

                if channel:
                    await interaction.response.send_message(
                        f"❌ You already have a ticket: {channel.mention}",
                        ephemeral=True
                    )
                    return

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME
        )

        if not category:
            category = await guild.create_category(
                TICKET_CATEGORY_NAME
            )

        ticket_id = random_ticket_id()

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True
            )
        }

        for member_id in (
            data["admins"]
            + data["vps_managers"]
        ):
            member = guild.get_member(member_id)

            if member:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await guild.create_text_channel(
            name=f"ticket-{ticket_id.lower()}",
            category=category,
            overwrites=overwrites
        )

        data["tickets"][ticket_id] = {
            "id": ticket_id,
            "channel_id": channel.id,
            "user_id": user.id,
            "type": ticket_type,
            "claimed_by": None,
            "open": True,
            "created_at": timestamp()
        }

        save_data(data)

        embed = make_embed(
            f"{ticket_type} Ticket",
            f"Welcome {user.mention}!\n\n"
            "Please explain what you need help with.\n"
            "A staff member will assist you shortly."
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=TicketControlView(ticket_id)
        )

        await interaction.response.send_message(
            f"🎫 Ticket created: {channel.mention}",
            ephemeral=True
        )

    @discord.ui.button(
        label="BUY",
        style=discord.ButtonStyle.green,
        custom_id="apex_ticket_buy"
    )
    async def buy(
        self,
        interaction,
        button
    ):
        await self.create_ticket(
            interaction,
            "BUY"
        )

    @discord.ui.button(
        label="REWARD CLAIM",
        style=discord.ButtonStyle.blurple,
        custom_id="apex_ticket_reward"
    )
    async def reward(
        self,
        interaction,
        button
    ):
        await self.create_ticket(
            interaction,
            "REWARD CLAIM"
        )

    @discord.ui.button(
        label="PARTNERSHIP",
        style=discord.ButtonStyle.gray,
        custom_id="apex_ticket_partnership"
    )
    async def partnership(
        self,
        interaction,
        button
    ):
        await self.create_ticket(
            interaction,
            "PARTNERSHIP"
        )

    @discord.ui.button(
        label="GENERAL SUPPORT",
        style=discord.ButtonStyle.blurple,
        custom_id="apex_ticket_support"
    )
    async def support(
        self,
        interaction,
        button
    ):
        await self.create_ticket(
            interaction,
            "GENERAL SUPPORT"
        )


class TicketControlView(discord.ui.View):

    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

        self.claim.custom_id = (
            f"apex_ticket_claim:{ticket_id}"
        )

        self.close.custom_id = (
            f"apex_ticket_close:{ticket_id}"
        )

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.green
    )
    async def claim(
        self,
        interaction,
        button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        ticket = data["tickets"].get(
            self.ticket_id
        )

        if not ticket:
            await interaction.response.send_message(
                "❌ Ticket not found.",
                ephemeral=True
            )
            return

        ticket["claimed_by"] = interaction.user.id
        save_data(data)

        await interaction.response.send_message(
            f"✅ Ticket claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.red
    )
    async def close(
        self,
        interaction,
        button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        ticket = data["tickets"].get(
            self.ticket_id
        )

        if not ticket:
            await interaction.response.send_message(
                "❌ Ticket not found.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(
            ticket["channel_id"]
        )

        ticket["open"] = False
        ticket["closed_by"] = interaction.user.id
        ticket["closed_at"] = timestamp()

        save_data(data)

        await interaction.response.send_message(
            "🔒 Closing ticket..."
        )

        await asyncio.sleep(2)

        if channel:
            try:
                await channel.delete(
                    reason=f"Ticket closed by {interaction.user}"
                )
            except Exception:
                pass


ticket_group = app_commands.Group(
    name="ticket",
    description="APEX CLOULD ticket system"
)


@ticket_group.command(
    name="setup",
    description="Create the ticket panel"
)
async def ticket_setup(
    interaction: discord.Interaction
):
    if not await require_staff(interaction):
        return

    embed = make_embed(
        "🎫 APEX CLOULD Support",
        "Select the type of ticket you need below."
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketCategoryView()
    )

    await interaction.response.send_message(
        "✅ Ticket panel created.",
        ephemeral=True
    )


@ticket_group.command(
    name="close",
    description="Close the current ticket"
)
async def ticket_close(
    interaction: discord.Interaction
):
    ticket_id = None

    for key, ticket in data["tickets"].items():
        if (
            ticket.get("channel_id")
            == interaction.channel.id
            and ticket.get("open")
        ):
            ticket_id = key
            break

    if not ticket_id:
        await interaction.response.send_message(
            "❌ This is not an open ticket.",
            ephemeral=True
        )
        return

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ Staff only.",
            ephemeral=True
        )
        return

    ticket = data["tickets"][ticket_id]
    ticket["open"] = False
    ticket["closed_by"] = interaction.user.id
    ticket["closed_at"] = timestamp()

    save_data(data)

    await interaction.response.send_message(
        "🔒 Closing ticket..."
    )

    await asyncio.sleep(2)

    try:
        await interaction.channel.delete()
    except Exception:
        pass


@ticket_group.command(
    name="add",
    description="Add a member to the current ticket"
)
@app_commands.describe(user="Member")
async def ticket_add(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_staff(interaction):
        return

    try:
        await interaction.channel.set_permissions(
            user,
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

        await interaction.response.send_message(
            f"✅ Added {user.mention}."
        )
    except Exception:
        await interaction.response.send_message(
            "❌ Could not add that member.",
            ephemeral=True
        )


@ticket_group.command(
    name="remove",
    description="Remove a member from the current ticket"
)
@app_commands.describe(user="Member")
async def ticket_remove(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_staff(interaction):
        return

    try:
        await interaction.channel.set_permissions(
            user,
            overwrite=None
        )

        await interaction.response.send_message(
            f"✅ Removed {user.mention}."
        )
    except Exception:
        await interaction.response.send_message(
            "❌ Could not remove that member.",
            ephemeral=True
        )


bot.tree.add_command(ticket_group)


# ============================================================
# APPLICATION SYSTEM
# ============================================================

application_group = app_commands.Group(
    name="application",
    description="APEX CLOULD applications"
)


class ApplicationView(discord.ui.View):

    def __init__(self, application_id):
        super().__init__(timeout=None)

        self.application_id = application_id

        self.accept.custom_id = (
            f"apex_application_accept:{application_id}"
        )

        self.reject.custom_id = (
            f"apex_application_reject:{application_id}"
        )

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.green
    )
    async def accept(
        self,
        interaction,
        button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        application = data["applications"].get(
            self.application_id
        )

        if not application:
            await interaction.response.send_message(
                "❌ Application not found.",
                ephemeral=True
            )
            return

        application["status"] = "accepted"
        application["reviewed_by"] = interaction.user.id
        application["reviewed_at"] = timestamp()

        save_data(data)

        user = interaction.guild.get_member(
            application["user_id"]
        )

        if user:
            await safe_dm(
                user,
                make_embed(
                    "Application Accepted",
                    f"Your application `{self.application_id}` "
                    "has been accepted.",
                    discord.Color.green()
                )
            )

        await interaction.response.send_message(
            f"✅ `{self.application_id}` accepted."
        )

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red
    )
    async def reject(
        self,
        interaction,
        button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        application = data["applications"].get(
            self.application_id
        )

        if not application:
            await interaction.response.send_message(
                "❌ Application not found.",
                ephemeral=True
            )
            return

        application["status"] = "rejected"
        application["reviewed_by"] = interaction.user.id
        application["reviewed_at"] = timestamp()

        save_data(data)

        user = interaction.guild.get_member(
            application["user_id"]
        )

        if user:
            await safe_dm(
                user,
                make_embed(
                    "Application Update",
                    f"Your application `{self.application_id}` "
                    "was not accepted at this time.",
                    discord.Color.red()
                )
            )

        await interaction.response.send_message(
            f"❌ `{self.application_id}` rejected."
        )


@application_group.command(
    name="setup",
    description="Create the application panel"
)
async def application_setup(
    interaction: discord.Interaction
):
    if not await require_staff(interaction):
        return

    data["config"]["application_channel"] = (
        interaction.channel.id
    )

    save_data(data)

    embed = make_embed(
        "📋 APEX CLOULD Applications",
        "Use the button below to submit an application."
    )

    await interaction.channel.send(
        embed=embed,
        view=ApplicationStartView()
    )

    await interaction.response.send_message(
        "✅ Application panel created.",
        ephemeral=True
    )


@application_group.command(
    name="list",
    description="List applications"
)
async def application_list(
    interaction: discord.Interaction
):
    if not await require_staff(interaction):
        return

    applications = data["applications"]

    if not applications:
        await interaction.response.send_message(
            "📋 No applications.",
            ephemeral=True
        )
        return

    lines = []

    for app_id, application in applications.items():
        lines.append(
            f"`{app_id}` — "
            f"<@{application['user_id']}> — "
            f"**{application['status']}**"
        )

    await interaction.response.send_message(
        embed=make_embed(
            "Applications",
            "\n".join(lines)
        ),
        ephemeral=True
    )


@application_group.command(
    name="view",
    description="View an application"
)
@app_commands.describe(
    application_id="Application ID"
)
async def application_view(
    interaction: discord.Interaction,
    application_id: str
):
    if not await require_staff(interaction):
        return

    application = data["applications"].get(
        application_id
    )

    if not application:
        await interaction.response.send_message(
            "❌ Application not found.",
            ephemeral=True
        )
        return

    embed = make_embed(
        f"Application {application_id}",
        ""
    )

    embed.add_field(
        name="Applicant",
        value=f"<@{application['user_id']}>",
        inline=False
    )

    embed.add_field(
        name="Name",
        value=application.get(
            "name",
            "Not provided"
        ),
        inline=True
    )

    embed.add_field(
        name="Age",
        value=application.get(
            "age",
            "Not provided"
        ),
        inline=True
    )

    embed.add_field(
        name="Reason",
        value=application.get(
            "reason",
            "Not provided"
        ),
        inline=False
    )

    embed.add_field(
        name="Status",
        value=application.get(
            "status",
            "pending"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        view=ApplicationView(application_id),
        ephemeral=True
    )


bot.tree.add_command(application_group)


class ApplicationStartView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply",
        style=discord.ButtonStyle.green,
        custom_id="apex_application_start"
    )
    async def apply(
        self,
        interaction,
        button
    ):
        await interaction.response.send_modal(
            ApplicationModal()
        )


class ApplicationModal(discord.ui.Modal):
    title = "APEX CLOULD Application"

    name = discord.ui.TextInput(
        label="Name",
        placeholder="Your name",
        required=True,
        max_length=100
    )

    age = discord.ui.TextInput(
        label="Age",
        placeholder="Your age",
        required=True,
        max_length=3
    )

    reason = discord.ui.TextInput(
        label="Why do you want to join?",
        placeholder="Tell us why...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    experience = discord.ui.TextInput(
        label="Experience",
        placeholder="Tell us about your experience",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    async def on_submit(
        self,
        interaction
    ):
        application_id = random_application_id()

        data["applications"][application_id] = {
            "id": application_id,
            "user_id": interaction.user.id,
            "name": str(self.name),
            "age": str(self.age),
            "reason": str(self.reason),
            "experience": str(self.experience),
            "status": "pending",
            "created_at": timestamp(),
            "reviewed_by": None,
            "reviewed_at": None
        }

        save_data(data)

        await interaction.response.send_message(
            embed=make_embed(
                "✅ Application Submitted",
                f"Your application ID is "
                f"`{application_id}`.\n\n"
                "Staff will review it.",
                discord.Color.green()
            ),
            ephemeral=True
        )

        review_channel_id = (
            data["config"].get(
                "application_review_channel"
            )
        )

        channel = (
            interaction.guild.get_channel(
                review_channel_id
            )
            if review_channel_id
            else None
        )

        if not channel:
            channel = interaction.channel

        embed = make_embed(
            f"📋 New Application — {application_id}",
            ""
        )

        embed.add_field(
            name="Applicant",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Name",
            value=str(self.name),
            inline=True
        )

        embed.add_field(
            name="Age",
            value=str(self.age),
            inline=True
        )

        embed.add_field(
            name="Reason",
            value=str(self.reason),
            inline=False
        )

        embed.add_field(
            name="Experience",
            value=str(self.experience)
            or "Not provided",
            inline=False
        )

        await channel.send(
            embed=embed,
            view=ApplicationView(application_id)
        )


# ============================================================
# REGIMENT
# ============================================================

@bot.tree.command(
    name="regiment",
    description="Show the APEX CLOULD regiment information"
)
async def regiment(
    interaction: discord.Interaction
):
    content = load_regiment()

    if not content:
        content = "No regiment information configured."

    if len(content) > 4000:
        content = content[:3990] + "..."

    await interaction.response.send_message(
        embed=make_embed(
            "🛡️ APEX CLOULD Regiment",
            content
        )
    )


@bot.tree.command(
    name="regimentreload",
    description="Reload regiment.txt"
)
async def regimentreload(
    interaction: discord.Interaction
):
    if not await require_admin(interaction):
        return

    content = load_regiment()

    await interaction.response.send_message(
        embed=make_embed(
            "🛡️ Regiment Reloaded",
            f"Loaded `{len(content)}` characters."
        ),
        ephemeral=True
    )


# ============================================================
# ROLE SYSTEM
# ============================================================

role_group = app_commands.Group(
    name="role",
    description="Role management"
)


@role_group.command(
    name="add",
    description="Give a role"
)
@app_commands.describe(
    user="Member",
    role="Role"
)
async def role_add(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not await require_staff(interaction):
        return

    try:
        await user.add_roles(role)

        await interaction.response.send_message(
            f"✅ Added {role.mention} to {user.mention}."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Remove a role"
)
@app_commands.describe(
    user="Member",
    role="Role"
)
async def role_remove(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not await require_staff(interaction):
        return

    try:
        await user.remove_roles(role)

        await interaction.response.send_message(
            f"✅ Removed {role.mention} from {user.mention}."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


@role_group.command(
    name="info",
    description="Show role information"
)
@app_commands.describe(role="Role")
async def role_info(
    interaction: discord.Interaction,
    role: discord.Role
):
    embed = make_embed(
        f"Role — {role.name}",
        f"Members: **{len(role.members)}**"
    )

    embed.add_field(
        name="Position",
        value=str(role.position)
    )

    embed.add_field(
        name="Mentionable",
        value=str(role.mentionable)
    )

    await interaction.response.send_message(
        embed=embed
    )


bot.tree.add_command(role_group)


# ============================================================
# PROMOTION
# ============================================================

@bot.tree.command(
    name="promotion",
    description="Promote a member"
)
@app_commands.describe(
    user="Member",
    role="Promotion role"
)
async def promotion(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not await require_staff(interaction):
        return

    try:
        await user.add_roles(role)

        await safe_dm(
            user,
            make_embed(
                "🎉 Promotion",
                f"You have been promoted to "
                f"**{role.name}** in {BRAND}.",
                discord.Color.green()
            )
        )

        await interaction.response.send_message(
            f"🎉 {user.mention} promoted to {role.mention}."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot give that role.",
            ephemeral=True
        )


# ============================================================
# LOCKDOWN
# ============================================================

lockdown_group = app_commands.Group(
    name="lockdown",
    description="Server lockdown"
)


@lockdown_group.command(
    name="start",
    description="Lock the current channel"
)
async def lockdown_start(
    interaction: discord.Interaction
):
    if not await require_admin(interaction):
        return

    channel = interaction.channel

    overwrite = channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    try:
        await channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )

        data["lockdown"]["active"] = True
        data["lockdown"]["channel"] = channel.id
        save_data(data)

        await interaction.response.send_message(
            "🔒 Channel locked."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot lock this channel.",
            ephemeral=True
        )


@lockdown_group.command(
    name="unlock",
    description="Unlock the current channel"
)
async def lockdown_unlock(
    interaction: discord.Interaction
):
    if not await require_admin(interaction):
        return

    channel = interaction.channel

    try:
        await channel.set_permissions(
            interaction.guild.default_role,
            send_messages=None
        )

        data["lockdown"]["active"] = False
        data["lockdown"]["channel"] = None
        save_data(data)

        await interaction.response.send_message(
            "🔓 Channel unlocked."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot unlock this channel.",
            ephemeral=True
        )


bot.tree.add_command(lockdown_group)


# ============================================================
# AUTOMOD
# ============================================================

automod_group = app_commands.Group(
    name="automod",
    description="Automod settings"
)


@automod_group.command(
    name="links",
    description="Enable or disable link protection"
)
@app_commands.describe(enabled="Enable or disable")
async def automod_links(
    interaction: discord.Interaction,
    enabled: bool
):
    if not await require_admin(interaction):
        return

    data["automod"]["links_enabled"] = enabled
    save_data(data)

    await interaction.response.send_message(
        f"✅ Link protection: **{enabled}**"
    )


@automod_group.command(
    name="badwords",
    description="Enable or disable bad word protection"
)
@app_commands.describe(enabled="Enable or disable")
async def automod_badwords(
    interaction: discord.Interaction,
    enabled: bool
):
    if not await require_admin(interaction):
        return

    data["automod"]["badwords_enabled"] = enabled
    save_data(data)

    await interaction.response.send_message(
        f"✅ Bad-word protection: **{enabled}**"
    )


@automod_group.command(
    name="addword",
    description="Add a bad word"
)
@app_commands.describe(word="Word")
async def automod_addword(
    interaction: discord.Interaction,
    word: str
):
    if not await require_admin(interaction):
        return

    word = word.lower().strip()

    if word not in data["automod"]["badwords"]:
        data["automod"]["badwords"].append(word)

    save_data(data)

    await interaction.response.send_message(
        f"✅ Added `{word}`."
    )


@automod_group.command(
    name="removeword",
    description="Remove a bad word"
)
@app_commands.describe(word="Word")
async def automod_removeword(
    interaction: discord.Interaction,
    word: str
):
    if not await require_admin(interaction):
        return

    word = word.lower().strip()

    if word in data["automod"]["badwords"]:
        data["automod"]["badwords"].remove(word)

    save_data(data)

    await interaction.response.send_message(
        f"✅ Removed `{word}`."
    )


bot.tree.add_command(automod_group)


# ============================================================
# GIVEAWAYS
# ============================================================

class GiveawayView(discord.ui.View):

    def __init__(self, giveaway_id):
        super().__init__(timeout=None)

        self.giveaway_id = giveaway_id

        self.enter.custom_id = (
            f"apex_giveaway_enter:{giveaway_id}"
        )

    @discord.ui.button(
        label="🎉 Enter",
        style=discord.ButtonStyle.green
    )
    async def enter(
        self,
        interaction,
        button
    ):
        giveaway = data["giveaways"].get(
            self.giveaway_id
        )

        if not giveaway:
            await interaction.response.send_message(
                "❌ Giveaway not found.",
                ephemeral=True
            )
            return

        if giveaway.get("ended"):
            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if user_id in giveaway["entries"]:
            giveaway["entries"].remove(user_id)

            save_data(data)

            await interaction.response.send_message(
                "You have left the giveaway.",
                ephemeral=True
            )

        else:
            giveaway["entries"].append(user_id)

            save_data(data)

            await interaction.response.send_message(
                "🎉 You entered the giveaway!",
                ephemeral=True
            )


giveaway_group = app_commands.Group(
    name="giveaway",
    description="Giveaway management"
)


@giveaway_group.command(
    name="create",
    description="Create a giveaway"
)
@app_commands.describe(
    prize="Prize",
    duration="Duration, e.g. 1h or 2d",
    winners="Number of winners"
)
async def giveaway_create(
    interaction: discord.Interaction,
    prize: str,
    duration: str,
    winners: app_commands.Range[int, 1, 20]
):
    if not await require_staff(interaction):
        return

    delta = parse_duration(duration)

    if not delta:
        await interaction.response.send_message(
            "❌ Invalid duration.",
            ephemeral=True
        )
        return

    giveaway_id = (
        "GW-"
        + "".join(
            random.choices(
                string.ascii_uppercase
                + string.digits,
                k=6
            )
        )
    )

    end_time = now() + delta

    data["giveaways"][giveaway_id] = {
        "id": giveaway_id,
        "channel_id": interaction.channel.id,
        "message_id": None,
        "prize": prize,
        "winners": winners,
        "entries": [],
        "ends_at": end_time.isoformat(),
        "ended": False,
        "created_by": interaction.user.id
    }

    save_data(data)

    embed = make_embed(
        "🎉 GIVEAWAY",
        f"**Prize:** {prize}\n"
        f"**Winners:** {winners}\n"
        f"**Ends:** <t:{int(end_time.timestamp())}:R>\n\n"
        f"Giveaway ID: `{giveaway_id}`"
    )

    message = await interaction.channel.send(
        embed=embed,
        view=GiveawayView(giveaway_id)
    )

    data["giveaways"][giveaway_id]["message_id"] = (
        message.id
    )

    save_data(data)

    await interaction.response.send_message(
        f"✅ Giveaway `{giveaway_id}` created.",
        ephemeral=True
    )


@giveaway_group.command(
    name="end",
    description="End a giveaway"
)
@app_commands.describe(
    giveaway_id="Giveaway ID"
)
async def giveaway_end(
    interaction: discord.Interaction,
    giveaway_id: str
):
    if not await require_staff(interaction):
        return

    giveaway = data["giveaways"].get(
        giveaway_id
    )

    if not giveaway:
        await interaction.response.send_message(
            "❌ Giveaway not found.",
            ephemeral=True
        )
        return

    await finish_giveaway(
        interaction.guild,
        giveaway_id
    )

    await interaction.response.send_message(
        f"✅ Giveaway `{giveaway_id}` ended."
    )


@giveaway_group.command(
    name="reroll",
    description="Reroll a giveaway"
)
@app_commands.describe(
    giveaway_id="Giveaway ID"
)
async def giveaway_reroll(
    interaction: discord.Interaction,
    giveaway_id: str
):
    if not await require_staff(interaction):
        return

    giveaway = data["giveaways"].get(
        giveaway_id
    )

    if not giveaway:
        await interaction.response.send_message(
            "❌ Giveaway not found.",
            ephemeral=True
        )
        return

    entries = giveaway.get(
        "entries",
        []
    )

    if not entries:
        await interaction.response.send_message(
            "❌ No entries.",
            ephemeral=True
        )
        return

    winners = random.sample(
        entries,
        min(
            giveaway["winners"],
            len(entries)
        )
    )

    mentions = " ".join(
        f"<@{user_id}>"
        for user_id in winners
    )

    await interaction.response.send_message(
        f"🎉 New winner(s): {mentions}"
    )


bot.tree.add_command(giveaway_group)


async def finish_giveaway(
    guild,
    giveaway_id
):
    giveaway = data["giveaways"].get(
        giveaway_id
    )

    if not giveaway or giveaway.get("ended"):
        return

    giveaway["ended"] = True
    save_data(data)

    entries = giveaway.get(
        "entries",
        []
    )

    if not entries:
        return

    winners = random.sample(
        entries,
        min(
            giveaway["winners"],
            len(entries)
        )
    )

    channel = guild.get_channel(
        giveaway["channel_id"]
    )

    if not channel:
        return

    mentions = " ".join(
        f"<@{user_id}>"
        for user_id in winners
    )

    await channel.send(
        embed=make_embed(
            "🎉 Giveaway Ended",
            f"**Prize:** {giveaway['prize']}\n\n"
            f"Winner(s): {mentions}",
            discord.Color.green()
        )
    )


# ============================================================
# VPS / PROXMOX
# ============================================================

vps_group = app_commands.Group(
    name="vps",
    description="APEX CLOULD VPS management"
)

vps_manager_subgroup = app_commands.Group(
    name="manager",
    description="VPS manager management",
    parent=vps_group
)


@vps_manager_subgroup.command(
    name="add",
    description="Add VPS manager"
)
@app_commands.describe(user="User")
async def vps_manager_add_command(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id not in data["vps_managers"]:
        data["vps_managers"].append(user.id)

    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} is now a VPS Manager."
    )


@vps_manager_subgroup.command(
    name="remove",
    description="Remove VPS manager"
)
@app_commands.describe(user="User")
async def vps_manager_remove_command(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not await require_owner(interaction):
        return

    if user.id in data["vps_managers"]:
        data["vps_managers"].remove(user.id)

    save_data(data)

    await interaction.response.send_message(
        f"✅ {user.mention} is no longer a VPS Manager."
    )


def get_proxmox():
    if not ProxmoxAPI:
        return None

    if not all([
        PROXMOX_HOST,
        PROXMOX_USER,
        PROXMOX_TOKEN_NAME,
        PROXMOX_TOKEN_VALUE
    ]):
        return None

    try:
        return ProxmoxAPI(
            PROXMOX_HOST,
            port=PROXMOX_PORT,
            user=PROXMOX_USER,
            token_name=PROXMOX_TOKEN_NAME,
            token_value=PROXMOX_TOKEN_VALUE,
            verify_ssl=PROXMOX_VERIFY_SSL
        )
    except Exception:
        return None


def proxmox_node(proxmox):
    if PROXMOX_NODE:
        return PROXMOX_NODE

    nodes = proxmox.nodes.get()

    if not nodes:
        return None

    return nodes[0]["node"]


def next_vmid(proxmox):
    try:
        result = proxmox.cluster.nextid.get()
        return int(result)
    except Exception:
        return random.randint(
            200,
            9999
        )


@vps_group.command(
    name="create",
    description="Create a VPS"
)
@app_commands.describe(
    user="VPS owner",
    plan="Plan 1-4",
    type="vm or ct",
    expires="Expiry in days"
)
@app_commands.choices(
    plan=[
        app_commands.Choice(
            name="Plan 1 — 4GB / 2 Core / 50GB",
            value="1"
        ),
        app_commands.Choice(
            name="Plan 2 — 8GB / 4 Core / 80GB",
            value="2"
        ),
        app_commands.Choice(
            name="Plan 3 — 16GB / 6 Core / 120GB",
            value="3"
        ),
        app_commands.Choice(
            name="Plan 4 — 32GB / 8 Core / 200GB",
            value="4"
        )
    ],
    type=[
        app_commands.Choice(
            name="Virtual Machine",
            value="vm"
        ),
        app_commands.Choice(
            name="Container",
            value="ct"
        )
    ]
)
async def vps_create(
    interaction: discord.Interaction,
    user: discord.Member,
    plan: app_commands.Choice[str],
    type: app_commands.Choice[str],
    expires: int = 30
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ VPS Manager permission required.",
            ephemeral=True
        )
        return

    if expires < 1:
        await interaction.response.send_message(
            "❌ Expiry must be at least 1 day.",
            ephemeral=True
        )
        return

    selected_plan = PLANS[plan.value]

    proxmox = get_proxmox()

    if not proxmox:
        await interaction.response.send_message(
            "❌ Proxmox is not configured or unavailable.",
            ephemeral=True
        )
        return

    node = proxmox_node(proxmox)

    if not node:
        await interaction.response.send_message(
            "❌ No Proxmox node available.",
            ephemeral=True
        )
        return

    if type.value == "vm":
        template = PROXMOX_VM_TEMPLATE
    else:
        template = PROXMOX_CT_TEMPLATE

    if not template:
        await interaction.response.send_message(
            f"❌ Proxmox {type.value.upper()} template "
            "is not configured in `.env`.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    vmid = next_vmid(proxmox)
    vps_id = random_vps_id()
    password = random_password()

    try:
        if type.value == "vm":
            proxmox.nodes(node).qemu(
                template
            ).clone.create(
                newid=vmid,
                name=f"apex-{vps_id}",
                full=1,
                target=node
            )

            await asyncio.sleep(3)

            proxmox.nodes(node).qemu(vmid).config.set(
                memory=selected_plan["ram"],
                cores=selected_plan["cores"],
                onboot=1,
                net0=f"virtio,bridge={PROXMOX_BRIDGE}"
            )

        else:
            proxmox.nodes(node).lxc(
                template
            ).clone.create(
                newid=vmid,
                hostname=f"apex-{vps_id}",
                target=node,
                full=1
            )

            await asyncio.sleep(3)

            proxmox.nodes(node).lxc(vmid).config.set(
                memory=selected_plan["ram"],
                cores=selected_plan["cores"],
                onboot=1,
                net0=(
                    f"name=eth0,"
                    f"bridge={PROXMOX_BRIDGE},"
                    f"ip=dhcp"
                )
            )

        record = {
            "id": vps_id,
            "vmid": vmid,
            "user_id": user.id,
            "plan": plan.value,
            "type": type.value,
            "node": node,
            "password": password,
            "ip": None,
            "status": "active",
            "created_at": timestamp(),
            "expires_at": (
                now()
                + timedelta(days=expires)
            ).isoformat()
        }

        data["vps"][vps_id] = record
        save_data(data)

        await safe_dm(
            user,
            make_embed(
                "🖥️ APEX CLOULD VPS Created",
                f"**VPS ID:** `{vps_id}`\n"
                f"**Type:** `{type.value.upper()}`\n"
                f"**Plan:** `{selected_plan['name']}`\n"
                f"**RAM:** `{selected_plan['ram']} MB`\n"
                f"**CPU:** `{selected_plan['cores']} cores`\n"
                f"**Disk:** `{selected_plan['disk']} GB`\n"
                f"**Node:** `{node}`\n"
                f"**Password:** `{password}`\n"
                f"**Expires:** <t:{int((now() + timedelta(days=expires)).timestamp())}:F>\n\n"
                "IP will be available once assigned by the VPS system.",
                discord.Color.green()
            )
        )

        await interaction.followup.send(
            f"✅ VPS `{vps_id}` created for {user.mention}."
        )

        await send_log(
            interaction.guild,
            "VPS Created",
            f"VPS: `{vps_id}`\n"
            f"User: {user.mention}\n"
            f"Type: {type.value}\n"
            f"Plan: {plan.value}"
        )

    except Exception as error:
        await interaction.followup.send(
            f"❌ Proxmox creation failed:\n`{error}`"
        )


@vps_group.command(
    name="list",
    description="List VPS"
)
async def vps_list(
    interaction: discord.Interaction
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ VPS Manager permission required.",
            ephemeral=True
        )
        return

    if not data["vps"]:
        await interaction.response.send_message(
            "No VPS records.",
            ephemeral=True
        )
        return

    lines = []

    for vps_id, vps in data["vps"].items():
        lines.append(
            f"`{vps_id}` — "
            f"<@{vps['user_id']}> — "
            f"{vps['type'].upper()} — "
            f"**{vps['status']}**"
        )

    await interaction.response.send_message(
        embed=make_embed(
            "🖥️ VPS List",
            "\n".join(lines)
        ),
        ephemeral=True
    )


@vps_group.command(
    name="info",
    description="View VPS information"
)
@app_commands.describe(
    vps_id="VPS ID"
)
async def vps_info(
    interaction: discord.Interaction,
    vps_id: str
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ VPS Manager permission required.",
            ephemeral=True
        )
        return

    vps = data["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    plan = PLANS.get(
        vps["plan"],
        {}
    )

    embed = make_embed(
        f"🖥️ VPS — {vps_id}",
        ""
    )

    embed.add_field(
        name="Owner",
        value=f"<@{vps['user_id']}>"
    )

    embed.add_field(
        name="Type",
        value=vps["type"].upper()
    )

    embed.add_field(
        name="Plan",
        value=plan.get(
            "name",
            vps["plan"]
        )
    )

    embed.add_field(
        name="VMID",
        value=str(vps["vmid"])
    )

    embed.add_field(
        name="Node",
        value=vps["node"]
    )

    embed.add_field(
        name="IP",
        value=vps.get("ip") or "Pending"
    )

    embed.add_field(
        name="Status",
        value=vps["status"]
    )

    embed.add_field(
        name="Expires",
        value=f"<t:{int(parse_timestamp(vps['expires_at']).timestamp())}:F>"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@vps_group.command(
    name="suspend",
    description="Suspend a VPS"
)
@app_commands.describe(
    vps_id="VPS ID"
)
async def vps_suspend(
    interaction: discord.Interaction,
    vps_id: str
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ VPS Manager permission required.",
            ephemeral=True
        )
        return

    vps = data["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    proxmox = get_proxmox()

    if not proxmox:
        await interaction.response.send_message(
            "❌ Proxmox unavailable.",
            ephemeral=True
        )
        return

    try:
        if vps["type"] == "vm":
            proxmox.nodes(
                vps["node"]
            ).qemu(
                vps["vmid"]
            ).status.stop.post()
        else:
            proxmox.nodes(
                vps["node"]
            ).lxc(
                vps["vmid"]
            ).status.stop.post()

        vps["status"] = "suspended"
        save_data(data)

        await interaction.response.send_message(
            f"⏸️ `{vps_id}` suspended."
        )

    except Exception as error:
        await interaction.response.send_message(
            f"❌ Suspend failed: `{error}`",
            ephemeral=True
        )


@vps_group.command(
    name="unsuspend",
    description="Unsuspend a VPS"
)
@app_commands.describe(
    vps_id="VPS ID"
)
async def vps_unsuspend(
    interaction: discord.Interaction,
    vps_id: str
):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ VPS Manager permission required.",
            ephemeral=True
        )
        return

    vps = data["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    proxmox = get_proxmox()

    if not proxmox:
        await interaction.response.send_message(
            "❌ Proxmox unavailable.",
            ephemeral=True
        )
        return

    try:
        if vps["type"] == "vm":
            proxmox.nodes(
                vps["node"]
            ).qemu(
                vps["vmid"]
            ).status.start.post()
        else:
            proxmox.nodes(
                vps["node"]
            ).lxc(
                vps["vmid"]
            ).status.start.post()

        vps["status"] = "active"
        save_data(data)

        await interaction.response.send_message(
            f"▶️ `{vps_id}` started."
        )

    except Exception as error:
        await interaction.response.send_message(
            f"❌ Start failed: `{error}`",
            ephemeral=True
        )


@vps_group.command(
    name="delete",
    description="Delete a VPS"
)
@app_commands.describe(
    vps_id="VPS ID"
)
async def vps_delete(
    interaction: discord.Interaction,
    vps_id: str
):
    if not await require_owner(interaction):
        return

    vps = data["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    proxmox = get_proxmox()

    if not proxmox:
        await interaction.response.send_message(
            "❌ Proxmox unavailable.",
            ephemeral=True
        )
        return

    try:
        if vps["type"] == "vm":
            proxmox.nodes(
                vps["node"]
            ).qemu(
                vps["vmid"]
            ).delete()
        else:
            proxmox.nodes(
                vps["node"]
            ).lxc(
                vps["vmid"]
            ).delete()

        del data["vps"][vps_id]
        save_data(data)

        await interaction.response.send_message(
            f"🗑️ VPS `{vps_id}` deleted."
        )

    except Exception as error:
        await interaction.response.send_message(
            f"❌ Delete failed: `{error}`",
            ephemeral=True
        )


bot.tree.add_command(vps_group)


# ============================================================
# VPS EXPIRY
# ============================================================

@tasks.loop(minutes=5)
async def expiry_checker():
    changed = False

    for vps_id, vps in list(
        data["vps"].items()
    ):
        if vps.get("status") == "expired":
            continue

        expires_at = parse_timestamp(
            vps["expires_at"]
        )

        if now() >= expires_at:
            proxmox = get_proxmox()

            if proxmox:
                try:
                    if vps["type"] == "vm":
                        proxmox.nodes(
                            vps["node"]
                        ).qemu(
                            vps["vmid"]
                        ).status.stop.post()
                    else:
                        proxmox.nodes(
                            vps["node"]
                        ).lxc(
                            vps["vmid"]
                        ).status.stop.post()
                except Exception:
                    pass

            vps["status"] = "expired"
            changed = True

    if changed:
        save_data(data)


# ============================================================
# GIVEAWAY CHECKER
# ============================================================

@tasks.loop(seconds=30)
async def giveaway_checker():
    for giveaway_id, giveaway in list(
        data["giveaways"].items()
    ):
        if giveaway.get("ended"):
            continue

        ends_at = parse_timestamp(
            giveaway["ends_at"]
        )

        if now() >= ends_at:
            for guild in bot.guilds:
                if (
                    giveaway["channel_id"]
                    in [channel.id for channel in guild.text_channels]
                ):
                    await finish_giveaway(
                        guild,
                        giveaway_id
                    )
                    break


# ============================================================
# WELCOME
# ============================================================

@bot.event
async def on_member_join(member):
    for role_id in data["member_roles"]:
        role = member.guild.get_role(role_id)

        if role:
            try:
                await member.add_roles(role)
            except Exception:
                pass

    channel_id = data["config"].get(
        "welcome_channel"
    )

    if channel_id:
        channel = member.guild.get_channel(
            channel_id
        )

        if channel:
            embed = make_embed(
                "Welcome to APEX CLOULD™!",
                f"Welcome {member.mention}!\n\n"
                "We're glad to have you here.\n"
                f"Need help? Open a ticket or visit "
                f"{DISCORD_INVITE}.",
                discord.Color.green()
            )

            embed.set_thumbnail(
                url=member.display_avatar.url
            )

            await channel.send(
                embed=embed
            )

    await safe_dm(
        member,
        make_embed(
            "Welcome to APEX CLOULD™!",
            "Welcome to the server!\n\n"
            f"Join the community: {DISCORD_INVITE}",
            discord.Color.green()
        )
    )


# ============================================================
# LEAVE
# ============================================================

@bot.event
async def on_member_remove(member):
    channel_id = data["config"].get(
        "leave_channel"
    )

    if not channel_id:
        return

    channel = member.guild.get_channel(
        channel_id
    )

    if not channel:
        return

    await channel.send(
        embed=make_embed(
            "Member Left",
            f"**{member}** has left {BRAND}.",
            discord.Color.orange()
        )
    )


# ============================================================
# AUTOMOD MESSAGE
# ============================================================

URL_REGEX = re.compile(
    r"(https?://|www\.|discord\.gg/|discord\.com/invite/)",
    re.IGNORECASE
)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        await bot.process_commands(message)
        return

    member = message.author

    if not has_bypass_role(member) and not is_staff(member):

        deleted = False

        if (
            data["automod"]["links_enabled"]
            and URL_REGEX.search(message.content)
        ):
            try:
                await message.delete()
                deleted = True
            except Exception:
                pass

        if (
            data["automod"]["badwords_enabled"]
            and not deleted
        ):
            content = message.content.lower()

            for word in data["automod"]["badwords"]:
                if word.lower() in content:
                    try:
                        await message.delete()
                        deleted = True
                    except Exception:
                        pass
                    break

        if deleted:
            try:
                await member.timeout(
                    timedelta(minutes=10),
                    reason="APEX CLOULD AutoMod"
                )
            except Exception:
                pass

            await safe_dm(
                member,
                make_embed(
                    "⚠️ AutoMod Action",
                    "Your message was removed because "
                    "it violated the server's AutoMod rules.\n\n"
                    "You received a **10 minute timeout**.",
                    discord.Color.red()
                )
            )

            await send_log(
                message.guild,
                "AutoMod Action",
                f"Member: {member.mention}\n"
                f"Channel: {message.channel.mention}\n"
                "Action: Message removed + 10m timeout."
            )

            return

    await bot.process_commands(message)


# ============================================================
# HELP
# ============================================================

@bot.tree.command(
    name="help",
    description="Show APEX CLOULD commands"
)
async def help_command(
    interaction: discord.Interaction
):
    embed = make_embed(
        "⚡ APEX CLOULD Help",
        "Main command categories"
    )

    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`/kick`\n"
            "`/ban`\n"
            "`/warn`\n"
            "`/warnings`\n"
            "`/clearwarnings`\n"
            "`/timeout`\n"
            "`/un`\n"
            "`/clear`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎫 Tickets",
        value=(
            "`/ticket setup`\n"
            "`/ticket close`\n"
            "`/ticket add`\n"
            "`/ticket remove`"
        ),
        inline=True
    )

    embed.add_field(
        name="🖥️ VPS",
        value=(
            "`/vps create`\n"
            "`/vps list`\n"
            "`/vps info`\n"
            "`/vps suspend`\n"
            "`/vps unsuspend`\n"
            "`/vps delete`"
        ),
        inline=True
    )

    embed.add_field(
        name="📋 Applications",
        value=(
            "`/application setup`\n"
            "`/application list`\n"
            "`/application view`"
        ),
        inline=True
    )

    embed.add_field(
        name="🛡️ Regiment",
        value=(
            "`/regiment`\n"
            "`/regimentreload`"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️ Configuration",
        value=(
            "`/config logs`\n"
            "`/config welcome`\n"
            "`/config leave`\n"
            "`/config role add`\n"
            "`/config role remove`\n"
            "`/config role list`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎉 Other",
        value=(
            "`/giveaway create`\n"
            "`/giveaway end`\n"
            "`/giveaway reroll`\n"
            "`/serverinfo`\n"
            "`/msg`"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# PERSISTENT VIEWS
# ============================================================

def restore_persistent_views():

    bot.add_view(
        TicketCategoryView()
    )

    bot.add_view(
        ApplicationStartView()
    )

    for ticket_id, ticket in data["tickets"].items():
        if ticket.get("open"):
            bot.add_view(
                TicketControlView(ticket_id)
            )

    for giveaway_id, giveaway in data["giveaways"].items():
        if not giveaway.get("ended"):
            bot.add_view(
                GiveawayView(giveaway_id)
            )

    for application_id, application in data["applications"].items():
        if application.get("status") == "pending":
            bot.add_view(
                ApplicationView(application_id)
            )


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):
    if isinstance(
        error,
        app_commands.CommandOnCooldown
    ):
        message = (
            f"Try again in "
            f"{error.retry_after:.1f}s."
        )
    else:
        print(
            f"[COMMAND ERROR] {repr(error)}"
        )
        message = (
            "❌ Something went wrong while "
            "running this command."
        )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )
    except Exception:
        pass


# ============================================================
# START
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from .env"
    )


bot.run(TOKEN)
