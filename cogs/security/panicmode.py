from __future__ import annotations

import asyncio
import json
from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from utils.acore import invalidate_guild_cache

DB_PATH = "database/antinuke.db"

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_SHIELD= "<:synapseShield:1477548906848981225>"
E_WARN  = "<:IconsDanger:1477315376982397018>"
E_NOTE  = "<:SynapseNote:1477236015830663324>"
E_LOCK  = "<:synapselock:1477546146095169649>"
E_UNLOCK= "<:synapseunlock:1477546157298155592>"

COLOR      = 0x2b2d31
COLOR_OK   = 0x2b2d31
COLOR_ERR  = 0x2b2d31
COLOR_WARN = 0xfca903
COLOR_RED  = 0xFF4444
COLOR_GRN  = 0x55FF55
FOOTER     = "Synapse · Panic Mode System"

DANGEROUS_PERMS = (
    "administrator", "ban_members", "kick_members", "manage_guild",
    "manage_roles", "manage_channels", "manage_webhooks", "mention_everyone",
    "manage_messages", "manage_threads",
)



def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_TICK} {desc}", color=COLOR_OK)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_CROSS} {desc}", color=COLOR_ERR)
    e.set_footer(text=FOOTER)
    return e

def _status_embed(title: str, desc: str, color: int) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text=FOOTER)
    return e



async def _is_an_admin(guild_id: int, user_id: int, bot: commands.Bot) -> bool:
    guild = bot.get_guild(guild_id)
    if guild and guild.owner_id == user_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ) as cur:
            return await cur.fetchone() is not None


async def _get_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM antinuke_config WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    keys = ["guild_id","enabled","punishment","log_channel_id","wall_role_id",
            "quarantine_role_id","autorecovery","antibetray","panic_mode","quickrole","setup_at"]
    return dict(zip(keys, row))


async def _set_panic(guild_id: int, value: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE antinuke_config SET panic_mode=? WHERE guild_id=?", (value, guild_id))
        await db.commit()


async def _init_panic_table() -> None:
    """Create the table that stores role permission snapshots for restore."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS panic_role_snapshots (
                guild_id    INTEGER NOT NULL,
                role_id     INTEGER NOT NULL,
                perms_value INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
        await db.commit()


class PanicMode(commands.Cog):
    """Panic Mode commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="panicmode", aliases=["panic", "pm"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def panicmode(self, ctx: commands.Context):
        """Show Panic Mode documentation."""
        cfg = await _get_config(ctx.guild.id)
        status = f"{E_TICK} **ACTIVE**" if (cfg and cfg["panic_mode"]) else f"{E_CROSS} **Inactive**"

        embed = discord.Embed(
            description=(
                f"**Panic Mode** is an emergency lockdown protocol. When enabled it:\n"
                f"- Locks all text channels for `@everyone`\n"
                f"- Strips **dangerous permissions** from every role\n"
                f"- Saves a snapshot of all original role permissions\n"
                f"- On disable, **restores** all permissions from snapshot\n\n"
                f"**Current Status:** {status}\n\n"
                f"{E_WARN} **Owner Only** — Available to Server Owner and Antinuke Admins.\n"
                f"{E_WARN} Enabling panic mode will immediately restrict permissions server-wide.\n\n"
                f"**Subcommands:** `enable`, `disable`"
            ),
            color=COLOR,
        )
        embed.set_author(
            name="Panic Mode Protocol",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @panicmode.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def panic_enable(self, ctx: commands.Context):
        """Trigger emergency panic mode lockdown."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or **Antinuke Admins** can use this."))

        cfg = await _get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=_err("Run `antinuke setup` first."))
        if cfg["panic_mode"]:
            return await ctx.send(embed=_err("Panic Mode is already **active**."))

        status_lines = [f"Emergency lockdown initiated by {ctx.author.mention}"]

        def _build_status(lines: list[str]) -> discord.Embed:
            return _status_embed(
                f"{E_LOCK} Panic Mode — Activating",
                "\n".join(f"> {l}" for l in lines),
                COLOR_RED,
            )

        msg = await ctx.send(embed=_build_status(status_lines))
        await asyncio.sleep(0.5)

        actions: list[str] = []

        status_lines.append("Locking channels…")
        await msg.edit(embed=_build_status(status_lines))
        locked = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = False
                await ch.set_permissions(
                    ctx.guild.default_role, overwrite=overwrite,
                    reason="Synapse Panic Mode activated"
                )
                locked += 1
            except Exception:
                pass
        if locked:
            actions.append(f"Locked `{locked}` text channels")
        await asyncio.sleep(0.4)

        status_lines.append("Stripping dangerous permissions…")
        await msg.edit(embed=_build_status(status_lines))

        bot_top_role = ctx.guild.me.top_role
        stripped = 0

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM panic_role_snapshots WHERE guild_id=?", (ctx.guild.id,))

            for role in ctx.guild.roles:
                if role.is_default() or role.managed or role >= bot_top_role:
                    continue

                has_dangerous = any(getattr(role.permissions, p, False) for p in DANGEROUS_PERMS)
                if not has_dangerous:
                    continue

                await db.execute(
                    "INSERT OR REPLACE INTO panic_role_snapshots (guild_id, role_id, perms_value) VALUES (?,?,?)",
                    (ctx.guild.id, role.id, role.permissions.value),
                )

                new_perms = discord.Permissions(role.permissions.value)
                for p in DANGEROUS_PERMS:
                    setattr(new_perms, p, False)

                try:
                    await role.edit(permissions=new_perms, reason="[Antinuke] Panic Mode — dangerous perms stripped")
                    stripped += 1
                except Exception:
                    pass

            await db.commit()

        if stripped:
            actions.append(f"Stripped dangerous perms from `{stripped}` roles")
        await asyncio.sleep(0.4)

        status_lines.append("Removing whitelists…")
        await msg.edit(embed=_build_status(status_lines))

        async with aiosqlite.connect(DB_PATH) as db:
            # Backup Users
            await db.execute(
                "INSERT INTO panic_whitelist_users_snapshot (guild_id, user_id, events) "
                "SELECT guild_id, user_id, events FROM antinuke_whitelist_users WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM antinuke_whitelist_users WHERE guild_id=?", (ctx.guild.id,))
            
            # Backup Roles
            await db.execute(
                "INSERT INTO panic_whitelist_roles_snapshot (guild_id, role_id, events) "
                "SELECT guild_id, role_id, events FROM antinuke_whitelist_roles WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM antinuke_whitelist_roles WHERE guild_id=?", (ctx.guild.id,))
            
            await db.commit()
            
        invalidate_guild_cache(ctx.guild.id)
        actions.append("Whitelists moved to snapshot")
        await asyncio.sleep(0.4)

        await _set_panic(ctx.guild.id, 1)
        actions.append("Panic Mode state saved")

        if cfg.get("log_channel_id"):
            log_ch = ctx.guild.get_channel(cfg["log_channel_id"])
            if log_ch:
                log_embed = discord.Embed(
                    description=(
                        f"**Triggered by:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                        f"**Time:** <t:{int(datetime.utcnow().timestamp())}:F>\n\n"
                        + "\n".join(f"- {a}" for a in actions)
                    ),
                    color=0xFF0000,
                    timestamp=datetime.utcnow(),
                )
                log_embed.set_author(name="Panic Mode Activated", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                log_embed.set_footer(text=FOOTER)
                try:
                    await log_ch.send(embed=log_embed)
                except Exception:
                    pass

        final_embed = discord.Embed(
            description=(
                f"**Emergency lockdown is now active.**\n\n"
                + "\n".join(f"{E_TICK} {a}" for a in actions)
                + f"\n\n> Run `panicmode disable` to lift the lockdown and restore permissions."
            ),
            color=COLOR_RED,
        )
        final_embed.set_author(name=f"{E_LOCK} Panic Mode — Active", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        final_embed.set_footer(text=FOOTER)
        await msg.edit(embed=final_embed)

    @panicmode.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def panic_disable(self, ctx: commands.Context):
        """Lift the panic mode lockdown."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or **Antinuke Admins** can use this."))

        cfg = await _get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=_err("Run `antinuke setup` first."))
        if not cfg["panic_mode"]:
            return await ctx.send(embed=_err("Panic Mode is not currently **active**."))

        status_lines = [f"Lifting lockdown initiated by {ctx.author.mention}…"]

        def _build_status(lines: list[str]) -> discord.Embed:
            return _status_embed(
                f"{E_UNLOCK} Panic Mode — Deactivating",
                "\n".join(f"> {l}" for l in lines),
                COLOR_GRN,
            )

        msg = await ctx.send(embed=_build_status(status_lines))
        await asyncio.sleep(0.5)

        actions: list[str] = []

        status_lines.append("Unlocking channels…")
        await msg.edit(embed=_build_status(status_lines))
        unlocked = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                if overwrite.send_messages is False:
                    overwrite.send_messages = None
                    await ch.set_permissions(
                        ctx.guild.default_role, overwrite=overwrite,
                        reason="Synapse Panic Mode deactivated"
                    )
                    unlocked += 1
            except Exception:
                pass
        if unlocked:
            actions.append(f"Unlocked `{unlocked}` text channels")
        await asyncio.sleep(0.4)

        status_lines.append("Restoring role permissions…")
        await msg.edit(embed=_build_status(status_lines))

        restored = 0
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id, perms_value FROM panic_role_snapshots WHERE guild_id=?",
                (ctx.guild.id,),
            ) as cur:
                snapshots = await cur.fetchall()

            for role_id, perms_value in snapshots:
                role = ctx.guild.get_role(role_id)
                if not role:
                    continue
                try:
                    await role.edit(
                        permissions=discord.Permissions(perms_value),
                        reason="[Antinuke] Panic Mode disabled — permissions restored",
                    )
                    restored += 1
                except Exception:
                    pass

            await db.execute("DELETE FROM panic_role_snapshots WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()

        if restored:
            actions.append(f"Restored permissions for `{restored}` roles")
        await asyncio.sleep(0.4)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM antinuke_mainroles WHERE guild_id=?", (ctx.guild.id,)) as cur:
                mainrole_rows = await cur.fetchall()
        if mainrole_rows:
            actions.append(f"`{len(mainrole_rows)}` main roles preserved in DB")

        status_lines.append("Restoring whitelists…")
        await msg.edit(embed=_build_status(status_lines))
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Restore Users
            await db.execute(
                "INSERT OR REPLACE INTO antinuke_whitelist_users (guild_id, user_id, events) "
                "SELECT guild_id, user_id, events FROM panic_whitelist_users_snapshot WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM panic_whitelist_users_snapshot WHERE guild_id=?", (ctx.guild.id,))
            
            # Restore Roles
            await db.execute(
                "INSERT OR REPLACE INTO antinuke_whitelist_roles (guild_id, role_id, events) "
                "SELECT guild_id, role_id, events FROM panic_whitelist_roles_snapshot WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM panic_whitelist_roles_snapshot WHERE guild_id=?", (ctx.guild.id,))
            
            await db.commit()

        invalidate_guild_cache(ctx.guild.id)
        actions.append("Whitelists restored from snapshot")
        await asyncio.sleep(0.4)

        await _set_panic(ctx.guild.id, 0)
        actions.append("Panic Mode deactivated")

        if cfg.get("log_channel_id"):
            log_ch = ctx.guild.get_channel(cfg["log_channel_id"])
            if log_ch:
                log_embed = discord.Embed(
                    description=(
                        f"**Lifted by:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                        f"**Time:** <t:{int(datetime.utcnow().timestamp())}:F>\n\n"
                        + "\n".join(f"- {a}" for a in actions)
                    ),
                    color=0x00CC88,
                    timestamp=datetime.utcnow(),
                )
                log_embed.set_author(name="Panic Mode Deactivated", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                log_embed.set_footer(text=FOOTER)
                try:
                    await log_ch.send(embed=log_embed)
                except Exception:
                    pass

        final_embed = discord.Embed(
            description="\n".join(f"{E_TICK} {a}" for a in actions),
            color=COLOR_OK,
        )
        final_embed.set_author(name=f"{E_UNLOCK} Panic Mode — Deactivated", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        final_embed.set_footer(text=FOOTER)
        await msg.edit(embed=final_embed)


async def setup(bot: commands.Bot) -> None:
    await _init_panic_table()
    await bot.add_cog(PanicMode(bot))
