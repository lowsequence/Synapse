from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/antinuke.db"
E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_SHIELD= "<:synapseShield:1477548906848981225>"
E_WARN  = "<:IconsDanger:1477315376982397018>"

COLOR      = 0x2b2d31
COLOR_RED  = 0x2b2d31
COLOR_GRN  = 0x2b2d31
FOOTER     = "Synapse · Nightmode System"

DANGEROUS_PERMS = (
    "administrator", "ban_members", "kick_members", "manage_guild",
    "manage_roles", "manage_channels", "manage_webhooks", "mention_everyone",
    "manage_messages", "manage_threads",
)

log = logging.getLogger(__name__)

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

async def _get_nightmode_status(guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT night_mode FROM antinuke_config WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
            return bool(row[0]) if row else False

async def _set_nightmode(guild_id: int, value: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE antinuke_config SET night_mode=? WHERE guild_id=?", (value, guild_id))
        await db.commit()

class Nightmode(commands.Cog):
    """Nightmode commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="nightmode", aliases=["nm"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def nightmode(self, ctx: commands.Context):
        """Show Nightmode documentation."""
        status_bool = await _get_nightmode_status(ctx.guild.id)
        status = f"{E_TICK} **ACTIVE**" if status_bool else f"{E_CROSS} **Inactive**"

        embed = discord.Embed(
            description=(
                f"**Nightmode** is a security protocol that strips dangerous permissions from roles.\n\n"
                f"- Strips **dangerous perms** from every role on enable.\n"
                f"- Saves a snapshot of original permissions.\n"
                f"- **Restores** permissions from snapshot on disable.\n\n"
                f"**Current Status:** {status}\n\n"
                f"{E_WARN} **Owner Only** — Available to Owner and Antinuke Admins.\n\n"
                f"**Subcommands:** `enable`, `disable`"
            ),
            color=COLOR,
        )
        embed.set_author(name="Nightmode System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @nightmode.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def nm_enable(self, ctx: commands.Context):
        """Enable Nightmode and strip role permissions."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Only Owner or Antinuke Admins can use this.", color=COLOR))

        if await _get_nightmode_status(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Nightmode is already **active**.", color=COLOR))

        msg = await ctx.send(embed=discord.Embed(description=f"<a:Loadixd:1469568214169288890> Activating Nightmode lockdown…", color=COLOR))
        
        bot_top_role = ctx.guild.me.top_role
        stripped = 0

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM nightmode_role_snapshots WHERE guild_id=?", (ctx.guild.id,))

            for role in ctx.guild.roles:
                if role.is_default() or role.managed or role >= bot_top_role:
                    continue

                has_dangerous = any(getattr(role.permissions, p, False) for p in DANGEROUS_PERMS)
                if not has_dangerous:
                    continue

                await db.execute(
                    "INSERT INTO nightmode_role_snapshots (guild_id, role_id, perms_value) VALUES (?,?,?)",
                    (ctx.guild.id, role.id, role.permissions.value),
                )

                new_perms = discord.Permissions(role.permissions.value)
                for p in DANGEROUS_PERMS:
                    setattr(new_perms, p, False)

                try:
                    await role.edit(permissions=new_perms, reason="[Antinuke] Nightmode — dangerous perms stripped")
                    stripped += 1
                except Exception:
                    pass

            await db.commit()

        await _set_nightmode(ctx.guild.id, 1)
        
        embed = discord.Embed(
            description=(
                f"{E_TICK} **Nightmode Lockdown Active**\n\n"
                f"- Stripped dangerous perms from `{stripped}` roles.\n"
                f"- Snapshots saved for easy restoration."
            ),
            color=COLOR_RED,
        )
        embed.set_footer(text=FOOTER)
        await msg.edit(embed=embed)

    @nightmode.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def nm_disable(self, ctx: commands.Context):
        """Disable Nightmode and restore role permissions."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Only Owner or Antinuke Admins can use this.", color=COLOR))

        if not await _get_nightmode_status(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Nightmode is not **active**.", color=COLOR))

        msg = await ctx.send(embed=discord.Embed(description=f"<a:Loadixd:1469568214169288890> Restoring role permissions…", color=COLOR))
        
        restored = 0
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id, perms_value FROM nightmode_role_snapshots WHERE guild_id=?",
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
                        reason="[Antinuke] Nightmode disabled — permissions restored",
                    )
                    restored += 1
                except Exception:
                    pass

            await db.execute("DELETE FROM nightmode_role_snapshots WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()

        await _set_nightmode(ctx.guild.id, 0)

        embed = discord.Embed(
            description=(
                f"{E_TICK} **Nightmode Lockdown Lifted**\n\n"
                f"- Restored permissions for `{restored}` roles.\n"
                f"- Mode deactivated."
            ),
            color=COLOR_GRN,
        )
        embed.set_footer(text=FOOTER)
        await msg.edit(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Nightmode(bot))
