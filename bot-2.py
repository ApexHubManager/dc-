import os
import re
import io
import json
import random
import string
import asyncio
import secrets
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv



# ============================================================
# APEX CLOULD™ BOT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "1373911333455659038"))
GUILD_ID = int(os.getenv("GUILD_ID", "1551158722490007617"))

BRAND = os.getenv("BRAND", "APEX CLOULD")
INVITE = os.getenv("DISCORD_INVITE", "https://discord.gg/6Vwvgf9Haw")

DATA_FILE = os.getenv("DATA_FILE", "data.json")
REGIMENT_FILE = os.getenv("REGIMENT_FILE", "regiment.txt")

TICKET_CATEGORY_NAME = os.getenv(
    "TICKET_CATEGORY_NAME",
    "APEX CLOULD TICKETS"
)

APPLICATION_CATEGORY_NAME = os.getenv(
    "APPLICATION_CATEGORY_NAME",
    "APEX CLOULD APPLICATIONS"
)



# ============================================================
# APEX EMOJI / STYLE
# ============================================================

ARROW = "<a:arrow_green_animated:1551176972015632464>"
ROCKET = "<a:Rocket:1551176743484792855>"
SUPPORT = "<:sl_support:1551189464242593922>"
RULES = "<:RULES_RULES:1551176661003669585>"
SUPPORTER = "<a:supporter:1551189615954886666>"
SIGNAL = "<:ateex_signal_high:1551177108569587723>"

ARROW_OLD = ARROW
SIGNAL_OLD = SIGNAL

TICKET_EMOJIS = {
    "support": "<:support889:1551189484077584475>",
    "partnership": SUPPORTER,
    "reward": "<:Admin:1551174424601038880>",
    "buy": "<:cart998:1551177586162278542>",
    "staff": "📝",
}


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def apex_embed(
    title: str,
    description: str = "",
    *,
    color: Optional[discord.Color] = None,
):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.green(),
        timestamp=now_utc(),
    )

    embed.set_footer(text="APEX CLOULD™")

    return embed


def success_embed(title, description):
    return apex_embed(
        f"💚 {title}",
        description,
        color=discord.Color.green(),
    )


def error_embed(title, description):
    return apex_embed(
        f"❌ {title}",
        description,
        color=discord.Color.red(),
    )


def info_embed(title, description):
    return apex_embed(
        f"{ARROW} {title}",
        description,
        color=discord.Color.green(),
    )


async def reply_embed(
    interaction: discord.Interaction,
    embed: discord.Embed,
    *,
    ephemeral=False,
):
    if interaction.response.is_done():
        await interaction.followup.send(
            embed=embed,
            ephemeral=ephemeral,
        )
    else:
        await interaction.response.send_message(
            embed=embed,
            ephemeral=ephemeral,
        )


async def dm_embed(
    user: discord.abc.User,
    embed: discord.Embed,
    *,
    file=None,
):
    try:
        if file:
            await user.send(embed=embed, file=file)
        else:
            await user.send(embed=embed)

        return True

    except Exception:
        return False


# ============================================================
# DATA
# ============================================================

DEFAULT_DATA = {
    "admins": [],

    "ticket_roles": [],

    "promotion_roles": [],

    "member_roles": [],

    "config": {
        "logs_channel": None,
        "welcome_channel": None,
        "leave_channel": None,
        "application_channel": None,
    },

    "automod": {
        "enabled": True,
        "links_enabled": True,
        "badwords_enabled": True,
        "badwords": [],
        "bypass_roles": [],
    },

    "warnings": {},

    "tickets": {},

    "ticket_counter": {
        "BUY": 0,
        "REWARD": 0,
        "PARTNERSHIP": 0,
        "SUPPORT": 0,
        "STAFF": 0,
    },

    "applications": {},

    "application_enabled": True,

    "application_drafts": {},

    "claim_codes": {},

    "giveaways": {},

    "vps": {},
    "websites": {},
    "website_panel": {"channel_id": None, "message_id": None},
    "security": {
        "anti_raid_enabled": True,
        "verification_enabled": True,
        "permission_alerts_enabled": True,
        "verified_role_id": None,
        "verification_channel_id": None,
        "join_threshold": 8,
        "join_window_seconds": 20,
        "recent_incidents": [],
        "raid_lockdown_active": False,
    },

    "lockdown": {
        "active": False,
        "allowed_roles": [],
    },

    "invite_stats": {},

    "counter": {
        "ticket": 0,
        "application": 0,
    },
}


def deep_merge(default, current):
    if isinstance(default, dict):
        if not isinstance(current, dict):
            current = {}

        for key, value in default.items():
            if key not in current:
                current[key] = value
            else:
                current[key] = deep_merge(
                    value,
                    current[key],
                )

        return current

    return current


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(
            DATA_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                DEFAULT_DATA,
                f,
                indent=4,
            )

        return json.loads(
            json.dumps(DEFAULT_DATA)
        )

    try:
        with open(
            DATA_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            current = json.load(f)

    except Exception:
        current = {}

    current = deep_merge(
        json.loads(json.dumps(DEFAULT_DATA)),
        current,
    )

    try:
        with open(
            DATA_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                current,
                f,
                indent=4,
            )

    except Exception:
        pass

    return current


data = load_data()
data.setdefault("websites", {})
data.setdefault("security", {})
data.setdefault("website_panel", {"channel_id": None, "message_id": None})


def save_data():
    temp = DATA_FILE + ".tmp"

    try:
        with open(
            temp,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                data,
                f,
                indent=4,
            )

        os.replace(
            temp,
            DATA_FILE,
        )

    except Exception:
        try:
            with open(
                DATA_FILE,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    data,
                    f,
                    indent=4,
                )
        except Exception:
            pass


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.invites = True
intents.moderation = True


class ApexBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.invite_cache = {}
        self.views_loaded = False
        self.startup_logged = False
        self.recent_joins = {}
        self.started_at = now_utc()

    async def setup_hook(self):
        self.restore_persistent_views()

        guild = self.get_guild(GUILD_ID)

        if guild:
            try:
                # Publish the registered global command definitions immediately to the configured guild.
                # This makes newly added slash commands appear in the server without waiting for global propagation.
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(
                    guild=guild
                )

                print(
                    f"Synced {len(synced)} guild commands."
                )

            except Exception as e:
                print(
                    f"Guild sync error: {e}"
                )

        # V2 intentionally syncs slash commands to the configured guild only.
        # Keeping a second global sync can make the same command set appear twice
        # while Discord still has older global registrations propagating.

        if not self.expiry_checker.is_running():
            self.expiry_checker.start()

        if not self.ticket_checker.is_running():
            self.ticket_checker.start()

        if not self.giveaway_checker.is_running():
            self.giveaway_checker.start()

    def restore_persistent_views(self):

        if self.views_loaded:
            return

        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        self.add_view(ApplicationStartView())
        self.add_view(GiveawayView())
        self.add_view(VerifyView())
        self.add_view(WebsiteRecheckView())
        self.add_view(SecurityPanelView())

        self.views_loaded = True

    @tasks.loop(minutes=5)
    async def expiry_checker(self):
        await check_vps_expiry()

    @expiry_checker.before_loop
    async def before_expiry_checker(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def ticket_checker(self):
        await check_ticket_inactivity()

    @ticket_checker.before_loop
    async def before_ticket_checker(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def giveaway_checker(self):
        await check_giveaways()

    @giveaway_checker.before_loop
    async def before_giveaway_checker(self):
        await self.wait_until_ready()


bot = ApexBot()


# ============================================================
# PERMISSIONS
# ============================================================

def owner_only(user):
    return user.id == OWNER_ID


def is_admin(member: discord.Member):
    if member.id == OWNER_ID:
        return True

    return member.id in data["admins"]


def has_ticket_access(member: discord.Member):
    if member.id == OWNER_ID:
        return True

    configured = set(
        int(x)
        for x in data.get(
            "ticket_roles",
            [],
        )
    )

    return any(
        role.id in configured
        for role in member.roles
    )


async def require_owner(interaction):
    if owner_only(interaction.user):
        return True

    await reply_embed(
        interaction,
        error_embed(
            "Owner Only",
            f"{ARROW} This command can only be used by the **APEX CLOULD™ Owner**.",
        ),
        ephemeral=True,
    )

    return False


async def require_admin(interaction):
    if isinstance(
        interaction.user,
        discord.Member,
    ) and is_admin(interaction.user):
        return True

    await reply_embed(
        interaction,
        error_embed(
            "Permission Denied",
            f"{ARROW} You do not have permission to use this command.",
        ),
        ephemeral=True,
    )

    return False


async def require_ticket_access(interaction):
    if isinstance(
        interaction.user,
        discord.Member,
    ) and has_ticket_access(interaction.user):
        return True

    await reply_embed(
        interaction,
        error_embed(
            "Permission Denied",
            f"{ARROW} You do not have a configured ticket staff role.",
        ),
        ephemeral=True,
    )

    return False


# ============================================================
# LOGGING
# ============================================================

async def send_log(
    guild: discord.Guild,
    title: str,
    description: str,
):
    channel_id = data["config"].get(
        "logs_channel"
    )

    if not channel_id:
        return

    channel = guild.get_channel(
        int(channel_id)
    )

    if not channel:
        return

    embed = apex_embed(
        title,
        description,
    )

    try:
        await channel.send(
            embed=embed
        )
    except Exception:
        pass


# ============================================================
# WELCOME / LEAVE
# ============================================================

def welcome_server_embed():
    description = f"""{ARROW_OLD} Your journey to fast, powerful hosting starts here.

{ROCKET} **What we offer:**  
{ARROW_OLD} High-performance nodes  
{ARROW_OLD} Advanced DDoS protection  
{ARROW_OLD} Instant deployment  
{ARROW_OLD} Budget & premium plans  

{SUPPORT} **Need assistance?**  
{ARROW_OLD} Open a ticket in https://discord.com/channels/1551158722490007617/1551160965607985253 — our team will respond fast ⚡

{SUPPORTER} **Earn free hosting!**  
{ARROW_OLD} Invite friends and unlock credits, upgrades & rewards.

{RULES} **Important:**  
{ARROW_OLD} Make sure to read https://discord.com/channels/1551158722490007617/1551160943398887436 before using our services.

{SIGNAL} *We’re glad you’re here — power up your servers with APEX CLOULD!* 🚀"""

    return apex_embed(
        "Welcome to APEX CLOULD™!",
        description,
    )


def welcome_dm_embed(member):
    description = f"""Hey {member.display_name}, thanks for joining us! 💚
{ARROW_OLD} Fast & powerful hosting starts here.
{ROCKET} Explore:
{ARROW_OLD} Minecraft Hosting
{ARROW_OLD} VPS Hosting
{ARROW_OLD} DDoS Protection
{ARROW_OLD} Free Hosting Rewards
{SUPPORT} Need help?
{ARROW_OLD} Open a ticket in our support channel.
{SUPPORTER} Want free hosting?
{ARROW_OLD} Invite friends and earn rewards! 🎁
{RULES} Don't forget to read the rules!
{SIGNAL} Enjoy your stay at APEX CLOULD™! 🚀"""

    return apex_embed(
        "Welcome to APEX CLOULD™! 🚀",
        description,
    )


def leave_server_embed():
    description = f"""{ARROW_OLD} We’re sorry to see you leave!
{ROCKET} **Before you go:**
{ARROW_OLD} Thank you for being part of our community
{ARROW_OLD} Your support means a lot to us
{ARROW_OLD} You’re always welcome back
{SUPPORT} **Need us again?**
{ARROW_OLD} You can always rejoin APEX CLOULD™ and continue your journey with us.
{SUPPORTER} **Remember:**
{ARROW_OLD} Invite friends, earn rewards & power up your servers!
{RULES} **Stay connected:**
{ARROW_OLD} We hope to see you again someday.
{SIGNAL_OLD} Thanks for being with us — see you next time! 🚀"""

    return apex_embed(
        "Goodbye from APEX CLOULD™!",
        description,
    )


def leave_dm_embed():
    description = f"""{ARROW_OLD} Thanks for being part of APEX CLOULD™!

{ROCKET} Your journey doesn't have to end here.

{ARROW_OLD} You’re always welcome to rejoin us.
{ARROW_OLD} Come back anytime and continue your hosting journey.

{SUPPORT} **Want to come back?**
{ARROW_OLD} Rejoin APEX CLOULD™: {INVITE}

{SUPPORTER} **Keep earning:**
{ARROW_OLD} Invite friends and earn hosting rewards! 🎁

{RULES} We hope to see you again soon!

{SIGNAL_OLD} Take care — APEX CLOULD™ will be here! 🚀"""

    return apex_embed(
        "We’ll Miss You at APEX CLOULD™! 💚",
        description,
    )


@bot.event
async def on_member_join(member: discord.Member):

    if member.guild.id != GUILD_ID:
        return

    # Anti-raid join burst detection
    # --------------------------------------------------------
    sec = data.setdefault("security", {})
    if sec.get("anti_raid_enabled", True):
        now_mono = asyncio.get_running_loop().time()
        joins = [t for t in bot.recent_joins.get(member.guild.id, []) if now_mono - t <= int(sec.get("join_window_seconds", 20))]
        joins.append(now_mono)
        bot.recent_joins[member.guild.id] = joins
        threshold = max(3, int(sec.get("join_threshold", 8)))
        if len(joins) >= threshold and not sec.get("raid_lockdown_active"):
            sec["raid_lockdown_active"] = True
            await record_security_incident("anti_raid", f"Detected {len(joins)} joins within {sec.get('join_window_seconds', 20)} seconds; automatic lockdown enabled.")
            guild = member.guild
            changed = 0
            allowed_roles = [guild.get_role(int(rid)) for rid in data.get("lockdown", {}).get("allowed_roles", [])]
            allowed_roles = [role for role in allowed_roles if role]
            for channel in guild.text_channels:
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.send_messages = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrite, reason="APEX CLOULD™ anti-raid automatic lockdown")
                    for allowed_role in allowed_roles:
                        role_overwrite = channel.overwrites_for(allowed_role)
                        role_overwrite.send_messages = True
                        await channel.set_permissions(allowed_role, overwrite=role_overwrite, reason="APEX CLOULD™ anti-raid allowed role")
                    changed += 1
                except Exception:
                    continue
            data.setdefault("lockdown", {})["active"] = True
            sec["raid_lockdown_active"] = True
            save_data()
            await dm_owner_security(f"🚨 **Possible raid detected — automatic lockdown enabled**\n{ARROW} {len(joins)} members joined within {sec.get('join_window_seconds', 20)} seconds.\n{ARROW} Channels updated: `{changed}`.\n{ARROW} Review the server and use `/unlockdown` when safe.\n{ARROW} Lockdown remains active until manually removed.")

    # --------------------------------------------------------
    # --------------------------------------------------------
    # Invite tracking
    # --------------------------------------------------------

    inviter = await find_inviter(member.guild)

    if inviter:
        stats = data["invite_stats"].setdefault(
            str(inviter.id),
            {
                "real": 0,
                "total": 0,
                "left": 0,
                "fake": 0,
                "members": [],
            },
        )

        stats["total"] += 1

        age = now_utc() - member.created_at

        if age < timedelta(days=30):
            stats["fake"] += 1
        else:
            stats["real"] += 1

        stats["members"].append(
            {
                "user_id": member.id,
                "fake": age < timedelta(days=30),
                "joined": iso(now_utc()),
            }
        )

        save_data()

    # --------------------------------------------------------
    # Member roles
    # --------------------------------------------------------

    for role_id in data.get(
        "member_roles",
        [],
    ):
        role = member.guild.get_role(
            int(role_id)
        )

        if role:
            try:
                await member.add_roles(
                    role,
                    reason="APEX CLOULD™ member role",
                )
            except Exception:
                pass

    # --------------------------------------------------------
    # Welcome channel
    # --------------------------------------------------------

    channel_id = data["config"].get(
        "welcome_channel"
    )

    if channel_id:
        channel = member.guild.get_channel(
            int(channel_id)
        )

        if channel:
            try:
                await channel.send(
                    content=member.mention,
                    embed=welcome_server_embed(),
                )
            except Exception:
                pass

    # --------------------------------------------------------
    # Welcome DM
    # --------------------------------------------------------

    await dm_embed(
        member,
        welcome_dm_embed(member),
    )

    # IMPORTANT:
    # No "Member joined" log.


@bot.event
async def on_member_remove(member: discord.Member):

    if member.guild.id != GUILD_ID:
        return

    # --------------------------------------------------------
    # Invite left tracking
    # --------------------------------------------------------

    for inviter_id, stats in data.get(
        "invite_stats",
        {},
    ).items():

        for tracked in stats.get(
            "members",
            [],
        ):

            if tracked.get(
                "user_id"
            ) == member.id:

                stats["left"] = (
                    int(stats.get("left", 0)) + 1
                )

                try:
                    stats["members"].remove(
                        tracked
                    )
                except ValueError:
                    pass

                break

    save_data()

    # --------------------------------------------------------
    # Leave channel
    # --------------------------------------------------------

    channel_id = data["config"].get(
        "leave_channel"
    )

    if channel_id:
        channel = member.guild.get_channel(
            int(channel_id)
        )

        if channel:
            try:
                await channel.send(
                    embed=leave_server_embed()
                )
            except Exception:
                pass

    # --------------------------------------------------------
    # Leave DM
    # --------------------------------------------------------

    await dm_embed(
        member,
        leave_dm_embed(),
    )

    # IMPORTANT:
    # No "Member left" log.


# ============================================================
# INVITE TRACKING
# ============================================================

async def refresh_invites(guild):
    try:
        invites = await guild.invites()

        self_cache = {}

        for invite in invites:
            self_cache[invite.code] = {
                "uses": invite.uses or 0,
                "inviter": (
                    invite.inviter.id
                    if invite.inviter
                    else None
                ),
            }

        bot.invite_cache[guild.id] = self_cache

    except Exception:
        bot.invite_cache[guild.id] = {}


async def find_inviter(guild):
    old = bot.invite_cache.get(
        guild.id,
        {},
    )

    try:
        invites = await guild.invites()

    except Exception:
        return None

    inviter = None

    new_cache = {}

    for invite in invites:
        uses = invite.uses or 0

        new_cache[invite.code] = {
            "uses": uses,
            "inviter": (
                invite.inviter.id
                if invite.inviter
                else None
            ),
        }

        previous = old.get(
            invite.code,
            {},
        ).get(
            "uses",
            0,
        )

        if uses > previous:
            inviter = invite.inviter

    bot.invite_cache[guild.id] = new_cache

    return inviter


@bot.event
async def on_invite_create(invite):
    if invite.guild:
        await refresh_invites(
            invite.guild
        )


@bot.event
async def on_invite_delete(invite):
    if invite.guild:
        await refresh_invites(
            invite.guild
        )


# ============================================================
# WARNING / MODERATION DM TEXT
# ============================================================

def warning_embed(reason, count):
    description = f"""⚠️ **APEX CLOULD™ — Warning**

{ARROW} You have received a warning from the APEX CLOULD™ moderation team.

{SUPPORTER} **Reason:**
> {reason}

{ARROW} Warning count: **{count}/3**

{SIGNAL} Please make sure you follow the server rules to avoid further action."""

    return apex_embed(
        "⚠️ APEX CLOULD™ — Warning",
        description,
    )


def timeout_24h_embed():
    description = f"""🔒 **APEX CLOULD™ — 24 Hour Timeout**

{ARROW} You have reached **3 warnings**.

{ROCKET} As a result, you have been placed in a **24-hour timeout**.

{SUPPORTER} **Reason:**
> Reaching 3 active warnings.

{ARROW} Please review the server rules before participating again.

{SIGNAL_OLD} APEX CLOULD™ Moderation"""

    return apex_embed(
        "🔒 APEX CLOULD™ — 24 Hour Timeout",
        description,
    )


def kick_embed(reason):
    description = f"""👢 **APEX CLOULD™ — You Were Kicked**

{ARROW} You have been removed from the server by the APEX CLOULD™ moderation team.

{SUPPORTER} **Reason:**
> {reason}

{ARROW} If you believe this was a mistake, you may contact the APEX CLOULD™ team.

{SIGNAL_OLD} APEX CLOULD™ Moderation"""

    return apex_embed(
        "👢 APEX CLOULD™ — You Were Kicked",
        description,
    )


def ban_embed(reason):
    description = f"""🔨 **APEX CLOULD™ — You Were Banned**

{ARROW} You have been banned from the APEX CLOULD™ server.

{SUPPORTER} **Reason:**
> {reason}

{ARROW} If you believe this action was made in error, you may contact the APEX CLOULD™ team.

{SIGNAL_OLD} APEX CLOULD™ Moderation"""

    return apex_embed(
        "🔨 APEX CLOULD™ — You Were Banned",
        description,
    )


def untimeout_embed():
    description = f"""🔓 **APEX CLOULD™ — Timeout Removed**

{ARROW} Your timeout has been removed by the APEX CLOULD™ moderation team.

{ARROW} You can now participate in the server again.

{SIGNAL_OLD} Please continue following the server rules. 💚"""

    return apex_embed(
        "🔓 APEX CLOULD™ — Timeout Removed",
        description,
    )


def automod_dm_embed(reason):
    description = f"""🤖 **APEX CLOULD™ — AutoMod Action**

{ARROW} Your message was removed by the APEX CLOULD™ AutoMod system.

{SUPPORTER} **Reason:**
> {reason}

{ARROW} Please make sure your messages follow our server rules.

{SIGNAL} Repeated violations may result in further moderation action."""

    return apex_embed(
        "🤖 APEX CLOULD™ — AutoMod Action",
        description,
    )


# ============================================================
# ADMIN COMMANDS
# ============================================================

admin_group = app_commands.Group(
    name="admin",
    description="APEX CLOULD™ administration",
)


@admin_group.command(
    name="add",
    description="Add an administrator",
)
async def admin_add(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if not await require_owner(interaction):
        return

    if user.id == OWNER_ID:
        await reply_embed(
            interaction,
            error_embed(
                "Administrator",
                f"{ARROW} The owner already has every permission.",
            ),
            ephemeral=True,
        )
        return

    if user.id in data["admins"]:
        await reply_embed(
            interaction,
            error_embed(
                "Already Administrator",
                f"{ARROW} {user.mention} is already an administrator.",
            ),
            ephemeral=True,
        )
        return

    data["admins"].append(user.id)
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Administrator Added",
            f"{ARROW} {user.mention} is now an **APEX CLOULD™ Administrator**.",
        ),
    )

    await send_log(
        interaction.guild,
        "Administrator Added",
        f"{ARROW} {user.mention} was added as an administrator by {interaction.user.mention}.",
    )


@admin_group.command(
    name="remove",
    description="Remove an administrator",
)
async def admin_remove(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if not await require_owner(interaction):
        return

    if user.id not in data["admins"]:
        await reply_embed(
            interaction,
            error_embed(
                "Not Administrator",
                f"{ARROW} {user.mention} is not an administrator.",
            ),
            ephemeral=True,
        )
        return

    data["admins"].remove(user.id)
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Administrator Removed",
            f"{ARROW} {user.mention} is no longer an administrator.",
        ),
    )

    await send_log(
        interaction.guild,
        "Administrator Removed",
        f"{ARROW} {user.mention} was removed from administrators by {interaction.user.mention}.",
    )


bot.tree.add_command(admin_group)


# ============================================================
# VPS EXPIRY TRACKING COMMAND
# ============================

vps_group = app_commands.Group(name="vps", description="APEX CLOULD™ VPS expiry tracking")


def parse_uk_expiry(value: str):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    text = " ".join(value.strip().replace(",", " ").split())
    formats = [
        "%d %B %Y %I%p", "%d %B %Y %I:%M%p",
        "%d %B %Y %I %p", "%d %B %Y %I:%M %p",
        "%d %B %Y %H:%M", "%d %B %Y %H%M",
        "%d/%m/%Y %I%p", "%d/%m/%Y %I:%M%p",
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H%M",
        "%d-%m-%Y %H:%M", "%d-%m-%Y %I%p",
    ]
    # Normalize AM/PM case and accept “6 pm”.
    text = re.sub(r"(?i)\b(am|pm)\b", lambda m: m.group(1).upper(), text)
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=ZoneInfo("Europe/London")).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


@vps_group.command(name="add", description="Track a VPS and notify its owner when it expires")
@app_commands.describe(name="VPS/service name", service="Choose Free or Paid", expiry="UK time, e.g. 12 October 2026 6pm", owner="Discord member who owns this VPS")
@app_commands.choices(service=[app_commands.Choice(name="Free", value="Free"), app_commands.Choice(name="Paid", value="Paid")])
async def vps_add(interaction: discord.Interaction, name: str, service: app_commands.Choice[str], expiry: str, owner: discord.Member):
    if not await require_owner(interaction):
        return
    expires = parse_uk_expiry(expiry)
    if not expires:
        await reply_embed(interaction, error_embed("Invalid Expiry Time", f"{ARROW} Use a UK date/time such as `12 October 2026 6pm` or `12/10/2026 18:00`."), ephemeral=True)
        return
    if expires <= now_utc():
        await reply_embed(interaction, error_embed("Expiry Must Be In The Future", f"{ARROW} Enter a future UK date and time."), ephemeral=True)
        return
    key = name.strip()[:80]
    if not key:
        await reply_embed(interaction, error_embed("Missing VPS Name", f"{ARROW} Enter a VPS name."), ephemeral=True)
        return
    data.setdefault("vps", {})[key.casefold()] = {
        "name": key, "service": service.value, "owner_id": owner.id,
        "expires_at": iso(expires), "status": "Active", "notified": False,
        "created_at": iso(now_utc()),
    }
    save_data()
    uk_time = expires.astimezone(__import__("zoneinfo").ZoneInfo("Europe/London")).strftime("%d %B %Y %I:%M %p UK")
    await reply_embed(interaction, success_embed("VPS Expiry Added", f"{ARROW} **VPS:** `{key}`\n{ARROW} **Service:** `{service.value}`\n{ARROW} **Expiry:** `{uk_time}`\n{ARROW} **Owner:** {owner.mention}\n\n{SIGNAL} The bot will DM you and the owner at expiry. It will **not** suspend or modify the VPS."), ephemeral=True)


bot.tree.add_command(vps_group)


# ============================================================


# MODERATION
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick a member",
)
async def kick(
    interaction,
    user: discord.Member,
    reason: str = "No reason provided.",
):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await reply_embed(
            interaction,
            error_embed(
                "Protected User",
                f"{ARROW} The owner cannot be kicked.",
            ),
            ephemeral=True,
        )
        return

    await dm_embed(
        user,
        kick_embed(reason),
    )

    try:
        await user.kick(
            reason=reason
        )

        await reply_embed(
            interaction,
            success_embed(
                "Member Kicked",
                f"{ARROW} {user.mention} has been kicked.\n"
                f"{SUPPORTER} Reason: `{reason}`",
            ),
        )

        await send_log(
            interaction.guild,
            "Member Kicked",
            f"{ARROW} Member: {user.mention}\n"
            f"{ARROW} Moderator: {interaction.user.mention}\n"
            f"{SUPPORTER} Reason: `{reason}`",
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Kick Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="ban",
    description="Ban a member",
)
async def ban(
    interaction,
    user: discord.Member,
    reason: str = "No reason provided.",
):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await reply_embed(
            interaction,
            error_embed(
                "Protected User",
                f"{ARROW} The owner cannot be banned.",
            ),
            ephemeral=True,
        )
        return

    await dm_embed(
        user,
        ban_embed(reason),
    )

    try:
        await user.ban(
            reason=reason
        )

        await reply_embed(
            interaction,
            success_embed(
                "Member Banned",
                f"{ARROW} {user.mention} has been banned.",
            ),
        )

        await send_log(
            interaction.guild,
            "Member Banned",
            f"{ARROW} Member: {user.mention}\n"
            f"{ARROW} Moderator: {interaction.user.mention}\n"
            f"{SUPPORTER} Reason: `{reason}`",
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Ban Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="timeout",
    description="Timeout a member",
)
@app_commands.describe(
    duration="Duration in minutes",
    reason="Reason",
)
async def timeout(
    interaction,
    user: discord.Member,
    duration: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided.",
):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await reply_embed(
            interaction,
            error_embed(
                "Protected User",
                f"{ARROW} The owner cannot be timed out.",
            ),
            ephemeral=True,
        )
        return

    until = now_utc() + timedelta(
        minutes=duration
    )

    try:
        await user.timeout(
            until,
            reason=reason,
        )

        await dm_embed(
            user,
            apex_embed(
                "🔒 APEX CLOULD™ — Timeout",
                f"""{ARROW} You have been placed in a timeout by the APEX CLOULD™ moderation team.

{SUPPORTER} **Duration:** `{duration}` minutes

{SUPPORTER} **Reason:**
> {reason}

{SIGNAL} Please follow the server rules.""",
            ),
        )

        await reply_embed(
            interaction,
            success_embed(
                "Member Timed Out",
                f"{ARROW} {user.mention} has been timed out for **{duration} minutes**.",
            ),
        )

        await send_log(
            interaction.guild,
            "Member Timeout",
            f"{ARROW} Member: {user.mention}\n"
            f"{ARROW} Moderator: {interaction.user.mention}\n"
            f"{ARROW} Duration: `{duration}` minutes\n"
            f"{SUPPORTER} Reason: `{reason}`",
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Timeout Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="untimeout",
    description="Remove a member timeout",
)
async def untimeout(
    interaction,
    user: discord.Member,
):
    if not await require_admin(interaction):
        return

    try:
        await user.timeout(
            None,
            reason=f"Timeout removed by {interaction.user}",
        )

        await dm_embed(
            user,
            untimeout_embed(),
        )

        await reply_embed(
            interaction,
            success_embed(
                "Timeout Removed",
                f"{ARROW} {user.mention} can participate again.",
            ),
        )

        await send_log(
            interaction.guild,
            "Timeout Removed",
            f"{ARROW} Member: {user.mention}\n"
            f"{ARROW} Moderator: {interaction.user.mention}",
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Unable to Remove Timeout",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="warn",
    description="Warn a member",
)
async def warn(
    interaction,
    user: discord.Member,
    reason: str = "No reason provided.",
):
    if not await require_admin(interaction):
        return

    if user.id == OWNER_ID:
        await reply_embed(
            interaction,
            error_embed(
                "Protected User",
                f"{ARROW} The owner cannot be warned.",
            ),
            ephemeral=True,
        )
        return

    key = str(user.id)

    warnings = data["warnings"].setdefault(
        key,
        [],
    )

    warnings.append(
        {
            "reason": reason,
            "moderator": interaction.user.id,
            "created_at": iso(now_utc()),
        }
    )

    count = len(warnings)

    save_data()

    await dm_embed(
        user,
        warning_embed(
            reason,
            count,
        ),
    )

    if count >= 3:
        try:
            await user.timeout(
                now_utc()
                + timedelta(days=1),
                reason="Reached 3 active warnings.",
            )

            await dm_embed(
                user,
                timeout_24h_embed(),
            )

            action = (
                f"{ARROW} {user.mention} reached **3 warnings** and received a **24-hour timeout**."
            )

        except Exception:
            action = (
                f"{ARROW} {user.mention} reached **3 warnings**, "
                "but the automatic timeout could not be applied."
            )

    else:
        action = (
            f"{ARROW} {user.mention} received warning **{count}/3**."
        )

    await reply_embed(
        interaction,
        success_embed(
            "Warning Issued",
            f"{action}\n\n"
            f"{SUPPORTER} Reason: `{reason}`",
        ),
    )

    await send_log(
        interaction.guild,
        "Warning Issued",
        f"{ARROW} Member: {user.mention}\n"
        f"{ARROW} Moderator: {interaction.user.mention}\n"
        f"{ARROW} Count: **{count}/3**\n"
        f"{SUPPORTER} Reason: `{reason}`",
    )


@bot.tree.command(
    name="warnclear",
    description="Clear a member's warnings",
)
async def warnclear(
    interaction,
    user: discord.Member,
):
    if not await require_admin(interaction):
        return

    data["warnings"][str(user.id)] = []
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Warnings Cleared",
            f"{ARROW} All warnings for {user.mention} have been cleared.",
        ),
    )

    await send_log(
        interaction.guild,
        "Warnings Cleared",
        f"{ARROW} Member: {user.mention}\n"
        f"{ARROW} Moderator: {interaction.user.mention}",
    )


@bot.tree.command(
    name="warnings",
    description="View a member's warnings",
)
async def warnings(
    interaction,
    user: discord.Member,
):
    if not await require_admin(interaction):
        return

    items = data["warnings"].get(
        str(user.id),
        [],
    )

    if not items:
        text = f"{ARROW} {user.mention} has no active warnings."
    else:
        lines = []

        for i, item in enumerate(
            items,
            start=1,
        ):
            lines.append(
                f"**{i}.** {item.get('reason', 'No reason')} "
                f"— <@{item.get('moderator')}>"
            )

        text = "\n".join(lines)

    await reply_embed(
        interaction,
        info_embed(
            f"Warnings — {user.display_name}",
            text,
        ),
        ephemeral=True,
    )


# ============================================================
# CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Clear messages. Use 'all' to clear as much as Discord allows.",
)
async def clear(
    interaction,
    amount: str = "10",
):
    if not await require_admin(interaction):
        return

    channel = interaction.channel

    try:
        if amount.lower() == "all":
            amount_int = 100
        else:
            amount_int = int(amount)

        amount_int = max(
            1,
            min(
                amount_int,
                100,
            ),
        )

    except ValueError:
        await reply_embed(
            interaction,
            error_embed(
                "Invalid Amount",
                f"{ARROW} Enter a number or `all`.",
            ),
            ephemeral=True,
        )
        return

    try:
        await interaction.response.defer(
            ephemeral=True
        )

        deleted = await channel.purge(
            limit=amount_int
        )

        await interaction.followup.send(
            embed=success_embed(
                "Messages Cleared",
                f"{ARROW} Deleted **{len(deleted)}** messages.",
            ),
            ephemeral=True,
        )

        await send_log(
            interaction.guild,
            "Messages Cleared",
            f"{ARROW} Channel: {channel.mention}\n"
            f"{ARROW} Moderator: {interaction.user.mention}\n"
            f"{ARROW} Amount: `{len(deleted)}`",
        )

    except Exception as e:
        await interaction.followup.send(
            embed=error_embed(
                "Clear Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


# ============================================================
# /MSG
# ============================================================

@bot.tree.command(
    name="msg",
    description="Send an APEX CLOULD™ embed to a channel",
)
@app_commands.describe(
    channel="Destination channel",
    title="Optional embed title",
    description="Message content",
)
async def msg(
    interaction,
    channel: discord.TextChannel,
    description: str,
    title: str = "",
):
    if not await require_admin(interaction):
        return

    if not title:
        title = "APEX CLOULD™"

    embed = apex_embed(
        title,
        description,
    )

    try:
        await channel.send(
            embed=embed
        )

        await reply_embed(
            interaction,
            success_embed(
                "Message Sent",
                f"{ARROW} Your message was sent to {channel.mention}.",
            ),
            ephemeral=True,
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Message Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


# ============================================================
# OWNER DM
# ============================================================

@bot.tree.command(
    name="dm",
    description="Send an APEX CLOULD™ DM",
)
@app_commands.describe(
    target="Mention a user or type all",
    title="Embed title",
    description="Embed message",
)
async def dm_command(
    interaction,
    target: str,
    title: str,
    description: str,
):
    if not await require_owner(interaction):
        return

    embed = apex_embed(
        title,
        description,
    )

    if target.lower().strip() == "all":
        members = [
            m
            for m in interaction.guild.members
            if not m.bot
        ]

        await interaction.response.send_message(
            embed=info_embed(
                "Mass DM Started",
                f"{ARROW} Targeted members: **{len(members)}**\n"
                f"{ROCKET} Sending messages with Discord rate-limit handling.",
            ),
            ephemeral=True,
        )

        success = 0
        failed = 0

        for member in members:
            try:
                await member.send(
                    embed=embed
                )
                success += 1

            except discord.HTTPException:
                failed += 1

            except Exception:
                failed += 1

            await asyncio.sleep(
                1.0
            )

        await interaction.followup.send(
            embed=success_embed(
                "Mass DM Finished",
                f"{ARROW} Total targeted: **{len(members)}**\n"
                f"{ARROW} Successfully sent: **{success}**\n"
                f"{ARROW} Failed: **{failed}**\n\n"
                f"{SIGNAL} APEX CLOULD™ DM system",
            ),
            ephemeral=True,
        )

        return

    user_id = re.search(
        r"\d{15,25}",
        target,
    )

    if not user_id:
        await reply_embed(
            interaction,
            error_embed(
                "Invalid Target",
                f"{ARROW} Mention a user or use `all`.",
            ),
            ephemeral=True,
        )
        return

    user = interaction.guild.get_member(
        int(user_id.group())
    )

    if not user:
        try:
            user = await bot.fetch_user(
                int(user_id.group())
            )
        except Exception:
            user = None

    if not user:
        await reply_embed(
            interaction,
            error_embed(
                "User Not Found",
                f"{ARROW} I could not find that user.",
            ),
            ephemeral=True,
        )
        return

    ok = await dm_embed(
        user,
        embed,
    )

    if ok:
        await reply_embed(
            interaction,
            success_embed(
                "DM Sent",
                f"{ARROW} Your APEX CLOULD™ message was sent to {user.mention}.",
            ),
            ephemeral=True,
        )
    else:
        await reply_embed(
            interaction,
            error_embed(
                "DM Failed",
                f"{ARROW} Discord could not deliver the message to {user.mention}.",
            ),
            ephemeral=True,
        )


# ============================================================
# CONFIG
# ============================================================

config_group = app_commands.Group(
    name="config",
    description="APEX CLOULD™ configuration",
)


@config_group.command(
    name="logs",
    description="Set the logs channel",
)
async def config_logs(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return

    data["config"]["logs_channel"] = channel.id
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Logs Channel Updated",
            f"{ARROW} Logs will now be sent to {channel.mention}.",
        ),
        ephemeral=True,
    )


@config_group.command(
    name="welcome",
    description="Set welcome channel",
)
async def config_welcome(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return

    data["config"]["welcome_channel"] = channel.id
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Welcome Channel Updated",
            f"{ARROW} Welcome messages will be sent to {channel.mention}.",
        ),
        ephemeral=True,
    )


@config_group.command(
    name="leave",
    description="Set leave channel",
)
async def config_leave(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return

    data["config"]["leave_channel"] = channel.id
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Leave Channel Updated",
            f"{ARROW} Leave messages will be sent to {channel.mention}.",
        ),
        ephemeral=True,
    )


@config_group.command(
    name="memberrole",
    description="Set the automatic member role",
)
async def config_memberrole(
    interaction,
    role: discord.Role,
):
    if not await require_admin(interaction):
        return

    data["member_roles"] = [role.id]
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Member Role Updated",
            f"{ARROW} New members will receive {role.mention}.",
        ),
        ephemeral=True,
    )


@config_group.command(
    name="roleadd",
    description="Add an automatic member role",
)
async def config_role_add(
    interaction,
    role: discord.Role,
):
    if not await require_admin(interaction):
        return

    if role.id not in data["member_roles"]:
        data["member_roles"].append(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Member Role Added",
            f"{ARROW} {role.mention} was added.",
        ),
        ephemeral=True,
    )


@config_group.command(
    name="roleremove",
    description="Remove an automatic member role",
)
async def config_role_remove(
    interaction,
    role: discord.Role,
):
    if not await require_admin(interaction):
        return

    if role.id in data["member_roles"]:
        data["member_roles"].remove(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Member Role Removed",
            f"{ARROW} {role.mention} was removed.",
        ),
        ephemeral=True,
    )


bot.tree.add_command(config_group)


# ============================================================
# ROLE / PROMOTION
# ============================================================

@bot.tree.command(
    name="role",
    description="Add or remove a role",
)
@app_commands.describe(
    action="add or remove",
    user="Member",
    role="Role",
)
async def role_command(
    interaction,
    action: str,
    user: discord.Member,
    role: discord.Role,
):
    if not await require_admin(interaction):
        return

    action = action.lower()

    try:
        if action == "add":
            await user.add_roles(
                role,
                reason=f"APEX CLOULD™ role command by {interaction.user}",
            )

            text = (
                f"{ARROW} {role.mention} was added to {user.mention}."
            )

        elif action == "remove":
            await user.remove_roles(
                role,
                reason=f"APEX CLOULD™ role command by {interaction.user}",
            )

            text = (
                f"{ARROW} {role.mention} was removed from {user.mention}."
            )

        else:
            text = (
                f"{ARROW} Use `add` or `remove`."
            )

            await reply_embed(
                interaction,
                error_embed(
                    "Invalid Action",
                    text,
                ),
                ephemeral=True,
            )
            return

        await reply_embed(
            interaction,
            success_embed(
                "Role Updated",
                text,
            ),
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Role Update Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="promote",
    description="Promote a member",
)
async def promote(
    interaction,
    user: discord.Member,
    role: discord.Role,
):
    if not await require_admin(interaction):
        return

    try:
        await user.add_roles(
            role,
            reason=f"APEX CLOULD™ promotion by {interaction.user}",
        )

        await reply_embed(
            interaction,
            success_embed(
                "Promotion Complete",
                f"{ARROW} {user.mention} has been promoted to {role.mention}.",
            ),
        )

        await send_log(
            interaction.guild,
            "Member Promoted",
            f"{ARROW} Member: {user.mention}\n"
            f"{ARROW} Role: {role.mention}\n"
            f"{ARROW} By: {interaction.user.mention}",
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Promotion Failed",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )


# ============================================================
# AUTOMOD
# ============================================================

URL_PATTERN = re.compile(
    r"(https?://|www\.|discord\.gg/|discord\.com/invite/|"
    r"tiktok\.com/|youtube\.com/|youtu\.be/)",
    re.IGNORECASE,
)


def has_automod_bypass(member):
    if member.id == OWNER_ID:
        return True

    bypass = set(
        int(x)
        for x in data["automod"].get(
            "bypass_roles",
            [],
        )
    )

    return any(
        role.id in bypass
        for role in member.roles
    )


def contains_badword(content):
    lower = content.lower()

    for word in data["automod"].get(
        "badwords",
        [],
    ):
        if word.lower() in lower:
            return word

    return None


@bot.tree.command(
    name="automod",
    description="View or control APEX CLOULD™ AutoMod",
)
@app_commands.describe(
    enabled="Set AutoMod on/off. Leave empty to view status.",
)
async def automod(
    interaction,
    enabled: Optional[bool] = None,
):
    if not await require_admin(interaction):
        return

    if enabled is not None:
        data["automod"]["enabled"] = enabled
        save_data()

        state = (
            "enabled"
            if enabled
            else "disabled"
        )

        await send_log(
            interaction.guild,
            "AutoMod Updated",
            f"{ARROW} AutoMod was **{state}** by {interaction.user.mention}.",
        )

    status = (
        "🟢 ON"
        if data["automod"]["enabled"]
        else "🔴 OFF"
    )

    links = (
        "🟢 ON"
        if data["automod"]["links_enabled"]
        else "🔴 OFF"
    )

    badwords = (
        "🟢 ON"
        if data["automod"]["badwords_enabled"]
        else "🔴 OFF"
    )

    await reply_embed(
        interaction,
        info_embed(
            "APEX CLOULD™ AutoMod",
            f"""{ARROW} **AutoMod:** {status}
{ARROW} **Link Protection:** {links}
{ARROW} **Bad-Word Protection:** {badwords}

{SUPPORTER} Link violations are deleted and can result in a **10-minute timeout**.
{SUPPORTER} Bad-word violations are automatically handled.
{SIGNAL} Configured bypass roles are excluded.""",
        ),
        ephemeral=True,
    )


automod_bypass_group = app_commands.Group(
    name="automodbypass",
    description="Manage AutoMod bypass roles",
)


@automod_bypass_group.command(
    name="add",
    description="Add an AutoMod bypass role",
)
async def automodbypass_add(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id not in data["automod"]["bypass_roles"]:
        data["automod"]["bypass_roles"].append(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "AutoMod Bypass Added",
            f"{ARROW} {role.mention} can now bypass AutoMod.",
        ),
        ephemeral=True,
    )


@automod_bypass_group.command(
    name="remove",
    description="Remove an AutoMod bypass role",
)
async def automodbypass_remove(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id in data["automod"]["bypass_roles"]:
        data["automod"]["bypass_roles"].remove(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "AutoMod Bypass Removed",
            f"{ARROW} {role.mention} no longer bypasses AutoMod.",
        ),
        ephemeral=True,
    )


@automod_bypass_group.command(
    name="list",
    description="List AutoMod bypass roles",
)
async def automodbypass_list(
    interaction,
):
    if not await require_owner(interaction):
        return

    roles = []

    for role_id in data["automod"].get(
        "bypass_roles",
        [],
    ):
        role = interaction.guild.get_role(
            int(role_id)
        )

        if role:
            roles.append(
                f"{ARROW} {role.mention}"
            )

    text = (
        "\n".join(roles)
        if roles
        else f"{ARROW} No AutoMod bypass roles configured."
    )

    await reply_embed(
        interaction,
        info_embed(
            "AutoMod Bypass Roles",
            text,
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    automod_bypass_group
)


# ============================================================
# BADWORDS
# ============================================================

badword_group = app_commands.Group(
    name="badword",
    description="Manage bad words",
)


@badword_group.command(
    name="add",
    description="Add a bad word",
)
async def badword_add(
    interaction,
    word: str,
):
    if not await require_admin(interaction):
        return

    word = word.strip().lower()

    if not word:
        await reply_embed(
            interaction,
            error_embed(
                "Invalid Word",
                f"{ARROW} Enter a valid word.",
            ),
            ephemeral=True,
        )
        return

    if word not in data["automod"]["badwords"]:
        data["automod"]["badwords"].append(
            word
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Bad Word Added",
            f"{ARROW} The word has been added to APEX CLOULD™ AutoMod.",
        ),
        ephemeral=True,
    )


@badword_group.command(
    name="remove",
    description="Remove a bad word",
)
async def badword_remove(
    interaction,
    word: str,
):
    if not await require_admin(interaction):
        return

    word = word.strip().lower()

    if word in data["automod"]["badwords"]:
        data["automod"]["badwords"].remove(
            word
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Bad Word Removed",
            f"{ARROW} The word has been removed from AutoMod.",
        ),
        ephemeral=True,
    )


@badword_group.command(
    name="list",
    description="List configured bad words",
)
async def badword_list(
    interaction,
):
    if not await require_admin(interaction):
        return

    words = data["automod"]["badwords"]

    if not words:
        text = (
            f"{ARROW} No bad words are configured."
        )
    else:
        text = "\n".join(
            f"{ARROW} `{word}`"
            for word in words
        )

    await reply_embed(
        interaction,
        info_embed(
            "Bad Words",
            text,
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    badword_group
)


# ============================================================
# LOCKDOWN
# ============================================================

@bot.tree.command(
    name="lockdown",
    description="Lock down the server",
)
async def lockdown(
    interaction,
):
    if not await require_admin(interaction):
        return

    guild = interaction.guild

    allowed_roles = [
        guild.get_role(
            int(role_id)
        )
        for role_id in data["lockdown"].get(
            "allowed_roles",
            [],
        )
    ]

    allowed_roles = [
        role
        for role in allowed_roles
        if role
    ]

    changed = 0

    for channel in guild.text_channels:
        try:
            overwrite = channel.overwrites_for(
                guild.default_role
            )

            overwrite.send_messages = False

            await channel.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason="APEX CLOULD™ lockdown",
            )

            for role in allowed_roles:
                overwrite = channel.overwrites_for(
                    role
                )

                overwrite.send_messages = True

                await channel.set_permissions(
                    role,
                    overwrite=overwrite,
                    reason="APEX CLOULD™ lockdown allowed role",
                )

            changed += 1

        except Exception:
            pass

    data["lockdown"]["active"] = True
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Server Lockdown",
            f"{ARROW} Lockdown has been enabled.\n"
            f"{ARROW} Channels updated: **{changed}**\n\n"
            f"{SUPPORTER} Configured lockdown roles remain allowed.",
        ),
    )

    await send_log(
        guild,
        "Server Lockdown",
        f"{ARROW} Lockdown enabled by {interaction.user.mention}.",
    )


@bot.tree.command(
    name="unlockdown",
    description="Remove server lockdown",
)
async def unlockdown(
    interaction,
):
    if not await require_admin(interaction):
        return

    guild = interaction.guild

    changed = 0

    for channel in guild.text_channels:
        try:
            overwrite = channel.overwrites_for(
                guild.default_role
            )

            overwrite.send_messages = None

            await channel.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason="APEX CLOULD™ unlockdown",
            )

            changed += 1

        except Exception:
            pass

    data["lockdown"]["active"] = False
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Server Unlocked",
            f"{ARROW} Lockdown has been removed from **{changed}** channels.",
        ),
    )

    await send_log(
        guild,
        "Server Unlockdown",
        f"{ARROW} Lockdown disabled by {interaction.user.mention}.",
    )


lockdown_role_group = app_commands.Group(
    name="lockdownrole",
    description="Manage lockdown allowed roles",
)


@lockdown_role_group.command(
    name="add",
    description="Add a lockdown allowed role",
)
async def lockdownrole_add(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id not in data["lockdown"]["allowed_roles"]:
        data["lockdown"]["allowed_roles"].append(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Lockdown Role Added",
            f"{ARROW} {role.mention} can now speak during lockdown.",
        ),
        ephemeral=True,
    )


@lockdown_role_group.command(
    name="remove",
    description="Remove a lockdown allowed role",
)
async def lockdownrole_remove(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id in data["lockdown"]["allowed_roles"]:
        data["lockdown"]["allowed_roles"].remove(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Lockdown Role Removed",
            f"{ARROW} {role.mention} is no longer allowed during lockdown.",
        ),
        ephemeral=True,
    )


@lockdown_role_group.command(
    name="list",
    description="List lockdown roles",
)
async def lockdownrole_list(
    interaction,
):
    if not await require_owner(interaction):
        return

    roles = []

    for role_id in data["lockdown"].get(
        "allowed_roles",
        [],
    ):
        role = interaction.guild.get_role(
            int(role_id)
        )

        if role:
            roles.append(
                f"{ARROW} {role.mention}"
            )

    text = (
        "\n".join(roles)
        if roles
        else f"{ARROW} No lockdown roles configured."
    )

    await reply_embed(
        interaction,
        info_embed(
            "Lockdown Roles",
            text,
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    lockdown_role_group
)


# ============================================================
# TICKET SYSTEM
# ============================================================

TICKET_TYPES = {
    "support": {
        "name": "General Support",
        "prefix": "APEX-SUPPORT",
    },
    "partnership": {
        "name": "Partnership / Staff",
        "prefix": "APEX-PARTNERSHIP",
    },
    "reward": {
        "name": "Reward Claim",
        "prefix": "APEX-REWARD",
    },
    "buy": {
        "name": "Buy",
        "prefix": "APEX-BUY",
    },
    "staff": {
        "name": "Staff Application",
        "prefix": "APEX-STAFF",
    },
}


TICKET_PANEL_DESCRIPTION = f"""{ARROW} **Need Help? Please Read Carefully**
{ARROW} Click the button that best matches the type of support you need.
{ARROW} Provide a clear and detailed description of your issue.
{ARROW} For remote timeout issues, include when it happens, how often, and any screenshots.
{ARROW} Missing or vague information may cause delays or timeouts.
{ARROW} Include all relevant details like screenshots, error messages, or steps to reproduce.
{ARROW} Repeated spam or unnecessary pinging of staff may lead to a timeout.
{ARROW} Reward Claim: No alt accounts, no rejoin counts, no fake counts. Your reward will be counted from Falcon.

{ARROW} Thank you for helping us help you! <a:69:1551174351913746463>"""


def next_ticket_name(ticket_type):
    key = ticket_type.upper()

    data["ticket_counter"][key] = (
        int(
            data["ticket_counter"].get(
                key,
                0,
            )
        )
        + 1
    )

    number = data["ticket_counter"][key]

    save_data()

    prefix = TICKET_TYPES[
        ticket_type
    ]["prefix"]

    return (
        f"{prefix}-{number:03d}"
    )


def ticket_staff_overwrites(
    guild,
    channel,
):
    pass


async def create_ticket(
    interaction,
    ticket_type,
):
    guild = interaction.guild
    member = interaction.user

    # Check if the member already has a ticket.
    for ticket in data["tickets"].values():
        if (
            int(ticket.get("creator_id", 0))
            == member.id
            and ticket.get("closed") is not True
        ):
            channel = guild.get_channel(
                int(ticket["channel_id"])
            )

            if channel:
                await reply_embed(
                    interaction,
                    error_embed(
                        "Ticket Already Open",
                        f"{ARROW} You already have an open ticket: {channel.mention}",
                    ),
                    ephemeral=True,
                )
                return

    # Staff Application ticket:
    # Applicant + owner only.
    # Other ticket types:
    # creator + configured ticket roles + owner.
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True,
            read_message_history=True,
        ),
    }

    if ticket_type == "staff":

        owner = guild.get_member(
            OWNER_ID
        )

        if owner:
            overwrites[owner] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )
            )

    else:
        for role_id in data.get(
            "ticket_roles",
            [],
        ):
            role = guild.get_role(
                int(role_id)
            )

            if role:
                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                    )
                )

        owner = guild.get_member(
            OWNER_ID
        )

        if owner:
            overwrites[owner] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )
            )

    category = discord.utils.get(
        guild.categories,
        name=TICKET_CATEGORY_NAME,
    )

    if not category:
        try:
            category = await guild.create_category(
                TICKET_CATEGORY_NAME
            )
        except Exception:
            category = None

    name = next_ticket_name(
        ticket_type
    )

    channel = await guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        reason="APEX CLOULD™ ticket opened",
    )

    ticket_id = name

    data["tickets"][ticket_id] = {
        "id": ticket_id,
        "channel_id": channel.id,
        "creator_id": member.id,
        "type": ticket_type,
        "created_at": iso(now_utc()),
        "claimed_by": None,
        "closed": False,
        "last_staff_reply": None,
        "last_user_reply": iso(now_utc()),
        "reminder_sent": False,
        "last_message_id": None,
    }

    save_data()

    await channel.send(
        content=member.mention,
        embed=apex_embed(
            f"🎫 APEX CLOULD™ — {TICKET_TYPES[ticket_type]['name']}",
            f"""{ARROW} Welcome to your APEX CLOULD™ support ticket.

{SUPPORT} **Ticket Information**
{ARROW} Ticket: `{ticket_id}`
{ARROW} Opened by: {member.mention}
{ARROW} Type: **{TICKET_TYPES[ticket_type]['name']}**

{ROCKET} Please explain your issue clearly and provide screenshots, errors, or other useful information.

{SUPPORTER} A member of the support team will assist you as soon as possible.

{SIGNAL} Please avoid unnecessary staff pinging.""",
        ),
        view=TicketControlView(),
    )

    await reply_embed(
        interaction,
        success_embed(
            "Ticket Opened",
            f"{ARROW} Your ticket has been created: {channel.mention}",
        ),
        ephemeral=True,
    )

    await send_log(
        guild,
        "Ticket Opened",
        f"{ARROW} Ticket: `{ticket_id}`\n"
        f"{ARROW} User: {member.mention}\n"
        f"{ARROW} Type: **{TICKET_TYPES[ticket_type]['name']}**",
    )


class TicketPanelView(
    discord.ui.View
):
    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="General Support",
        style=discord.ButtonStyle.success,
        emoji=TICKET_EMOJIS["support"],
        custom_id="apex_ticket_support",
    )
    async def support(
        self,
        interaction,
        button,
    ):
        await create_ticket(
            interaction,
            "support",
        )

    @discord.ui.button(
        label="Partnership / Staff",
        style=discord.ButtonStyle.success,
        emoji=TICKET_EMOJIS["partnership"],
        custom_id="apex_ticket_partnership",
    )
    async def partnership(
        self,
        interaction,
        button,
    ):
        await create_ticket(
            interaction,
            "partnership",
        )

    @discord.ui.button(
        label="Reward Claim",
        style=discord.ButtonStyle.success,
        emoji=TICKET_EMOJIS["reward"],
        custom_id="apex_ticket_reward",
    )
    async def reward(
        self,
        interaction,
        button,
    ):
        await create_ticket(
            interaction,
            "reward",
        )

    @discord.ui.button(
        label="Buy",
        style=discord.ButtonStyle.success,
        emoji=TICKET_EMOJIS["buy"],
        custom_id="apex_ticket_buy",
    )
    async def buy(
        self,
        interaction,
        button,
    ):
        await create_ticket(
            interaction,
            "buy",
        )

    @discord.ui.button(
        label="Staff Application",
        style=discord.ButtonStyle.primary,
        emoji=TICKET_EMOJIS["staff"],
        custom_id="apex_ticket_staff",
    )
    async def staff(
        self,
        interaction,
        button,
    ):
        await create_ticket(
            interaction,
            "staff",
        )


class TicketControlView(
    discord.ui.View
):
    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        custom_id="apex_ticket_claim",
    )
    async def claim(
        self,
        interaction,
        button,
    ):
        if not await require_ticket_access(
            interaction
        ):
            return

        ticket = find_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket:
            await reply_embed(
                interaction,
                error_embed(
                    "Ticket Not Found",
                    f"{ARROW} This channel is not registered as a ticket.",
                ),
                ephemeral=True,
            )
            return

        ticket["claimed_by"] = interaction.user.id
        save_data()

        await reply_embed(
            interaction,
            success_embed(
                "Ticket Claimed",
                f"{ARROW} {interaction.user.mention} has claimed this ticket.",
            ),
        )

        await send_log(
            interaction.guild,
            "Ticket Claimed",
            f"{ARROW} Ticket: `{ticket['id']}`\n"
            f"{ARROW} Claimed by: {interaction.user.mention}",
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="apex_ticket_close",
    )
    async def close(
        self,
        interaction,
        button,
    ):
        ticket = find_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket:
            await reply_embed(
                interaction,
                error_embed(
                    "Ticket Not Found",
                    f"{ARROW} This is not a registered ticket.",
                ),
                ephemeral=True,
            )
            return

        if (
            interaction.user.id
            != ticket["creator_id"]
            and not has_ticket_access(
                interaction.user
            )
        ):
            await reply_embed(
                interaction,
                error_embed(
                    "Permission Denied",
                    f"{ARROW} Only the ticket owner or ticket staff can close this ticket.",
                ),
                ephemeral=True,
            )
            return

        await close_ticket(
            interaction.channel,
            ticket,
            automatic=False,
            closed_by=interaction.user,
        )


def find_ticket_by_channel(
    channel_id,
):
    for ticket in data["tickets"].values():
        if int(
            ticket.get("channel_id", 0)
        ) == channel_id:
            return ticket

    return None


async def generate_transcript(
    channel,
):
    lines = []

    try:
        async for message in channel.history(
            limit=None,
            oldest_first=True,
        ):
            timestamp = message.created_at.strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )

            content = message.content or ""

            if message.attachments:
                content += " " + " ".join(
                    attachment.url
                    for attachment in message.attachments
                )

            lines.append(
                f"[{timestamp}] "
                f"{message.author} "
                f"({message.author.id}): "
                f"{content}"
            )

    except Exception as e:
        lines.append(
            f"Transcript error: {e}"
        )

    text = "\n".join(lines)

    return io.BytesIO(
        text.encode(
            "utf-8",
            errors="replace",
        )
    )


def manual_close_embed(
    user,
):
    return apex_embed(
        "🎫 APEX CLOULD™ — Ticket Closed",
        f"""Hello {user.display_name} 👋

{ARROW} Your ticket has been **closed by our support team**.

{SUPPORT} Thank you for contacting **APEX CLOULD™ Support**.

📎 **Your ticket transcript is attached** to this message for your records.

{SUPPORTER} **Need more help?**

{ARROW} If you still need assistance, you can open a new ticket whenever you're ready.

{SIGNAL} **APEX CLOULD™ Support**
We're always here to help. 💚""",
    )


def automatic_close_embed(
    user,
):
    return apex_embed(
        "🎫 APEX CLOULD™ — Ticket Closed",
        f"""Hello {user.display_name} 👋

{ARROW} Your support ticket has been **closed and deleted due to inactivity**.

{SUPPORT} We didn't receive a response from you within **8 hours** after our support team replied.

📎 **Your ticket transcript is attached to this message** for your records.

{SUPPORTER} **Need further help?**

{ARROW} You can open a new ticket whenever you're ready, and our team will be happy to assist you.

{SIGNAL} **APEX CLOULD™ Support**
Thank you for contacting us! 💚""",
    )


async def close_ticket(
    channel,
    ticket,
    *,
    automatic,
    closed_by,
):
    guild = channel.guild

    member = guild.get_member(
        int(ticket["creator_id"])
    )

    transcript = await generate_transcript(
        channel
    )

    transcript.seek(0)

    if automatic:
        embed = automatic_close_embed(
            member
            if member
            else await bot.fetch_user(
                int(ticket["creator_id"])
            )
        )
    else:
        embed = manual_close_embed(
            member
            if member
            else await bot.fetch_user(
                int(ticket["creator_id"])
            )
        )

    user = member

    if not user:
        try:
            user = await bot.fetch_user(
                int(ticket["creator_id"])
            )
        except Exception:
            user = None

    dm_success = False

    if user:
        try:
            await user.send(
                embed=embed,
                file=discord.File(
                    transcript,
                    filename=f"{ticket['id']}-transcript.txt",
                ),
            )

            dm_success = True

        except Exception:
            dm_success = False

    ticket["closed"] = True
    ticket["closed_at"] = iso(
        now_utc()
    )
    ticket["closed_by"] = (
        closed_by.id
        if closed_by
        else None
    )

    save_data()

    await send_log(
        guild,
        "Ticket Closed",
        f"""{ARROW} Ticket: `{ticket['id']}`
{ARROW} Type: **{TICKET_TYPES[ticket['type']]['name']}**
{ARROW} Closed by: {closed_by.mention if closed_by else 'Automatic system'}
{ARROW} Transcript DM: **{'Success' if dm_success else 'Failed'}**""",
    )

    try:
        await channel.delete(
            reason="APEX CLOULD™ ticket closed",
        )
    except Exception:
        pass


@bot.tree.command(
    name="close",
    description="Close the current ticket",
)
async def close_command(
    interaction,
):
    ticket = find_ticket_by_channel(
        interaction.channel.id
    )

    if not ticket:
        await reply_embed(
            interaction,
            error_embed(
                "Not a Ticket",
                f"{ARROW} This channel is not a registered APEX CLOULD™ ticket.",
            ),
            ephemeral=True,
        )
        return

    if (
        interaction.user.id
        != ticket["creator_id"]
        and not has_ticket_access(
            interaction.user
        )
    ):
        await reply_embed(
            interaction,
            error_embed(
                "Permission Denied",
                f"{ARROW} Only the ticket owner or ticket staff can close this ticket.",
            ),
            ephemeral=True,
        )
        return

    await close_ticket(
        interaction.channel,
        ticket,
        automatic=False,
        closed_by=interaction.user,
    )


ticket_group = app_commands.Group(
    name="ticket",
    description="Ticket management",
)


@ticket_group.command(
    name="setup",
    description="Send the APEX CLOULD™ ticket panel",
)
async def ticket_setup(
    interaction,
):
    if not await require_admin(interaction):
        return

    embed = apex_embed(
        "🎫 APEX CLOULD™ Support",
        TICKET_PANEL_DESCRIPTION,
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketPanelView(),
    )

    await reply_embed(
        interaction,
        success_embed(
            "Ticket Panel Created",
            f"{ARROW} The ticket panel is now active in {interaction.channel.mention}.",
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    ticket_group
)


# ============================================================
# TICKET ROLE MANAGEMENT
# ============================================================

ticketrole_group = app_commands.Group(
    name="ticketrole",
    description="Manage ticket staff roles",
)


@ticketrole_group.command(
    name="add",
    description="Add a ticket staff role",
)
async def ticketrole_add(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id not in data["ticket_roles"]:
        data["ticket_roles"].append(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Ticket Role Added",
            f"{ARROW} {role.mention} can now access standard tickets.",
        ),
        ephemeral=True,
    )


@ticketrole_group.command(
    name="remove",
    description="Remove a ticket staff role",
)
async def ticketrole_remove(
    interaction,
    role: discord.Role,
):
    if not await require_owner(interaction):
        return

    if role.id in data["ticket_roles"]:
        data["ticket_roles"].remove(
            role.id
        )

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Ticket Role Removed",
            f"{ARROW} {role.mention} can no longer access standard tickets.",
        ),
        ephemeral=True,
    )


@ticketrole_group.command(
    name="list",
    description="List ticket staff roles",
)
async def ticketrole_list(
    interaction,
):
    if not await require_owner(interaction):
        return

    roles = []

    for role_id in data["ticket_roles"]:
        role = interaction.guild.get_role(
            int(role_id)
        )

        if role:
            roles.append(
                f"{ARROW} {role.mention}"
            )

    await reply_embed(
        interaction,
        info_embed(
            "Ticket Staff Roles",
            "\n".join(roles)
            if roles
            else f"{ARROW} No ticket roles configured.",
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    ticketrole_group
)


# ============================================================
# TICKET INACTIVITY
# ============================================================

async def check_ticket_inactivity():

    for ticket_id, ticket in list(
        data["tickets"].items()
    ):

        if ticket.get("closed"):
            continue

        channel = bot.get_channel(
            int(ticket.get("channel_id", 0))
        )

        if not channel:
            continue

        last_staff = parse_iso(
            ticket.get("last_staff_reply")
        )

        if not last_staff:
            continue

        last_user = parse_iso(
            ticket.get("last_user_reply")
        )

        # If user replied after staff,
        # timer should wait for another staff response.
        if (
            last_user
            and last_user > last_staff
        ):
            ticket["reminder_sent"] = False
            continue

        elapsed = (
            now_utc() - last_staff
        ).total_seconds()

        # 1-hour reminder
        if (
            elapsed >= 3600
            and not ticket.get(
                "reminder_sent",
                False,
            )
        ):

            member = channel.guild.get_member(
                int(ticket["creator_id"])
            )

            if member:
                reminder = apex_embed(
                    "🎫 APEX CLOULD™ — Ticket Reminder",
                    f"""Hey {member.display_name} 👋

{ARROW} Our support team has replied to your ticket, but we haven't received a response from you in **1 hour**.

{SUPPORT} **Your ticket is still waiting for you.**

Please check the staff's latest message and reply when you're available so we can continue helping you. 💚

{SIGNAL_OLD} **APEX CLOULD™ Support**
Thank you for your patience!""",
                )

                try:
                    await channel.send(
                        content=member.mention,
                        embed=reminder,
                    )
                except Exception:
                    pass

            ticket["reminder_sent"] = True
            save_data()

        # 8-hour auto close
        if elapsed >= 8 * 3600:

            member = channel.guild.get_member(
                int(ticket["creator_id"])
            )

            if member:
                try:
                    await channel.send(
                        embed=apex_embed(
                            "🎫 APEX CLOULD™ — Auto Close",
                            f"""{ARROW} This ticket will now be closed because no response was received from the ticket owner for **8 hours**.

{SUPPORT} The transcript will be sent privately to the ticket owner.""",
                        )
                    )
                except Exception:
                    pass

            await close_ticket(
                channel,
                ticket,
                automatic=True,
                closed_by=None,
            )


# ============================================================
# APPLICATION SYSTEM
# ============================================================

APPLICATION_QUESTIONS = [
    "Name / What should we call you?",
    "Age",
    "Timezone",
    "Why do you want to become staff at APEX CLOULD?",
    "What experience do you have?",
    "What skills can you bring to the team?",
    "How active can you be?",
    "Have you worked in a Discord/hosting team before?",
    "Why should we choose you?",
    "Scenario: A member repeatedly breaks rules after being warned. What would you do?",
    "Scenario: Two members start arguing in public. How would you handle it?",
    "Scenario: Customer says VPS is down and is angry. What do you do?",
    "Scenario: Member claims another staff member treated them unfairly. How do you handle it?",
    "Scenario: You notice another staff member abusing permissions. What do you do?",
    "Scenario: Member is spamming/pinging staff for help. How do you respond?",
    "Anything else you'd like us to know?",
]


def generate_application_id():
    data["counter"]["application"] += 1

    value = (
        f"APP-{data['counter']['application']:04d}"
    )

    save_data()

    return value


def generate_claim_code():
    chars = (
        string.ascii_uppercase
        + string.digits
    )

    return (
        "APEX-"
        + "".join(
            secrets.choice(chars)
            for _ in range(6)
        )
    )


def score_application(
    answers,
):
    score = 0

    # Name
    if len(answers[0].strip()) >= 2:
        score += 5

    # Age
    try:
        age = int(
            re.search(
                r"\d+",
                answers[1],
            ).group()
        )

        if age >= 14:
            score += 10

        if age >= 16:
            score += 5

    except Exception:
        pass

    # Timezone
    if len(answers[2].strip()) >= 2:
        score += 5

    # Written answers
    for index in range(
        3,
        9,
    ):
        if len(
            answers[index].strip()
        ) >= 50:
            score += 7
        elif len(
            answers[index].strip()
        ) >= 20:
            score += 4

    # Scenario questions
    for index in range(
        9,
        15,
    ):
        if len(
            answers[index].strip()
        ) >= 80:
            score += 5
        elif len(
            answers[index].strip()
        ) >= 30:
            score += 3

    # Anything else
    if len(
        answers[15].strip()
    ) >= 20:
        score += 5

    return min(
        score,
        100,
    )


class ApplicationModal(
    discord.ui.Modal
):
    def __init__(
        self,
        page,
        user_id,
    ):
        self.page = page
        self.user_id = user_id

        start = (
            page * 4
        )

        questions = APPLICATION_QUESTIONS[
            start:start + 4
        ]

        super().__init__(
            title=f"APEX CLOULD™ Application {page + 1}/4"
        )

        for index, question in enumerate(
            questions
        ):

            field = discord.ui.TextInput(
                label=question[:45],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=4000,
            )

            self.add_item(
                field
            )

    async def on_submit(
        self,
        interaction,
    ):
        draft = data[
            "application_drafts"
        ].setdefault(
            str(self.user_id),
            {
                "answers": [
                    ""
                    for _ in APPLICATION_QUESTIONS
                ]
            },
        )

        start = (
            self.page * 4
        )

        for index, child in enumerate(
            self.children
        ):
            draft["answers"][
                start + index
            ] = child.value

        save_data()

        if self.page < 3:
            await interaction.response.send_message(
                embed=info_embed(
                    "Application Saved",
                    f"{ARROW} Page **{self.page + 1}/4** has been saved.\n\n"
                    f"{ROCKET} Continue to the next page below.",
                ),
                view=ApplicationContinueView(
                    self.user_id,
                    self.page + 1,
                ),
                ephemeral=True,
            )

            return

        answers = draft["answers"]

        app_id = generate_application_id()
        score = score_application(
            answers
        )

        accepted = (
            score >= 70
            and all(
                len(answer.strip()) >= 3
                for answer in answers
            )
        )

        status = (
            "Accepted"
            if accepted
            else "Declined"
        )

        claim_code = None

        if accepted:
            claim_code = generate_claim_code()

        data["applications"][app_id] = {
            "id": app_id,
            "user_id": self.user_id,
            "answers": answers,
            "score": score,
            "status": status,
            "claim_code": claim_code,
            "created_at": iso(now_utc()),
            "reviewed_at": iso(now_utc()),
        }

        if claim_code:
            data["claim_codes"][claim_code] = {
                "user_id": self.user_id,
                "application_id": app_id,
                "used": False,
                "created_at": iso(
                    now_utc()
                ),
            }

        del data[
            "application_drafts"
        ][str(self.user_id)]

        save_data()

        user = interaction.user

        if accepted:
            user_embed = apex_embed(
                "🎉 APEX CLOULD™ — Application Accepted",
                f"""Congratulations {user.display_name}! 💚

{ARROW} Your staff application has been **accepted**.

{ROCKET} **Application:** `{app_id}`
{ARROW} **Score:** `{score}/100`

{SUPPORTER} **Your Claim Code**
`{claim_code}`

{ARROW} Open a **Reward Claim** ticket and send your claim code to the support team.

{RULES} Do not share your claim code publicly.

{SIGNAL} Welcome to the next stage of APEX CLOULD™! 🚀""",
            )

        else:
            user_embed = apex_embed(
                "APEX CLOULD™ — Application Result",
                f"""Hello {user.display_name}.

{ARROW} Thank you for applying to the APEX CLOULD™ team.

{ARROW} Application: `{app_id}`
{ARROW} Score: `{score}/100`

{SUPPORTER} Unfortunately, your application was **not accepted** this time.

{SIGNAL} Thank you for your interest in APEX CLOULD™.""",
            )

        await dm_embed(
            user,
            user_embed,
        )

        review_channel_id = data["config"].get(
            "application_channel"
        )

        review_channel = (
            interaction.guild.get_channel(
                int(review_channel_id)
            )
            if review_channel_id
            else interaction.channel
        )

        if review_channel:
            answers_text = "\n\n".join(
                f"**{i + 1}. {APPLICATION_QUESTIONS[i]}**\n"
                f"{answers[i][:1000]}"
                for i in range(
                    len(answers)
                )
            )

            await review_channel.send(
                embed=apex_embed(
                    f"📝 Application {status}",
                    f"""{ARROW} **Application:** `{app_id}`
{ARROW} **Applicant:** {user.mention}
{ARROW} **Score:** `{score}/100`
{ARROW} **Status:** **{status}**

{answers_text}""",
                )
            )

        await interaction.response.send_message(
            embed=success_embed(
                "Application Submitted",
                f"{ARROW} Your application `{app_id}` has been submitted.\n\n"
                f"{SIGNAL} Your result has been sent to you privately.",
            ),
            ephemeral=True,
        )


class ApplicationContinueView(
    discord.ui.View
):
    def __init__(
        self,
        user_id,
        page,
    ):
        super().__init__(
            timeout=600
        )

        self.user_id = user_id
        self.page = page

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.success,
    )
    async def continue_button(
        self,
        interaction,
        button,
    ):
        if interaction.user.id != self.user_id:
            await reply_embed(
                interaction,
                error_embed(
                    "Not Your Application",
                    f"{ARROW} This application belongs to another member.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApplicationModal(
                self.page,
                self.user_id,
            )
        )


class ApplicationStartView(
    discord.ui.View
):
    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Apply Now",
        style=discord.ButtonStyle.success,
        emoji="📝",
        custom_id="apex_application_start",
    )
    async def apply(
        self,
        interaction,
        button,
    ):
        if not data.get(
            "application_enabled",
            True,
        ):
            await reply_embed(
                interaction,
                info_embed(
                    "Applications Closed",
                    "Applications are currently closed. Our applications will be open soon. Please check back later! 💚",
                ),
                ephemeral=True,
            )
            return

        data["application_drafts"][
            str(interaction.user.id)
        ] = {
            "answers": [
                ""
                for _ in APPLICATION_QUESTIONS
            ]
        }

        save_data()

        await interaction.response.send_modal(
            ApplicationModal(
                0,
                interaction.user.id,
            )
        )


application_group = app_commands.Group(
    name="application",
    description="APEX CLOULD™ applications",
)


@application_group.command(
    name="setup",
    description="Create the application panel",
)
async def application_setup(
    interaction,
):
    if not await require_admin(interaction):
        return

    await interaction.channel.send(
        embed=apex_embed(
            "📝 APEX CLOULD™ Staff Applications",
            f"""{ARROW} Want to become part of the APEX CLOULD™ team?

{ROCKET} Complete our staff application honestly and provide detailed answers.

{SUPPORTER} Applications are scored using defined requirements and application rules.

{RULES} Do not copy another person's application.

{SIGNAL} Good luck! 💚""",
        ),
        view=ApplicationStartView(),
    )

    await reply_embed(
        interaction,
        success_embed(
            "Application Panel Created",
            f"{ARROW} The application panel is now active.",
        ),
        ephemeral=True,
    )


@application_group.command(
    name="on",
    description="Open applications",
)
async def application_on(
    interaction,
):
    if not await require_owner(interaction):
        return

    data["application_enabled"] = True
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Applications Open",
            f"{ARROW} APEX CLOULD™ applications are now open.",
        ),
    )


@application_group.command(
    name="off",
    description="Close applications",
)
async def application_off(
    interaction,
):
    if not await require_owner(interaction):
        return

    data["application_enabled"] = False
    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Applications Closed",
            f"{ARROW} APEX CLOULD™ applications are now closed.",
        ),
    )


@application_group.command(
    name="list",
    description="List applications",
)
async def application_list(
    interaction,
):
    if not await require_admin(interaction):
        return

    if not data["applications"]:
        await reply_embed(
            interaction,
            info_embed(
                "Applications",
                f"{ARROW} No applications have been submitted.",
            ),
            ephemeral=True,
        )
        return

    lines = []

    for app_id, app in data["applications"].items():
        lines.append(
            f"{ARROW} `{app_id}` — <@{app['user_id']}> — "
            f"**{app['status']}** — `{app['score']}/100`"
        )

    await reply_embed(
        interaction,
        info_embed(
            "APEX CLOULD™ Applications",
            "\n".join(lines),
        ),
        ephemeral=True,
    )


@application_group.command(
    name="view",
    description="View an application",
)
async def application_view(
    interaction,
    application_id: str,
):
    if not await require_admin(interaction):
        return

    app = data["applications"].get(
        application_id.upper()
    )

    if not app:
        await reply_embed(
            interaction,
            error_embed(
                "Application Not Found",
                f"{ARROW} No application `{application_id}` exists.",
            ),
            ephemeral=True,
        )
        return

    answers = app["answers"]

    description = f"""{ARROW} Application: `{app['id']}`
{ARROW} Applicant: <@{app['user_id']}>
{ARROW} Score: `{app['score']}/100`
{ARROW} Status: **{app['status']}**

"""

    for i, answer in enumerate(
        answers
    ):
        description += (
            f"**{i + 1}. {APPLICATION_QUESTIONS[i]}**\n"
            f"{answer[:700]}\n\n"
        )

    await reply_embed(
        interaction,
        apex_embed(
            f"📝 {app['id']}",
            description[:5900],
        ),
        ephemeral=True,
    )


application_code_group = app_commands.Group(
    name="code",
    description="Application claim code management",
    parent=application_group,
)


@application_code_group.command(
    name="view",
    description="View an applicant claim code",
)
async def application_code(
    interaction,
    user: discord.Member,
):
    if not await require_owner(interaction):
        return

    found = None

    for app in data["applications"].values():
        if (
            int(app["user_id"])
            == user.id
            and app.get("claim_code")
        ):
            found = app
            break

    if not found:
        await reply_embed(
            interaction,
            error_embed(
                "Claim Code Not Found",
                f"{ARROW} No claim code was found for {user.mention}.",
            ),
            ephemeral=True,
        )
        return

    await reply_embed(
        interaction,
        info_embed(
            "Application Claim Code",
            f"{ARROW} Applicant: {user.mention}\n"
            f"{ARROW} Application: `{found['id']}`\n"
            f"{SUPPORTER} Claim code: `{found['claim_code']}`",
        ),
        ephemeral=True,
    )


@application_group.command(
    name="codes",
    description="List application claim codes",
)
async def application_codes(
    interaction,
):
    if not await require_owner(interaction):
        return

    codes = []

    for code, item in data["claim_codes"].items():
        codes.append(
            f"{ARROW} `{code}` — <@{item['user_id']}> — "
            f"{'USED' if item.get('used') else 'UNUSED'}"
        )

    await reply_embed(
        interaction,
        info_embed(
            "Application Claim Codes",
            "\n".join(codes)
            if codes
            else f"{ARROW} No claim codes exist.",
        ),
        ephemeral=True,
    )


bot.tree.add_command(
    application_group
)


# ============================================================
# GIVEAWAYS
# ============================================================

class GiveawayView(
    discord.ui.View
):
    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Enter Giveaway",
        style=discord.ButtonStyle.success,
        emoji="🎁",
        custom_id="apex_giveaway_enter",
    )
    async def enter(
        self,
        interaction,
        button,
    ):
        giveaway = None

        for item in data["giveaways"].values():
            if (
                int(item["channel_id"])
                == interaction.channel.id
                and not item.get("ended")
            ):
                giveaway = item
                break

        if not giveaway:
            await reply_embed(
                interaction,
                error_embed(
                    "Giveaway Ended",
                    f"{ARROW} This giveaway is no longer active.",
                ),
                ephemeral=True,
            )
            return

        user_id = interaction.user.id

        if user_id not in giveaway["entries"]:
            giveaway["entries"].append(
                user_id
            )
            save_data()

            text = (
                f"{ARROW} You have entered the giveaway! 🎁"
            )
        else:
            text = (
                f"{ARROW} You are already entered."
            )

        await reply_embed(
            interaction,
            success_embed(
                "Giveaway",
                text,
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="giveaway",
    description="Create a giveaway",
)
async def giveaway(
    interaction,
    duration_minutes: app_commands.Range[int, 1, 10080],
):
    if not await require_admin(interaction):
        return

    end = now_utc() + timedelta(
        minutes=duration_minutes
    )

    giveaway_id = secrets.token_hex(
        4
    )

    data["giveaways"][giveaway_id] = {
        "id": giveaway_id,
        "channel_id": interaction.channel.id,
        "message_id": None,
        "ends_at": iso(end),
        "entries": [],
        "ended": False,
        "prize": "4GB Free VPS",
    }

    save_data()

    embed = apex_embed(
        "🎁 APEX CLOULD™ — Giveaway",
        f"""{ARROW} **Prize:** 🎉 **4GB Free VPS**

{ROCKET} Enter the giveaway using the button below.

{ARROW} Duration: <t:{int(end.timestamp())}:R>
{ARROW} Ends: <t:{int(end.timestamp())}:F>

{SUPPORTER} One winner will be selected when the giveaway ends.

{SIGNAL} Good luck from APEX CLOULD™! 💚""",
    )

    message = await interaction.channel.send(
        embed=embed,
        view=GiveawayView(),
    )

    data["giveaways"][giveaway_id][
        "message_id"
    ] = message.id

    save_data()

    await reply_embed(
        interaction,
        success_embed(
            "Giveaway Created",
            f"{ARROW} The giveaway is now live.",
        ),
        ephemeral=True,
    )


async def check_giveaways():

    for giveaway_id, giveaway_data in list(
        data["giveaways"].items()
    ):

        if giveaway_data.get("ended"):
            continue

        end = parse_iso(
            giveaway_data.get("ends_at")
        )

        if not end:
            continue

        if now_utc() < end:
            continue

        giveaway_data["ended"] = True

        entries = list(
            set(
                giveaway_data.get(
                    "entries",
                    [],
                )
            )
        )

        channel = bot.get_channel(
            int(
                giveaway_data["channel_id"]
            )
        )

        if not channel:
            continue

        if not entries:
            await channel.send(
                embed=info_embed(
                    "Giveaway Ended",
                    f"{ARROW} No valid entries were received.\n"
                    f"{SIGNAL} No winner could be selected.",
                )
            )

            continue

        winner_id = random.choice(
            entries
        )

        winner = channel.guild.get_member(
            winner_id
        )

        if winner:
            await channel.send(
                content=winner.mention,
                embed=apex_embed(
                    "🎉 APEX CLOULD™ — Giveaway Winner",
                    f"""{ROCKET} Congratulations {winner.mention}!

{ARROW} You won the **4GB Free VPS** giveaway! 🎁

{SUPPORTER} Please open a ticket to claim your VPS.

{SIGNAL} Thank you to everyone who participated in the APEX CLOULD™ giveaway! 💚""",
                ),
            )

        save_data()


# ============================================================
# INVITE COMMANDS
# ============================================================

@bot.command(
    name="i"
)
async def invite_stats_command(
    ctx,
    member: Optional[discord.Member] = None,
):
    member = member or ctx.author

    stats = data["invite_stats"].get(
        str(member.id),
        {
            "real": 0,
            "total": 0,
            "left": 0,
            "fake": 0,
        },
    )

    embed = apex_embed(
        f"📨 {member.display_name} — Invite Stats",
        f"""{ARROW} **Real Invites:** `{stats.get('real', 0)}`
{ARROW} **Total Invites:** `{stats.get('total', 0)}`
{ARROW} **Left:** `{stats.get('left', 0)}`
{ARROW} **Fake:** `{stats.get('fake', 0)}`

{SUPPORTER} Fake accounts are accounts less than **1 month old**.

{SIGNAL} APEX CLOULD™ Invite Tracker""",
    )

    await ctx.send(
        embed=embed
    )


@bot.command(
    name="invleaderboard"
)
async def invite_leaderboard(
    ctx,
):
    ranking = []

    for user_id, stats in data[
        "invite_stats"
    ].items():
        ranking.append(
            (
                int(
                    stats.get(
                        "real",
                        0,
                    )
                ),
                int(user_id),
            )
        )

    ranking.sort(
        reverse=True
    )

    if not ranking:
        text = (
            f"{ARROW} No invite data is available yet."
        )
    else:
        lines = []

        for position, (
            real,
            user_id,
        ) in enumerate(
            ranking[:10],
            start=1,
        ):
            lines.append(
                f"**{position}.** <@{user_id}> — **{real} real invites**"
            )

        text = "\n".join(lines)

    await ctx.send(
        embed=info_embed(
            "🏆 APEX CLOULD™ Invite Leaderboard",
            text,
        )
    )


# ============================================================
# SERVER INFO
# ============================================================

def server_age(created):
    delta = now_utc() - created
    days = delta.days
    years = days // 365
    remaining = days % 365
    months = remaining // 30
    days = remaining % 30
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    return ", ".join(parts) if parts else "Less than a day"


def build_serverinfo_embed(guild: discord.Guild):
    owner = guild.owner
    online = sum(
        1 for m in guild.members
        if not m.bot and m.status != discord.Status.offline
    )
    bots = sum(1 for m in guild.members if m.bot)
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    vanity = getattr(guild, "vanity_url", None) or "Not configured"
    locale = getattr(guild, "preferred_locale", None) or "Unknown"
    verification = str(getattr(guild, "verification_level", "Unknown")).replace("VerificationLevel.", "").title()
    two_factor = "Required" if "2FA_REQUIREMENT" in getattr(guild, "features", []) else "Not required"

    return apex_embed(
        f"🌐 {guild.name}",
        f"""{ARROW} **Server Owner:** {owner.mention if owner else 'Unknown'}
{ARROW} **Members:** `{guild.member_count}`
{ARROW} **Online Members:** `{online}`
{ARROW} **Bots:** `{bots}`
{ARROW} **Boost Level:** `{guild.premium_tier}`
{ARROW} **Boost Count:** `{guild.premium_subscription_count or 0}`
{ARROW} **Server Created:** <t:{int(guild.created_at.timestamp())}:F>
{ARROW} **Server Age:** `{server_age(guild.created_at)}`
{ARROW} **Channels:** `{len(guild.channels)}`
{ARROW} **Text Channels:** `{text_channels}`
{ARROW} **Voice Channels:** `{voice_channels}`
{ARROW} **Roles:** `{len(guild.roles)}`
{ARROW} **Emojis:** `{len(guild.emojis)}`
{ARROW} **Stickers:** `{len(guild.stickers)}`
{ARROW} **Vanity URL:** `{vanity}`
{ARROW} **Server Locale:** `{locale}`
{ARROW} **Verification Level:** `{verification}`
{ARROW} **2FA Requirement:** `{two_factor}`

{ROCKET} **APEX CLOULD™ Community**
{SUPPORTER} High-performance hosting, VPS services, support and rewards.
{SIGNAL} APEX CLOULD™ 💚""",
    )


@bot.command(name="serverinfo")
async def serverinfo_prefix(ctx):
    await ctx.send(embed=build_serverinfo_embed(ctx.guild))


@bot.tree.command(name="serverinfo", description="View server information")
async def serverinfo_slash(interaction):
    await reply_embed(interaction, build_serverinfo_embed(interaction.guild))


# ============================================================
# HELP
# ============================================================

@bot.tree.command(
    name="help",
    description="Show APEX CLOULD™ commands",
)
async def help_command(
    interaction,
):
    embed = apex_embed(
        "☁️ APEX CLOULD™ — Command Center",
        f"""{ROCKET} **Moderation**
{ARROW} `/kick`
{ARROW} `/ban`
{ARROW} `/warn`
{ARROW} `/warnclear`
{ARROW} `/warnings`
{ARROW} `/timeout`
{ARROW} `/untimeout`
{ARROW} `/clear`

{SUPPORT} **Tickets**
{ARROW} `/ticket setup`
{ARROW} `/close`
{ARROW} `/ticketrole add`
{ARROW} `/ticketrole remove`
{ARROW} `/ticketrole list`

{SUPPORTER} **Applications**
{ARROW} `/application setup`
{ARROW} `/application on`
{ARROW} `/application off`
{ARROW} `/application list`
{ARROW} `/application view`
{ARROW} `/application code view`
{ARROW} `/application code delete`
{ARROW} `/application codes`

{ROCKET} **VPS**
{ARROW} `/vps create`
{ARROW} `/vps list`
{ARROW} `/vps suspend`
{ARROW} `/vps unsuspend`
{ARROW} `/vps info`
{ARROW} `/vps delete`

{RULES} **AutoMod**
{ARROW} `/automod`
{ARROW} `/automodbypass add`
{ARROW} `/automodbypass remove`
{ARROW} `/automodbypass list`
{ARROW} `/badword add`
{ARROW} `/badword remove`
{ARROW} `/badword list`

{SIGNAL} **Other**
{ARROW} `/msg`
{ARROW} `/config`
{ARROW} `/role`
{ARROW} `/promote`
{ARROW} `/lockdown`
{ARROW} `/unlockdown`
{ARROW} `/dm`
{ARROW} `!i`
{ARROW} `!invleaderboard`
{ARROW} `!serverinfo`

💚 **APEX CLOULD™ — Powering Your Servers**""",
    )

    await reply_embed(
        interaction,
        embed,
        ephemeral=False,
    )


# ============================================================
# AUTOMOD MESSAGE HANDLER
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if not message.guild:
        await bot.process_commands(
            message
        )
        return

    member = message.author

    # --------------------------------------------------------
    # AutoMod
    # --------------------------------------------------------

    if (
        data["automod"].get(
            "enabled",
            True,
        )
        and isinstance(
            member,
            discord.Member,
        )
        and not has_automod_bypass(
            member
        )
    ):

        reason = None

        if (
            data["automod"].get(
                "links_enabled",
                True,
            )
            and URL_PATTERN.search(
                message.content
            )
        ):
            reason = (
                "Sending links is not allowed."
            )

        badword = None

        if (
            not reason
            and data["automod"].get(
                "badwords_enabled",
                True,
            )
        ):
            badword = contains_badword(
                message.content
            )

            if badword:
                reason = (
                    "Your message contained a prohibited word."
                )

        if reason:

            try:
                await message.delete()
            except Exception:
                pass

            # Link protection gets 10 minute timeout.
            if (
                URL_PATTERN.search(
                    message.content
                )
                and data["automod"].get(
                    "links_enabled",
                    True,
                )
            ):
                try:
                    await member.timeout(
                        now_utc()
                        + timedelta(minutes=10),
                        reason="APEX CLOULD™ AutoMod link protection",
                    )
                except Exception:
                    pass

            await dm_embed(
                member,
                automod_dm_embed(
                    reason
                ),
            )

            await send_log(
                message.guild,
                "AutoMod Action",
                f"{ARROW} Member: {member.mention}\n"
                f"{ARROW} Channel: {message.channel.mention}\n"
                f"{SUPPORTER} Reason: `{reason}`",
            )

            return

    # --------------------------------------------------------
    # Ticket activity tracking
    # --------------------------------------------------------

    ticket = find_ticket_by_channel(
        message.channel.id
    )

    if ticket and not ticket.get(
        "closed"
    ):

        if has_ticket_access(
            member
        ):
            ticket["last_staff_reply"] = iso(
                now_utc()
            )

            ticket["reminder_sent"] = False

        elif member.id == int(
            ticket["creator_id"]
        ):
            ticket["last_user_reply"] = iso(
                now_utc()
            )
            ticket["reminder_sent"] = False

        save_data()

    # Optional TTS queue for the channel associated with !botjoin.
    if message.guild and not message.author.bot:
        text_channel_id = bot._apex_voice_channels.get(message.guild.id)
        if text_channel_id == message.channel.id and message.content.strip():
            queue = bot._apex_tts_queues.get(message.guild.id)
            if queue is not None:
                await queue.put(message.content.strip())

    await bot.process_commands(
        message
    )


# ============================================================
# MESSAGE / CHANNEL / ROLE LOGGING
# ============================================================


@bot.event
async def on_member_update(
    before,
    after,
):
    if before.nick != after.nick:
        await send_log(
            after.guild,
            "Member Name Changed",
            f"{ARROW} Member: {after.mention}\n"
            f"{ARROW} Previous: `{before.nick}`\n"
            f"{ARROW} New: `{after.nick}`",
        )

    before_roles = {
        r.id for r in before.roles
    }

    after_roles = {
        r.id for r in after.roles
    }

    added = after_roles - before_roles
    removed = before_roles - after_roles

    for role_id in added:
        role = after.guild.get_role(
            role_id
        )

        if role:
            await send_log(
                after.guild,
                "Role Given",
                f"{ARROW} Member: {after.mention}\n"
                f"{ARROW} Role: {role.mention}",
            )

    for role_id in removed:
        role = after.guild.get_role(
            role_id
        )

        if role:
            await send_log(
                after.guild,
                "Role Removed",
                f"{ARROW} Member: {after.mention}\n"
                f"{ARROW} Role: {role.mention}",
            )

    if (
        before.premium_since
        != after.premium_since
    ):
        if after.premium_since:
            await send_log(
                after.guild,
                "Server Boost",
                f"{ARROW} {after.mention} boosted the server! 💚",
            )
        else:
            await send_log(
                after.guild,
                "Server Boost Removed",
                f"{ARROW} {after.mention} is no longer boosting the server.",
            )


@bot.event
async def on_guild_channel_create(
    channel,
):
    await send_log(
        channel.guild,
        "Channel Created",
        f"{ARROW} Channel: {channel.mention if hasattr(channel, 'mention') else channel.name}",
    )


@bot.event
async def on_guild_channel_delete(
    channel,
):
    await send_log(
        channel.guild,
        "Channel Deleted",
        f"{ARROW} Channel: `{channel.name}`",
    )


@bot.event
async def on_guild_channel_update(
    before,
    after,
):
    changes = []

    if before.name != after.name:
        changes.append(
            f"{ARROW} Name: `{before.name}` → `{after.name}`"
        )

    if (
        getattr(before, "topic", None)
        != getattr(after, "topic", None)
    ):
        changes.append(
            f"{ARROW} Topic changed."
        )

    if changes:
        await send_log(
            after.guild,
            "Channel Updated",
            f"{ARROW} Channel: {after.mention}\n"
            + "\n".join(changes),
        )


@bot.event
async def on_guild_role_create(
    role,
):
    await send_log(
        role.guild,
        "Role Created",
        f"{ARROW} Role: {role.mention}",
    )


@bot.event
async def on_guild_role_delete(
    role,
):
    await send_log(
        role.guild,
        "Role Deleted",
        f"{ARROW} Role: `{role.name}`",
    )


@bot.event
async def on_guild_role_update(
    before,
    after,
):
    changes = []

    if before.name != after.name:
        changes.append(
            f"{ARROW} Name: `{before.name}` → `{after.name}`"
        )

    if before.permissions != after.permissions:
        changes.append(
            f"{ARROW} Permissions changed."
        )

    if changes:
        await send_log(
            after.guild,
            "Role Updated",
            f"{ARROW} Role: {after.mention}\n"
            + "\n".join(changes),
        )


@bot.event
async def on_member_ban(
    guild,
    user,
):
    await send_log(
        guild,
        "Member Banned",
        f"{ARROW} Member: {user.mention}",
    )


@bot.event
async def on_member_unban(
    guild,
    user,
):
    await send_log(
        guild,
        "Member Unbanned",
        f"{ARROW} Member: {user.mention}",
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user} ({bot.user.id})"
    )

    guild = bot.get_guild(
        GUILD_ID
    )

    if guild:
        await refresh_invites(
            guild
        )

        if not bot.startup_logged:
            bot.startup_logged = True

            await send_log(
                guild,
                "Bot Online",
                f"{ARROW} **APEX CLOULD™ Bot** is now online.\n"
                f"{ROCKET} Account: {bot.user.mention}\n"
                f"{SIGNAL} All persistent systems are active.",
            )


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error,
):

    original = error

    if isinstance(
        error,
        app_commands.CommandOnCooldown,
    ):
        await reply_embed(
            interaction,
            error_embed(
                "Command Cooldown",
                f"{ARROW} Try again in **{error.retry_after:.1f}s**.",
            ),
            ephemeral=True,
        )
        return

    if isinstance(
        error,
        app_commands.MissingPermissions,
    ):
        await reply_embed(
            interaction,
            error_embed(
                "Missing Discord Permission",
                f"{ARROW} The bot does not have the required Discord permission.",
            ),
            ephemeral=True,
        )
        return

    if isinstance(
        error,
        app_commands.TransformerError,
    ):
        await reply_embed(
            interaction,
            error_embed(
                "Invalid Input",
                f"{ARROW} One of the supplied values could not be processed.",
            ),
            ephemeral=True,
        )
        return

    print(
        "Application command error:",
        repr(original),
    )

    try:
        await reply_embed(
            interaction,
            error_embed(
                "Command Error",
                f"{ARROW} Something went wrong while processing that command.\n\n"
                f"{SUPPORTER} Error ID: `{secrets.token_hex(4)}`",
            ),
            ephemeral=True,
        )

    except Exception:
        pass


@bot.event
async def on_error(
    event,
    *args,
    **kwargs,
):
    import traceback

    traceback.print_exc()


# ============================================================
# VPS EXPIRY
# ============================================================

async def check_vps_expiry():
    from zoneinfo import ZoneInfo
    for key, item in list(data.get("vps", {}).items()):
        if item.get("notified") or item.get("status") == "Expired":
            continue
        expires = parse_iso(item.get("expires_at"))
        if not expires or now_utc() < expires:
            continue
        item["status"] = "Expired"
        item["notified"] = True
        save_data()
        owner_id = int(item.get("owner_id", 0))
        owner = bot.get_user(owner_id)
        if owner is None:
            try:
                owner = await bot.fetch_user(owner_id)
            except Exception:
                owner = None
        name = item.get("name", key)
        expiry_dt = expires.astimezone(ZoneInfo("Europe/London")).strftime("%d %B %Y %I:%M %p UK")
        owner_embed = apex_embed("🔒 APEX CLOULD™ — VPS Expired", f"Hello **{getattr(owner, 'display_name', 'there')}** 👋\n\n{ARROW} Your VPS service has reached its expiry date.\n\n{ROCKET} **VPS Details**\n{ARROW} **VPS Name:** `{name}`\n{ARROW} **Service:** `{item.get('service', 'Unknown')}`\n{ARROW} **Expiry Date:** `{expiry_dt}`\n{ARROW} **Status:** `Expired — review or renewal required`\n\n{SUPPORT} Please contact the APEX CLOULD™ team if you need to renew your service.\n\n{SIGNAL} No automatic suspension or server modification was performed.")
        if owner:
            await dm_embed(owner, owner_embed)
        admin_embed = apex_embed("⚠️ APEX CLOULD™ — VPS Expiry Alert", f"{ARROW} A tracked VPS has expired.\n\n{ROCKET} **VPS Details**\n{ARROW} **VPS Name:** `{name}`\n{ARROW} **Service:** `{item.get('service', 'Unknown')}`\n{ARROW} **Expiry Date:** `{expiry_dt}`\n{ARROW} **Status:** `Expired — review or renewal required`\n\n{SUPPORTER} **Owner Details**\n{ARROW} **Name:** {getattr(owner, 'display_name', 'Unknown')}\n{ARROW} **Discord ID:** `{owner_id}`\n\n{SIGNAL} The bot did not suspend or modify the VPS.")
        admin = bot.get_user(OWNER_ID)
        if admin is None:
            try:
                admin = await bot.fetch_user(OWNER_ID)
            except Exception:
                admin = None
        if admin:
            await dm_embed(admin, admin_embed)


# ============================================================
# COMMANDS FOR LEGACY TICKET PANELS
# ============================================================

@bot.tree.command(
    name="ticketpanel",
    description="Create the APEX CLOULD™ ticket panel",
)
async def ticketpanel(
    interaction,
):
    if not await require_admin(interaction):
        return

    await interaction.channel.send(
        embed=apex_embed(
            "🎫 APEX CLOULD™ Support",
            TICKET_PANEL_DESCRIPTION,
        ),
        view=TicketPanelView(),
    )

    await reply_embed(
        interaction,
        success_embed(
            "Ticket Panel Created",
            f"{ARROW} The panel is active.",
        ),
        ephemeral=True,
    )


# ============================================================
# APPLICATION PANEL COMPATIBILITY
# ============================================================

@bot.tree.command(
    name="applicationpanel",
    description="Create the APEX CLOULD™ application panel",
)
async def applicationpanel(
    interaction,
):
    if not await require_admin(interaction):
        return

    await interaction.channel.send(
        embed=apex_embed(
            "📝 APEX CLOULD™ Staff Applications",
            f"""{ARROW} Applications are handled through the APEX CLOULD™ application system.

{ROCKET} Click **Apply Now** to begin.

{SUPPORTER} Applications are automatically scored using defined rules.

{SIGNAL} Good luck! 💚""",
        ),
        view=ApplicationStartView(),
    )

    await reply_embed(
        interaction,
        success_embed(
            "Application Panel Created",
            f"{ARROW} The application panel is active.",
        ),
        ephemeral=True,
    )


# ============================================================
# REGIMENT / FILE COMPATIBILITY
# ============================================================

@bot.tree.command(
    name="regiment",
    description="View the configured regiment file",
)
async def regiment(
    interaction,
):
    if not await require_admin(interaction):
        return

    if not os.path.exists(
        REGIMENT_FILE
    ):
        await reply_embed(
            interaction,
            info_embed(
                "Regiment",
                f"{ARROW} `{REGIMENT_FILE}` does not currently exist.",
            ),
            ephemeral=True,
        )
        return

    try:
        with open(
            REGIMENT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            text = f.read()

        text = text[:5900]

        await reply_embed(
            interaction,
            info_embed(
                "APEX CLOULD™ Regiment",
                text
                if text
                else f"{ARROW} Regiment file is empty.",
            ),
            ephemeral=True,
        )

    except Exception as e:
        await reply_embed(
            interaction,
            error_embed(
                "Regiment Error",
                f"{ARROW} `{str(e)[:1000]}`",
            ),
            ephemeral=True,
        )



# ============================================================
# V2 APPLICATION CLAIM CODE DELETE
# ============================================================

@application_code_group.command(
    name="delete",
    description="Delete and permanently invalidate an application claim code",
)
async def application_code_delete(interaction, code: str):
    if not await require_owner(interaction):
        return

    code = code.strip().upper()
    item = data["claim_codes"].get(code)
    if not item:
        await reply_embed(
            interaction,
            error_embed("Claim Code Not Found", f"{ARROW} `{code}` does not exist."),
            ephemeral=True,
        )
        return

    del data["claim_codes"][code]
    for app in data["applications"].values():
        if app.get("claim_code") == code:
            app["claim_code"] = None
    save_data()

    await reply_embed(
        interaction,
        success_embed("Claim Code Deleted", f"{ARROW} `{code}` has been permanently invalidated."),
        ephemeral=True,
    )
    await send_log(
        interaction.guild,
        "Application Claim Code Deleted",
        f"{ARROW} Code: `{code}`\n{ARROW} Deleted by: {interaction.user.mention}",
    )


# ============================================================
# WEBSITE MONITORING
# ============================================================

async def check_website(url):
    import urllib.request, time
    started = time.perf_counter()
    try:
        def request():
            req = urllib.request.Request(url, headers={"User-Agent": "APEX-CLOULD-Monitor/3.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status
        status = await asyncio.to_thread(request)
        ms = round((time.perf_counter() - started) * 1000)
        return True, status, ms
    except Exception:
        return False, None, round((time.perf_counter() - started) * 1000)


async def refresh_website_data():
    checked_at = iso(now_utc())
    for name, item in data.setdefault("websites", {}).items():
        was_online = item.get("status") == "Online"
        online, status, ms = await check_website(item.get("url", ""))
        item["status"] = "Online" if online else "Offline"
        item["http_status"] = status
        item["response_ms"] = ms
        item["last_checked"] = checked_at
        history = item.setdefault("history", [])
        history.append({"at": checked_at, "online": online, "ms": ms})
        del history[:-1000]
        item["uptime_pct"] = round((sum(1 for h in history if h.get("online")) / len(history)) * 100, 2) if history else 0.0
        if was_online != online and item.get("ever_checked"):
            guild = bot.get_guild(GUILD_ID)
            if guild:
                state = "BACK ONLINE" if online else "OFFLINE"
                await dm_owner_security(f"🌐 Website alert: **{name}** is now **{state}**. Response: `{ms}ms`; HTTP: `{status or 'failed'}`.")
        item["ever_checked"] = True
    save_data()


def website_status_embed():
    websites = data.get("websites", {})
    online_count = sum(1 for x in websites.values() if x.get("status") == "Online")
    total = len(websites)
    if total == 0:
        health = "⚪ NO WEBSITES CONFIGURED"
    elif online_count == total:
        health = "🟢 ALL SYSTEMS OPERATIONAL"
    elif online_count == 0:
        health = "🔴 SERVICE OUTAGE"
    else:
        health = "🟡 PARTIAL OUTAGE"
    lines = [f"{health}\n**{online_count}/{total} Services Online**\n"]
    for name, item in websites.items():
        online = item.get("status") == "Online"
        icon = "🟢" if online else ("🔴" if item.get("status") == "Offline" else "⚪")
        http = f"HTTP {item.get('http_status')}" if item.get("http_status") else "HTTP —"
        ms = f"{item.get('response_ms')}ms" if item.get("response_ms") is not None else "—"
        uptime = f"{item.get('uptime_pct', 0):.2f}%" if item.get("history") else "Collecting data"
        lines.append(f"{icon} **{name}**\n{ARROW} Status: **{item.get('status', 'Unknown')}**  •  ⚡ `{ms}`\n{ARROW} 📡 `{http}`  •  📈 Uptime: **{uptime}**")
    lines.append(f"\n{SUPPORTER} **Monitoring**\n{ARROW} Last checked: **Just now**\n{ARROW} Monitoring: **{total} websites**\n{ARROW} Region: **UK (Europe/London)**\n\n{SIGNAL} *Click below to check all services again.*")
    return apex_embed("🌐 APEX CLOULD™ — WEBSITE STATUS", "\n\n".join(lines))


class WebsiteRecheckView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Recheck All Websites", emoji="🔄", style=discord.ButtonStyle.success, custom_id="apex:website:recheck")
    async def recheck(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        if not data.get("websites"):
            await interaction.followup.send(embed=info_embed("Website Status", f"{ARROW} No websites are configured yet."), ephemeral=True)
            return
        await refresh_website_data()
        panel = data.get("website_panel", {})
        if panel.get("message_id") and panel.get("channel_id"):
            channel = bot.get_channel(int(panel["channel_id"]))
            try:
                message = await channel.fetch_message(int(panel["message_id"])) if channel else None
                if message:
                    await message.edit(embed=website_status_embed(), view=WebsiteRecheckView())
            except Exception:
                pass
        await interaction.followup.send(embed=success_embed("Websites Rechecked", f"{ARROW} Checked all {len(data['websites'])} configured websites."), ephemeral=True)


@bot.tree.command(name="website", description="Post or refresh the public APEX CLOULD™ website status panel")
async def website_command(interaction: discord.Interaction):
    if not data.get("websites"):
        await reply_embed(interaction, info_embed("Website Status", f"{ARROW} No websites configured. An owner can add them with `/website-add`."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    await refresh_website_data()
    panel_msg = await interaction.channel.send(embed=website_status_embed(), view=WebsiteRecheckView())
    data["website_panel"] = {"channel_id": interaction.channel_id, "message_id": panel_msg.id}
    save_data()
    await interaction.followup.send(embed=success_embed("Website Panel Posted", f"{ARROW} Public status panel posted in {interaction.channel.mention}. Anyone can use Recheck All Websites."), ephemeral=True)


@bot.tree.command(name="website-add", description="Owner: add a website to monitoring")
async def website_add(interaction: discord.Interaction, name: str, url: str):
    if not await require_owner(interaction): return
    if not re.match(r"^https?://", url, re.I):
        await reply_embed(interaction, error_embed("Invalid URL", f"{ARROW} URL must start with http:// or https://."), ephemeral=True); return
    data.setdefault("websites", {})[name.strip()[:80]] = {"url": url.strip(), "status": "Unknown", "http_status": None, "response_ms": None, "last_checked": None, "history": [], "uptime_pct": 0.0}
    save_data()
    await reply_embed(interaction, success_embed("Website Added", f"{ARROW} Monitoring **{name}** at `{url}`."), ephemeral=True)


@bot.tree.command(name="website-remove", description="Owner: remove a monitored website")
async def website_remove(interaction: discord.Interaction, name: str):
    if not await require_owner(interaction): return
    if name not in data.setdefault("websites", {}):
        await reply_embed(interaction, error_embed("Website Not Found", f"{ARROW} No website named `{name}`."), ephemeral=True); return
    del data["websites"][name]; save_data()
    await reply_embed(interaction, success_embed("Website Removed", f"{ARROW} Removed **{name}** from monitoring."), ephemeral=True)


@bot.tree.command(name="website-list", description="Owner: list monitored websites")
async def website_list(interaction: discord.Interaction):
    if not await require_owner(interaction): return
    text = "\n".join(f"{ARROW} **{n}** — `{v.get('url','')}`" for n, v in data.setdefault("websites", {}).items()) or f"{ARROW} No websites configured."
    await reply_embed(interaction, info_embed("Monitored Websites", text), ephemeral=True)


# ============================================================
# VERIFICATION, ANTI-RAID & SECURITY CENTER
# ============================================================

async def dm_owner_security(message: str):
    try:
        user = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        await dm_embed(user, apex_embed("🛡️ APEX CLOULD™ — Security Alert", message, color=discord.Color.orange()))
    except Exception:
        pass


async def record_security_incident(kind: str, details: str):
    sec = data.setdefault("security", {})
    incidents = sec.setdefault("recent_incidents", [])
    incidents.append({"type": kind, "details": details[:1000], "at": iso(now_utc())})
    del incidents[:-50]
    save_data()


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Me", emoji="🛡️", style=discord.ButtonStyle.success, custom_id="apex:verify:member")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        sec = data.setdefault("security", {})
        if not sec.get("verification_enabled", True):
            await reply_embed(interaction, info_embed("Verification Disabled", f"{ARROW} Verification is currently disabled."), ephemeral=True); return
        if not isinstance(interaction.user, discord.Member):
            await reply_embed(interaction, error_embed("Server Only", "Please use this button inside the server."), ephemeral=True); return
        role_id = sec.get("verified_role_id")
        role = interaction.guild.get_role(int(role_id)) if role_id else None
        if not role:
            await reply_embed(interaction, error_embed("Not Configured", f"{ARROW} The verified role has not been configured. Contact staff."), ephemeral=True); return
        if role in interaction.user.roles:
            await reply_embed(interaction, info_embed("Already Verified", f"{ARROW} You already have {role.mention}."), ephemeral=True); return
        me = interaction.guild.me
        if not me or not me.guild_permissions.manage_roles or role >= me.top_role:
            await reply_embed(interaction, error_embed("Role Setup Required", f"{ARROW} The bot needs Manage Roles and its highest role must be above {role.mention}."), ephemeral=True); return
        try:
            await interaction.user.add_roles(role, reason="APEX CLOULD™ verification button")
            await reply_embed(interaction, success_embed("Verification Complete", f"{ARROW} Welcome! You now have {role.mention}."), ephemeral=True)
        except discord.HTTPException:
            await reply_embed(interaction, error_embed("Verification Failed", f"{ARROW} I could not assign the role. Please contact staff."), ephemeral=True)


verify_group = app_commands.Group(name="verify", description="APEX CLOULD™ member verification")


@verify_group.command(name="setup", description="Owner: configure the role awarded after verification")
async def verify_setup(interaction: discord.Interaction, role: discord.Role):
    if not await require_owner(interaction): return
    if role.is_default() or role.managed:
        await reply_embed(interaction, error_embed("Invalid Role", f"{ARROW} Choose a normal role that the bot can assign."), ephemeral=True); return
    data.setdefault("security", {})["verified_role_id"] = role.id
    save_data()
    await reply_embed(interaction, success_embed("Verified Role Saved", f"{ARROW} Members who click Verify Me will receive {role.mention}. Ensure the bot's role is above it and configure channel permissions."), ephemeral=True)


@verify_group.command(name="panel", description="Owner: post the verification panel in a channel")
async def verify_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await require_owner(interaction): return
    description = f"{ARROW} **Welcome to APEX CLOULD™!** 💚\n\nBefore accessing our community, verify that you're a member of our server.\n\n{ROCKET} **Why verify?**\n{ARROW} Unlock access to community channels.\n{ARROW} Explore our hosting services and offers.\n{ARROW} Get support and participate in events.\n\n🔐 **How to verify**\nClick **Verify Me** below to receive the configured verified role.\n\n⚠️ **Important**\n{ARROW} Follow the server rules.\n{ARROW} Do not use alternate accounts to bypass restrictions.\n\n{SIGNAL} Thank you for joining APEX CLOULD™! 💚"
    msg = await channel.send(embed=apex_embed("🛡️ APEX CLOULD™ — Server Verification", description), view=VerifyView())
    data.setdefault("security", {})["verification_channel_id"] = channel.id
    save_data()
    await reply_embed(interaction, success_embed("Verification Panel Posted", f"{ARROW} Posted in {channel.mention}. Message ID: `{msg.id}`."), ephemeral=True)


bot.tree.add_command(verify_group)


@bot.tree.command(name="security", description="Owner-only APEX CLOULD™ security center")
async def security_command(interaction: discord.Interaction):
    if not await require_owner(interaction): return
    sec = data.setdefault("security", {})
    incidents = sec.setdefault("recent_incidents", [])
    role_id = sec.get("verified_role_id")
    role_text = f"<@&{role_id}>" if role_id else "Not configured"
    description = (
        f"🛡️ **SECURITY CENTER**\n\n"
        f"{'🟢' if sec.get('anti_raid_enabled', True) else '🔴'} Anti-Raid Shield: **{'ENABLED' if sec.get('anti_raid_enabled', True) else 'DISABLED'}**\n"
        f"{'🟢' if sec.get('verification_enabled', True) else '🔴'} Verification Gate: **{'ENABLED' if sec.get('verification_enabled', True) else 'DISABLED'}**\n"
        f"{'🟢' if sec.get('permission_alerts_enabled', True) else '🔴'} Permission Alerts: **{'ENABLED' if sec.get('permission_alerts_enabled', True) else 'DISABLED'}**\n\n"
        f"📊 **OVERVIEW**\n{ARROW} Recent security incidents: `{len(incidents)}`\n"
        f"{ARROW} Active lockdown: **{'Yes' if sec.get('raid_lockdown_active') else 'No'}**\n"
        f"{ARROW} Verified role: {role_text}\n\n{SIGNAL} Use the buttons below to manage protection and view incidents."
    )
    await interaction.response.send_message(embed=apex_embed("🛡️ APEX CLOULD™ — Security Center", description), ephemeral=True, view=SecurityPanelView())


class SecurityPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle(self, interaction, key, label):
        if interaction.user.id != OWNER_ID:
            await reply_embed(interaction, error_embed("Owner Only", "Only the bot owner can change security settings."), ephemeral=True); return
        sec = data.setdefault("security", {})
        sec[key] = not sec.get(key, True)
        save_data()
        await record_security_incident("setting_change", f"{label} set to {sec[key]} by {interaction.user.id}")
        await reply_embed(interaction, success_embed("Security Setting Updated", f"{ARROW} {label}: **{'ENABLED' if sec[key] else 'DISABLED'}**"), ephemeral=True)

    @discord.ui.button(label="Anti-Raid", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="apex:security:raid")
    async def raid(self, interaction, button):
        await self.toggle(interaction, "anti_raid_enabled", "Anti-Raid Shield")

    @discord.ui.button(label="Verification", emoji="✅", style=discord.ButtonStyle.secondary, custom_id="apex:security:verify")
    async def verification(self, interaction, button):
        await self.toggle(interaction, "verification_enabled", "Verification Gate")

    @discord.ui.button(label="Permission Alerts", emoji="🔐", style=discord.ButtonStyle.secondary, custom_id="apex:security:permissions")
    async def permissions(self, interaction, button):
        await self.toggle(interaction, "permission_alerts_enabled", "Permission Alerts")

    @discord.ui.button(label="View Incidents", emoji="📋", style=discord.ButtonStyle.primary, custom_id="apex:security:incidents")
    async def incidents_button(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            await reply_embed(interaction, error_embed("Owner Only", "Only the bot owner can view incidents."), ephemeral=True); return
        incidents = data.setdefault("security", {}).setdefault("recent_incidents", [])[-10:]
        text = "\n".join(f"• `{x.get('at','unknown')}` **{x.get('type','incident')}** — {x.get('details','')}" for x in incidents) or "No security incidents recorded."
        await reply_embed(interaction, info_embed("Recent Security Incidents", text[:4000]), ephemeral=True)


@bot.event
async def on_audit_log_entry_create(entry: discord.AuditLogEntry):
    sec = data.setdefault("security", {})
    if not sec.get("permission_alerts_enabled", True) or entry.guild.id != GUILD_ID:
        return
    risky = {
        discord.AuditLogAction.role_update, discord.AuditLogAction.role_create,
        discord.AuditLogAction.role_delete, discord.AuditLogAction.channel_update,
        discord.AuditLogAction.channel_create, discord.AuditLogAction.channel_delete,
        discord.AuditLogAction.overwrite_create, discord.AuditLogAction.overwrite_update,
        discord.AuditLogAction.overwrite_delete, discord.AuditLogAction.webhook_create,
        discord.AuditLogAction.webhook_update, discord.AuditLogAction.webhook_delete,
    }
    if entry.action not in risky:
        return
    actor = getattr(entry, "user", None)
    if actor and bot.user and actor.id == bot.user.id:
        return
    target = getattr(entry, "target", None)
    detail = f"Action: `{entry.action.name}`\nActor: {actor} (`{getattr(actor, 'id', 'unknown')}`)\nTarget: `{target}`\nReason: {entry.reason or 'No reason provided.'}"
    await record_security_incident("permission_change", detail)
    await dm_owner_security(detail)


# ============================================================
# OWNER BACKUP / BOT STATUS
# ============================================================

@bot.tree.command(name="botstatus", description="Owner-only live APEX CLOULD™ bot dashboard")
async def botstatus_slash(interaction: discord.Interaction):
    if not await require_owner(interaction): return
    guild = bot.get_guild(GUILD_ID)
    open_tickets = sum(1 for x in data.get("tickets", {}).values() if not x.get("closed"))
    pending_apps = sum(1 for x in data.get("applications", {}).values() if x.get("status") == "Pending")
    active_giveaways = sum(1 for x in data.get("giveaways", {}).values() if not x.get("ended"))
    active_vps = sum(1 for x in data.get("vps", {}).values() if x.get("status", "Active") == "Active")
    website_items = list(data.get("websites", {}).values())
    websites_online = sum(1 for x in website_items if x.get("status") == "Online")
    latency = round(bot.latency * 1000) if bot.latency is not None else 0
    started = getattr(bot, "started_at", None)
    uptime = str(now_utc() - started).split(".")[0] if started else "Available after startup"
    description = (f"🟢 **Bot Status:** Online\n⚡ **Latency:** `{latency}ms`\n⏱️ **Uptime:** `{uptime}`\n\n"
      f"👥 **Server**\n{ARROW} Members: `{guild.member_count if guild else 'Unknown'}`\n\n"
      f"🎫 **Tickets:** `{open_tickets}` open\n📝 **Applications:** `{pending_apps}` pending\n🎁 **Giveaways:** `{active_giveaways}` active\n🖥️ **Tracked VPS:** `{active_vps}`\n"
      f"🌐 **Websites:** `{websites_online}/{len(website_items)} online`\n💾 **Database:** `Loaded`\n{SIGNAL} APEX CLOULD™ System Dashboard")
    await reply_embed(interaction, apex_embed("🤖 APEX CLOULD™ — BOT STATUS", description), ephemeral=True)


@bot.tree.command(name="backup", description="Send a private backup of bot data to the owner")
async def backup_command(interaction):
    if not await require_owner(interaction):
        return
    try:
        payload = json.dumps(data, indent=4).encode("utf-8")
        file = discord.File(io.BytesIO(payload), filename="data.json")
        await interaction.user.send(embed=apex_embed("💾 APEX CLOULD™ — Backup", f"{ARROW} Your private `data.json` backup is attached.\n{SIGNAL} Keep this file secure."), file=file)
        await reply_embed(interaction, success_embed("Backup Sent", f"{ARROW} The backup was sent to your DM."), ephemeral=True)
        await send_log(interaction.guild, "Bot Backup Created", f"{ARROW} Backup requested by {interaction.user.mention} and delivered privately.")
    except Exception as e:
        await reply_embed(interaction, error_embed("Backup Failed", f"{ARROW} `{str(e)[:1000]}`"), ephemeral=True)


@bot.command(name="botstatus")
async def botstatus(ctx):
    if ctx.author.id != OWNER_ID:
        return
    open_tickets = sum(1 for x in data["tickets"].values() if not x.get("closed"))
    pending_apps = sum(1 for x in data["applications"].values() if x.get("status") == "Pending")
    active_giveaways = sum(1 for x in data["giveaways"].values() if not x.get("ended"))
    active_vps = sum(1 for x in data["vps"].values() if x.get("status", "Active") == "Active")
    await ctx.send(embed=apex_embed(
        "🤖 APEX CLOULD™ — Bot Status",
        f"{ARROW} **Bot:** {bot.user.mention if bot.user else 'Unknown'}\n"
        f"{ARROW} **Open Tickets:** `{open_tickets}`\n"
        f"{ARROW} **Pending Applications:** `{pending_apps}`\n"
        f"{ARROW} **Active Giveaways:** `{active_giveaways}`\n"
        f"{ARROW} **Active VPS:** `{active_vps}`\n"
        f"{SIGNAL} APEX CLOULD™ systems online.",
    ))


# ============================================================
# VOICE / TTS
# ============================================================

bot._apex_voice_channels = {}
bot._apex_tts_queues = {}
bot._apex_tts_workers = {}

async def tts_worker(guild_id):
    try:
        import edge_tts
    except ImportError:
        return
    queue = bot._apex_tts_queues.setdefault(guild_id, asyncio.Queue())
    while True:
        text_to_speak = await queue.get()
        try:
            voice = bot.get_guild(guild_id)
            vc = voice.voice_client if voice else None
            if not vc or not vc.is_connected():
                continue
            path = f"/tmp/apex_tts_{guild_id}_{secrets.token_hex(4)}.mp3"
            await edge_tts.Communicate(text_to_speak[:500], "en-GB-RyanNeural").save(path)
            done = asyncio.Event()
            def after(_):
                bot.loop.call_soon_threadsafe(done.set)
            if not vc.is_playing():
                vc.play(discord.FFmpegPCMAudio(path), after=after)
                await done.wait()
            try:
                os.remove(path)
            except OSError:
                pass
        except Exception:
            pass
        finally:
            queue.task_done()


@bot.command(name="botjoin")
async def botjoin(ctx):
    if not ctx.guild or not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send(embed=error_embed("Voice Channel Required", f"{ARROW} Join a voice channel first."))
        return
    channel = ctx.author.voice.channel
    try:
        vc = ctx.guild.voice_client
        if vc and vc.is_connected():
            await vc.move_to(channel)
        else:
            await channel.connect()
        bot._apex_voice_channels[ctx.guild.id] = ctx.channel.id
        bot._apex_tts_queues.setdefault(ctx.guild.id, asyncio.Queue())
        if ctx.guild.id not in bot._apex_tts_workers or bot._apex_tts_workers[ctx.guild.id].done():
            bot._apex_tts_workers[ctx.guild.id] = asyncio.create_task(tts_worker(ctx.guild.id))
        await ctx.send(embed=success_embed("Voice Connected", f"{ARROW} Joined **{channel.name}**.\n{ROCKET} Text messages in this chat can be spoken using TTS."))
    except Exception as e:
        await ctx.send(embed=error_embed("Voice Connection Failed", f"{ARROW} `{str(e)[:1000]}`\n{SUPPORTER} Install `PyNaCl`, `ffmpeg` and `edge-tts` on the VPS."))


@bot.command(name="botleave")
async def botleave(ctx):
    vc = ctx.guild.voice_client if ctx.guild else None
    if not vc or not vc.is_connected():
        await ctx.send(embed=info_embed("Voice", f"{ARROW} The bot is not currently in a voice channel."))
        return
    await vc.disconnect()
    bot._apex_voice_channels.pop(ctx.guild.id, None)
    await ctx.send(embed=success_embed("Voice Disconnected", f"{ARROW} APEX CLOULD™ has left the voice channel."))


# Extend the existing AutoMod/message pipeline with TTS after command processing.
_original_on_message = None

# ============================================================
# STARTUP
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from .env"
    )


if __name__ == "__main__":
    bot.run(TOKEN)
