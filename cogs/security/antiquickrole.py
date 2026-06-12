"""
Anti Quick Role — Antinuke System
Synapse Discord Bot | discord.py 2.7.0 | aiosqlite 0.19.0 | Python 3.12

Automatically strips dangerous roles if a user receives powerful roles too quickly
upon joining. May trigger panic mode. Logs all actions to the antinuke channel.

Commands:
  antiquickrole         — documentation
  antiquickrole enable
  antiquickrole disable
"""
from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/antinuke.db"
COLOR   = 0x2b2d31

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_OK    = "<:emoji_1769867605256:1467155817726873650>"
E_SHIELD= "<:synapseShield:1477548906848981225>"
E_NOTE  = "<:SynapseNote:1477236015830663324>"
E_GEAR  = "<:synapseGear:1477546806232743999>"
FOOTER  = "Synapse — Anti Quick Role System"


def _ok(text: str) -> discord.Embed:
    return discord.Embed(
        description=f"> {E_OK} **Success:** {text}",
        color=COLOR, timestamp=datetime.utcnow()
    ).set_footer(text=FOOTER)


def _err(text: str) -> discord.Embed:
    return discord.Embed(
        description=f"> {E_EXCL} **Error:** {text}",
        color=COLOR, timestamp=datetime.utcnow()
    ).set_footer(text=FOOTER)


async def _get_quickrole(guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT quickrole FROM antinuke_config WHERE guild_id=?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return bool(row and row[0])


async def _set_quickrole(guild_id: int, value: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE antinuke_config SET quickrole=? WHERE guild_id=?",
            (value, guild_id),
        )
        await db.commit()


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


class AntiQuickRole(commands.Cog):
    """Anti Quick Role commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="antiquickrole", aliases=["aqr"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def antiquickrole(self, ctx: commands.Context):
        """Show Anti Quick Role documentation."""
        enabled = await _get_quickrole(ctx.guild.id)
        status  = f"{E_TICK} **Enabled**" if enabled else f"{E_CROSS} **Disabled**"

        embed = discord.Embed(
            title=f"{E_SHIELD} Anti Quick Role",
            description=(
                "**Anti Quick Role** automatically strips dangerous roles if a user receives "
                "powerful roles too quickly upon joining. May trigger **Panic Mode**. "
                "Logs all actions to the antinuke channel.\n\n"
                f"**Current Status:** {status}\n\n"
                f"> {E_NOTE} This event is **unwhitelistable** — it always applies.\n"
                f"> Only **Antinuke Admins** or the **Server Owner** can toggle this.\n\n"
                f"**Subcommands:** `enable` · `disable`"
            ),
            color=COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @antiquickrole.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def aqr_enable(self, ctx: commands.Context):
        """Enable anti quick role protection."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id FROM antinuke_config WHERE guild_id=?", (ctx.guild.id,)) as cur:
                if not await cur.fetchone():
                    return await ctx.send(embed=_err("Run `antinuke setup` first."))

        if await _get_quickrole(ctx.guild.id):
            return await ctx.send(embed=_err("Anti Quick Role is already **enabled**."))

        await _set_quickrole(ctx.guild.id, 1)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT log_channel_id FROM antinuke_config WHERE guild_id=?", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()
        if row and row[0]:
            ch = ctx.guild.get_channel(row[0])
            if ch:
                try:
                    await ch.send(embed=discord.Embed(
                        title=f"{E_SHIELD} Anti Quick Role Enabled",
                        description=f"Enabled by {ctx.author.mention}",
                        color=COLOR, timestamp=datetime.utcnow()
                    ).set_footer(text=FOOTER))
                except Exception:
                    pass

        await ctx.send(embed=_ok("**Anti Quick Role** has been **enabled**."))

    @antiquickrole.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def aqr_disable(self, ctx: commands.Context):
        """Disable anti quick role protection."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        if not await _get_quickrole(ctx.guild.id):
            return await ctx.send(embed=_err("Anti Quick Role is already **disabled**."))

        await _set_quickrole(ctx.guild.id, 0)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT log_channel_id FROM antinuke_config WHERE guild_id=?", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()
        if row and row[0]:
            ch = ctx.guild.get_channel(row[0])
            if ch:
                try:
                    await ch.send(embed=discord.Embed(
                        title=f" Anti Quick Role Disabled",
                        description=f"Disabled by {ctx.author.mention}",
                        color=0xFF5555, timestamp=datetime.utcnow()
                    ).set_footer(text=FOOTER))
                except Exception:
                    pass

        await ctx.send(embed=_ok("**Anti Quick Role** has been **disabled**."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiQuickRole(bot))
