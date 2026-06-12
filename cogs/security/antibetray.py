from __future__ import annotations

import asyncio
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from cogs.engagement.prime import premium_check
from utils.acore import (
    ANTIBETRAY_DB,
    COLOR,
    E_TICK,
    E_CROSS,
    E_EXCL,
    E_SHIELD,
    FOOTER,
    invalidate_guild_cache,
)

async def init_ab_db():
    async with aiosqlite.connect(ANTIBETRAY_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS config ("
            "guild_id INTEGER PRIMARY KEY, "
            "enabled INTEGER DEFAULT 0, "
            "window INTEGER DEFAULT 60, "
            "threshold INTEGER DEFAULT 3"
            ")"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS limits ("
            "guild_id INTEGER, "
            "event TEXT, "
            "max_actions INTEGER, "
            "PRIMARY KEY (guild_id, event)"
            ")"
        )
        await db.commit()

class ABE:
    """Antibetray Embed Helpers"""
    @staticmethod
    def info(title: str, description: str):
        embed = discord.Embed(title=f"{E_SHIELD} {title}", description=description, color=COLOR)
        embed.set_footer(text=FOOTER)
        return embed

    @staticmethod
    def success(text: str):
        return discord.Embed(description=f"{E_TICK} {text}", color=0x00FF00)

    @staticmethod
    def error(text: str):
        return discord.Embed(description=f"{E_CROSS} {text}", color=0xFF0000)

class Antibetray(commands.Cog):
    """Stand-alone Antibetray security system for Whitelisted users."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_admin(self, ctx: commands.Context) -> bool:
        if ctx.author.id == ctx.guild.owner_id or await self.bot.is_owner(ctx.author):
            return True
        # Check antinuke admins as well since it's a security module
        from utils.acore import is_antinuke_admin
        if await is_antinuke_admin(self.bot, ctx.guild.id, ctx.author.id):
            return True
        await ctx.send(embed=ABE.error("You need **Administrator** or **Antinuke Admin** permissions."))
        return False

    @commands.group(name="antibetray", aliases=["ab"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @premium_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antibetray(self, ctx: commands.Context):
        """Main command for configuring the Antibetray system."""
        if not await self._is_admin(ctx):
            return

        from utils.acore import get_antibetray_config
        cfg = await get_antibetray_config(ctx.guild.id)
        
        status = f"{E_TICK} **Enabled**" if cfg["enabled"] else f"{E_CROSS} **Disabled**"
        
        embed = ABE.info(
            "Security — Antibetray",
            f"**Antibetray** is an advanced security layer that monitors whitelisted users.\n"
            f"It enforces strict limits and mass-action thresholds within a rolling window.\n\n"
            f"**__Current Settings__**:\n"
            f"> **Status:** {status}\n"
            f"> **Window:** `{cfg['window']}s`\n"
            f"> **Global Threshold:** `{cfg['threshold']}` actions\n\n"
            f"**Use `{ctx.prefix}antibetray config` to see per-event limits.**"
        )
        await ctx.send(embed=embed)

    @antibetray.command(name="enable")
    @premium_check()
    async def ab_enable(self, ctx: commands.Context):
        """Enable the Antibetray system."""
        if not await self._is_admin(ctx): return
        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute(
                "INSERT INTO config (guild_id, enabled) VALUES (?, 1) "
                "ON CONFLICT(guild_id) DO UPDATE SET enabled=1",
                (ctx.guild.id,)
            )
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success("Antibetray system has been **enabled**."))

    @antibetray.command(name="disable")
    @premium_check()
    async def ab_disable(self, ctx: commands.Context):
        """Disable the Antibetray system."""
        if not await self._is_admin(ctx): return
        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute("UPDATE config SET enabled=0 WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success("Antibetray system has been **disabled**."))

    @antibetray.command(name="window")
    @premium_check()
    async def ab_window(self, ctx: commands.Context, seconds: int):
        """Set the monitoring window (10-600 seconds)."""
        if not await self._is_admin(ctx): return
        if not 10 <= seconds <= 600:
            return await ctx.send(embed=ABE.error("Window must be between **10** and **600** seconds."))

        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute(
                "INSERT INTO config (guild_id, window) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET window=?",
                (ctx.guild.id, seconds, seconds)
            )
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success(f"Antibetray window set to **{seconds}s**."))

    @antibetray.command(name="threshold")
    @premium_check()
    async def ab_threshold(self, ctx: commands.Context, count: int):
        """Set the global mass action threshold (1-50)."""
        if not await self._is_admin(ctx): return
        if not 1 <= count <= 50:
            return await ctx.send(embed=ABE.error("Threshold must be between **1** and **50**."))

        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute(
                "INSERT INTO config (guild_id, threshold) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET threshold=?",
                (ctx.guild.id, count, count)
            )
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success(f"Global action threshold set to **{count}**."))

    @antibetray.command(name="limit")
    @premium_check()
    async def ab_limit(self, ctx: commands.Context, event: str, limit: int):
        """Set a specific limit for an event (e.g. channel_delete)."""
        if not await self._is_admin(ctx): return
        
        # Validate event name (could expand this list)
        valid_events = [
            "anti_ban", "anti_kick", "anti_unban", "anti_prune",
            "anti_bot_add", "anti_channel_create", "anti_channel_delete",
            "anti_channel_update", "anti_role_create", "anti_role_delete",
            "anti_role_update", "anti_member_update", "anti_guild_update",
            "anti_webhook_create", "anti_webhook_delete", "anti_webhook_update",
            "anti_emoji_create", "anti_emoji_delete", "anti_emoji_update",
            "anti_sticker_create", "anti_sticker_delete", "anti_sticker_update"
        ]
        if event not in valid_events:
            return await ctx.send(embed=ABE.error(f"Invalid event. Valid events: `{', '.join(valid_events[:5])}...`"))

        if not 1 <= limit <= 100:
            return await ctx.send(embed=ABE.error("Limit must be between **1** and **100**."))

        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute(
                "INSERT OR REPLACE INTO limits (guild_id, event, max_actions) VALUES (?, ?, ?)",
                (ctx.guild.id, event, limit)
            )
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success(f"Limit for **{event}** set to **{limit}**."))

    @antibetray.command(name="config", aliases=["settings", "show"])
    @premium_check()
    async def ab_config(self, ctx: commands.Context):
        """Show all Antibetray limits and settings."""
        if not await self._is_admin(ctx): return

        from utils.acore import get_antibetray_config
        cfg = await get_antibetray_config(ctx.guild.id)
        
        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            async with db.execute("SELECT event, max_actions FROM limits WHERE guild_id=?", (ctx.guild.id,)) as cur:
                limits = await cur.fetchall()

        limit_str = "\n".join([f"> **{ev}:** `{lim}`" for ev, lim in limits]) if limits else "> *No custom limits set (using Antinuke defaults)*"
        
        embed = ABE.info(
            "Antibetray Configuration",
            f"**__General__**\n"
            f"> **Status:** {'Enabled' if cfg['enabled'] else 'Disabled'}\n"
            f"> **Window:** `{cfg['window']}s`\n"
            f"> **Global Threshold:** `{cfg['threshold']}`\n\n"
            f"**__Specific Event Limits__**\n{limit_str}"
        )
        await ctx.send(embed=embed)

    @antibetray.command(name="reset")
    @premium_check()
    async def ab_reset(self, ctx: commands.Context):
        """Reset Antibetray settings to default."""
        if not await self._is_admin(ctx): return
        async with aiosqlite.connect(ANTIBETRAY_DB) as db:
            await db.execute("DELETE FROM config WHERE guild_id=?", (ctx.guild.id,))
            await db.execute("DELETE FROM limits WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        invalidate_guild_cache(ctx.guild.id)
        await ctx.send(embed=ABE.success("Antibetray settings have been **reset** to defaults."))

async def setup(bot: commands.Bot):
    await init_ab_db()
    await bot.add_cog(Antibetray(bot))
