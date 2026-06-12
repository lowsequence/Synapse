from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional, List

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from utils.paginator import Paginator as HackerPaginator
from utils.paginators import DescriptionEmbedPaginator
from cogs.engagement.prime import premium_check

DB_PATH      = "database/antinuke.db"
PREMIUM_DB   = "database/premium_codes.db"
COLOR        = 0x2b2d31

E_TICK   = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS  = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL   = "<:SynapseExcl:1477234549552320634>"
E_SHIELD = "<:synapseShield:1477548906848981225>"
E_SEARCH = "<:Synapse_search:1471871156783943812>"
E_WARN   = "<:IconsDanger:1477315376982397018>"
E_OK     = "<:emoji_1769867605256:1467155817726873650>"
E_NOTE   = "<:SynapseNote:1477236015830663324>"
E_LOCK   = "<:synapselock:1477546146095169649>"
E_UNLOCK = "<:synapseunlock:1477546157298155592>"
E_GEAR   = "<:synapseGear:1477546806232743999>"
E_STAR   = "<:Icon_Star:1477547731420581979>"
E_FIRE   = "<:SynapseFire:1477547713598849025>"

ALL_EVENTS = [
    "anti_member_update", "anti_ban", "anti_bot_add",
    "anti_channel_create", "anti_channel_delete", "anti_channel_update",
    "anti_integration", "anti_everyone", "anti_guild", "anti_kick",
    "anti_prune", "anti_role_create", "anti_role_update", "anti_role_delete",
    "anti_webhook_create", "anti_webhook_update", "anti_webhook_delete",
    "anti_emotes_create", "anti_emotes_delete", "anti_emotes_update",
    "anti_unban", "anti_admin_mention",
]

MANAGE_EVENTS = ALL_EVENTS + ["anti_linked_role", "anti_invite_role"]

EVENT_LABELS = {
    "anti_member_update":  "Anti Member Update",
    "anti_ban":            "Anti Ban",
    "anti_bot_add":        "Anti Bot Add",
    "anti_channel_create": "Anti Channel Create",
    "anti_channel_delete": "Anti Channel Delete",
    "anti_channel_update": "Anti Channel Update",
    "anti_integration":    "Anti Integration",
    "anti_everyone":       "Anti Everyone",
    "anti_guild":          "Anti Guild",
    "anti_kick":           "Anti Kick",
    "anti_prune":          "Anti Prune",
    "anti_role_create":    "Anti Role Create",
    "anti_role_update":    "Anti Role Update",
    "anti_role_delete":    "Anti Role Delete",
    "anti_webhook_create": "Anti Webhook Create",
    "anti_webhook_update": "Anti Webhook Update",
    "anti_webhook_delete": "Anti Webhook Delete",
    "anti_emotes_create":  "Anti Emotes Create",
    "anti_emotes_delete":  "Anti Emotes Delete",
    "anti_emotes_update":  "Anti Emotes Update",
    "anti_unban":          "Anti Unban",
    "anti_admin_mention":  "Anti Admin-Mention",
    "anti_linked_role":    "Anti Linked Role",
    "anti_invite_role":    "Anti Invite Role",
}


async def init_antinuke_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_config (
                guild_id        INTEGER PRIMARY KEY,
                enabled         INTEGER NOT NULL DEFAULT 0,
                punishment      TEXT    NOT NULL DEFAULT 'ban',
                log_channel_id  INTEGER,
                wall_role_id    INTEGER,
                quarantine_role_id INTEGER,
                autorecovery    INTEGER NOT NULL DEFAULT 0,
                panic_mode      INTEGER NOT NULL DEFAULT 0,
                night_mode      INTEGER NOT NULL DEFAULT 0,
                cynical_mode    INTEGER NOT NULL DEFAULT 0,
                quickrole       INTEGER NOT NULL DEFAULT 0,
                setup_at        TEXT
            )
        """)

        # MIGRATION FIX: Ensure legacy columns removed during previous "cleanup" are restored
        for col in ["night_mode", "cynical_mode", "quickrole"]:
            try:
                await db.execute(f"ALTER TABLE antinuke_config ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
                await db.commit()
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_events (
                guild_id  INTEGER NOT NULL,
                event     TEXT    NOT NULL,
                enabled   INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (guild_id, event)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_whitelist_users (
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL DEFAULT '[]',
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_whitelist_roles (
                guild_id  INTEGER NOT NULL,
                role_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL DEFAULT '[]',
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_admins (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_mainroles (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_limits (
                guild_id    INTEGER NOT NULL,
                event       TEXT    NOT NULL,
                max_actions INTEGER NOT NULL DEFAULT 50,
                PRIMARY KEY (guild_id, event)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS panic_whitelist_users_snapshot (
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS panic_whitelist_roles_snapshot (
                guild_id  INTEGER NOT NULL,
                role_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cynical_whitelist_users_snapshot (
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cynical_whitelist_roles_snapshot (
                guild_id  INTEGER NOT NULL,
                role_id   INTEGER NOT NULL,
                events    TEXT    NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS nightmode_role_snapshots (
                guild_id    INTEGER NOT NULL,
                role_id     INTEGER NOT NULL,
                perms_value INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        await db.commit()


class ANE:
    """Antinuke Embed helper — Premium Minimalist aesthetic style."""
    FOOTER = "Synapse Antinuke"
    URL_TICK   = "https://cdn.discordapp.com/emojis/1467155817726873650.png"
    URL_EXCL   = "https://cdn.discordapp.com/emojis/1477234549552320634.png"
    URL_SHIELD = "https://cdn.discordapp.com/emojis/1477548906848981225.png"
    URL_GEAR   = "https://cdn.discordapp.com/emojis/1477546806232743999.png"
    URL_WARN   = "https://cdn.discordapp.com/emojis/1477315376982397018.png"

    @staticmethod
    def success(text: str) -> discord.Embed:
        return discord.Embed(
            description=f"{E_TICK} {text}",
            color=0x2b2d31,
        )

    @staticmethod
    def error(text: str) -> discord.Embed:
        return discord.Embed(
            description=f"{E_EXCL} {text}",
            color=0x2b2d31,
        )

    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            description=description,
            color=0x2b2d31,
        ).set_author(name=title, icon_url=ANE.URL_SHIELD)

    @staticmethod
    def panel(title: str) -> discord.Embed:
        return discord.Embed(
            color=0x2b2d31,
        ).set_author(name=title, icon_url=ANE.URL_GEAR)


async def is_antinuke_admin(guild_id: int, user_id: int, bot: commands.Bot) -> bool:
    """Check if user is guild owner or added antinuke admin."""
    guild = bot.get_guild(guild_id)
    if guild and guild.owner_id == user_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ) as cur:
            return await cur.fetchone() is not None


async def get_config(guild_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM antinuke_config WHERE guild_id=?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    keys = [
        "guild_id", "enabled", "punishment", "log_channel_id",
        "wall_role_id", "quarantine_role_id", "autorecovery",
        "antibetray", "panic_mode", "night_mode", "cynical_mode", "quickrole", "setup_at",
    ]
    return dict(zip(keys, row))


async def get_enabled_events(guild_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT event FROM antinuke_events WHERE guild_id=? AND enabled=1",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            async with db.execute(
                "SELECT 1 FROM antinuke_events WHERE guild_id=? LIMIT 1", (guild_id,)
            ) as cur:
                has_any = await cur.fetchone()
            if not has_any:
                return list(ALL_EVENTS)
    return [r[0] for r in rows]


async def send_log(bot: commands.Bot, guild_id: int, embed: discord.Embed) -> None:
    """Send embed to the configured antinuke log channel."""
    cfg = await get_config(guild_id)
    if not cfg or not cfg.get("log_channel_id"):
        return
    ch = bot.get_channel(cfg["log_channel_id"])
    if ch:
        try:
            await ch.send(embed=embed)
        except Exception:
            pass


class SetupWizardView(discord.ui.View):
    """Animated confirm/cancel view for antinuke setup."""

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                embed=ANE.error("This is not your menu."), ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.green, emoji=E_TICK)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=E_CROSS)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=ANE.error("Setup cancelled."), view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class DisableConfirmView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                embed=ANE.error("This is not your menu."), ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, Disable", style=discord.ButtonStyle.red, emoji=E_WARN)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji=E_CROSS)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=ANE.error("Cancelled — antinuke is still active."), view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Antinuke(commands.Cog):
    """Main antinuke command group."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.color = COLOR

    async def _require_owner(self, ctx: commands.Context) -> bool:
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send(embed=ANE.error("Only the **server owner** can use this."))
            return False
        return True

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if not await is_antinuke_admin(ctx.guild.id, ctx.author.id, self.bot):
            await ctx.send(embed=ANE.error("Only the **server owner** or an **Antinuke Admin** can use this."))
            return False
        return True

    @commands.group(
        name="antinuke",
        aliases=["an"],
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke(self, ctx: commands.Context):
        """Antinuke base — shows help."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        embed = ANE.info(
            "Antinuke System",
            f"**Available subcommands:**\n"
            f"`setup` · `disable` · `config` · `reset`\n"
            f"`autorecovery` · `logging` · `manage`\n"
            f"`punishment` · `whitelist` · `antibetray` (Premium)",
        )
        await ctx.send(embed=embed)

    @antinuke.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def antinuke_setup(self, ctx: commands.Context):
        """Wizard-style antinuke setup: creates wall role, log channel, enables all modules."""
        if not await self._require_owner(ctx):
            return

        existing_cfg = await get_config(ctx.guild.id)
        if existing_cfg and existing_cfg.get("enabled"):
            enabled_evs = await get_enabled_events(ctx.guild.id)
            if enabled_evs:
                return await ctx.send(embed=ANE.error(
                    f"Antinuke is currently **active** with `{len(enabled_evs)}` event(s) enabled.\n"
                    f"- {E_WARN} Disable all events via `antinuke manage` before re-running setup."
                ))

        bot_role = ctx.guild.me.top_role
        admin_roles_above = [
            r for r in ctx.guild.roles
            if r.position > bot_role.position and r.permissions.administrator and not r.managed
        ]

        if admin_roles_above:
            roles_limit = 5
            roles_str = ", ".join(r.name for r in admin_roles_above[:roles_limit])
            if len(admin_roles_above) > roles_limit:
                roles_str += f" and {len(admin_roles_above) - roles_limit} others"

            embed_h = ANE.error(
                f"**Role Hierarchy Error**\n\n"
                f"The **{self.bot.user.name}** role is too low in the role hierarchy. "
                f"There are other **Administrator** roles above me: `{roles_str}`\n\n"
                f"To protect your server effectively, please **drag my role to the top** of the role list and try again."
            )
            return await ctx.send(embed=embed_h)

        embed1 = discord.Embed(
            description=(
                f"{E_STAR} **Welcome to the Synapse Antinuke Setup!**\n\n"
                f"**This wizard will:**\n"
                f"- Enable **all** antinuke modules\n"
                f"- Create a **Wall Role** (anti-nuke shield)\n"
                f"- Create a **logging channel** (`Synapse-Antinuke`)\n"
                f"- Set default punishment to **Ban**\n\n"
                f"Press **Confirm Setup** to proceed."
            ),
            color=COLOR,
            timestamp=datetime.utcnow(),
        )
        embed1.set_author(name="Antinuke Setup Wizard", icon_url=ANE.URL_SHIELD)
        embed1.set_footer(text=ANE.FOOTER)
        embed1.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)

        view = SetupWizardView(ctx)
        msg = await ctx.send(embed=embed1, view=view)
        await view.wait()

        if not view.confirmed:
            return

        embed2 = discord.Embed(
            description=f"<a:Loadixd:1469568214169288890> Initialising database…",
            color=COLOR,
        )
        embed2.set_author(name="Setting up Antinuke…", icon_url=ANE.URL_SHIELD)
        embed2.set_footer(text=ANE.FOOTER)
        await msg.edit(embed=embed2, view=None)
        await asyncio.sleep(0.8)

        errors: list[str] = []

        wall_role = None
        try:
            wall_role = await ctx.guild.create_role(
                name="Synapse Unbypassable Security™",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.from_str("#DBDBDB"),
                reason="Synapse Antinuke — Wall Role",
            )
            bot_top = ctx.guild.me.top_role.position
            try:
                await wall_role.edit(position=max(bot_top - 1, 1))
            except Exception:
                pass
            await ctx.guild.me.add_roles(wall_role, reason="Synapse Antinuke — Wall Role assigned to bot")
        except Exception as e:
            errors.append(f"Wall role: `{e}`")

        embed2.description = f"<a:Loadixd:1469568214169288890> Creating logging channel…"
        await msg.edit(embed=embed2)
        await asyncio.sleep(0.8)

        log_channel = None
        try:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                ctx.guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, embed_links=True
                ),
            }
            if wall_role:
                overwrites[wall_role] = discord.PermissionOverwrite(view_channel=True)
            log_channel = await ctx.guild.create_text_channel(
                name="synapse-antinuke",
                topic="Synapse Antinuke — Moderation Logs",
                overwrites=overwrites,
                reason="Synapse Antinuke — Log Channel",
            )
        except Exception as e:
            errors.append(f"Log channel: `{e}`")

        embed2.description = f"<a:Loadixd:1469568214169288890> Saving configuration…"
        await msg.edit(embed=embed2)
        await asyncio.sleep(0.6)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO antinuke_config
                    (guild_id, enabled, punishment, log_channel_id, wall_role_id,
                     autorecovery, panic_mode, night_mode, cynical_mode, quickrole, setup_at)
                VALUES (?, 1, 'ban', ?, ?, 1, 0, 0, 0, 0, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    enabled=1, punishment='ban',
                    autorecovery=1,
                    log_channel_id=excluded.log_channel_id,
                    wall_role_id=excluded.wall_role_id,
                    setup_at=excluded.setup_at
                """,
                (
                    ctx.guild.id,
                    log_channel.id if log_channel else None,
                    wall_role.id if wall_role else None,
                    datetime.utcnow().isoformat(),
                ),
            )
            for event in MANAGE_EVENTS:
                await db.execute(
                    "INSERT OR REPLACE INTO antinuke_events (guild_id, event, enabled) VALUES (?,?,1)",
                    (ctx.guild.id, event),
                )
            await db.commit()

        await asyncio.sleep(0.5)

        embed_done = discord.Embed(
            description=(
                f"{E_STAR} **Synapse Antinuke is now protecting your server.**\n\n"
                + (f"- **Warnings:**\n" + "\n".join(errors) + "\n\n" if errors else "")
                + f"Use `antinuke config` to view full status."
            ),
            color=COLOR,
            timestamp=datetime.utcnow(),
        )
        embed_done.set_author(name="Antinuke Activated!", icon_url=ANE.URL_SHIELD)
        embed_done.add_field(
            name="Security Assets",
            value=f"- **Wall Role:** {wall_role.mention if wall_role else '`Failed`'}\n- **Log Channel:** {log_channel.mention if log_channel else '`Failed`'}",
            inline=False
        )
        embed_done.add_field(
            name="Active Modules",
            value=f"- **Punishment:** `Ban`\n- **Modules:** All `{len(MANAGE_EVENTS)}` enabled\n- **Autorecovery:** Enabled",
            inline=False
        )
        embed_done.set_footer(text=ANE.FOOTER)
        embed_done.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)
        await msg.edit(embed=embed_done)

    @antinuke.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def antinuke_disable(self, ctx: commands.Context):
        """Disable the entire antinuke system."""
        if ctx.author.id != 1368989570816802886 and not await self._require_owner(ctx):
            return

        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg["enabled"]:
            return await ctx.send(embed=ANE.error("Antinuke is already **disabled**."))

        embed = discord.Embed(
            description=(
                f"- {E_EXCL} Are you sure you want to **completely disable** the antinuke system?\n"
                f"- This will leave your server **unprotected**."
            ),
            color=0x2b2d31,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=ANE.FOOTER)

        view = DisableConfirmView(ctx)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT log_channel_id, wall_role_id FROM antinuke_config WHERE guild_id=?",
                (ctx.guild.id,),
            ) as cur:
                row = await cur.fetchone()
            await db.execute(
                "UPDATE antinuke_config SET enabled=0 WHERE guild_id=?",
                (ctx.guild.id,),
            )
            await db.commit()

        if row:
            log_ch_id, wall_role_id = row
            if log_ch_id:
                ch = ctx.guild.get_channel(log_ch_id)
                if ch:
                    try:
                        await ch.delete(reason="[Antinuke] Disabled — log channel removed")
                    except Exception:
                        pass
            if wall_role_id:
                wr = ctx.guild.get_role(wall_role_id)
                if wr:
                    try:
                        await wr.delete(reason="[Antinuke] Disabled — wall role removed")
                    except Exception:
                        pass

        await msg.edit(
            embed=ANE.success("Antinuke system has been **disabled**. Log channel and wall role deleted."),
            view=None,
        )

    @antinuke.command(name="config", aliases=["cfg", "status"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_config(self, ctx: commands.Context):
        """Display full antinuke configuration for this guild."""
        if not await self._require_admin(ctx):
            return

        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=ANE.error("Antinuke is not set up. Run `antinuke setup` first."))

        enabled_events = await get_enabled_events(ctx.guild.id)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM antinuke_admins WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                admin_count = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COUNT(*) FROM antinuke_whitelist_users WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                wl_user_count = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COUNT(*) FROM antinuke_whitelist_roles WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                wl_role_count = (await cur.fetchone())[0]

        log_ch = ctx.guild.get_channel(cfg["log_channel_id"]) if cfg["log_channel_id"] else None
        status_str   = f"{E_TICK} Enabled"  if cfg["enabled"]       else f"{E_CROSS} Disabled"
        ar_str       = f"{E_TICK} Enabled"  if cfg["autorecovery"]  else f"{E_CROSS} Disabled"
        pm_str       = f"{E_TICK} Enabled"  if cfg["panic_mode"]    else f"{E_CROSS} Disabled"
        qr_str       = f"{E_TICK} Enabled"  if cfg["quickrole"]     else f"{E_CROSS} Disabled"
        ab_str       = f"{E_TICK} Enabled"  if cfg.get("antibetray") else f"{E_CROSS} Disabled"
        log_str      = log_ch.mention       if log_ch               else "`Not Set`"
        punch_str    = f"`{cfg['punishment'].capitalize()}`"

        event_lines = ""
        for ev in MANAGE_EVENTS:
            icon = E_TICK if ev in enabled_events else E_CROSS
            event_lines += f"{icon} {EVENT_LABELS[ev]}\n"

        embed = ANE.panel(f"Antinuke Config — {ctx.guild.name}")
        embed.add_field(
            name="General Settings",
            value=f"**Status:** {status_str}\n**Punishment:** {punch_str}\n**Log Channel:** {log_str}",
            inline=True
        )
        embed.add_field(
            name="Access Control",
            value=f"**Admins:** `{admin_count}`\n**WL Users:** `{wl_user_count}`\n**WL Roles:** `{wl_role_count}`",
            inline=True
        )
        embed.add_field(
            name="Sub-Systems",
            value=f"**Auto-Recovery:** {ar_str}\n**Panic Mode:** {pm_str}\n**Quickrole:** {qr_str}\n**Antibetray:** {ab_str} (Threshold: `{cfg.get('antibetray_threshold', 3)}`)",
            inline=False
        )
        view = ConfigView(ctx, enabled_events)
        await ctx.send(embed=embed, view=view)

    @antinuke.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def antinuke_reset(self, ctx: commands.Context):
        """Reset specific parts of the antinuke configuration."""
        if not await self._require_admin(ctx):
            return
        view = ResetView(ctx)
        embed = ANE.panel("Antinuke Reset")
        embed.description = (
            f"- {E_NOTE} Select what you want to reset from the dropdown.\n"
            f"- Press **Select All** to reset everything, then **Confirm**."
        )
        await ctx.send(embed=embed, view=view)

    @antinuke.group(name="autorecovery", aliases=["ar"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_autorecovery(self, ctx: commands.Context):
        embed = ANE.info(
            "Auto-Recovery",
            f"Auto-Recovery automatically restores roles and channels after a nuke attempt.\n\n"
            f"**Subcommands:** `enable` · `disable`",
        )
        await ctx.send(embed=embed)

    @antinuke_autorecovery.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def autorecovery_enable(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT autorecovery FROM antinuke_config WHERE guild_id=?", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()
            if row and row[0] == 1:
                return await ctx.send(embed=ANE.error("**Auto-Recovery** is already enabled."))

            await db.execute(
                "UPDATE antinuke_config SET autorecovery=1 WHERE guild_id=?",
                (ctx.guild.id,),
            )
            await db.commit()
        await ctx.send(embed=ANE.success("**Auto-Recovery** has been **enabled**."))

    @antinuke_autorecovery.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def autorecovery_disable(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT autorecovery FROM antinuke_config WHERE guild_id=?", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()
            if not row or row[0] == 0:
                return await ctx.send(embed=ANE.error("**Auto-Recovery** is not enabled."))

            await db.execute(
                "UPDATE antinuke_config SET autorecovery=0 WHERE guild_id=?",
                (ctx.guild.id,),
            )
            await db.commit()
        await ctx.send(embed=ANE.success("**Auto-Recovery** has been **disabled**."))

    @antinuke.group(name="logging", aliases=["log"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_logging(self, ctx: commands.Context):
        embed = ANE.info("Antinuke Logging", "Subcommands: `set <channel>` · `reset`")
        await ctx.send(embed=embed)

    @antinuke_logging.command(name="set")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def logging_set(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._require_admin(ctx):
            return
        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=ANE.error("Run `antinuke setup` first."))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE antinuke_config SET log_channel_id=? WHERE guild_id=?",
                (channel.id, ctx.guild.id),
            )
            await db.commit()
        await ctx.send(embed=ANE.success(f"Logging channel set to {channel.mention}."))

    @antinuke_logging.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def logging_reset(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE antinuke_config SET log_channel_id=NULL WHERE guild_id=?",
                (ctx.guild.id,),
            )
            await db.commit()
        await ctx.send(embed=ANE.success("Logging channel has been **reset**."))

    @antinuke.group(name="punishment", aliases=["punish"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_punishment(self, ctx: commands.Context):
        embed = ANE.info("Punishment", "Subcommands: `set <ban|kick|quarantine>`")
        await ctx.send(embed=embed)

    @antinuke_punishment.command(name="set")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def punishment_set(self, ctx: commands.Context, mode: str):
        if not await self._require_owner(ctx):
            return
        mode = mode.lower()
        if mode not in ("ban", "kick", "quarantine"):
            return await ctx.send(embed=ANE.error("Valid modes: `ban`, `kick`, `quarantine`."))

        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=ANE.error("Run `antinuke setup` first."))

        quarantine_role_id = cfg.get("quarantine_role_id")

        if mode == "quarantine" and not quarantine_role_id:
            try:
                qr = await ctx.guild.create_role(
                    name="Antinuke Quarantine",
                    permissions=discord.Permissions.none(),
                    color=discord.Color.dark_red(),
                    reason="Synapse Antinuke — Quarantine Role",
                )
                for ch in ctx.guild.channels:
                    try:
                        await ch.set_permissions(
                            qr,
                            send_messages=False,
                            read_messages=False,
                            connect=False,
                            reason="Antinuke Quarantine setup",
                        )
                    except Exception:
                        pass
                quarantine_role_id = qr.id
            except Exception as e:
                return await ctx.send(embed=ANE.error(f"Could not create quarantine role: `{e}`"))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE antinuke_config SET punishment=?, quarantine_role_id=? WHERE guild_id=?",
                (mode, quarantine_role_id, ctx.guild.id),
            )
            await db.commit()

        extra = " Quarantine role created and configured." if mode == "quarantine" and not cfg.get("quarantine_role_id") else ""
        await ctx.send(embed=ANE.success(f"Punishment mode set to **{mode.capitalize()}**.{extra}"))

    @antinuke.command(name="manage")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 8, commands.BucketType.guild)
    async def antinuke_manage(self, ctx: commands.Context):
        """Interactive panel to enable/disable antinuke events."""
        if not await self._require_admin(ctx):
            return
        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=ANE.error("Run `antinuke setup` first."))
        if not cfg["enabled"]:
            return await ctx.send(embed=ANE.error("Antinuke is currently **disabled**. Enable it first."))

        enabled = await get_enabled_events(ctx.guild.id)
        enabled_set = set(enabled)
        view = ManageEventsView(ctx, enabled_set)
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @antinuke.command(name="limit")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_limit(self, ctx: commands.Context, module: str, limit: int):
        """Set the whitelist action limit for a specific antinuke module."""
        if not await self._require_admin(ctx):
            return
        module = module.lower()
        if module not in ALL_EVENTS:
            suggestions = [e for e in ALL_EVENTS if module in e]
            hint = f" Did you mean: `{'`, `'.join(suggestions)}`?" if suggestions else ""
            return await ctx.send(embed=ANE.error(f"Unknown module `{module}`.{hint}\nUse `antinuke limits` to see all events."))
        if limit < 1 or limit > 999:
            return await ctx.send(embed=ANE.error("Limit must be between **1** and **999**."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO antinuke_limits (guild_id, event, max_actions) VALUES (?,?,?) "
                "ON CONFLICT(guild_id, event) DO UPDATE SET max_actions=excluded.max_actions",
                (ctx.guild.id, module, limit),
            )
            await db.commit()

        from utils.acore import invalidate_guild_cache
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ANE.success(f"**{EVENT_LABELS.get(module, module)}** limit set to **{limit}** actions per 60s."))

    @antinuke.command(name="limits")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antinuke_limits(self, ctx: commands.Context):
        """View all whitelist action limits."""
        if not await self._require_admin(ctx):
            return

        custom: dict[str, int] = {}
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT event, max_actions FROM antinuke_limits WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                rows = await cur.fetchall()
        for event, limit in rows:
            custom[event] = limit

        from utils.acore import DEFAULT_LIMIT
        lines = []
        for ev in ALL_EVENTS:
            lim = custom.get(ev, DEFAULT_LIMIT)
            marker = f"  *(custom)*" if ev in custom else ""
            lines.append(f"**{EVENT_LABELS.get(ev, ev)}:** `{lim}`{marker}")

        mid = len(lines) // 2
        embed = discord.Embed(color=COLOR)
        embed.set_author(name="Antinuke Whitelist Limits", icon_url=ANE.URL_SHIELD)
        embed.description = (
            f"> Whitelisted users/roles are allowed up to this many actions\n"
            f"> per event within a **60-second** window before being punished.\n\n"
            + "\n".join(lines[:mid]) + "\n\n" + "\n".join(lines[mid:])
        )
        embed.set_footer(text=f"Synapse Antinuke — Default: {DEFAULT_LIMIT} | Use: antinuke limit <module> <value>")
        await ctx.send(embed=embed)


RESET_OPTIONS = {
    "logging":   "Reset Logging Channel",
    "config":    "Reset Antinuke Config",
    "whitelist": "Reset Whitelist Config",
    "all":       "Reset EVERYTHING",
}


class ResetSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=value, emoji=E_WARN)
            for value, label in RESET_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Select what to reset…",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected = set(self.values)
        await interaction.response.defer()


class ResetView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.selected: set[str] = set()
        self.add_item(ResetSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=ANE.error("Not your menu."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Select All", style=discord.ButtonStyle.secondary, emoji=E_STAR, row=1)
    async def select_all(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.selected = set(RESET_OPTIONS.keys())
        await interaction.response.send_message(
            embed=ANE.info("Selection", "All options selected. Press **Confirm** to proceed."),
            ephemeral=True,
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji=E_TICK, row=1)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.selected:
            return await interaction.response.send_message(
                embed=ANE.error("Select at least one option."), ephemeral=True
            )
        guild_id = self.ctx.guild.id
        msgs: list[str] = []

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT log_channel_id, wall_role_id FROM antinuke_config WHERE guild_id=?", (guild_id,)
            ) as cur:
                cfg_row = await cur.fetchone()

            if "all" in self.selected or "logging" in self.selected:
                await db.execute(
                    "UPDATE antinuke_config SET log_channel_id=NULL WHERE guild_id=?", (guild_id,)
                )
                msgs.append("Logging channel reset")

            if "all" in self.selected or "config" in self.selected:
                await db.execute("DELETE FROM antinuke_config WHERE guild_id=?", (guild_id,))
                await db.execute("DELETE FROM antinuke_events WHERE guild_id=?", (guild_id,))
                msgs.append("Antinuke config reset")

            if "all" in self.selected or "whitelist" in self.selected:
                await db.execute(
                    "DELETE FROM antinuke_whitelist_users WHERE guild_id=?", (guild_id,)
                )
                await db.execute(
                    "DELETE FROM antinuke_whitelist_roles WHERE guild_id=?", (guild_id,)
                )
                msgs.append("Whitelist config reset")

            await db.commit()

        if cfg_row and ("all" in self.selected or "config" in self.selected):
            log_ch_id, wall_role_id = cfg_row
            guild = self.ctx.guild
            if log_ch_id:
                ch = guild.get_channel(log_ch_id)
                if ch:
                    try:
                        await ch.delete(reason="[Antinuke] Reset — log channel removed")
                    except Exception:
                        pass
            if wall_role_id:
                wr = guild.get_role(wall_role_id)
                if wr:
                    try:
                        await wr.delete(reason="[Antinuke] Reset — wall role removed")
                    except Exception:
                        pass

        self.stop()
        await interaction.response.edit_message(
            embed=ANE.success(f"Reset complete: {', '.join(msgs)}."),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=E_CROSS, row=1)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=ANE.error("Reset cancelled."), view=None)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def _build_manage_embed(to_enable: set) -> discord.Embed:
    embed = discord.Embed(title=f"{E_SHIELD} Antinuke Event Manager", color=COLOR)
    mid = len(MANAGE_EVENTS) // 2
    group1 = MANAGE_EVENTS[:mid]
    group2 = MANAGE_EVENTS[mid:]

    def fmt_group(events):
        return "\n".join(
            f"**{EVENT_LABELS[ev]} `:`** {E_TICK if ev in to_enable else E_CROSS}"
            for ev in events
        )

    enabled_count = sum(1 for ev in MANAGE_EVENTS if ev in to_enable)
    embed.description = (
        f"- {E_NOTE} Top dropdown **enables** · Bottom dropdown **disables**\n\n"
        f"**Events [1] ({enabled_count}/{len(MANAGE_EVENTS)} on)**\n{fmt_group(group1)}"
        f"\n\n**Events [2]**\n{fmt_group(group2)}"
    )
    embed.set_footer(text="Synapse Antinuke — Event Manager")
    return embed


class _EnableSelect(discord.ui.Select):
    """Row 0 — shows disabled events; selecting enables them."""
    def __init__(self, disabled_evs: list, row: int = 0):
        if disabled_evs:
            opts = [
                discord.SelectOption(label=EVENT_LABELS[e], value=e)
                for e in disabled_evs[:25]
            ]
            mx = len(opts)
        else:
            opts = [discord.SelectOption(label="All events are enabled", value="__none__")]
            mx = 1
        super().__init__(placeholder=f"Enable events… ({len(disabled_evs)} disabled)", min_values=0, max_values=mx, options=opts, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for v in self.values:
            if v != "__none__":
                view.to_enable.add(v)
        view._rebuild()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class _DisableSelect(discord.ui.Select):
    """Row 1 — shows enabled events; selecting disables them."""
    def __init__(self, enabled_evs: list, row: int = 1):
        if enabled_evs:
            opts = [
                discord.SelectOption(label=EVENT_LABELS[e], value=e)
                for e in enabled_evs[:25]
            ]
            mx = len(opts)
        else:
            opts = [discord.SelectOption(label="No events are enabled", value="__none__")]
            mx = 1
        super().__init__(placeholder=f"Disable events… ({len(enabled_evs)} enabled)", min_values=0, max_values=mx, options=opts, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for v in self.values:
            if v != "__none__":
                view.to_enable.discard(v)
        view._rebuild()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class ManageEventsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, enabled: set):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.to_enable: set = set(enabled)
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        disabled_evs = [ev for ev in MANAGE_EVENTS if ev not in self.to_enable]
        enabled_evs  = [ev for ev in MANAGE_EVENTS if ev in self.to_enable]
        self.add_item(_EnableSelect(disabled_evs, row=0))
        self.add_item(_DisableSelect(enabled_evs,  row=1))

        btn_all = discord.ui.Button(label="Enable All",  style=discord.ButtonStyle.secondary, emoji=E_STAR,  row=2)
        btn_all.callback = self._select_all
        self.add_item(btn_all)

        btn_none = discord.ui.Button(label="Disable All", style=discord.ButtonStyle.secondary, emoji=E_CROSS, row=2)
        btn_none.callback = self._disable_all
        self.add_item(btn_none)

        btn_ok = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green, emoji=E_TICK, row=2)
        btn_ok.callback = self._confirm
        self.add_item(btn_ok)

        btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji=E_CROSS, row=2)
        btn_cancel.callback = self._cancel
        self.add_item(btn_cancel)

    def build_embed(self) -> discord.Embed:
        return _build_manage_embed(self.to_enable)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=ANE.error("Not your menu."), ephemeral=True)
            return False
        return True

    async def _select_all(self, interaction: discord.Interaction):
        self.to_enable = set(MANAGE_EVENTS)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _disable_all(self, interaction: discord.Interaction):
        self.to_enable = set()
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _confirm(self, interaction: discord.Interaction):
        guild_id = self.ctx.guild.id
        async with aiosqlite.connect(DB_PATH) as db:
            for event in MANAGE_EVENTS:
                enabled_val = 1 if event in self.to_enable else 0
                await db.execute(
                    "INSERT OR REPLACE INTO antinuke_events (guild_id, event, enabled) VALUES (?,?,?)",
                    (guild_id, event, enabled_val),
                )
            await db.commit()
        self.stop()
        await interaction.response.edit_message(
            embed=ANE.success(f"Event settings saved — **{len(self.to_enable)}/{len(MANAGE_EVENTS)}** events enabled."),
            view=None,
        )

    async def _cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(embed=ANE.error("Event manager cancelled."), view=None)

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True


import json as _json


def _build_whitelist_embed(target_name: str, target_mention: str, selected: set) -> discord.Embed:
    embed = discord.Embed(title=f"{E_SHIELD} Whitelist — {target_name}", color=COLOR)
    mid    = len(ALL_EVENTS) // 2
    group1 = ALL_EVENTS[:mid]
    group2 = ALL_EVENTS[mid:]

    def fmt(events):
        return "\n".join(
            f"**{EVENT_LABELS[ev]}:** {E_TICK if ev in selected else E_CROSS}"
            for ev in events
        )

    wl_count = len(selected)
    embed.description = (
        f"- {E_NOTE} Top dropdown **adds** · Bottom dropdown **removes**\n"
        f"- Whitelisted events will **not** trigger antinuke for {target_mention}.\n\n"
        f"**Events [1] ({wl_count}/{len(ALL_EVENTS)} whitelisted)**\n{fmt(group1)}"
        f"\n\n**Events [2]**\n{fmt(group2)}"
    )
    embed.set_footer(text="Synapse Antinuke — Whitelist Manager")
    return embed


class _WLEnableSelect(discord.ui.Select):
    """Row 0 — unwhitelisted events; selecting adds to whitelist."""
    def __init__(self, unwhitelisted: list, row: int = 0):
        if unwhitelisted:
            opts = [discord.SelectOption(label=EVENT_LABELS[e], value=e) for e in unwhitelisted[:25]]
            mx = len(opts)
        else:
            opts = [discord.SelectOption(label="All events whitelisted", value="__none__")]
            mx = 1
        super().__init__(placeholder=f"Add to whitelist… ({len(unwhitelisted)} not set)", min_values=0, max_values=mx, options=opts, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for v in self.values:
            if v != "__none__":
                view.selected_events.add(v)
        view._rebuild()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class _WLDisableSelect(discord.ui.Select):
    """Row 1 — whitelisted events; selecting removes from whitelist."""
    def __init__(self, whitelisted: list, row: int = 1):
        if whitelisted:
            opts = [discord.SelectOption(label=EVENT_LABELS[e], value=e) for e in whitelisted[:25]]
            mx = len(opts)
        else:
            opts = [discord.SelectOption(label="No events whitelisted", value="__none__")]
            mx = 1
        super().__init__(placeholder=f"Remove from whitelist… ({len(whitelisted)} set)", min_values=0, max_values=mx, options=opts, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for v in self.values:
            if v != "__none__":
                view.selected_events.discard(v)
        view._rebuild()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class WhitelistAddView(discord.ui.View):
    def __init__(self, ctx: commands.Context, target_name: str, target_mention: str, existing: set = None):
        super().__init__(timeout=90)
        self.ctx = ctx
        self.target_name = target_name
        self.target_mention = target_mention
        self.selected_events: set = set(existing or set())
        self.confirmed = False
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        unwhitelisted = [ev for ev in ALL_EVENTS if ev not in self.selected_events]
        whitelisted   = [ev for ev in ALL_EVENTS if ev in self.selected_events]
        self.add_item(_WLEnableSelect(unwhitelisted, row=0))
        self.add_item(_WLDisableSelect(whitelisted,   row=1))

        btn_all = discord.ui.Button(label="Select All", style=discord.ButtonStyle.secondary, emoji=E_STAR, row=2)
        btn_all.callback = self._select_all
        self.add_item(btn_all)

        btn_ok = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green, emoji=E_TICK, row=2)
        btn_ok.callback = self._confirm
        self.add_item(btn_ok)

        btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji=E_CROSS, row=2)
        btn_cancel.callback = self._cancel
        self.add_item(btn_cancel)

    def build_embed(self) -> discord.Embed:
        return _build_whitelist_embed(self.target_name, self.target_mention, self.selected_events)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=ANE.error("Not your menu."), ephemeral=True)
            return False
        return True

    async def _select_all(self, interaction: discord.Interaction):
        self.selected_events = set(ALL_EVENTS)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _confirm(self, interaction: discord.Interaction):
        if not self.selected_events:
            return await interaction.response.send_message(embed=ANE.error("Select at least one event."), ephemeral=True)
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    async def _cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(embed=ANE.error("Cancelled."), view=None)

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True


class ConfigView(discord.ui.View):
    def __init__(self, ctx: commands.Context, enabled_events: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.enabled_events = enabled_events

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=ANE.error("Not your panel."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="View Events", style=discord.ButtonStyle.secondary)
    async def view_events(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.enabled_events:
            return await interaction.response.send_message(embed=ANE.error("No events are currently enabled."), ephemeral=True)
        lines = [f"{E_TICK} {EVENT_LABELS.get(ev, ev)}" for ev in MANAGE_EVENTS if ev in self.enabled_events]
        embed = discord.Embed(
            title=f"{E_SHIELD} Enabled Events ({len(lines)})",
            description="\n".join(lines) or "*None*",
            color=COLOR,
        ).set_footer(text=ANE.FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AntiNukeWhitelist(commands.Cog):
    """antinuke whitelist / wl commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if not await is_antinuke_admin(ctx.guild.id, ctx.author.id, self.bot):
            await ctx.send(embed=ANE.error("Only the **server owner** or an **Antinuke Admin** can use this."))
            return False
        return True

    @commands.group(name="whitelist", aliases=["wl"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def whitelist(self, ctx: commands.Context):
        embed = ANE.info("Antinuke Whitelist", "**Subgroups:** `user` · `role` · `violations`\n**Alias:** `wl`")
        await ctx.send(embed=embed)

    @whitelist.group(name="user", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def whitelist_user(self, ctx: commands.Context):
        embed = ANE.info("Whitelist — User", "**Subcommands:** `set` · `remove` · `list` · `reset`")
        await ctx.send(embed=embed)

    @whitelist_user.command(name="set")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_user_set(self, ctx: commands.Context, member: discord.Member):
        if not await self._require_admin(ctx):
            return
        existing: set = set()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT events FROM antinuke_whitelist_users WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, member.id),
            ) as cur:
                row = await cur.fetchone()
        if row:
            import json as _j
            existing = set(_j.loads(row[0]))
        view = WhitelistAddView(ctx, str(member), member.mention, existing=existing)
        msg = await ctx.send(embed=view.build_embed(), view=view)
        await view.wait()
        if not view.confirmed:
            return
        events_json = _json.dumps(list(view.selected_events))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO antinuke_whitelist_users (guild_id, user_id, events) VALUES (?,?,?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET events=excluded.events",
                (ctx.guild.id, member.id, events_json),
            )
            await db.commit()
        await msg.edit(embed=ANE.success(f"**{member.mention}** whitelisted for `{len(view.selected_events)}` events."), view=None)

    @whitelist_user.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_user_remove(self, ctx: commands.Context, member: discord.Member):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM antinuke_whitelist_users WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id)) as cur:
                if not await cur.fetchone():
                    return await ctx.send(embed=ANE.error(f"**{member}** is not whitelisted."))
            await db.execute("DELETE FROM antinuke_whitelist_users WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.send(embed=ANE.success(f"**{member.mention}** removed from whitelist."))

    @whitelist_user.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_user_list(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, events FROM antinuke_whitelist_users WHERE guild_id=?", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.send(embed=ANE.error("No whitelisted users."))
        entries = [f"{E_TICK} {ctx.guild.get_member(uid) or uid} — `{len(_json.loads(ev))}` events" for uid, ev in rows]
        source = DescriptionEmbedPaginator(entries, per_page=10, title="Whitelisted Users")
        await HackerPaginator(source, ctx=ctx).paginate()

    @whitelist_user.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def wl_user_reset(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM antinuke_whitelist_users WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        await ctx.send(embed=ANE.success("All whitelisted users have been **reset**."))

    @whitelist.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def whitelist_role(self, ctx: commands.Context):
        embed = ANE.info("Whitelist — Role", "**Subcommands:** `set` · `remove` · `list` · `reset`")
        await ctx.send(embed=embed)

    @whitelist_role.command(name="set")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_role_set(self, ctx: commands.Context, role: discord.Role):
        if not await self._require_admin(ctx):
            return
        existing: set = set()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT events FROM antinuke_whitelist_roles WHERE guild_id=? AND role_id=?",
                (ctx.guild.id, role.id),
            ) as cur:
                row = await cur.fetchone()
        if row:
            import json as _j
            existing = set(_j.loads(row[0]))
        view = WhitelistAddView(ctx, role.name, role.mention, existing=existing)
        msg = await ctx.send(embed=view.build_embed(), view=view)
        await view.wait()
        if not view.confirmed:
            return
        events_json = _json.dumps(list(view.selected_events))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO antinuke_whitelist_roles (guild_id, role_id, events) VALUES (?,?,?) "
                "ON CONFLICT(guild_id, role_id) DO UPDATE SET events=excluded.events",
                (ctx.guild.id, role.id, events_json),
            )
            await db.commit()
        await msg.edit(embed=ANE.success(f"**{role.mention}** whitelisted for `{len(view.selected_events)}` events."), view=None)

    @whitelist_role.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_role_remove(self, ctx: commands.Context, role: discord.Role):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM antinuke_whitelist_roles WHERE guild_id=? AND role_id=?", (ctx.guild.id, role.id)) as cur:
                if not await cur.fetchone():
                    return await ctx.send(embed=ANE.error(f"**{role.name}** is not whitelisted."))
            await db.execute("DELETE FROM antinuke_whitelist_roles WHERE guild_id=? AND role_id=?", (ctx.guild.id, role.id))
            await db.commit()
        await ctx.send(embed=ANE.success(f"**{role.mention}** removed from whitelist."))

    @whitelist_role.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_role_list(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id, events FROM antinuke_whitelist_roles WHERE guild_id=?", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.send(embed=ANE.error("No whitelisted roles."))
        entries = []
        for rid, ev in rows:
            r = ctx.guild.get_role(rid)
            entries.append(f"{E_TICK} {r.mention if r else rid} — `{len(_json.loads(ev))}` events")
        source = DescriptionEmbedPaginator(entries, per_page=10, title="Whitelisted Roles")
        await HackerPaginator(source, ctx=ctx).paginate()

    @whitelist_role.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def wl_role_reset(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM antinuke_whitelist_roles WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        await ctx.send(embed=ANE.success("All whitelisted roles have been **reset**."))

    @whitelist.group(name="violations", aliases=["v", "viol"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def wl_violations(self, ctx: commands.Context):
        """Whitelist violation management."""
        if not await self._require_admin(ctx):
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @wl_violations.command(name="list", aliases=["ls"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def viol_list(self, ctx: commands.Context):
        """See flagged members with violations."""
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, COUNT(*) as cnt, MAX(timestamp) as last_ts "
                "FROM antinuke_violations WHERE guild_id=? "
                "GROUP BY user_id ORDER BY cnt DESC",
                (ctx.guild.id,),
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.send(embed=ANE.error("No violations recorded."))

        entries = []
        for uid, cnt, last_ts in rows:
            member = ctx.guild.get_member(uid)
            name = member.mention if member else f"`{uid}`"
            entries.append(f"{E_WARN} {name} — **{cnt}** violation{'s' if cnt != 1 else ''} — Last: `{last_ts[:16]}`")

        source = DescriptionEmbedPaginator(entries, per_page=10, title="Whitelist Violations")
        await HackerPaginator(source, ctx=ctx).paginate()

    @wl_violations.command(name="info", aliases=["check"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def viol_info(self, ctx: commands.Context, member: discord.Member):
        """Check violation history for a specific user."""
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT event, count, punished, timestamp FROM antinuke_violations "
                "WHERE guild_id=? AND user_id=? ORDER BY id DESC",
                (ctx.guild.id, member.id),
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.send(embed=ANE.error(f"No violations found for **{member}**."))

        entries = []
        for event, count, punished, ts in rows:
            label = EVENT_LABELS.get(event, event)
            entries.append(
                f"{E_WARN} **{label}** — `{count}` actions — {punished} — `{ts[:16]}`"
            )

        source = DescriptionEmbedPaginator(entries, per_page=10, title=f"Violations — {member}")
        await HackerPaginator(source, ctx=ctx).paginate()

    @wl_violations.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def viol_reset(self, ctx: commands.Context, member: discord.Member):
        """Clear violations for a specific user."""
        if not await self._require_admin(ctx):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute(
                "DELETE FROM antinuke_violations WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, member.id),
            )
            count = c.rowcount
            await db.commit()
        if count == 0:
            return await ctx.send(embed=ANE.error(f"No violations found for **{member}**."))
        await ctx.send(embed=ANE.success(f"Cleared **{count}** violation(s) for {member.mention}."))

    @wl_violations.command(name="clear", aliases=["purge"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def viol_clear(self, ctx: commands.Context):
        """Clear ALL violations for this server."""
        if not await self._require_admin(ctx):
            return

        view = _ViolClearConfirm(ctx)
        embed = discord.Embed(
            description=(
                f"{E_EXCL} This will **permanently delete all violations** for this server.\n"
                f"Are you sure?"
            ),
            color=0xFF5555,
        )
        embed.set_author(name="Clear All Violations?", icon_url=ANE.URL_WARN)
        embed.set_footer(text=ANE.FOOTER)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        if not view.confirmed:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM antinuke_violations WHERE guild_id=?", (ctx.guild.id,))
            count = c.rowcount
            await db.commit()
        await msg.edit(embed=ANE.success(f"Cleared **{count}** violation(s) server-wide."), view=None)


class _ViolClearConfirm(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, Clear All", style=discord.ButtonStyle.red)
    async def yes_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def no_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=ANE.error("Cancelled."), view=None)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot) -> None:
    await init_antinuke_db()
    await bot.add_cog(Antinuke(bot))
    await bot.add_cog(AntiNukeWhitelist(bot))
