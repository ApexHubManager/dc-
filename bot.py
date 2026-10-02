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
# APEX CLOULD DISCORD BOT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "1373911333455659038"))
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

PROXMOX_HOST = os.getenv("PROXMOX_HOST", "")
PROXMOX_PORT = int(os.getenv("PROXMOX_PORT", "8006"))
PROXMOX_TOKEN_ID = os.getenv("PROXMOX_TOKEN_ID", "")
PROXMOX_TOKEN_SECRET = os.getenv("PROXMOX_TOKEN_SECRET", "")
PROXMOX_STORAGE = os.getenv("PROXMOX_STORAGE", "local-lvm")
PROXMOX_BRIDGE = os.getenv("PROXMOX_BRIDGE", "vmbr0")
PROXMOX_VERIFY_SSL = os.getenv("PROXMOX_VERIFY_SSL", "false").lower() == "true"

DATA_FILE = "data.json"

BRAND = "APEX CLOULD"
DISCORD_INVITE = "https://discord.gg/6Vwvgf9Haw"

MAX_TIMEOUT_SECONDS = 28 * 24 * 60 * 60


# ============================================================
# DATA
# ============================================================

DEFAULT_DATA = {
    "admins": [],
    "vps_managers": [],
    "promotion_roles": [],
    "lockdown_roles": [],
    "ticket_access_roles": [],
    "config": {
        "logs_channel": None,
        "member_role": None,
        "welcome_channel": None,
        "leave_channel": None
    },
    "automod": {
        "link_bypass": [],
        "badwords": [],
        "badword_bypass": []
    },
    "warnings": {},
    "tickets": {},
    "ticket_counter": 0,
    "giveaways": {},
    "vps": {},
    "lockdown": {
        "active": False,
        "channels": []
    }
}


def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = json.loads(json.dumps(DEFAULT_DATA))

    merge_defaults(data, DEFAULT_DATA)
    return data


def merge_defaults(target, defaults):
    for key, value in defaults.items():
        if key not in target:
            target[key] = json.loads(json.dumps(value))
        elif isinstance(value, dict) and isinstance(target[key], dict):
            merge_defaults(target[key], value)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


DATA = load_data()


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ============================================================
# HELPERS
# ============================================================

def is_owner(user):
    return user.id == OWNER_ID


def is_admin(user):
    return is_owner(user) or user.id in DATA["admins"]


def is_vps_manager(user):
    return is_owner(user) or user.id in DATA["vps_managers"]


def has_staff_access(user):
    return is_admin(user) or is_vps_manager(user)


def role_is_promotion_allowed(role):
    return role.id in DATA["promotion_roles"]


def lockdown_role_allowed(member):
    if is_owner(member):
        return True

    allowed = set(DATA["lockdown_roles"])

    return any(role.id in allowed for role in member.roles)


def mention_user(user):
    return user.mention


def now():
    return datetime.now(timezone.utc)


def timestamp():
    return now().strftime("%Y-%m-%d %H:%M:%S UTC")


def make_vps_id():
    while True:
        value = "APEX-" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        if value not in DATA["vps"]:
            return value


def make_password(length=18):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))


def parse_duration(value):
    value = value.lower().strip()

    match = re.fullmatch(r"(\d+)\s*(s|m|h|d|w)", value)

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800
    }[unit]

    return amount * multiplier


def duration_text(seconds):
    if seconds % 604800 == 0:
        return f"{seconds // 604800}w"

    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"

    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"

    if seconds % 60 == 0:
        return f"{seconds // 60}m"

    return f"{seconds}s"


async def send_log(guild, title, description, color=discord.Color.blurple()):
    channel_id = DATA["config"].get("logs_channel")

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now()
    )

    try:
        await channel.send(embed=embed)
    except Exception:
        pass


async def dm_embed(user, title, description, color=discord.Color.blurple(), file=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now()
    )

    try:
        if file:
            await user.send(embed=embed, file=file)
        else:
            await user.send(embed=embed)
        return True
    except Exception:
        return False


async def require_admin(interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return False

    return True


async def require_vps_manager(interaction):
    if not is_vps_manager(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have VPS Manager permission.",
            ephemeral=True
        )
        return False

    return True


async def require_staff(interaction):
    if not has_staff_access(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return False

    return True


# ============================================================
# PROXMOX
# ============================================================

def proxmox_available():
    return bool(
        ProxmoxAPI
        and PROXMOX_HOST
        and PROXMOX_TOKEN_ID
        and PROXMOX_TOKEN_SECRET
    )


def get_proxmox():
    if not proxmox_available():
        raise RuntimeError("Proxmox is not configured.")

    return ProxmoxAPI(
        PROXMOX_HOST,
        port=PROXMOX_PORT,
        token_name=PROXMOX_TOKEN_ID,
        token_value=PROXMOX_TOKEN_SECRET,
        verify_ssl=PROXMOX_VERIFY_SSL
    )


def get_proxmox_node(proxmox):
    nodes = proxmox.nodes.get()

    if not nodes:
        raise RuntimeError("No Proxmox nodes were found.")

    online = [
        node for node in nodes
        if node.get("status") == "online"
    ]

    if online:
        return online[0]["node"]

    return nodes[0]["node"]


def get_next_vmid(proxmox):
    cluster = proxmox.cluster.nextid.get()

    if isinstance(cluster, dict):
        cluster = cluster.get("id") or cluster.get("vmid")

    return int(cluster)


async def proxmox_create_vps(vps):
    if not proxmox_available():
        return {
            "success": False,
            "error": "Proxmox is not configured."
        }

    try:
        proxmox = get_proxmox()

        node = get_proxmox_node(proxmox)
        vmid = get_next_vmid(proxmox)

        vps["proxmox_node"] = node
        vps["proxmox_vmid"] = vmid

        plan = vps["plan"]

        memory = plan["ram"]
        cores = plan["cores"]
        disk = plan["disk"]

        password = vps["password"]

        # Default QEMU configuration.
        # OS/template/storage can be adjusted later for your Proxmox setup.
        proxmox.nodes(node).qemu.create(
            vmid=vmid,
            name=vps["id"],
            memory=memory,
            cores=cores,
            sockets=1,
            net0=f"virtio,bridge={PROXMOX_BRIDGE}",
            scsihw="virtio-scsi-pci",
            scsi0=f"{PROXMOX_STORAGE}:{disk}",
            ostype="l26",
            agent=1,
            onboot=1
        )

        return {
            "success": True,
            "node": node,
            "vmid": vmid
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def proxmox_action(vps, action):
    if not proxmox_available():
        return {
            "success": False,
            "error": "Proxmox is not configured."
        }

    try:
        proxmox = get_proxmox()

        node = vps.get("proxmox_node")
        vmid = vps.get("proxmox_vmid")

        if not node or not vmid:
            return {
                "success": False,
                "error": "This VPS has no Proxmox VM information."
            }

        qemu = proxmox.nodes(node).qemu(vmid)

        if action == "start":
            qemu.status.start.post()

        elif action == "stop":
            qemu.status.stop.post()

        elif action == "shutdown":
            qemu.status.shutdown.post()

        elif action == "delete":
            qemu.delete()

        else:
            return {
                "success": False,
                "error": "Unknown Proxmox action."
            }

        return {"success": True}

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# VPS PLANS
# ============================================================

# Change these later to your exact APEX CLOULD plans.
VPS_PLANS = {
    "4gb": {
        "ram": 4096,
        "cores": 2,
        "disk": 50
    },
    "8gb": {
        "ram": 8192,
        "cores": 4,
        "disk": 80
    },
    "16gb": {
        "ram": 16384,
        "cores": 6,
        "disk": 120
    },
    "32gb": {
        "ram": 32768,
        "cores": 8,
        "disk": 200
    }
}


# ============================================================
# COMMAND GROUPS
# ============================================================

config_group = app_commands.Group(
    name="config",
    description="APEX CLOULD configuration commands"
)

automod_group = app_commands.Group(
    name="automod",
    description="AutoMod configuration"
)

ticket_group = app_commands.Group(
    name="ticket",
    description="Ticket system"
)

vps_group = app_commands.Group(
    name="vps",
    description="VPS management"
)

giveaway_group = app_commands.Group(
    name="giveaway",
    description="Giveaway management"
)

role_group = app_commands.Group(
    name="role",
    description="Role management"
)

lockdown_group = app_commands.Group(
    name="lockdown",
    description="Server lockdown"
)


# ============================================================
# OWNER COMMANDS
# ============================================================

@bot.tree.command(name="admin_add", description="Add an Admin")
@app_commands.describe(user="User to make Admin")
async def admin_add(interaction, user: discord.Member):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner already has all permissions.",
            ephemeral=True
        )
        return

    if user.id in DATA["admins"]:
        await interaction.response.send_message(
            "❌ This user is already an Admin.",
            ephemeral=True
        )
        return

    DATA["admins"].append(user.id)
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {user.mention} as an Admin.",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        "Admin Added",
        f"{user.mention} was added as an Admin by {interaction.user.mention}."
    )


@bot.tree.command(name="admin_remove", description="Remove an Admin")
@app_commands.describe(user="Admin to remove")
async def admin_remove(interaction, user: discord.Member):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner cannot be removed.",
            ephemeral=True
        )
        return

    if user.id not in DATA["admins"]:
        await interaction.response.send_message(
            "❌ This user is not an Admin.",
            ephemeral=True
        )
        return

    DATA["admins"].remove(user.id)
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {user.mention} from Admin.",
        ephemeral=True
    )


# ============================================================
# VPS MANAGER PERMISSION
# ============================================================

@bot.tree.command(name="vps_manager_add", description="Add a VPS Manager")
@app_commands.describe(user="User to make VPS Manager")
async def vps_manager_add(interaction, user: discord.Member):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner already has all permissions.",
            ephemeral=True
        )
        return

    if user.id in DATA["vps_managers"]:
        await interaction.response.send_message(
            "❌ This user is already a VPS Manager.",
            ephemeral=True
        )
        return

    DATA["vps_managers"].append(user.id)
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {user.mention} as a VPS Manager.",
        ephemeral=True
    )


@bot.tree.command(name="vps_manager_remove", description="Remove a VPS Manager")
@app_commands.describe(user="VPS Manager to remove")
async def vps_manager_remove(interaction, user: discord.Member):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if user.id in DATA["vps_managers"]:
        DATA["vps_managers"].remove(user.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {user.mention} from VPS Manager.",
        ephemeral=True
    )


# ============================================================
# LOG CONFIG
# ============================================================

@config_group.command(name="logs", description="Set the action log channel")
@app_commands.describe(channel="Log channel")
async def config_logs(interaction, channel: discord.TextChannel):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    DATA["config"]["logs_channel"] = channel.id
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully configured {channel.mention} as the logs channel.",
        ephemeral=True
    )


# ============================================================
# PROMOTION ROLE CONFIG
# ============================================================

promotion_group = app_commands.Group(
    name="promotionrole",
    description="Promotion role whitelist"
)


@promotion_group.command(name="add", description="Allow a role for promotions")
@app_commands.describe(role="Role to allow")
async def promotionrole_add(interaction, role: discord.Role):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if role.id not in DATA["promotion_roles"]:
        DATA["promotion_roles"].append(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to the promotion role list.",
        ephemeral=True
    )


@promotion_group.command(name="remove", description="Remove a promotion role")
@app_commands.describe(role="Role to remove")
async def promotionrole_remove(interaction, role: discord.Role):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if role.id in DATA["promotion_roles"]:
        DATA["promotion_roles"].remove(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from the promotion role list.",
        ephemeral=True
    )


@promotion_group.command(name="list", description="List promotion roles")
async def promotionrole_list(interaction):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    roles = []

    for role_id in DATA["promotion_roles"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    embed = discord.Embed(
        title="Promotion Role Whitelist",
        description="\n".join(roles) if roles else "No roles configured.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


config_group.add_command(promotion_group)


# ============================================================
# MEMBER / WELCOME / LEAVE
# ============================================================

@config_group.command(name="memberrole", description="Set the automatic Member role")
@app_commands.describe(role="Member role")
async def config_memberrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    DATA["config"]["member_role"] = role.id
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully configured {role.mention} as the Member role.",
        ephemeral=True
    )


@config_group.command(name="welcome", description="Set the welcome channel")
@app_commands.describe(channel="Welcome channel")
async def config_welcome(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return

    DATA["config"]["welcome_channel"] = channel.id
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully configured {channel.mention} as the welcome channel.",
        ephemeral=True
    )


@config_group.command(name="leave", description="Set the leave channel")
@app_commands.describe(channel="Leave channel")
async def config_leave(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return

    DATA["config"]["leave_channel"] = channel.id
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully configured {channel.mention} as the leave channel.",
        ephemeral=True
    )


# ============================================================
# AUTOMOD
# ============================================================

@automod_group.command(name="linkbypass_add", description="Add a link bypass role")
@app_commands.describe(role="Role allowed to send links")
async def linkbypass_add(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id not in DATA["automod"]["link_bypass"]:
        DATA["automod"]["link_bypass"].append(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to the link bypass list.",
        ephemeral=True
    )


@automod_group.command(name="linkbypass_remove", description="Remove a link bypass role")
@app_commands.describe(role="Role to remove")
async def linkbypass_remove(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id in DATA["automod"]["link_bypass"]:
        DATA["automod"]["link_bypass"].remove(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from the link bypass list.",
        ephemeral=True
    )


@automod_group.command(name="linkbypass_list", description="List link bypass roles")
async def linkbypass_list(interaction):
    if not await require_admin(interaction):
        return

    roles = []

    for role_id in DATA["automod"]["link_bypass"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    embed = discord.Embed(
        title="Link Bypass Roles",
        description="\n".join(roles) if roles else "No roles configured.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@automod_group.command(name="badword_add", description="Add a bad word")
@app_commands.describe(word="Word to block")
async def badword_add(interaction, word: str):
    if not await require_admin(interaction):
        return

    word = word.lower().strip()

    if word and word not in DATA["automod"]["badwords"]:
        DATA["automod"]["badwords"].append(word)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added `{word}` to the bad-word list.",
        ephemeral=True
    )


@automod_group.command(name="badword_remove", description="Remove a bad word")
@app_commands.describe(word="Word to remove")
async def badword_remove(interaction, word: str):
    if not await require_admin(interaction):
        return

    word = word.lower().strip()

    if word in DATA["automod"]["badwords"]:
        DATA["automod"]["badwords"].remove(word)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed `{word}` from the bad-word list.",
        ephemeral=True
    )


@automod_group.command(name="badword_list", description="List blocked words")
async def badword_list(interaction):
    if not await require_admin(interaction):
        return

    words = DATA["automod"]["badwords"]

    embed = discord.Embed(
        title="Bad-Word List",
        description="\n".join(f"• `{word}`" for word in words)
        if words else "No blocked words.",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@automod_group.command(name="badwordbypass_add", description="Add a bad-word bypass role")
@app_commands.describe(role="Role allowed to bypass bad words")
async def badwordbypass_add(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id not in DATA["automod"]["badword_bypass"]:
        DATA["automod"]["badword_bypass"].append(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to the bad-word bypass list.",
        ephemeral=True
    )


@automod_group.command(name="badwordbypass_remove", description="Remove a bad-word bypass role")
@app_commands.describe(role="Role to remove")
async def badwordbypass_remove(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id in DATA["automod"]["badword_bypass"]:
        DATA["automod"]["badword_bypass"].remove(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from the bad-word bypass list.",
        ephemeral=True
    )


@automod_group.command(name="badwordbypass_list", description="List bad-word bypass roles")
async def badwordbypass_list(interaction):
    if not await require_admin(interaction):
        return

    roles = []

    for role_id in DATA["automod"]["badword_bypass"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    embed = discord.Embed(
        title="Bad-Word Bypass Roles",
        description="\n".join(roles) if roles else "No roles configured.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(automod_group)


# ============================================================
# ROLE COMMANDS
# ============================================================

@role_group.command(name="add", description="Give a promotion-approved role")
@app_commands.describe(user="Member", role="Role")
async def role_add(interaction, user: discord.Member, role: discord.Role):
    if not await require_admin(interaction):
        return

    if not role_is_promotion_allowed(role):
        await interaction.response.send_message(
            "❌ This role is not on the Promotion Role Whitelist.",
            ephemeral=True
        )
        return

    try:
        await user.add_roles(role)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot give this role. Check my role hierarchy.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to {user.mention}.",
        ephemeral=True
    )


@role_group.command(name="remove", description="Remove a role")
@app_commands.describe(user="Member", role="Role")
async def role_remove(interaction, user: discord.Member, role: discord.Role):
    if not await require_admin(interaction):
        return

    try:
        await user.remove_roles(role)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot remove this role.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from {user.mention}.",
        ephemeral=True
    )


@role_group.command(name="info", description="Show role information")
@app_commands.describe(role="Role")
async def role_info(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    embed = discord.Embed(
        title=f"Role Information — {role.name}",
        color=role.color
    )

    embed.add_field(name="Role ID", value=str(role.id), inline=False)
    embed.add_field(name="Members", value=str(len(role.members)))
    embed.add_field(name="Position", value=str(role.position))
    embed.add_field(name="Mentionable", value=str(role.mentionable))

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


bot.tree.add_command(role_group)


# ============================================================
# PROMOTION
# ============================================================

@bot.tree.command(name="promotion", description="Give an approved promotion role")
@app_commands.describe(user="Member", role="Promotion role")
async def promotion(interaction, user: discord.Member, role: discord.Role):
    if not await require_admin(interaction):
        return

    if not role_is_promotion_allowed(role):
        await interaction.response.send_message(
            "❌ This role is not on the Promotion Role Whitelist.",
            ephemeral=True
        )
        return

    try:
        await user.add_roles(role)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot give this role. Check my role hierarchy.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully promoted {user.mention} with {role.mention}.",
        ephemeral=True
    )


# ============================================================
# MODERATION
# ============================================================

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(user="Member", reason="Reason")
async def kick(interaction, user: discord.Member, reason: str):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner cannot be kicked.",
            ephemeral=True
        )
        return

    try:
        await user.kick(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot kick this member.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully kicked {user.mention}.",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        "Member Kicked",
        f"{user} was kicked by {interaction.user.mention}.\nReason: {reason}",
        discord.Color.red()
    )


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(user="Member", reason="Reason")
async def ban(interaction, user: discord.Member, reason: str):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner cannot be banned.",
            ephemeral=True
        )
        return

    try:
        await user.ban(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot ban this member.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully banned {user.mention}.",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        "Member Banned",
        f"{user} was banned by {interaction.user.mention}.\nReason: {reason}",
        discord.Color.red()
    )


@bot.tree.command(name="warn", description="Warn a member")
@app_commands.describe(user="Member", reason="Reason")
async def warn(interaction, user: discord.Member, reason: str):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner cannot be warned.",
            ephemeral=True
        )
        return

    key = str(user.id)

    DATA["warnings"].setdefault(key, [])

    DATA["warnings"][key].append({
        "reason": reason,
        "moderator": interaction.user.id,
        "time": timestamp()
    })

    count = len(DATA["warnings"][key])

    save_data(DATA)

    await dm_embed(
        user,
        "⚠️ APEX CLOULD Warning",
        f"You received a warning in **{interaction.guild.name}**.\n\n"
        f"**Reason:** {reason}\n"
        f"**Warning:** {count}/3"
    )

    if count >= 3:
        try:
            await user.timeout(
                timedelta(hours=24),
                reason="Reached 3 warnings."
            )

            DATA["warnings"][key] = []
            save_data(DATA)

            extra = "\n\n🔒 3 warnings reached — 24-hour timeout applied."
        except discord.Forbidden:
            extra = "\n\n⚠️ 3 warnings reached, but I could not apply the timeout."
    else:
        extra = ""

    await interaction.response.send_message(
        f"✅ Successfully warned {user.mention}. Warning {count}/3.{extra}",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        "Warning",
        f"{user.mention} was warned by {interaction.user.mention}.\n"
        f"Reason: {reason}\nWarning: {count}/3",
        discord.Color.orange()
    )


@bot.tree.command(name="warnings", description="View a member's warnings")
@app_commands.describe(user="Member")
async def warnings(interaction, user: discord.Member):
    if not await require_admin(interaction):
        return

    records = DATA["warnings"].get(str(user.id), [])

    if not records:
        description = "No active warnings."
    else:
        description = "\n\n".join(
            f"**{i + 1}.** {item['reason']}\n"
            f"Moderator: <@{item['moderator']}>\n"
            f"Time: {item['time']}"
            for i, item in enumerate(records)
        )

    embed = discord.Embed(
        title=f"Warnings — {user}",
        description=description,
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(name="clearwarnings", description="Clear a member's warnings")
@app_commands.describe(user="Member")
async def clearwarnings(interaction, user: discord.Member):
    if not await require_admin(interaction):
        return

    DATA["warnings"][str(user.id)] = []
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully cleared warnings for {user.mention}.",
        ephemeral=True
    )


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(
    user="Member",
    duration="Example: 10m, 1h, 1d",
    reason="Reason"
)
async def timeout_command(interaction, user: discord.Member, duration: str, reason: str):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await interaction.response.send_message(
            "❌ The Owner cannot be timed out.",
            ephemeral=True
        )
        return

    seconds = parse_duration(duration)

    if seconds is None or seconds <= 0:
        await interaction.response.send_message(
            "❌ Invalid duration. Use `10m`, `1h`, `1d`, etc.",
            ephemeral=True
        )
        return

    if seconds > MAX_TIMEOUT_SECONDS:
        await interaction.response.send_message(
            "❌ Discord timeout maximum is 28 days.",
            ephemeral=True
        )
        return

    try:
        await user.timeout(
            timedelta(seconds=seconds),
            reason=reason
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot timeout this member.",
            ephemeral=True
        )
        return

    await dm_embed(
        user,
        "🔒 APEX CLOULD Timeout",
        f"You have been timed out in **{interaction.guild.name}**.\n\n"
        f"**Duration:** {duration}\n"
        f"**Reason:** {reason}"
    )

    await interaction.response.send_message(
        f"✅ Successfully timed out {user.mention} for `{duration}`.",
        ephemeral=True
    )


@bot.tree.command(name="untimeout", description="Remove a timeout")
@app_commands.describe(user="Member", reason="Reason")
async def untimeout(interaction, user: discord.Member, reason: str):
    if not await require_admin(interaction):
        return

    try:
        await user.timeout(None, reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot remove this timeout.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully removed the timeout from {user.mention}.",
        ephemeral=True
    )


@bot.tree.command(name="clear", description="Clear messages")
@app_commands.describe(amount="Number of messages to delete")
async def clear(interaction, amount: app_commands.Range[int, 1, 100]):
    if not await require_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(limit=amount)

        await interaction.followup.send(
            f"✅ Successfully deleted **{len(deleted)}** messages.",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I do not have permission to delete messages.",
            ephemeral=True
        )


# ============================================================
# MSG
# ============================================================

@bot.tree.command(name="msg", description="Send an embed message")
@app_commands.describe(
    channel="Channel",
    text="Message text",
    title="Optional embed title"
)
async def msg(
    interaction,
    channel: discord.TextChannel,
    text: str,
    title: str = None
):
    if not await require_staff(interaction):
        return

    embed = discord.Embed(
        title=title if title else BRAND,
        description=text,
        color=discord.Color.green()
    )

    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I cannot send messages in that channel.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Successfully sent the embed to {channel.mention}.",
        ephemeral=True
    )


# ============================================================
# SERVER INFO
# ============================================================

@bot.tree.command(name="serverinfo", description="Show server information")
async def serverinfo(interaction):
    guild = interaction.guild

    bots_count = sum(member.bot for member in guild.members)
    human_count = guild.member_count - bots_count

    embed = discord.Embed(
        title=f"{guild.name} — Server Information",
        color=discord.Color.blurple()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="Server Owner",
        value=f"<@{guild.owner_id}>",
        inline=True
    )

    embed.add_field(
        name="Members",
        value=str(human_count),
        inline=True
    )

    embed.add_field(
        name="Bots",
        value=str(bots_count),
        inline=True
    )

    embed.add_field(
        name="Total Boosts",
        value=str(guild.premium_subscription_count),
        inline=True
    )

    embed.add_field(
        name="Created",
        value=discord.utils.format_dt(guild.created_at, "F"),
        inline=True
    )

    embed.add_field(
        name="Verification",
        value=str(guild.verification_level).title(),
        inline=True
    )

    embed.add_field(
        name="Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
        name="Roles",
        value=str(len(guild.roles)),
        inline=True
    )

    embed.add_field(
        name="Emojis",
        value=str(len(guild.emojis)),
        inline=True
    )

    embed.add_field(
        name="Voice Channels",
        value=str(len(guild.voice_channels)),
        inline=True
    )

    await interaction.response.send_message(embed=embed)


# ============================================================
# HELP
# ============================================================

@bot.tree.command(name="help", description="Show commands available to you")
async def help_command(interaction):
    lines = []

    lines.append("### 👤 Everyone")
    lines.append("`/help`")
    lines.append("`/serverinfo`")

    if is_admin(interaction.user):
        lines.append("\n### 🛡️ Admin")
        lines.append("`/config`")
        lines.append("`/automod`")
        lines.append("`/promotion`")
        lines.append("`/role`")
        lines.append("`/kick` `/ban` `/warn`")
        lines.append("`/warnings` `/clearwarnings`")
        lines.append("`/timeout` `/untimeout`")
        lines.append("`/clear`")
        lines.append("`/ticket`")
        lines.append("`/giveaway`")

    if is_vps_manager(interaction.user):
        lines.append("\n### 🖥️ VPS Manager")
        lines.append("`/msg`")
        lines.append("`/vps`")

    if is_owner(interaction.user):
        lines.append("\n### 👑 Owner")
        lines.append("`/admin_add` `/admin_remove`")
        lines.append("`/vps_manager_add` `/vps_manager_remove`")
        lines.append("`/vps delete`")
        lines.append("`/lockdown`")

    embed = discord.Embed(
        title="☁️ APEX CLOULD — Help",
        description="\n".join(lines),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# VPS COMMANDS
# ============================================================

@vps_group.command(name="create", description="Create a VPS")
@app_commands.describe(
    user="VPS owner",
    plan="VPS plan",
    type="VM or CT",
    days="Number of days"
)
@app_commands.choices(
    plan=[
        app_commands.Choice(name="4GB", value="4gb"),
        app_commands.Choice(name="8GB", value="8gb"),
        app_commands.Choice(name="16GB", value="16gb"),
        app_commands.Choice(name="32GB", value="32gb")
    ],
    type=[
        app_commands.Choice(name="VM", value="VM"),
        app_commands.Choice(name="CT", value="CT")
    ]
)
async def vps_create(
    interaction,
    user: discord.Member,
    plan: app_commands.Choice[str],
    type: app_commands.Choice[str],
    days: app_commands.Range[int, 1, 3650]
):
    if not await require_vps_manager(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    plan_data = VPS_PLANS[plan.value]

    vps_id = make_vps_id()
    password = make_password()

    expiry = now() + timedelta(days=days)

    vps = {
        "id": vps_id,
        "owner_id": user.id,
        "plan_name": plan.value,
        "plan": plan_data,
        "type": type.value,
        "days": days,
        "created_at": timestamp(),
        "expires_at": expiry.isoformat(),
        "status": "creating",
        "password": password,
        "proxmox_node": None,
        "proxmox_vmid": None
    }

    DATA["vps"][vps_id] = vps
    save_data(DATA)

    result = await proxmox_create_vps(vps)

    if result["success"]:
        vps["status"] = "active"
        save_data(DATA)

        credential_text = (
            f"☁️ **APEX CLOULD — VPS Created**\n\n"
            f"🎫 **VPS ID:** `{vps_id}`\n"
            f"🖥️ **Type:** `{type.value}`\n"
            f"📦 **Plan:** `{plan.value.upper()}`\n"
            f"💾 **RAM:** `{plan_data['ram']} MB`\n"
            f"⚙️ **CPU:** `{plan_data['cores']} cores`\n"
            f"💽 **Disk:** `{plan_data['disk']} GB`\n"
            f"📅 **Expires:** <t:{int(expiry.timestamp())}:F>\n"
            f"🖥️ **Proxmox Node:** `{result['node']}`\n"
            f"🔢 **VMID:** `{result['vmid']}`\n\n"
            f"🔐 **Password:** `{password}`\n\n"
            f"⚠️ Keep these credentials private."
        )

        sent = await dm_embed(
            user,
            "☁️ APEX CLOULD — VPS Created",
            credential_text
        )

        if sent:
            dm_status = "Credentials were sent by DM."
        else:
            dm_status = "⚠️ The user's DMs are closed, so credentials were not sent."

        await interaction.followup.send(
            f"✅ Successfully created `{vps_id}` for {user.mention}.\n{dm_status}",
            ephemeral=True
        )

        await send_log(
            interaction.guild,
            "VPS Created",
            f"VPS `{vps_id}` was created for {user.mention} by "
            f"{interaction.user.mention}."
        )

    else:
        vps["status"] = "failed"
        vps["error"] = result["error"]
        save_data(DATA)

        await interaction.followup.send(
            f"❌ VPS creation failed.\n```{result['error'][:1500]}```",
            ephemeral=True
        )


@vps_group.command(name="suspend", description="Suspend a VPS")
@app_commands.describe(vps_id="VPS ID")
async def vps_suspend(interaction, vps_id: str):
    if not await require_vps_manager(interaction):
        return

    vps_id = vps_id.upper()
    vps = DATA["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    result = await proxmox_action(vps, "stop")

    if not result["success"] and proxmox_available():
        await interaction.response.send_message(
            f"❌ Could not suspend VPS.\n```{result['error'][:1000]}```",
            ephemeral=True
        )
        return

    vps["status"] = "suspended"
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully suspended `{vps_id}`.",
        ephemeral=True
    )


@vps_group.command(name="unsuspend", description="Unsuspend a VPS")
@app_commands.describe(
    vps_id="VPS ID",
    days="New number of days"
)
async def vps_unsuspend(
    interaction,
    vps_id: str,
    days: app_commands.Range[int, 1, 3650]
):
    if not await require_vps_manager(interaction):
        return

    vps_id = vps_id.upper()
    vps = DATA["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    result = await proxmox_action(vps, "start")

    if not result["success"] and proxmox_available():
        await interaction.response.send_message(
            f"❌ Could not start VPS.\n```{result['error'][:1000]}```",
            ephemeral=True
        )
        return

    expiry = now() + timedelta(days=days)

    vps["status"] = "active"
    vps["days"] = days
    vps["expires_at"] = expiry.isoformat()

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully unsuspended `{vps_id}`.\n"
        f"📅 New expiry: <t:{int(expiry.timestamp())}:F>",
        ephemeral=True
    )


@vps_group.command(name="info", description="View VPS information")
@app_commands.describe(vps_id="VPS ID")
async def vps_info(interaction, vps_id: str):
    if not await require_vps_manager(interaction):
        return

    vps_id = vps_id.upper()
    vps = DATA["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    expiry = datetime.fromisoformat(vps["expires_at"])

    embed = discord.Embed(
        title=f"☁️ APEX CLOULD — {vps_id}",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Owner",
        value=f"<@{vps['owner_id']}>",
        inline=True
    )

    embed.add_field(
        name="Status",
        value=vps["status"].upper(),
        inline=True
    )

    embed.add_field(
        name="Type",
        value=vps["type"],
        inline=True
    )

    embed.add_field(
        name="Plan",
        value=vps["plan_name"].upper(),
        inline=True
    )

    embed.add_field(
        name="RAM",
        value=f"{vps['plan']['ram']} MB",
        inline=True
    )

    embed.add_field(
        name="CPU",
        value=f"{vps['plan']['cores']} cores",
        inline=True
    )

    embed.add_field(
        name="Disk",
        value=f"{vps['plan']['disk']} GB",
        inline=True
    )

    embed.add_field(
        name="Expires",
        value=f"<t:{int(expiry.timestamp())}:F>",
        inline=True
    )

    embed.add_field(
        name="Proxmox Node",
        value=str(vps.get("proxmox_node") or "Not assigned"),
        inline=True
    )

    embed.add_field(
        name="VMID",
        value=str(vps.get("proxmox_vmid") or "Not assigned"),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@vps_group.command(name="list", description="List VPS servers")
async def vps_list(interaction):
    if not await require_vps_manager(interaction):
        return

    if not DATA["vps"]:
        await interaction.response.send_message(
            "No VPS records found.",
            ephemeral=True
        )
        return

    lines = []

    for vps_id, vps in DATA["vps"].items():
        lines.append(
            f"`{vps_id}` • <@{vps['owner_id']}> • "
            f"`{vps['status']}` • `{vps['plan_name'].upper()}`"
        )

    embed = discord.Embed(
        title="☁️ APEX CLOULD — VPS List",
        description="\n".join(lines),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@vps_group.command(name="delete", description="Permanently delete a VPS")
@app_commands.describe(vps_id="VPS ID")
async def vps_delete(interaction, vps_id: str):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    vps_id = vps_id.upper()
    vps = DATA["vps"].get(vps_id)

    if not vps:
        await interaction.response.send_message(
            "❌ VPS not found.",
            ephemeral=True
        )
        return

    result = await proxmox_action(vps, "delete")

    if not result["success"] and proxmox_available():
        await interaction.response.send_message(
            f"❌ Could not delete the Proxmox VPS.\n"
            f"```{result['error'][:1000]}```",
            ephemeral=True
        )
        return

    del DATA["vps"][vps_id]
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully permanently deleted `{vps_id}`.",
        ephemeral=True
    )


bot.tree.add_command(vps_group)


# ============================================================
# LOCKDOWN
# ============================================================

@lockdown_group.command(name="role_add", description="Allow a role during lockdown")
@app_commands.describe(role="Allowed role")
async def lockdown_role_add(interaction, role: discord.Role):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if role.id not in DATA["lockdown_roles"]:
        DATA["lockdown_roles"].append(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to the lockdown role list.",
        ephemeral=True
    )


@lockdown_group.command(name="role_remove", description="Remove a lockdown role")
@app_commands.describe(role="Role")
async def lockdown_role_remove(interaction, role: discord.Role):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if role.id in DATA["lockdown_roles"]:
        DATA["lockdown_roles"].remove(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from the lockdown role list.",
        ephemeral=True
    )


@lockdown_group.command(name="role_list", description="List lockdown roles")
async def lockdown_role_list(interaction):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    roles = []

    for role_id in DATA["lockdown_roles"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    embed = discord.Embed(
        title="Lockdown Roles",
        description="\n".join(roles) if roles else "No lockdown roles configured.",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@lockdown_group.command(name="start", description="Start server lockdown")
async def lockdown_start(interaction):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    if DATA["lockdown"]["active"]:
        await interaction.response.send_message(
            "❌ Lockdown is already active.",
            ephemeral=True
        )
        return

    changed = []

    for channel in interaction.guild.text_channels:
        try:
            await channel.set_permissions(
                interaction.guild.default_role,
                send_messages=False
            )

            for role_id in DATA["lockdown_roles"]:
                role = interaction.guild.get_role(role_id)

                if role:
                    await channel.set_permissions(
                        role,
                        send_messages=True
                    )

            changed.append(channel.id)

        except discord.Forbidden:
            continue

    DATA["lockdown"]["active"] = True
    DATA["lockdown"]["channels"] = changed
    save_data(DATA)

    await interaction.response.send_message(
        f"🔒 Lockdown started successfully. `{len(changed)}` channels locked.",
        ephemeral=True
    )


@lockdown_group.command(name="unlock", description="End server lockdown")
async def lockdown_unlock(interaction):
    if not is_owner(interaction.user):
        await interaction.response.send_message(
            "❌ Owner only.",
            ephemeral=True
        )
        return

    for channel_id in DATA["lockdown"]["channels"]:
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            continue

        try:
            await channel.set_permissions(
                interaction.guild.default_role,
                send_messages=None
            )

            for role_id in DATA["lockdown_roles"]:
                role = interaction.guild.get_role(role_id)

                if role:
                    await channel.set_permissions(
                        role,
                        send_messages=None
                    )

        except discord.Forbidden:
            continue

    DATA["lockdown"]["active"] = False
    DATA["lockdown"]["channels"] = []

    save_data(DATA)

    await interaction.response.send_message(
        "🔓 Lockdown successfully removed.",
        ephemeral=True
    )


bot.tree.add_command(lockdown_group)


# ============================================================
# TICKET SYSTEM
# ============================================================

TICKET_CATEGORIES = {
    "BUY": "🛒",
    "REWARD CLAIM": "🎁",
    "PARTNERSHIP": "🤝",
    "GENERAL SUPPORT": "🛠️"
}


class TicketCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction, category):
        guild = interaction.guild
        user = interaction.user

        for ticket_id, ticket in DATA["tickets"].items():
            if (
                ticket.get("creator_id") == user.id
                and not ticket.get("closed", False)
            ):
                await interaction.response.send_message(
                    "❌ You already have an open ticket.",
                    ephemeral=True
                )
                return

        DATA["ticket_counter"] += 1

        number = DATA["ticket_counter"]
        ticket_id = f"APEX-{number:04d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        for role_id in DATA["ticket_access_roles"]:
            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        category_channel = discord.utils.get(
            guild.categories,
            name="Tickets"
        )

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{number}",
                overwrites=overwrites,
                category=category_channel,
                topic=f"{ticket_id} | {category} | {user.id}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I cannot create the ticket channel.",
                ephemeral=True
            )
            return

        DATA["tickets"][ticket_id] = {
            "channel_id": channel.id,
            "creator_id": user.id,
            "category": category,
            "claimed_by": None,
            "closed": False,
            "created_at": timestamp()
        }

        save_data(DATA)

        embed = discord.Embed(
            title="🎫 APEX CLOULD",
            description=(
                f"**Support Ticket**\n\n"
                f"🎟️ **Ticket:** {ticket_id}\n"
                f"👤 **Created by:** {user.mention}\n"
                f"📂 **Category:** {category}\n"
                f"👤 **Claimed by:** Nobody\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Please explain your issue clearly and provide all "
                f"relevant information.\n\n"
                f"**Please include:**\n"
                f"> • A clear description of your issue\n"
                f"> • Screenshots when necessary\n"
                f"> • Error messages\n"
                f"> • Any relevant information\n\n"
                f"**Support Guidelines**\n"
                f"> Please be patient while waiting for staff.\n"
                f"> Do not repeatedly ping staff.\n"
                f"> Do not spam the ticket.\n"
                f"> Missing information may delay support.\n\n"
                f"**A staff member will assist you shortly.**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"☁️ **APEX CLOULD Support**"
            ),
            color=discord.Color.green()
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=TicketControlView(ticket_id)
        )

        await interaction.response.send_message(
            f"✅ Successfully created your ticket: {channel.mention}",
            ephemeral=True
        )

        await dm_embed(
            user,
            "☁️ APEX CLOULD — Ticket Opened",
            f"Your support ticket has been successfully opened.\n\n"
            f"🎟️ **Ticket:** {ticket_id}\n"
            f"📂 **Category:** {category}\n\n"
            f"Our support team will assist you shortly.\n\n"
            f"Please keep your ticket open while waiting for support."
        )

    @discord.ui.button(
        label="BUY",
        emoji="🛒",
        style=discord.ButtonStyle.success,
        custom_id="apex_ticket_buy"
    )
    async def buy(self, interaction, button):
        await self.create_ticket(interaction, "BUY")

    @discord.ui.button(
        label="REWARD CLAIM",
        emoji="🎁",
        style=discord.ButtonStyle.success,
        custom_id="apex_ticket_reward"
    )
    async def reward(self, interaction, button):
        await self.create_ticket(interaction, "REWARD CLAIM")

    @discord.ui.button(
        label="PARTNERSHIP",
        emoji="🤝",
        style=discord.ButtonStyle.primary,
        custom_id="apex_ticket_partner"
    )
    async def partnership(self, interaction, button):
        await self.create_ticket(interaction, "PARTNERSHIP")

    @discord.ui.button(
        label="GENERAL SUPPORT",
        emoji="🛠️",
        style=discord.ButtonStyle.secondary,
        custom_id="apex_ticket_support"
    )
    async def support(self, interaction, button):
        await self.create_ticket(interaction, "GENERAL SUPPORT")


class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="Claim Ticket",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="apex_ticket_claim"
    )
    async def claim(self, interaction, button):
        if not has_staff_access(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have ticket staff access.",
                ephemeral=True
            )
            return

        ticket = DATA["tickets"].get(self.ticket_id)

        if not ticket:
            await interaction.response.send_message(
                "❌ Ticket not found.",
                ephemeral=True
            )
            return

        ticket["claimed_by"] = interaction.user.id
        save_data(DATA)

        await interaction.response.send_message(
            f"🙋 **Claimed by:** {interaction.user.mention}"
        )

        await send_log(
            interaction.guild,
            "Ticket Claimed",
            f"`{self.ticket_id}` was claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="apex_ticket_close"
    )
    async def close(self, interaction, button):
        ticket = DATA["tickets"].get(self.ticket_id)

        if not ticket:
            await interaction.response.send_message(
                "❌ Ticket not found.",
                ephemeral=True
            )
            return

        if not (
            is_owner(interaction.user)
            or is_admin(interaction.user)
            or is_vps_manager(interaction.user)
            or interaction.user.id == ticket["creator_id"]
        ):
            await interaction.response.send_message(
                "❌ You cannot close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🔒 **Close Ticket**\n\n"
            f"Are you sure you want to close this ticket?\n\n"
            f"Use `/ticket close` after confirming.",
            ephemeral=True
        )


# ============================================================
# TICKET COMMANDS
# ============================================================

@ticket_group.command(name="setup", description="Create the ticket panel")
async def ticket_setup(interaction):
    if not await require_admin(interaction):
        return

    embed = discord.Embed(
        title="📩 Support Tickets",
        description=(
            "🟢 **Need Help? Please Read Carefully**\n\n"
            "🟢 Click the button that best matches the type of support you need.\n"
            "🟢 Provide a clear and detailed description of your issue.\n"
            "🟢 For remote timeout issues, include when it happens, "
            "how often, and any screenshots.\n"
            "🟢 Missing or vague information may cause delays or timeouts.\n"
            "🟢 Include screenshots, error messages, or steps to reproduce.\n"
            "🟢 Repeated spam or unnecessary pinging of staff may lead to a timeout.\n"
            "🟢 Reward Claim: No alt accounts, no rejoin counts, no fake counts. "
            "Your reward will be counted from Falcon.\n\n"
            "🟢 Thank you for helping us help you! 💚"
        ),
        color=discord.Color.green()
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketCategoryView()
    )

    await interaction.response.send_message(
        "✅ Successfully created the ticket panel.",
        ephemeral=True
    )


@ticket_group.command(name="access_add", description="Add a ticket access role")
@app_commands.describe(role="Role")
async def ticket_access_add(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id not in DATA["ticket_access_roles"]:
        DATA["ticket_access_roles"].append(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully added {role.mention} to ticket access.",
        ephemeral=True
    )


@ticket_group.command(name="access_remove", description="Remove a ticket access role")
@app_commands.describe(role="Role")
async def ticket_access_remove(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return

    if role.id in DATA["ticket_access_roles"]:
        DATA["ticket_access_roles"].remove(role.id)

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully removed {role.mention} from ticket access.",
        ephemeral=True
    )


@ticket_group.command(name="access_list", description="List ticket access roles")
async def ticket_access_list(interaction):
    if not await require_admin(interaction):
        return

    roles = []

    for role_id in DATA["ticket_access_roles"]:
        role = interaction.guild.get_role(role_id)

        if role:
            roles.append(role.mention)

    embed = discord.Embed(
        title="Ticket Access Roles",
        description="\n".join(roles) if roles else "No roles configured.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@ticket_group.command(name="add", description="Add a member to a ticket")
@app_commands.describe(user="Member")
async def ticket_add(interaction, user: discord.Member):
    if not await require_staff(interaction):
        return

    ticket = next(
        (
            value for value in DATA["tickets"].values()
            if value["channel_id"] == interaction.channel.id
            and not value["closed"]
        ),
        None
    )

    if not ticket:
        await interaction.response.send_message(
            "❌ This is not an active ticket.",
            ephemeral=True
        )
        return

    await interaction.channel.set_permissions(
        user,
        view_channel=True,
        send_messages=True,
        read_message_history=True
    )

    await interaction.response.send_message(
        f"✅ Successfully added {user.mention} to the ticket."
    )


@ticket_group.command(name="remove", description="Remove a member from a ticket")
@app_commands.describe(user="Member")
async def ticket_remove(interaction, user: discord.Member):
    if not await require_staff(interaction):
        return

    await interaction.channel.set_permissions(
        user,
        overwrite=None
    )

    await interaction.response.send_message(
        f"✅ Successfully removed {user.mention} from the ticket."
    )


@ticket_group.command(name="close", description="Close the current ticket")
async def ticket_close(interaction):
    if not await require_staff(interaction):
        return

    ticket_id = None
    ticket = None

    for key, value in DATA["tickets"].items():
        if value["channel_id"] == interaction.channel.id:
            ticket_id = key
            ticket = value
            break

    if not ticket:
        await interaction.response.send_message(
            "❌ This is not a ticket channel.",
            ephemeral=True
        )
        return

    creator = interaction.guild.get_member(ticket["creator_id"])

    ticket["closed"] = True
    ticket["closed_by"] = interaction.user.id
    ticket["closed_at"] = timestamp()

    if creator:
        await interaction.channel.set_permissions(
            creator,
            view_channel=False,
            send_messages=False
        )

    await interaction.channel.edit(
        name=f"closed-{ticket_id.lower()}"
    )

    save_data(DATA)

    if creator:
        await dm_embed(
            creator,
            "☁️ APEX CLOULD — Ticket Closed",
            f"Your support ticket has been closed.\n\n"
            f"🎟️ **Ticket:** {ticket_id}\n"
            f"📂 **Category:** {ticket['category']}\n"
            f"👤 **Closed by:** {interaction.user.mention}\n\n"
            f"Thank you for contacting APEX CLOULD! 💚"
        )

    await interaction.response.send_message(
        f"🔒 Successfully closed `{ticket_id}`."
    )

    await send_log(
        interaction.guild,
        "Ticket Closed",
        f"`{ticket_id}` was closed by {interaction.user.mention}."
    )


bot.tree.add_command(ticket_group)


# ============================================================
# GIVEAWAYS
# ============================================================

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="Enter Giveaway",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="apex_giveaway_enter"
    )
    async def enter(self, interaction, button):
        giveaway = DATA["giveaways"].get(self.giveaway_id)

        if not giveaway:
            await interaction.response.send_message(
                "❌ Giveaway not found.",
                ephemeral=True
            )
            return

        if giveaway["ended"]:
            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if user_id in giveaway["entries"]:
            await interaction.response.send_message(
                "❌ You are already entered.",
                ephemeral=True
            )
            return

        giveaway["entries"].append(user_id)
        save_data(DATA)

        await interaction.response.send_message(
            "🎉 You have successfully entered the giveaway!",
            ephemeral=True
        )


async def finish_giveaway(giveaway_id):
    giveaway = DATA["giveaways"].get(giveaway_id)

    if not giveaway or giveaway["ended"]:
        return

    giveaway["ended"] = True

    guild = bot.get_guild(giveaway["guild_id"])

    if not guild:
        save_data(DATA)
        return

    channel = guild.get_channel(giveaway["channel_id"])

    eligible = []

    for user_id in giveaway["entries"]:
        member = guild.get_member(user_id)

        if member and not member.bot:
            eligible.append(member)

    winners_count = min(
        giveaway["winners"],
        len(eligible)
    )

    winners = random.sample(eligible, winners_count) if winners_count else []

    giveaway["winner_ids"] = [member.id for member in winners]

    save_data(DATA)

    if channel:
        if winners:
            mentions = ", ".join(member.mention for member in winners)

            embed = discord.Embed(
                title="🎉 Giveaway Ended!",
                description=(
                    f"**Prize:** {giveaway['prize']}\n\n"
                    f"🏆 **Winner(s):** {mentions}\n\n"
                    f"Congratulations! 🎉"
                ),
                color=discord.Color.gold()
            )

            await channel.send(embed=embed)

            for winner in winners:
                await dm_embed(
                    winner,
                    "🎉 You Won an APEX CLOULD Giveaway!",
                    f"Congratulations!\n\n"
                    f"🏆 **Prize:** {giveaway['prize']}\n\n"
                    f"You won the giveaway in **{guild.name}**!"
                )
        else:
            embed = discord.Embed(
                title="🎉 Giveaway Ended",
                description=(
                    f"**Prize:** {giveaway['prize']}\n\n"
                    f"❌ No eligible winners."
                ),
                color=discord.Color.red()
            )

            await channel.send(embed=embed)


@giveaway_group.command(name="create", description="Create a giveaway")
@app_commands.describe(
    prize="Giveaway prize",
    duration="Example: 1d, 12h, 30m",
    winners="Number of winners"
)
async def giveaway_create(
    interaction,
    prize: str,
    duration: str,
    winners: app_commands.Range[int, 1, 20] = 1
):
    if not await require_admin(interaction):
        return

    seconds = parse_duration(duration)

    if seconds is None or seconds < 10:
        await interaction.response.send_message(
            "❌ Invalid duration. Minimum is 10 seconds.",
            ephemeral=True
        )
        return

    if seconds > 30 * 86400:
        await interaction.response.send_message(
            "❌ Maximum giveaway duration is 30 days.",
            ephemeral=True
        )
        return

    giveaway_id = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=8)
    )

    end_time = now() + timedelta(seconds=seconds)

    DATA["giveaways"][giveaway_id] = {
        "guild_id": interaction.guild.id,
        "channel_id": interaction.channel.id,
        "prize": prize,
        "duration": duration,
        "winners": winners,
        "entries": [],
        "winner_ids": [],
        "created_at": now().isoformat(),
        "end_at": end_time.isoformat(),
        "ended": False
    }

    save_data(DATA)

    embed = discord.Embed(
        title="🎉 APEX CLOULD Giveaway",
        description=(
            f"🎁 **Prize:** {prize}\n\n"
            f"🏆 **Winners:** {winners}\n"
            f"⏰ **Ends:** <t:{int(end_time.timestamp())}:R>\n\n"
            f"Click **🎉 Enter Giveaway** to participate!"
        ),
        color=discord.Color.gold()
    )

    message = await interaction.channel.send(
        embed=embed,
        view=GiveawayView(giveaway_id)
    )

    DATA["giveaways"][giveaway_id]["message_id"] = message.id
    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Successfully created giveaway `{giveaway_id}`.",
        ephemeral=True
    )


@giveaway_group.command(name="end", description="End a giveaway")
@app_commands.describe(giveaway_id="Giveaway ID")
async def giveaway_end(interaction, giveaway_id: str):
    if not await require_admin(interaction):
        return

    giveaway_id = giveaway_id.upper()

    if giveaway_id not in DATA["giveaways"]:
        await interaction.response.send_message(
            "❌ Giveaway not found.",
            ephemeral=True
        )
        return

    await finish_giveaway(giveaway_id)

    await interaction.response.send_message(
        f"✅ Successfully ended giveaway `{giveaway_id}`.",
        ephemeral=True
    )


@giveaway_group.command(name="reroll", description="Reroll a giveaway")
@app_commands.describe(giveaway_id="Giveaway ID")
async def giveaway_reroll(interaction, giveaway_id: str):
    if not await require_admin(interaction):
        return

    giveaway_id = giveaway_id.upper()
    giveaway = DATA["giveaways"].get(giveaway_id)

    if not giveaway:
        await interaction.response.send_message(
            "❌ Giveaway not found.",
            ephemeral=True
        )
        return

    if not giveaway["ended"]:
        await interaction.response.send_message(
            "❌ This giveaway has not ended.",
            ephemeral=True
        )
        return

    guild = interaction.guild

    eligible = []

    for user_id in giveaway["entries"]:
        member = guild.get_member(user_id)

        if (
            member
            and not member.bot
            and member.id not in giveaway["winner_ids"]
        ):
            eligible.append(member)

    if not eligible:
        await interaction.response.send_message(
            "❌ No eligible members remain for a reroll.",
            ephemeral=True
        )
        return

    winner = random.choice(eligible)

    giveaway["winner_ids"].append(winner.id)
    save_data(DATA)

    embed = discord.Embed(
        title="🎉 Giveaway Reroll",
        description=(
            f"🎁 **Prize:** {giveaway['prize']}\n\n"
            f"🏆 **New Winner:** {winner.mention}"
        ),
        color=discord.Color.gold()
    )

    await interaction.channel.send(embed=embed)

    await dm_embed(
        winner,
        "🎉 APEX CLOULD Giveaway Reroll",
        f"You won the reroll!\n\n"
        f"🏆 **Prize:** {giveaway['prize']}"
    )

    await interaction.response.send_message(
        f"✅ Successfully rerolled `{giveaway_id}`.",
        ephemeral=True
    )


@giveaway_group.command(name="info", description="View giveaway information")
@app_commands.describe(giveaway_id="Giveaway ID")
async def giveaway_info(interaction, giveaway_id: str):
    if not await require_admin(interaction):
        return

    giveaway_id = giveaway_id.upper()
    giveaway = DATA["giveaways"].get(giveaway_id)

    if not giveaway:
        await interaction.response.send_message(
            "❌ Giveaway not found.",
            ephemeral=True
        )
        return

    end_time = datetime.fromisoformat(giveaway["end_at"])

    embed = discord.Embed(
        title=f"🎉 Giveaway — {giveaway_id}",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Prize",
        value=giveaway["prize"],
        inline=False
    )

    embed.add_field(
        name="Entries",
        value=str(len(giveaway["entries"]))
    )

    embed.add_field(
        name="Winners",
        value=str(giveaway["winners"])
    )

    embed.add_field(
        name="Status",
        value="Ended" if giveaway["ended"] else "Active"
    )

    embed.add_field(
        name="Ends",
        value=f"<t:{int(end_time.timestamp())}:R>"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


bot.tree.add_command(giveaway_group)


# ============================================================
# WELCOME / LEAVE
# ============================================================

WELCOME_THUMBNAIL = (
    "https://cdn.discordapp.com/attachments/"
    "1551160968682151956/1551241905202008114/"
    "1789897602018.png"
)


@bot.event
async def on_member_join(member):
    guild = member.guild

    channel_id = DATA["config"].get("welcome_channel")

    if channel_id:
        channel = guild.get_channel(channel_id)

        if channel:
            embed = discord.Embed(
                title="Welcome to APEX CLOULD™!",
                description=(
                    "🟢 Your journey to fast, powerful hosting starts here.\n\n"
                    "🚀 **What we offer:**\n"
                    "🟢 High-performance nodes\n"
                    "🟢 Advanced DDoS protection\n"
                    "🟢 Instant deployment\n"
                    "🟢 Budget & premium plans\n\n"
                    "🛠️ **Need assistance?**\n"
                    "Open a ticket and our team will respond fast ⚡\n\n"
                    "🤝 **Earn free hosting!**\n"
                    "Invite friends and unlock credits, upgrades & rewards.\n\n"
                    "📜 **Important:**\n"
                    "Make sure to read the server rules before using our services.\n\n"
                    "📡 *We're glad you're here — power up your servers with "
                    "APEX CLOULD!* 🚀"
                ),
                color=discord.Color.green()
            )

            embed.set_thumbnail(url=WELCOME_THUMBNAIL)

            await channel.send(
                content=member.mention,
                embed=embed
            )

    role_id = DATA["config"].get("member_role")

    if role_id:
        role = guild.get_role(role_id)

        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

    await dm_embed(
        member,
        "☁️ Welcome to APEX CLOULD™!",
        f"Hey {member.mention}! 👋\n\n"
        f"🚀 **Your hosting journey starts here.**\n\n"
        f"🟢 **What we offer:**\n"
        f"• 🖥️ VPS & server hosting\n"
        f"• ⚡ Fast deployment\n"
        f"• 🛡️ DDoS-protected infrastructure\n"
        f"• 💰 Free & affordable plans\n"
        f"• 🎁 Community rewards\n"
        f"• 🛠️ Support from our team\n\n"
        f"🛠️ **Need help?**\n"
        f"Open a ticket in the server and our team will help you.\n\n"
        f"🤝 **Want free hosting?**\n"
        f"Invite friends, participate in the community, and unlock rewards.\n\n"
        f"📜 **Before getting started:**\n"
        f"Please read the server rules and check the available hosting plans.\n\n"
        f"📡 **Welcome to the community!** 🚀"
    )


@bot.event
async def on_member_remove(member):
    guild = member.guild

    channel_id = DATA["config"].get("leave_channel")

    if channel_id:
        channel = guild.get_channel(channel_id)

        if channel:
            embed = discord.Embed(
                title="Goodbye from APEX CLOULD™!",
                description=(
                    "🟢 We're sorry to see you leave!\n\n"
                    "🚀 **Before you go:**\n"
                    "🟢 Thank you for being part of our community\n"
                    "🟢 Your support means a lot to us\n"
                    "🟢 You're always welcome back\n\n"
                    "🛠️ **Need us again?**\n"
                    "You can always rejoin APEX CLOULD™ and continue "
                    "your journey with us.\n\n"
                    "🤝 **Remember:**\n"
                    "Invite friends, earn rewards & power up your servers!\n\n"
                    "📡 We hope to see you again someday.\n\n"
                    "Thanks for being with us — see you next time! 🚀"
                ),
                color=discord.Color.green()
            )

            embed.set_thumbnail(url=WELCOME_THUMBNAIL)

            await channel.send(embed=embed)

    await dm_embed(
        member,
        "☁️ Goodbye from APEX CLOULD™!",
        f"Hey {member.mention}, we're sorry to see you leave. 👋\n\n"
        f"🟢 **Before you go:**\n"
        f"• Thank you for being part of the community\n"
        f"• Your support means a lot to us\n"
        f"• You're always welcome back\n\n"
        f"🛠️ **Need us again?**\n"
        f"You can always rejoin APEX CLOULD™ whenever you want.\n\n"
        f"🤝 **Remember:**\n"
        f"Invite friends, earn rewards & power up your servers!\n\n"
        f"📡 **Thanks for being with us — see you next time!** 🚀"
    )


# ============================================================
# AUTOMOD
# ============================================================

URL_PATTERN = re.compile(
    r"(https?://|www\.|discord\.gg/|discord\.com/invite/)",
    re.IGNORECASE
)


def member_has_role(member, role_ids):
    return any(role.id in role_ids for role in member.roles)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        await bot.process_commands(message)
        return

    member = message.author

    # Owner/Admin bypass
    if not is_owner(member):
        # Link AutoMod
        if URL_PATTERN.search(message.content):
            if not member_has_role(
                member,
                DATA["automod"]["link_bypass"]
            ):
                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    await member.timeout(
                        timedelta(minutes=10),
                        reason="AutoMod link protection"
                    )
                except Exception:
                    pass

                await dm_embed(
                    member,
                    "🛡️ APEX CLOULD AutoMod",
                    "Your message was removed because links are not allowed here.\n\n"
                    "You have received a **10 minute timeout**."
                )

                await send_log(
                    message.guild,
                    "AutoMod — Link",
                    f"{member.mention} sent a blocked link in "
                    f"{message.channel.mention}."
                )

                return

        # Bad word AutoMod
        content_lower = message.content.lower()

        bad_word = next(
            (
                word for word in DATA["automod"]["badwords"]
                if word in content_lower
            ),
            None
        )

        if bad_word:
            if not member_has_role(
                member,
                DATA["automod"]["badword_bypass"]
            ):
                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    await member.timeout(
                        timedelta(minutes=10),
                        reason="AutoMod bad-word protection"
                    )
                except Exception:
                    pass

                await dm_embed(
                    member,
                    "🛡️ APEX CLOULD AutoMod",
                    "Your message was removed because it contained a "
                    "blocked word.\n\n"
                    "You have received a **10 minute timeout**."
                )

                await send_log(
                    message.guild,
                    "AutoMod — Bad Word",
                    f"{member.mention} triggered bad-word protection."
                )

                return

    await bot.process_commands(message)


# ============================================================
# VPS EXPIRY
# ============================================================

@tasks.loop(seconds=30)
async def expiry_checker():
    changed = False

    for vps_id, vps in list(DATA["vps"].items()):
        if vps.get("status") != "active":
            continue

        try:
            expiry = datetime.fromisoformat(vps["expires_at"])
        except Exception:
            continue

        if now() >= expiry:
            result = await proxmox_action(vps, "stop")

            vps["status"] = "suspended"
            vps["suspended_at"] = timestamp()

            changed = True

            guild = bot.get_guild(GUILD_ID)

            if guild:
                owner = guild.get_member(vps["owner_id"])

                if owner:
                    await dm_embed(
                        owner,
                        "⏰ APEX CLOULD — VPS Expired",
                        f"Your VPS `{vps_id}` has expired and has been suspended.\n\n"
                        f"Your data has not been deleted."
                    )

                await send_log(
                    guild,
                    "VPS Expired",
                    f"`{vps_id}` expired and was automatically suspended."
                )

    if changed:
        save_data(DATA)


@expiry_checker.before_loop
async def before_expiry_checker():
    await bot.wait_until_ready()


# ============================================================
# GIVEAWAY CHECKER
# ============================================================

@tasks.loop(seconds=5)
async def giveaway_checker():
    current = now()

    for giveaway_id, giveaway in list(DATA["giveaways"].items()):
        if giveaway["ended"]:
            continue

        try:
            end_time = datetime.fromisoformat(giveaway["end_at"])
        except Exception:
            continue

        if current >= end_time:
            await finish_giveaway(giveaway_id)


@giveaway_checker.before_loop
async def before_giveaway_checker():
    await bot.wait_until_ready()


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"{BRAND} BOT ONLINE")
    print(f"Logged in as: {bot.user}")
    print(f"Guild ID: {GUILD_ID}")
    print(f"Owner ID: {OWNER_ID}")
    print("=" * 50)

    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild.")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global commands.")
    except Exception as e:
        print(f"Command sync error: {e}")

    if not expiry_checker.is_running():
        expiry_checker.start()

    if not giveaway_checker.is_running():
        giveaway_checker.start()


# ============================================================
# START
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from the .env file."
    )

bot.run(TOKEN)
/admin remove @user

/vps manager add @user
/vps manager remove @user

/vps delete <VPS-ID>

/config logs #channel

/config role add @role
/config role remove @role
/config role list/admin add @user
/admin remove @user

/vps manager add @user
/vps manager remove @user

/vps delete <VPS-ID>

/config logs #channel

/config role add @role
/config role remove @role
/config role list/admin add @user
/admin remove @user

/vps manager add @user
/vps manager remove @user

/vps delete <VPS-ID>

/config logs #channel

/config role add @role
/config role remove @role
/config role list/admin add @user
/admin remove @user

/vps manager add @user
/vps manager remove @user

/vps delete <VPS-ID>

/config logs #channel

/config role add @role
/config role remove @role
/config role list
