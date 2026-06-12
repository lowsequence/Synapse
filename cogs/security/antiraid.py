from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check

DB_PATH      = "database/antiraid.db"
COLOR        = 0x2b2d31

E_TICK   = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS  = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL   = "<:SynapseExcl:1477234549552320634>"
E_SHIELD = "<:synapseShield:1477548906848981225>"
E_SEARCH = "<:Synapse_search:1471871156783943812>"
E_WARN   = "<:IconsDanger:1477315376982397018>"
E_OK     = "<:emoji_1769867605256:1467155817726873650>"
E_NOTE   = "<:SynapseNote:1477236015830663324>"
E_GEAR   = "<:synapseGear:1477546806232743999>"

VALID_EVENTS = ["massjoin", "accountage", "samecreation", "defaultpfp"]
EVENT_LABELS = {
    "massjoin": "Mass Join",
    "accountage": "Account Age",
    "samecreation": "Same Creation Date",
    "defaultpfp": "Default Avatar"
}

class ARE:
    """Antiraid Embed helper — Premium Minimalist aesthetic style."""
    FOOTER = "Synapse Antiraid"
    URL_SHIELD = "https://cdn.discordapp.com/emojis/1477548906848981225.png"
    URL_GEAR   = "https://cdn.discordapp.com/emojis/1477546806232743999.png"

    @staticmethod
    def success(text: str) -> discord.Embed:
        return discord.Embed(
            description=f"{E_TICK} {text}",
            color=COLOR,
        )

    @staticmethod
    def error(text: str) -> discord.Embed:
        return discord.Embed(
            description=f"{E_EXCL} {text}",
            color=COLOR,
        )

    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            description=description,
            color=COLOR,
        ).set_author(name=title, icon_url=ARE.URL_SHIELD)

    @staticmethod
    def panel(title: str) -> discord.Embed:
        return discord.Embed(
            color=COLOR,
        ).set_author(name=title, icon_url=ARE.URL_GEAR)

async def init_antiraid_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antiraid_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                punishment TEXT NOT NULL DEFAULT 'ban',
                log_channel_id INTEGER,
                alert_role_id INTEGER,
                massjoin_limit INTEGER NOT NULL DEFAULT 5,
                massjoin_time INTEGER NOT NULL DEFAULT 10,
                accountage_days INTEGER NOT NULL DEFAULT 3
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antiraid_events (
                guild_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, event_name)
            )
        """)
        await db.commit()

async def get_config(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM antiraid_config WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return {
            "guild_id": guild_id, "enabled": 0, "punishment": "ban",
            "log_channel_id": None, "alert_role_id": None,
            "massjoin_limit": 5, "massjoin_time": 10, "accountage_days": 3
        }
    keys = ["guild_id", "enabled", "punishment", "log_channel_id", "alert_role_id", "massjoin_limit", "massjoin_time", "accountage_days"]
    return dict(zip(keys, row))

async def set_config(guild_id: int, key: str, value: any) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO antiraid_config (guild_id) VALUES (?)",
            (guild_id,)
        )
        await db.execute(
            f"UPDATE antiraid_config SET {key}=? WHERE guild_id=?",
            (value, guild_id)
        )
        await db.commit()

async def get_enabled_events(guild_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT event_name FROM antiraid_events WHERE guild_id=? AND enabled=1",
            (guild_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

async def toggle_event(guild_id: int, event_name: str, enabled: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO antiraid_events (guild_id, event_name, enabled) VALUES (?, ?, ?) ON CONFLICT(guild_id, event_name) DO UPDATE SET enabled=?",
            (guild_id, event_name, enabled, enabled)
        )
        await db.commit()

class Antiraid(commands.Cog):
    """Advanced Antiraid System commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        asyncio.create_task(init_antiraid_db())

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if ctx.author.id != ctx.guild.owner_id and not ctx.author.guild_permissions.administrator:
            
            await ctx.send(embed=ARE.error("Only the **server owner** or administrators can use this."))
            return False
        return True

    @commands.group(name="antiraid", aliases=["atr"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.guild)
    async def antiraid(self, ctx: commands.Context):
        """Configure the Advanced Antiraid System."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
      
    @antiraid.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_enable(self, ctx: commands.Context):
        """Enable the Antiraid system."""
        if not await self._require_admin(ctx): return
        cfg = await get_config(ctx.guild.id)
        if cfg["enabled"]:
            return await ctx.send(embed=ARE.error("Antiraid is already **enabled**."))
        await set_config(ctx.guild.id, "enabled", 1)
        await ctx.send(embed=ARE.success("Antiraid system has been **enabled**."))

    @antiraid.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_disable(self, ctx: commands.Context):
        """Disable the Antiraid system."""
        if not await self._require_admin(ctx): return
        cfg = await get_config(ctx.guild.id)
        if not cfg["enabled"]:
            return await ctx.send(embed=ARE.error("Antiraid is already **disabled**."))
        await set_config(ctx.guild.id, "enabled", 0)
        await ctx.send(embed=ARE.success("Antiraid system has been **disabled**."))

    @antiraid.command(name="config", aliases=["status"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_config(self, ctx: commands.Context):
        """Display Antiraid configuration."""
        if not await self._require_admin(ctx): return
        cfg = await get_config(ctx.guild.id)
        events = await get_enabled_events(ctx.guild.id)

        status_str = f"{E_TICK} Enabled" if cfg["enabled"] else f"{E_CROSS} Disabled"
        punish_str = f"`{cfg['punishment'].capitalize()}`"
        log_ch = ctx.guild.get_channel(cfg["log_channel_id"]) if cfg["log_channel_id"] else None
        log_str = log_ch.mention if log_ch else "`Not Set`"
        alert_role = ctx.guild.get_role(cfg["alert_role_id"]) if cfg["alert_role_id"] else None
        alert_str = alert_role.mention if alert_role else "`Not Set`"

        events_str = ""
        for ev in VALID_EVENTS:
            icon = E_TICK if ev in events else E_CROSS
            events_str += f"{icon} {EVENT_LABELS[ev]}\n"

        embed = ARE.panel(f"Antiraid Config — {ctx.guild.name}")
        embed.add_field(name="General Settings", value=f"**Status:** {status_str}\n**Punishment:** {punish_str}\n**Log Channel:** {log_str}\n**Alert Role:** {alert_str}", inline=False)
        embed.add_field(name="Thresholds", value=f"**Mass Join:** `{cfg['massjoin_limit']} joins` in `{cfg['massjoin_time']}s`\n**Account Age:** < `{cfg['accountage_days']} days`", inline=False)
        embed.add_field(name="Detected Events", value=events_str, inline=False)
        await ctx.send(embed=embed)

    @antiraid.command(name="event")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_event(self, ctx: commands.Context, event_name: str, state: str):
        """Toggle an antiraid event (massjoin, accountage, samecreation, defaultpfp)."""
        if not await self._require_admin(ctx): return
        event_name = event_name.lower().replace(" ", "")
        if event_name not in VALID_EVENTS:
            return await ctx.send(embed=ARE.error(f"Invalid event. Valid events: `{', '.join(VALID_EVENTS)}`"))
        
        state = state.lower()
        if state not in ("on", "off", "enable", "disable", "true", "false"):
            return await ctx.send(embed=ARE.error("Specify `on` or `off`."))
            
        is_enabling = state in ("on", "enable", "true")
        await toggle_event(ctx.guild.id, event_name, 1 if is_enabling else 0)
        action = "enabled" if is_enabling else "disabled"
        await ctx.send(embed=ARE.success(f"Event **{EVENT_LABELS[event_name]}** has been **{action}**."))

    @antiraid.command(name="limit")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_limit(self, ctx: commands.Context, joins: int, seconds: int):
        """Set the massjoin threshold (e.g. 5 joins in 10 seconds)."""
        if not await self._require_admin(ctx): return
        if joins < 2 or joins > 100:
            return await ctx.send(embed=ARE.error("Joins must be between `2` and `100`."))
        if seconds < 2 or seconds > 300:
            return await ctx.send(embed=ARE.error("Seconds must be between `2` and `300`."))
            
        await set_config(ctx.guild.id, "massjoin_limit", joins)
        await set_config(ctx.guild.id, "massjoin_time", seconds)
        await ctx.send(embed=ARE.success(f"Massjoin limit set to **{joins} joins** every **{seconds} seconds**."))

    @antiraid.command(name="accountage", aliases=["age"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_accountage(self, ctx: commands.Context, days: int):
        """Set the minimum account age threshold in days."""
        if not await self._require_admin(ctx): return
        if days < 0 or days > 365:
            return await ctx.send(embed=ARE.error("Days must be between `0` and `365`."))
            
        await set_config(ctx.guild.id, "accountage_days", days)
        await ctx.send(embed=ARE.success(f"Account age minimum set to **{days} days**."))

    @antiraid.command(name="punishment")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_punishment(self, ctx: commands.Context, action: str):
        """Set the punishment action (ban, kick)."""
        if not await self._require_admin(ctx): return
        action = action.lower()
        if action not in ("ban", "kick"):
            return await ctx.send(embed=ARE.error("Punishment must be `ban` or `kick`."))
            
        await set_config(ctx.guild.id, "punishment", action)
        await ctx.send(embed=ARE.success(f"Antiraid punishment set to **{action}**."))

    @antiraid.command(name="log")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_log(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the antiraid log channel."""
        if not await self._require_admin(ctx): return
        await set_config(ctx.guild.id, "log_channel_id", channel.id)
        await ctx.send(embed=ARE.success(f"Antiraid log channel set to {channel.mention}."))

    @antiraid.command(name="alert")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def ar_alert(self, ctx: commands.Context, role: discord.Role):
        """Set the antiraid alert role."""
        if not await self._require_admin(ctx): return
        await set_config(ctx.guild.id, "alert_role_id", role.id)
        await ctx.send(embed=ARE.success(f"Antiraid alert role set to {role.mention}."))

async def setup(bot: commands.Bot):
    await bot.add_cog(Antiraid(bot))
