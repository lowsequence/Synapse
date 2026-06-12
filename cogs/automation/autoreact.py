from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from utils.paginator import Paginator as HackerPaginator
from utils.paginators import DescriptionEmbedPaginator


EMBED_COLOR = 0x2b2d31
DB_PATH = "database/autoreact.db"
PREMIUM_DB = "database/premium_codes.db"

MAX_EMOJIS_PER_TRIGGER = 5
GUILD_LIMIT_NORMAL = 7
GUILD_LIMIT_PREMIUM = 15



async def _init_autoreact_db() -> None:
    """Create the autoreact database tables if they do not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS autoreacts (
                guild_id   INTEGER NOT NULL,
                trigger    TEXT    NOT NULL,
                emojis     TEXT    NOT NULL DEFAULT '[]',
                enabled    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    NOT NULL,
                PRIMARY KEY (guild_id, trigger)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ignored_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
            """
        )
        await db.commit()



async def _is_premium_guild(guild_id: int) -> bool:
    """Return True if the guild currently has an active premium subscription."""
    try:
        async with aiosqlite.connect(PREMIUM_DB) as db:
            async with db.execute(
                "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                return False
            expires_at = datetime.fromisoformat(row[0])
            return expires_at > datetime.utcnow()
    except Exception:
        return False


async def _get_guild_limit(guild_id: int) -> int:
    """Return the autoreact limit for a guild (normal vs premium)."""
    if await _is_premium_guild(guild_id):
        return GUILD_LIMIT_PREMIUM
    return GUILD_LIMIT_NORMAL


async def _get_autoreact_count(guild_id: int) -> int:
    """Return the number of autoreact triggers configured for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM autoreacts WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0



async def trim_autoreacts_on_premium_expire(guild_id: int) -> None:
    """
    Called when a guild's premium expires.
    Deletes the newest autoreacts until only GUILD_LIMIT_NORMAL (7) remain.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM autoreacts WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0

        if total <= GUILD_LIMIT_NORMAL:
            return

        excess = total - GUILD_LIMIT_NORMAL

        await db.execute(
            """
            DELETE FROM autoreacts
            WHERE rowid IN (
                SELECT rowid FROM autoreacts
                WHERE guild_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (guild_id, excess),
        )
        await db.commit()



def _parse_emoji_input(emoji_str: str) -> list[str]:
    """
    Parse a comma-separated or space-separated string of emojis.
    Returns a list of individual emoji strings (unicode or custom format).
    """
    # First, handle comma-separated
    if "," in emoji_str:
        return [e.strip() for e in emoji_str.split(",") if e.strip()]

   
    import re
  
    pattern = r'(<a?:\w+:\d+>|[^\s\w,]+|\w+)'
    raw_parts = re.findall(pattern, emoji_str)
  
    
    return [p.strip() for p in raw_parts if p.strip()]


def _validate_emoji(emoji_str: str, bot: commands.Bot) -> bool:
    """
    Validate that an emoji string is a valid unicode emoji or a custom emoji.
    """
    try:
        # Check if it's a custom emoji first
        import re
        if re.match(r'<a?:\w+:\d+>', emoji_str):
            
            return True
       
        if emoji_str.isalnum():
            return False
            
       
        return len(emoji_str) <= 32
    except Exception:
        return False



class AutoReact(commands.Cog):
    """AutoReact command system — react to messages matching configured triggers."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_path = DB_PATH
        self.color = EMBED_COLOR


    @commands.group(
        name="autoreact",
        aliases=["ar"],
        help="Manage autoreact triggers for this server.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def autoreact(self, ctx: commands.Context) -> None:
        """Show the autoreact help menu when invoked without a subcommand."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)




    @autoreact.command(
        name="add",
        help="Add a new autoreact trigger.",
        usage="<trigger> <emoji1> [emoji2] ... (max 5)",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_add(
        self,
        ctx: commands.Context,
        trigger: str,
        *,
        emojis: str,
    ) -> None:
        """Add a new autoreact trigger with up to 5 emojis."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                if await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> Autoreact with trigger **{trigger}** already exists.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

        current_count = await _get_autoreact_count(ctx.guild.id)
        guild_limit = await _get_guild_limit(ctx.guild.id)
        is_premium = await _is_premium_guild(ctx.guild.id)

        if current_count >= guild_limit:
            if is_premium:
                embed = discord.Embed(
                    description=(
                        f"<:SynapseExcl:1477234549552320634> Autoreact premium limit reached. "
                        f"You can only have ``{GUILD_LIMIT_PREMIUM}`` autoreact triggers with Premium."
                    ),
                    color=self.color,
                )
            else:
                embed = discord.Embed(
                    description=(
                        f"<:SynapseExcl:1477234549552320634> Autoreact limit reached. "
                        f"You can only have ``{GUILD_LIMIT_NORMAL}`` autoreact triggers. "
                        f"To Create a new autoreact u must have to delete one by using `autoreact delete <trigger>` command."
                        f"*<:SynapseNote:1477236015830663324> Note: You can upgrade to **Premium** for up to ``{GUILD_LIMIT_PREMIUM}`` max autoreacts.*"
                    ),
                    color=0x2b2d31,
                )
            return await ctx.send(embed=embed)

        emoji_list = _parse_emoji_input(emojis)
        if not emoji_list:
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> You must provide at least one emoji.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        if len(emoji_list) > MAX_EMOJIS_PER_TRIGGER:
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> You can only add up to **{MAX_EMOJIS_PER_TRIGGER}** emojis per trigger.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        valid_emojis = []
        for emoji in emoji_list:
            if _validate_emoji(emoji, self.bot):
                valid_emojis.append(emoji)
            else:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Invalid emoji: `{emoji}`. Make sure the bot can access this emoji.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

        now = datetime.utcnow().isoformat()
        emojis_json = json.dumps(valid_emojis)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO autoreacts (guild_id, trigger, emojis, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
                (ctx.guild.id, trigger, emojis_json, now),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        emoji_display = " ".join(valid_emojis)
        embed = discord.Embed(
            description=(
                f"<:emoji_1769867605256:1467155817726873650> Successfully added autoreact for trigger **{trigger}**.\n"
                f"**Emojis:** {emoji_display}"
            ),
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="remove",
        aliases=["delete", "rm"],
        help="Remove an existing autoreact trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_remove(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Remove an existing autoreact trigger."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                if not await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> No autoreact found with trigger **{trigger}**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

            await db.execute(
                "DELETE FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed autoreact for trigger **{trigger}**.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="edit",
        help="Edit the emojis of an existing autoreact trigger.",
        usage="<trigger> <emoji1> [emoji2] ... (max 5)",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_edit(
        self,
        ctx: commands.Context,
        trigger: str,
        *,
        emojis: str,
    ) -> None:
        """Edit the emojis of an existing autoreact trigger."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                if not await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> No autoreact found with trigger **{trigger}**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

        emoji_list = _parse_emoji_input(emojis)
        if not emoji_list:
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> You must provide at least one emoji.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        if len(emoji_list) > MAX_EMOJIS_PER_TRIGGER:
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> You can only add up to **{MAX_EMOJIS_PER_TRIGGER}** emojis per trigger.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        valid_emojis = []
        for emoji in emoji_list:
            if _validate_emoji(emoji, self.bot):
                valid_emojis.append(emoji)
            else:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Invalid emoji: `{emoji}`. Make sure the bot can access this emoji.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

        emojis_json = json.dumps(valid_emojis)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE autoreacts SET emojis = ? WHERE guild_id = ? AND trigger = ?",
                (emojis_json, ctx.guild.id, trigger),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        emoji_display = " ".join(valid_emojis)
        embed = discord.Embed(
            description=(
                f"<:emoji_1769867605256:1467155817726873650> Successfully updated autoreact for trigger **{trigger}**.\n"
                f"**New Emojis:** {emoji_display}"
            ),
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="enable",
        help="Enable a specific autoreact trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_enable(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Enable a specific autoreact trigger."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT enabled FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> No autoreact found with trigger **{trigger}**.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if row[0] == 1:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Autoreact **{trigger}** is already enabled.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            await db.execute(
                "UPDATE autoreacts SET enabled = 1 WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully enabled autoreact for trigger **{trigger}**.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="disable",
        help="Disable a specific autoreact trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_disable(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Disable a specific autoreact trigger."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT enabled FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> No autoreact found with trigger **{trigger}**.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if row[0] == 0:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Autoreact **{trigger}** is already disabled.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            await db.execute(
                "UPDATE autoreacts SET enabled = 0 WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully disabled autoreact for trigger **{trigger}**.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="toggle",
        help="Toggle a specific autoreact trigger on or off.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_toggle(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Toggle a specific autoreact trigger on or off."""
        trigger = trigger.lower().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT enabled FROM autoreacts WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> No autoreact found with trigger **{trigger}**.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            new_state = 0 if row[0] == 1 else 1
            await db.execute(
                "UPDATE autoreacts SET enabled = ? WHERE guild_id = ? AND trigger = ?",
                (new_state, ctx.guild.id, trigger),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        state_text = "enabled" if new_state == 1 else "disabled"
        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully **{state_text}** autoreact for trigger **{trigger}**.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact.command(
        name="show",
        aliases=["list", "all"],
        help="Show all autoreact triggers in this guild.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoreact_show(self, ctx: commands.Context) -> None:
        """Show all autoreact triggers in this guild with pagination."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT trigger, emojis, enabled, created_at FROM autoreacts WHERE guild_id = ? ORDER BY created_at ASC",
                (ctx.guild.id,),
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> No autoreacts in this guild.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        guild_limit = await _get_guild_limit(ctx.guild.id)
        entries = []
        for idx, (trigger, emojis_json, enabled, created_at) in enumerate(rows, start=1):
            emoji_list = json.loads(emojis_json)
            emoji_display = " ".join(emoji_list) if emoji_list else "None"
            status = "<:emoji_1769867605256:1467155817726873650> Enabled" if enabled else "<:emoji_1769867589372:1467155751456735326> Disabled"
            entries.append(
                f"`{idx}.` **{trigger}** — {emoji_display}\n"
                f"╰ {status}"
            )

        source = DescriptionEmbedPaginator(
            entries,
            per_page=10,
            title=f"AutoReact Triggers ({len(rows)}/{guild_limit})",
        )
        paginator = HackerPaginator(source, ctx=ctx)
        await paginator.paginate()


    @autoreact.group(
        name="ignore",
        help="Manage ignored channels for autoreact.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def autoreact_ignore(self, ctx: commands.Context) -> None:
        """Show ignored channels help when invoked without subcommand."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)




    @autoreact_ignore.command(
        name="add",
        help="Add a channel to the autoreact ignore list.",
        usage="<channel>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ) -> None:
        """Add a channel to the autoreact ignore list."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM ignored_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            ) as cursor:
                if await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> Channel {channel.mention} is already ignored.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

            await db.execute(
                "INSERT INTO ignored_channels (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully added {channel.mention} to the autoreact ignore list.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact_ignore.command(
        name="remove",
        help="Remove a channel from the autoreact ignore list.",
        usage="<channel>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_remove(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ) -> None:
        """Remove a channel from the autoreact ignore list."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM ignored_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            ) as cursor:
                if not await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> Channel {channel.mention} is not ignored.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

            await db.execute(
                "DELETE FROM ignored_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed {channel.mention} from the autoreact ignore list.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact_ignore.command(
        name="reset",
        aliases=["clear"],
        help="Reset all ignored channels for autoreact.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_reset(self, ctx: commands.Context) -> None:
        """Reset all ignored channels for autoreact in this guild."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM ignored_channels WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0

            if count == 0:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> No ignored channels to reset.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            await db.execute(
                "DELETE FROM ignored_channels WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await db.commit()

        self.bot.dispatch("autoreact_update", ctx.guild.id)

        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully reset **{count}** ignored channel(s) for autoreact.",
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoreact_ignore.command(
        name="show",
        aliases=["list"],
        help="Show all ignored channels for autoreact.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_show(self, ctx: commands.Context) -> None:
        """Show all ignored channels for autoreact with pagination."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id FROM ignored_channels WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> No ignored channels are currently configured.",
                color=self.color,
            )
            return await ctx.send(embed=embed)

        entries = []
        for idx, (channel_id,) in enumerate(rows, start=1):
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                entries.append(f"`{idx}.` {channel.mention}")
            else:
                entries.append(f"`{idx}.` Unknown Channel (`{channel_id}`)")

        source = DescriptionEmbedPaginator(
            entries,
            per_page=10,
            title=f"Ignored Channels ({len(rows)})",
        )
        paginator = HackerPaginator(source, ctx=ctx)
        await paginator.paginate()



async def setup(bot: commands.Bot) -> None:
    """Initialize the autoreact database and load the AutoReact cog."""
    await _init_autoreact_db()
    await bot.add_cog(AutoReact(bot))
