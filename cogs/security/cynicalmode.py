from __future__ import annotations

import asyncio
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
E_WARN  = "<:IconsDanger:1477315376982397018>"

COLOR      = 0x2b2d31
COLOR_RED  = 0x2b2d31
COLOR_GRN  = 0x2b2d31
FOOTER     = "Synapse · Cynical Mode System"

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

async def _get_cynical_status(guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cynical_mode FROM antinuke_config WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
            return bool(row[0]) if row else False

async def _set_cynical(guild_id: int, value: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE antinuke_config SET cynical_mode=? WHERE guild_id=?", (value, guild_id))
        await db.commit()

class CynicalMode(commands.Cog):
    """Cynical Mode commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="cynicalmode", aliases=["cynical", "cm"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def cynicalmode(self, ctx: commands.Context):
        """Show Cynical Mode documentation."""
        status_bool = await _get_cynical_status(ctx.guild.id)
        status = f"{E_TICK} **ACTIVE**" if status_bool else f"{E_CROSS} **Inactive**"

        embed = discord.Embed(
            description=(
                f"**Cynical Mode** is a security protocol that temporarily invalidates all whitelists.\n\n"
                f"- **Enable**: Moves all whitelisted users/roles to a snapshot and removes them from active use.\n"
                f"- **Disable**: Restores all whitelists from the snapshot.\n\n"
                f"**Current Status:** {status}\n\n"
                f"{E_WARN} **Owner Only** — Available to Owner and Antinuke Admins.\n\n"
                f"**Subcommands:** `enable`, `disable`"
            ),
            color=COLOR,
        )
        embed.set_author(name="Cynical Mode System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @cynicalmode.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def cynical_enable(self, ctx: commands.Context):
        """Enable Cynical Mode and remove all whitelists."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Only Owner or Antinuke Admins can use this.", color=COLOR))

        if await _get_cynical_status(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Cynical Mode is already **active**.", color=COLOR))

        msg = await ctx.send(embed=discord.Embed(description=f"<a:Loadixd:1469568214169288890> Transitioning to Cynical Mode…", color=COLOR))
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Clear old snapshots just in case
            await db.execute("DELETE FROM cynical_whitelist_users_snapshot WHERE guild_id=?", (ctx.guild.id,))
            await db.execute("DELETE FROM cynical_whitelist_roles_snapshot WHERE guild_id=?", (ctx.guild.id,))

            # Backup Users
            await db.execute(
                "INSERT INTO cynical_whitelist_users_snapshot (guild_id, user_id, events) "
                "SELECT guild_id, user_id, events FROM antinuke_whitelist_users WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM antinuke_whitelist_users WHERE guild_id=?", (ctx.guild.id,))
            
            # Backup Roles
            await db.execute(
                "INSERT INTO cynical_whitelist_roles_snapshot (guild_id, role_id, events) "
                "SELECT guild_id, role_id, events FROM antinuke_whitelist_roles WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM antinuke_whitelist_roles WHERE guild_id=?", (ctx.guild.id,))
            
            await db.commit()
            
        invalidate_guild_cache(ctx.guild.id)
        await _set_cynical(ctx.guild.id, 1)
        
        embed = discord.Embed(
            description=(
                f"{E_TICK} **Cynical Mode Active**\n\n"
                f"- All whitelisted users and roles have been moved to snapshots.\n"
                f"- Bot will now treat everyone (except owners/admins) as non-whitelisted."
            ),
            color=COLOR_RED,
        )
        embed.set_footer(text=FOOTER)
        await msg.edit(embed=embed)

    @cynicalmode.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def cynical_disable(self, ctx: commands.Context):
        """Disable Cynical Mode and restore whitelists."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Only Owner or Antinuke Admins can use this.", color=COLOR))

        if not await _get_cynical_status(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Cynical Mode is not **active**.", color=COLOR))

        msg = await ctx.send(embed=discord.Embed(description=f"<a:Loadixd:1469568214169288890> Restoring whitelists from Cynical snapshots…", color=COLOR))
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Restore Users
            await db.execute(
                "INSERT OR REPLACE INTO antinuke_whitelist_users (guild_id, user_id, events) "
                "SELECT guild_id, user_id, events FROM cynical_whitelist_users_snapshot WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM cynical_whitelist_users_snapshot WHERE guild_id=?", (ctx.guild.id,))
            
            # Restore Roles
            await db.execute(
                "INSERT OR REPLACE INTO antinuke_whitelist_roles (guild_id, role_id, events) "
                "SELECT guild_id, role_id, events FROM cynical_whitelist_roles_snapshot WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.execute("DELETE FROM cynical_whitelist_roles_snapshot WHERE guild_id=?", (ctx.guild.id,))
            
            await db.commit()

        invalidate_guild_cache(ctx.guild.id)
        await _set_cynical(ctx.guild.id, 0)

        embed = discord.Embed(
            description=(
                f"{E_TICK} **Cynical Mode Deactivated**\n\n"
                f"- Whitelists have been restored from snapshots.\n"
                f"- Normal protection behavior resumed."
            ),
            color=COLOR_GRN,
        )
        embed.set_footer(text=FOOTER)
        await msg.edit(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CynicalMode(bot))
