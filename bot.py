#!/usr/bin/env python3
# ============================================================
# ☁️ APEX CLOULD™ — DISCORD BOT
# Version: 1.0.0
# Built: 4000+ Lines | All-In-One
# Features: Moderation • Tickets • VPS Manager • Applications • Giveaways • Logging
# ============================================================

import os
import re
import json
import random
import string
import asyncio
import secrets
import sqlite3
import traceback
import datetime as dt
import io
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    from proxmoxer import ProxmoxAPI
except ImportError:
    ProxmoxAPI = None


# ============================================================
# ENVIRONMENT / CONFIG
# ============================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

OWNER_ID = int(os.getenv("OWNER_ID", "1373911333455659038"))
GUILD_ID = int(os.getenv("GUILD_ID", "1551158722490007617"))
APPLICATION_ID = int(os.getenv("APPLICATION_ID", "1555601710074962023"))

BRAND = os.getenv("BRAND", "APEX CLOULD")
DISCORD_INVITE = os.getenv("DISCORD_INVITE", "https://discord.gg/6Vwvgf9Haw")
DB_FILE = os.getenv("DATABASE_FILE", "apex_cloud.db")

# Proxmox Settings
PROXMOX_HOST = os.getenv("PROXMOX_HOST", "")
PROXMOX_PORT = int(os.getenv("PROXMOX_PORT", "8006"))
PROXMOX_USER = os.getenv("PROXMOX_USER", "")
PROXMOX_TOKEN_NAME = os.getenv("PROXMOX_TOKEN_NAME", "")
PROXMOX_TOKEN_VALUE = os.getenv("PROXMOX_TOKEN_VALUE", "")
PROXMOX_VERIFY_SSL = os.getenv("PROXMOX_VERIFY_SSL", "false").lower() == "true"
PROXMOX_NODE = os.getenv("PROXMOX_NODE", "")
PROXMOX_STORAGE = os.getenv("PROXMOX_STORAGE", "local-lvm")
PROXMOX_BRIDGE = os.getenv("PROXMOX_BRIDGE", "vmbr0")
PROXMOX_VM_TEMPLATE = os.getenv("PROXMOX_VM_TEMPLATE", "")
PROXMOX_CT_TEMPLATE = os.getenv("PROXMOX_CT_TEMPLATE", "")


# ============================================================
# EMOJIS
# ============================================================

ARROW = "<a:arrow_green_animated:1551176972015632464>"
ARROW_WELCOME = "<a:arrow_green_animated:1496588531701645472>"
ROCKET = "<a:Rocket:1551176743484792855>"
SUPPORTER = "<a:supporter:1551189615954886666>"
SUPPORT = "<:sl_support:1551189464242593922>"
RULES = "<:RULES_RULES:1496588421370744895>"
SIGNAL = "<a:ateex_signal_high:1496588570478247977>"
CART = "<:cart998:1551177586162278542>"
ADMIN_EMOJI = "<:Admin:1551174424601038880>"
GENERAL_SUPPORT_EMOJI = "<:support889:1551189484077584475>"
REWARD_EMOJI = "<:Admin:1551174424601038880>"
PARTNERSHIP_EMOJI = "<a:supporter:1551189615954886666>"
THUMBNAIL = "https://cdn.discordapp.com/attachments/1551160968682151956/1551241905202008114/1789897602018.png"


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=APPLICATION_ID
)


# ============================================================
# HELPERS / UTILS
# ============================================================

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def iso_now():
    return utcnow().isoformat()

def parse_iso(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None

def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con

def rows(query, args=()):
    con = db()
    try:
        return con.execute(query, args).fetchall()
    finally:
        con.close()

def execute(query, args=()):
    con = db()
    try:
        cur = con.execute(query, args)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


# ============================================================
# DATABASE SETUP
# ============================================================

def setup_database():
    con = db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            guild INTEGER PRIMARY KEY,
            logs_channel INTEGER,
            welcome_channel INTEGER,
            leave_channel INTEGER,
            member_role INTEGER,
            automod_enabled INTEGER DEFAULT 1,
            link_protection INTEGER DEFAULT 1,
            badword_protection INTEGER DEFAULT 1,
            applications_enabled INTEGER DEFAULT 1,
            lockdown INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admins (
            guild INTEGER,
            user INTEGER,
            PRIMARY KEY(guild, user)
        );

        CREATE TABLE IF NOT EXISTS managers (
            guild INTEGER,
            user INTEGER,
            PRIMARY KEY(guild, user)
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild INTEGER,
            user INTEGER,
            moderator INTEGER,
            reason TEXT,
            created_at TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS badwords (
            guild INTEGER,
            word TEXT,
            PRIMARY KEY(guild, word)
        );

        CREATE TABLE IF NOT EXISTS automod_bypass (
            guild INTEGER,
            role INTEGER,
            PRIMARY KEY(guild, role)
        );

        CREATE TABLE IF NOT EXISTS invites (
            guild INTEGER,
            user INTEGER,
            invited_user INTEGER,
            joined_at TEXT,
            left_at TEXT,
            fake INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS invite_cache (
            guild INTEGER,
            code TEXT,
            inviter INTEGER,
            uses INTEGER,
            PRIMARY KEY(guild, code)
        );

        CREATE TABLE IF NOT EXISTS ticket_access (
            guild INTEGER,
            role INTEGER,
            PRIMARY KEY(guild, role)
        );

        CREATE TABLE IF NOT EXISTS ticket_counter (
            guild INTEGER,
            type TEXT,
            number INTEGER,
            PRIMARY KEY(guild, type)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            channel INTEGER PRIMARY KEY,
            guild INTEGER,
            creator INTEGER,
            type TEXT,
            number INTEGER,
            claimed_by INTEGER,
            created_at TEXT,
            last_staff_reply TEXT,
            reminder_sent INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ticket_messages (
            channel INTEGER PRIMARY KEY,
            message INTEGER
        );

        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            guild INTEGER,
            user INTEGER,
            answers TEXT,
            status TEXT,
            claim_code TEXT,
            created_at TEXT,
            reviewed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS vps (
            vps_id TEXT PRIMARY KEY,
            guild INTEGER,
            user INTEGER,
            vmid INTEGER,
            node TEXT,
            vtype TEXT,
            plan TEXT,
            name TEXT,
            username TEXT,
            status TEXT,
            created_at TEXT,
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS vps_managers (
            guild INTEGER,
            user INTEGER,
            PRIMARY KEY(guild, user)
        );

        CREATE TABLE IF NOT EXISTS giveaways (
            id TEXT PRIMARY KEY,
            guild INTEGER,
            channel INTEGER,
            message INTEGER,
            prize TEXT,
            winners INTEGER,
            ends_at TEXT,
            entries TEXT,
            ended INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS lockdown_roles (
            guild INTEGER,
            role INTEGER,
            PRIMARY KEY(guild, role)
        );

        CREATE TABLE IF NOT EXISTS promotion_roles (
            guild INTEGER,
            role INTEGER,
            PRIMARY KEY(guild, role)
        );
    """)

    migrations = [
        ("settings", "automod_enabled", "INTEGER DEFAULT 1"),
        ("settings", "link_protection", "INTEGER DEFAULT 1"),
        ("settings", "badword_protection", "INTEGER DEFAULT 1"),
        ("settings", "applications_enabled", "INTEGER DEFAULT 1"),
        ("settings", "lockdown", "INTEGER DEFAULT 0"),
        ("tickets", "last_staff_reply", "TEXT"),
        ("tickets", "reminder_sent", "INTEGER DEFAULT 0")
    ]

    for table, column, typ in migrations:
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typ}")
        except sqlite3.OperationalError:
            pass

    con.commit()
    con.close()

def setting(guild_id, key, default=None):
    con = db()
    try:
        row = con.execute("SELECT * FROM settings WHERE guild=?", (guild_id,)).fetchone()
        if row and key in row.keys():
            return row[key]
        return default
    finally:
        con.close()

def set_setting(guild_id, key, value):
    con = db()
    try:
        con.execute("INSERT OR IGNORE INTO settings(guild) VALUES(?)", (guild_id,))
        con.execute(f"UPDATE settings SET {key}=? WHERE guild=?", (value, guild_id))
        con.commit()
    finally:
        con.close()


# ============================================================
# EMBED SYSTEM
# ============================================================

def apex_embed(title, description="", colour=0x39FF88):
    e = discord.Embed(
        title=title,
        description=description,
        colour=colour,
        timestamp=utcnow()
    )
    e.set_footer(text="☁️ APEX CLOULD™")
    return e

def styled_log(title, description):
    return apex_embed(f"{ARROW} {title}", description)


# ============================================================
# PERMISSION CHECKS
# ============================================================

def is_owner(user):
    return user.id == OWNER_ID

def is_admin(user, guild):
    if is_owner(user):
        return True
    return bool(rows("SELECT 1 FROM admins WHERE guild=? AND user=?", (guild.id, user.id)))

def is_vps_manager(user, guild):
    if is_owner(user):
        return True
    return bool(rows("SELECT 1 FROM vps_managers WHERE guild=? AND user=?", (guild.id, user.id)))

def ticket_allowed(member):
    if member.id == OWNER_ID:
        return True
    allowed = {r["role"] for r in rows("SELECT role FROM ticket_access WHERE guild=?", (member.guild.id,))}
    return bool(allowed.intersection(role.id for role in member.roles))

async def require_admin(interaction):
    if not interaction.guild:
        await interaction.response.send_message(embed=apex_embed(f"{ARROW} Server Only", f"{ARROW} This command can only be used inside a server."), ephemeral=True)
        return False
    if not is_admin(interaction.user, interaction.guild):
        await interaction.response.send_message(embed=apex_embed(f"{ARROW} Access Denied", f"{ARROW} You do not have permission to use this command."), ephemeral=True)
        return False
    return True

async def require_owner(interaction):
    if not is_owner(interaction.user):
        await interaction.response.send_message(embed=apex_embed(f"{ARROW} Owner Only", f"{ARROW} This command can only be used by the APEX CLOULD™ owner."), ephemeral=True)
        return False
    return True

async def require_vps_manager(interaction):
    if not interaction.guild:
        await interaction.response.send_message(embed=apex_embed(f"{ARROW} Server Only", f"{ARROW} This command can only be used inside a server."), ephemeral=True)
        return False
    if not is_vps_manager(interaction.user, interaction.guild):
        await interaction.response.send_message(embed=apex_embed(f"{ARROW} Access Denied", f"{ARROW} You are not an APEX CLOULD™ VPS manager."), ephemeral=True)
        return False
    return True


# ============================================================
# DM HELPER
# ============================================================

async def send_dm(member, embed_obj=None, content=None, file=None):
    try:
        await member.send(content=content, embed=embed_obj, file=file)
        return True
    except Exception:
        return False


# ============================================================
# MODERATION DM TEMPLATES
# ============================================================

def warning_dm(reason, count):
    return apex_embed("⚠️ APEX CLOULD™ — Warning", f"""
{ARROW} You have received a warning from the **APEX CLOULD™ moderation team.**

{SUPPORTER} **Reason:**
> {reason}

{ARROW} Warning count: **{count}/3**

{SIGNAL} Please make sure you follow the server rules to avoid further action.
""")

def timeout_dm():
    return apex_embed("🔒 APEX CLOULD™ — 24 Hour Timeout", f"""
{ARROW} You have reached **3 warnings**.

{ROCKET} As a result, you have been placed in a **24-hour timeout**.

{SUPPORTER} **Reason:**
> Reaching 3 active warnings.

{ARROW} Please review the server rules before participating again.

{SIGNAL} **APEX CLOULD™ Moderation**
""")

def kick_dm(reason):
    return apex_embed("👢 APEX CLOULD™ — You Were Kicked", f"""
{ARROW} You have been removed from the server by the **APEX CLOULD™ moderation team.**

{SUPPORTER} **Reason:**
> {reason}

{ARROW} If you believe this was a mistake, you may contact the APEX CLOULD™ team.

{SIGNAL} **APEX CLOULD™ Moderation**
""")

def ban_dm(reason):
    return apex_embed("🔨 APEX CLOULD™ — You Were Banned", f"""
{ARROW} You have been banned from the **APEX CLOULD™ server.**

{SUPPORTER} **Reason:**
> {reason}

{ARROW} If you believe this action was made in error, you may contact the APEX CLOULD™ team.

{SIGNAL} **APEX CLOULD™ Moderation**
""")

def untimeout_dm():
    return apex_embed("🔓 APEX CLOULD™ — Timeout Removed", f"""
{ARROW} Your timeout has been removed by the **APEX CLOULD™ moderation team.**

{ARROW} You can now participate in the server again.

{SIGNAL} Please continue following the server rules. 💚
""")

def automod_dm(reason):
    return apex_embed("🤖 APEX CLOULD™ — AutoMod Action", f"""
{ARROW} Your message was removed by the **APEX CLOULD™ AutoMod system.**

{SUPPORTER} **Reason:**
> {reason}

{ARROW} Please make sure your messages follow our server rules.

{SIGNAL} Repeated violations may result in further moderation action.
""")


# ============================================================
# LOGGING SYSTEM
# ============================================================

async def log_action(guild, title, description):
    channel_id = setting(guild.id, "logs_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    try:
        await channel.send(embed=styled_log(title, description))
    except Exception:
        pass

async def audit_actor(guild, action, target_id=None):
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if target_id is None or getattr(entry.target, "id", None) == target_id:
                return entry.user
    except Exception:
        pass
    return None


# ============================================================
# WELCOME / LEAVE SYSTEM
# ============================================================

@bot.event
async def on_member_join(member):
    guild = member.guild

    role_id = setting(guild.id, "member_role")
    if role_id:
        role = guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="APEX CLOULD™ member role")
            except Exception:
                pass

    description = f"""
{ARROW_WELCOME} Your journey to fast, powerful hosting starts here.

{ROCKET} **What we offer:**
{ARROW_WELCOME} High-performance nodes
{ARROW_WELCOME} Advanced DDoS protection
{ARROW_WELCOME} Instant deployment
{ARROW_WELCOME} Budget & premium plans

{SUPPORT} **Need assistance?**
{ARROW_WELCOME} Open a ticket — our team will respond fast ⚡

{SUPPORTER} **Earn free hosting!**
{ARROW_WELCOME} Invite friends and unlock credits, upgrades & rewards.

{RULES} **Important:**
{ARROW_WELCOME} Make sure to read the rules before using our services.

{SIGNAL} *We're glad you're here — power up your servers with APEX CLOULD!* 🚀
"""

    welcome_channel_id = setting(guild.id, "welcome_channel")
    if welcome_channel_id:
        channel = guild.get_channel(welcome_channel_id)
        if channel:
            embed_obj = discord.Embed(title="Welcome to APEX CLOULD™!", description=description, colour=0x39FF88, timestamp=utcnow())
            embed_obj.set_footer(text="☁️ APEX CLOULD™")
            embed_obj.set_thumbnail(url=THUMBNAIL)
            try:
                await channel.send(content=member.mention, embed=embed_obj)
            except Exception:
                pass

    dm_description = f"""
Hey {member.display_name}, thanks for joining us! 💚

{ARROW_WELCOME} Fast & powerful hosting starts here.

{ROCKET} **Explore:**
{ARROW_WELCOME} Minecraft Hosting
{ARROW_WELCOME} VPS Hosting
{ARROW_WELCOME} DDoS Protection
{ARROW_WELCOME} Free Hosting Rewards

{SUPPORT} **Need help?**
{ARROW_WELCOME} Open a ticket in our support channel.

{SUPPORTER} **Want free hosting?**
{ARROW_WELCOME} Invite friends and earn rewards! 🎁

{RULES} Don't forget to read the rules!

{SIGNAL} Enjoy your stay at APEX CLOULD™! 🚀
"""
    await send_dm(member, embed_obj=discord.Embed(title="Welcome to APEX CLOULD™! 🚀", description=dm_description, colour=0x39FF88, timestamp=utcnow()))


@bot.event
async def on_member_remove(member):
    guild = member.guild

    for row in rows("SELECT rowid FROM invites WHERE guild=? AND invited_user=? AND left_at IS NULL", (guild.id, member.id)):
        execute("UPDATE invites SET left_at=? WHERE rowid=?", (iso_now(), row["rowid"]))

    description = f"""
{ARROW_WELCOME} We're sorry to see you leave!

{ROCKET} **Before you go:**
{ARROW_WELCOME} Thank you for being part of our community
{ARROW_WELCOME} Your support means a lot to us
{ARROW_WELCOME} You're always welcome back

{SUPPORT} **Need us again?**
{ARROW_WELCOME} You can always rejoin APEX CLOULD™ and continue your journey with us.

{SUPPORTER} **Remember:**
{ARROW_WELCOME} Invite friends, earn rewards & power up your servers!

{RULES} **Stay connected:**
{ARROW_WELCOME} We hope to see you again someday.

{SIGNAL} Thanks for being with us — see you next time! 🚀
"""

    leave_channel_id = setting(guild.id, "leave_channel")
    if leave_channel_id:
        channel = guild.get_channel(leave_channel_id)
        if channel:
            embed_obj = discord.Embed(title="Goodbye from APEX CLOULD™!", description=description, colour=0x39FF88, timestamp=utcnow())
            embed_obj.set_footer(text="☁️ APEX CLOULD™")
            embed_obj.set_thumbnail(url=THUMBNAIL)
            try:
                await channel.send(embed=embed_obj)
            except Exception:
                pass

    dm_description = f"""
{ARROW_WELCOME} Thanks for being part of APEX CLOULD™!

{ROCKET} Your journey doesn't have to end here.

{ARROW_WELCOME} You're always welcome to rejoin us.
{ARROW_WELCOME} Come back anytime and continue your hosting journey.

{SUPPORT} **Want to come back?**
{ARROW_WELCOME} Rejoin APEX CLOULD™: {DISCORD_INVITE}

{SUPPORTER} **Keep earning:**
{ARROW_WELCOME} Invite friends and earn hosting rewards! 🎁

{RULES} We hope to see you again soon!

{SIGNAL} Take care — APEX CLOULD™ will be here! 🚀
"""
    await send_dm(member, embed_obj=discord.Embed(title="We'll Miss You at APEX CLOULD™! 💚", description=dm_description, colour=0x39FF88, timestamp=utcnow()))


# ============================================================
# CHANNEL / ROLE LOGGING
# ============================================================

@bot.event
async def on_guild_channel_delete(channel):
    actor = await audit_actor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
    await log_action(channel.guild, "🗑️ Channel Deleted", f"""
{ARROW} **Channel:** `#{channel.name}`
{ARROW} **Deleted by:** {actor.mention if actor else "Unknown"}
{ARROW} **Channel type:** `{channel.type}`
""")

@bot.event
async def on_guild_channel_create(channel):
    actor = await audit_actor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
    await log_action(channel.guild, "📁 Channel Created", f"""
{ARROW} **Channel:** {getattr(channel, "mention", channel.name)}
{ARROW} **Created by:** {actor.mention if actor else "Unknown"}
{ARROW} **Channel type:** `{channel.type}`
""")

@bot.event
async def on_guild_channel_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"{ARROW} Name: `{before.name}` → `{after.name}`")
    if hasattr(before, "topic") and before.topic != after.topic:
        changes.append(f"{ARROW} Topic changed")
    if not changes:
        return
    actor = await audit_actor(after.guild, discord.AuditLogAction.channel_update, after.id)
    await log_action(after.guild, "✏️ Channel Updated", "\n".join(changes) + f"\n\n{ARROW} **Changed by:** {actor.mention if actor else 'Unknown'}")

@bot.event
async def on_guild_role_create(role):
    actor = await audit_actor(role.guild, discord.AuditLogAction.role_create, role.id)
    await log_action(role.guild, "🎭 Role Created", f"""
{ARROW} **Role:** {role.mention}
{ARROW} **Created by:** {actor.mention if actor else "Unknown"}
""")

@bot.event
async def on_guild_role_delete(role):
    actor = await audit_actor(role.guild, discord.AuditLogAction.role_delete, role.id)
    await log_action(role.guild, "🗑️ Role Deleted", f"""
{ARROW} **Role:** `{role.name}`
{ARROW} **Deleted by:** {actor.mention if actor else "Unknown"}
""")

@bot.event
async def on_guild_role_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"{ARROW} Name: `{before.name}` → `{after.name}`")
    if before.permissions != after.permissions:
        changes.append(f"{ARROW} Permissions updated")
    if not changes:
        return
    actor = await audit_actor(after.guild, discord.AuditLogAction.role_update, after.id)
    await log_action(after.guild, "✏️ Role Updated", "\n".join(changes) + f"\n\n{ARROW} **Changed by:** {actor.mention if actor else 'Unknown'}")


# ============================================================
# WARNING SYSTEM
# ============================================================

def warning_count(guild_id, user_id):
    result = rows("SELECT COUNT(*) AS count FROM warnings WHERE guild=? AND user=? AND active=1", (guild_id, user_id))
    return int(result[0]["count"])

async def add_warning(guild, member, moderator, reason):
    execute("INSERT INTO warnings(guild, user, moderator, reason, created_at, active) VALUES(?,?,?,?,?,1)",
        (guild.id, member.id, moderator.id, reason, iso_now()))
    count = warning_count(guild.id, member.id)
    await send_dm(member, embed_obj=warning_dm(reason, count))
    await log_action(guild, "⚠️ Warning Issued", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Moderator:** {moderator.mention}
{SUPPORTER} **Reason:**
> {reason}
{ARROW} **Warning count:** `{count}/3`
""")
    if count >= 3:
        try:
            until = utcnow() + dt.timedelta(hours=24)
            await member.timeout(until, reason="APEX CLOULD™ — 3 warnings")
            await send_dm(member, embed_obj=timeout_dm())
            await log_action(guild, "🔒 Automatic 24 Hour Timeout", f"""
{ARROW} **Member:** {member.mention}
{ARROW} The member reached **3 active warnings**.
{ROCKET} A **24-hour timeout** has been automatically applied.
""")
        except Exception:
            pass
    return count


# ============================================================
# MODERATION COMMANDS
# ============================================================

@bot.tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="Member to warn", reason="Reason for the warning")
async def warn_command(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not await require_admin(interaction):
        return
    count = await add_warning(interaction.guild, member, interaction.user, reason)
    await interaction.response.send_message(embed=apex_embed("⚠️ Warning Issued", f"""
{ARROW} {member.mention} has received a warning.
{SUPPORTER} **Reason:**
> {reason}
{ARROW} Warning count: **{count}/3**
"""), ephemeral=True)

@bot.tree.command(name="warn_clear", description="Clear all active warnings from a member")
@app_commands.describe(member="Member whose warnings should be cleared")
async def warn_clear_command(interaction, member: discord.Member):
    if not await require_admin(interaction):
        return
    execute("UPDATE warnings SET active=0 WHERE guild=? AND user=? AND active=1", (interaction.guild.id, member.id))
    await interaction.response.send_message(embed=apex_embed("🧹 Warnings Cleared", f"""
{ARROW} All active warnings for {member.mention} have been cleared.
{SIGNAL} The member is now at **0/3** active warnings.
"""), ephemeral=True)
    await log_action(interaction.guild, "🧹 Warnings Cleared", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Cleared by:** {interaction.user.mention}
""")

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="Member to kick", reason="Reason")
async def kick_command(interaction, member: discord.Member, reason: str = "No reason provided"):
    if not await require_admin(interaction):
        return
    await send_dm(member, embed_obj=kick_dm(reason))
    try:
        await member.kick(reason=reason)
    except Exception as e:
        await interaction.response.send_message(embed=apex_embed("❌ Kick Failed", f"{ARROW} `{e}`"), ephemeral=True)
        return
    await interaction.response.send_message(embed=apex_embed("👢 Member Kicked", f"""
{ARROW} {member.mention} has been removed from the server.
{SUPPORTER} **Reason:**
> {reason}
"""))
    await log_action(interaction.guild, "👢 Member Kicked", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Moderator:** {interaction.user.mention}
{SUPPORTER} **Reason:**
> {reason}
""")

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="Member to ban", reason="Reason")
async def ban_command(interaction, member: discord.Member, reason: str = "No reason provided"):
    if not await require_admin(interaction):
        return
    await send_dm(member, embed_obj=ban_dm(reason))
    try:
        await member.ban(reason=reason)
    except Exception as e:
        await interaction.response.send_message(embed=apex_embed("❌ Ban Failed", f"{ARROW} `{e}`"), ephemeral=True)
        return
    await interaction.response.send_message(embed=apex_embed("🔨 Member Banned", f"""
{ARROW} {member.mention} has been banned.
{SUPPORTER} **Reason:**
> {reason}
"""))
    await log_action(interaction.guild, "🔨 Member Banned", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Moderator:** {interaction.user.mention}
{SUPPORTER} **Reason:**
> {reason}
""")

@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="Member", duration="Duration such as 10m, 1h or 1d", reason="Reason")
async def timeout_command(interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if not await require_admin(interaction):
        return
    match = re.fullmatch(r"(\d+)([smhd])", duration.lower())
    if not match:
        await interaction.response.send_message(embed=apex_embed("❌ Invalid Duration", f"""
{ARROW} Use a format such as:
`10m`
`1h`
`1d`
"""), ephemeral=True)
        return
    number = int(match.group(1))
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    seconds = number * multiplier
    if seconds > 28 * 86400:
        await interaction.response.send_message(embed=apex_embed("❌ Duration Too Long", f"{ARROW} Discord allows a maximum timeout of 28 days."), ephemeral=True)
        return
    until = utcnow() + dt.timedelta(seconds=seconds)
    try:
        await member.timeout(until, reason=reason)
    except Exception as e:
        await interaction.response.send_message(embed=apex_embed("❌ Timeout Failed", f"{ARROW} `{e}`"), ephemeral=True)
        return
    await interaction.response.send_message(embed=apex_embed("🔒 Member Timed Out", f"""
{ARROW} {member.mention} has been timed out.
{ROCKET} **Duration:** `{duration}`
{SUPPORTER} **Reason:**
> {reason}
"""))
    await log_action(interaction.guild, "🔒 Member Timed Out", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Moderator:** {interaction.user.mention}
{ROCKET} **Duration:** `{duration}`
{SUPPORTER} **Reason:**
> {reason}
""")

@bot.tree.command(name="untimeout", description="Remove a timeout")
async def untimeout_command(interaction, member: discord.Member):
    if not await require_admin(interaction):
        return
    try:
        await member.timeout(None, reason="APEX CLOULD™ timeout removed")
    except Exception as e:
        await interaction.response.send_message(embed=apex_embed("❌ Failed", f"{ARROW} `{e}`"), ephemeral=True)
        return
    await send_dm(member, embed_obj=untimeout_dm())
    await interaction.response.send_message(embed=apex_embed("🔓 Timeout Removed", f"""
{ARROW} Timeout removed from {member.mention}.
{SIGNAL} The member can participate again.
"""))
    await log_action(interaction.guild, "🔓 Timeout Removed", f"""
{ARROW} **Member:** {member.mention}
{ARROW} **Moderator:** {interaction.user.mention}
""")

@bot.tree.command(name="clear", description="Delete messages")
@app_commands.describe(amount="Amount of messages to delete")
async def clear_command(interaction, amount: int):
    if not await require_admin(interaction):
        return
    if amount < 1 or amount > 100:
        await interaction.response.send_message(embed=apex_embed("❌ Invalid Amount", f"{ARROW} Choose between **1 and 100**."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=apex_embed("🧹 Messages Cleared", f"""
{ARROW} Deleted **{len(deleted)}** messages.
{SIGNAL} Cleaned by {interaction.user.mention}.
"""), ephemeral=True)
    await log_action(interaction.guild, "🧹 Messages Cleared", f"""
{ARROW} **Channel:** {interaction.channel.mention}
{ARROW} **Messages deleted:** `{len(deleted)}`
{ARROW} **Moderator:** {interaction.user.mention}
""")

@bot.tree.command(name="clear_all", description="Clear messages from the channel")
async def clear_all_command(interaction):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    deleted_total = 0
    while True:
        deleted = await interaction.channel.purge(limit=100)
        deleted_total += len(deleted)
        if len(deleted) < 100:
            break
        await asyncio.sleep(1)
    await interaction.followup.send(embed=apex_embed("🧹 Channel Cleared", f"""
{ARROW} Removed **{deleted_total}** messages.
{SIGNAL} APEX CLOULD™ moderation
"""), ephemeral=True)


# ============================================================
# ADMIN MANAGEMENT
# ============================================================

@bot.tree.command(name="admin_add", description="Add an administrator")
@app_commands.describe(member="Member to make administrator")
async def admin_add(interaction, member: discord.Member):
    if not await require_owner(interaction):
        return
    execute("INSERT OR IGNORE INTO admins(guild, user) VALUES(?,?)", (interaction.guild.id, member.id))
    await interaction.response.send_message(embed=apex_embed("🛡️ Administrator Added", f"""
{ARROW} {member.mention} is now an APEX CLOULD™ administrator.
{SIGNAL} Administrator permissions have been updated.
"""), ephemeral=True)

@bot.tree.command(name="admin_remove", description="Remove an administrator")
@app_commands.describe(member="Administrator to remove")
async def admin_remove(interaction, member: discord.Member):
    if not await require_owner(interaction):
        return
    if member.id == OWNER_ID:
        await interaction.response.send_message(embed=apex_embed("❌ Protected Account", f"{ARROW} The owner cannot be removed."), ephemeral=True)
        return
    execute("DELETE FROM admins WHERE guild=? AND user=?", (interaction.guild.id, member.id))
    await interaction.response.send_message(embed=apex_embed("🛡️ Administrator Removed", f"""
{ARROW} {member.mention} is no longer an administrator.
{SIGNAL} Administrator permissions have been updated.
"""), ephemeral=True)


# ============================================================
# VPS MANAGER MANAGEMENT
# ============================================================

@bot.tree.command(name="vps_manager_add", description="Add a VPS manager")
async def vps_manager_add(interaction, member: discord.Member):
    if not await require_owner(interaction):
        return
    execute("INSERT OR IGNORE INTO vps_managers(guild, user) VALUES(?,?)", (interaction.guild.id, member.id))
    await interaction.response.send_message(embed=apex_embed("☁️ VPS Manager Added", f"""
{ARROW} {member.mention} is now a VPS manager.
{ROCKET} They can manage VPS functions but are **not automatically an administrator**.
"""), ephemeral=True)

@bot.tree.command(name="vps_manager_remove", description="Remove a VPS manager")
async def vps_manager_remove(interaction, member: discord.Member):
    if not await require_owner(interaction):
        return
    execute("DELETE FROM vps_managers WHERE guild=? AND user=?", (interaction.guild.id, member.id))
    await interaction.response.send_message(embed=apex_embed("☁️ VPS Manager Removed", f"""
{ARROW} {member.mention} is no longer a VPS manager.
"""), ephemeral=True)

@bot.tree.command(name="vps_manager_list", description="List VPS managers")
async def vps_manager_list(interaction):
    if not await require_owner(interaction):
        return
    manager_rows = rows("SELECT user FROM vps_managers WHERE guild=?", (interaction.guild.id,))
    mentions = []
    for row in manager_rows:
        member = interaction.guild.get_member(row["user"])
        if member:
            mentions.append(member.mention)
    await interaction.response.send_message(embed=apex_embed("☁️ VPS Managers", "\n".join(mentions) if mentions else f"{ARROW} No VPS managers configured."), ephemeral=True)


# ============================================================
# CONFIGURATION COMMANDS
# ============================================================

@bot.tree.command(name="config_logs", description="Set the logging channel")
async def config_logs(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    set_setting(interaction.guild.id, "logs_channel", channel.id)
    await interaction.response.send_message(embed=apex_embed("📋 Logging Channel Updated", f"""
{ARROW} Logs will now be sent to {channel.mention}.
{SUPPORTER} Member joins and leaves are **not logged**.
"""), ephemeral=True)

@bot.tree.command(name="config_welcome", description="Set the welcome channel")
async def config_welcome(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    set_setting(interaction.guild.id, "welcome_channel", channel.id)
    await interaction.response.send_message(embed=apex_embed("👋 Welcome Channel Updated", f"{ARROW} Welcome messages will be sent in {channel.mention}."), ephemeral=True)

@bot.tree.command(name="config_leave", description="Set the leave channel")
async def config_leave(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    set_setting(interaction.guild.id, "leave_channel", channel.id)
    await interaction.response.send_message(embed=apex_embed("👋 Leave Channel Updated", f"{ARROW} Leave messages will be sent in {channel.mention}."), ephemeral=True)

@bot.tree.command(name="config_memberrole", description="Set the automatic member role")
async def config_memberrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return
    set_setting(interaction.guild.id, "member_role", role.id)
    await interaction.response.send_message(embed=apex_embed("🎭 Member Role Updated", f"{ARROW} New members will receive {role.mention}."), ephemeral=True)


# ============================================================
# AUTOMOD SYSTEM
# ============================================================

URL_PATTERN = re.compile(r"(https?://|www\.|discord\.gg/|discord\.com/invite/|youtube\.com|youtu\.be/|tiktok\.com/)", re.IGNORECASE)

def has_bypass_role(member):
    bypass = {r["role"] for r in rows("SELECT role FROM automod_bypass WHERE guild=?", (member.guild.id,))}
    return bool(bypass.intersection(role.id for role in member.roles))

def contains_badword(guild_id, content):
    words = rows("SELECT word FROM badwords WHERE guild=?", (guild_id,))
    lowered = content.lower()
    for row in words:
        word = row["word"].lower().strip()
        if word and word in lowered:
            return True
    return False

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        await bot.process_commands(message)
        return

    enabled = bool(setting(message.guild.id, "automod_enabled", 1))
    if enabled and isinstance(message.author, discord.Member):
        if not has_bypass_role(message.author):

            links_enabled = bool(setting(message.guild.id, "link_protection", 1))
            if links_enabled and URL_PATTERN.search(message.content):
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.author.timeout(utcnow() + dt.timedelta(minutes=10), reason="APEX CLOULD™ AutoMod — link")
                except Exception:
                    pass
                await send_dm(message.author, embed_obj=automod_dm("Unauthorized links are not allowed."))
                await log_action(message.guild, "🤖 AutoMod — Link Protection", f"""
{ARROW} **Member:** {message.author.mention}
{ARROW} The message was removed because it contained a link.
{ARROW} A **10-minute timeout** was applied where possible.
""")
                return

            badwords_enabled = bool(setting(message.guild.id, "badword_protection", 1))
            if badwords_enabled and contains_badword(message.guild.id, message.content):
                try:
                    await message.delete()
                except Exception:
                    pass
                await send_dm(message.author, embed_obj=automod_dm("Your message contained blocked language."))
                await log_action(message.guild, "🤖 AutoMod — Bad Word Protection", f"""
{ARROW} **Member:** {message.author.mention}
{ARROW} A message was removed by the bad-word filter.
""")
                return

    await bot.process_commands(message)

@bot.tree.command(name="automod", description="View AutoMod status")
async def automod_status(interaction):
    if not await require_admin(interaction):
        return
    enabled = bool(setting(interaction.guild.id, "automod_enabled", 1))
    links = bool(setting(interaction.guild.id, "link_protection", 1))
    badwords = bool(setting(interaction.guild.id, "badword_protection", 1))
    await interaction.response.send_message(embed=apex_embed("🤖 APEX CLOULD™ AutoMod", f"""
{ARROW} **AutoMod:** `{"ON" if enabled else "OFF"}`
{ARROW} **Link Protection:** `{"ON" if links else "OFF"}`
{ARROW} **Bad Word Protection:** `{"ON" if badwords else "OFF"}`
{SIGNAL} AutoMod protection is managed by APEX CLOULD™.
"""), ephemeral=True)

@bot.tree.command(name="automod_toggle", description="Toggle AutoMod")
async def automod_toggle(interaction):
    if not await require_admin(interaction):
        return
    current = bool(setting(interaction.guild.id, "automod_enabled", 1))
    set_setting(interaction.guild.id, "automod_enabled", int(not current))
    await interaction.response.send_message(embed=apex_embed("🤖 AutoMod Updated", f"{ARROW} AutoMod is now **{'ON' if not current else 'OFF'}**."), ephemeral=True)

@bot.tree.command(name="automodbypass_add", description="Add an AutoMod bypass role")
async def automodbypass_add(interaction, role: discord.Role):
    if not await require_owner(interaction):
        return
    execute("INSERT OR IGNORE INTO automod_bypass(guild, role) VALUES(?,?)", (interaction.guild.id, role.id))
    await interaction.response.send_message(embed=apex_embed("🛡️ AutoMod Bypass Added", f"{ARROW} {role.mention} can now bypass AutoMod."), ephemeral=True)

@bot.tree.command(name="automodbypass_remove", description="Remove an AutoMod bypass role")
async def automodbypass_remove(interaction, role: discord.Role):
    if not await require_owner(interaction):
        return
    execute("DELETE FROM automod_bypass WHERE guild=? AND role=?", (interaction.guild.id, role.id))
    await interaction.response.send_message(embed=apex_embed("🛡️ AutoMod Bypass Removed", f"{ARROW} {role.mention} can no longer bypass AutoMod."), ephemeral=True)

@bot.tree.command(name="automodbypass_list", description="List AutoMod bypass roles")
async def automodbypass_list(interaction):
    if not await require_owner(interaction):
        return
    role_rows = rows("SELECT role FROM automod_bypass WHERE guild=?", (interaction.guild.id,))
    roles = []
    for row in role_rows:
        role = interaction.guild.get_role(row["role"])
        if role:
            roles.append(role.mention)
    await interaction.response.send_message(embed=apex_embed("🛡️ AutoMod Bypass Roles", "\n".join(roles) if roles else f"{ARROW} No bypass roles configured."), ephemeral=True)

@bot.tree.command(name="badword_add", description="Add a blocked word")
async def badword_add(interaction, word: str):
    if not await require_admin(interaction):
        return
    word = word.lower().strip()
    execute("INSERT OR IGNORE INTO badwords(guild, word) VALUES(?,?)", (interaction.guild.id, word))
    await interaction.response.send_message(embed=apex_embed("🚫 Bad Word Added", f"{ARROW} The word has been added to the AutoMod filter."), ephemeral=True)

@bot.tree.command(name="badword_remove", description="Remove a blocked word")
async def badword_remove(interaction, word: str):
    if not await require_admin(interaction):
        return
    execute("DELETE FROM badwords WHERE guild=? AND word=?", (interaction.guild.id, word.lower().strip()))
    await interaction.response.send_message(embed=apex_embed("🚫 Bad Word Removed", f"{ARROW} The word has been removed from the AutoMod filter."), ephemeral=True)

@bot.tree.command(name="badword_list", description="List blocked words")
async def badword_list(interaction):
    if not await require_admin(interaction):
        return
    word_rows = rows("SELECT word FROM badwords WHERE guild=? ORDER BY word", (interaction.guild.id,))
    await interaction.response.send_message(embed=apex_embed("🚫 Bad Word Filter", f"{ARROW} **{len(word_rows)}** blocked words are configured."), ephemeral=True)


# ============================================================
# TICKET SYSTEM
# ============================================================

TICKET_TYPES = {
    "support": ("GENERAL SUPPORT", GENERAL_SUPPORT_EMOJI, "SUPPORT"),
    "partnership": ("PARTNERSHIP / STA
