from __future__ import annotations

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
DB_PATH = "database/autoresponder.db"
PREMIUM_DB = "database/premium_codes.db"

GUILD_LIMIT_NORMAL = 10
GUILD_LIMIT_PREMIUM = 25

MAX_TRIGGER_LENGTH = 100
MAX_RESPONSE_LENGTH = 2000



async def _init_autoresponder_db() -> None:
    """Create the autoresponder database tables if they do not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS autoresponders (
                guild_id   INTEGER NOT NULL,
                trigger    TEXT    NOT NULL,
                response   TEXT    NOT NULL,
                enabled    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    NOT NULL,
                updated_at TEXT    NOT NULL,
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
    """Return the autoresponder limit for a guild (normal vs premium)."""
    if await _is_premium_guild(guild_id):
        return GUILD_LIMIT_PREMIUM
    return GUILD_LIMIT_NORMAL


async def _get_autoresponder_count(guild_id: int) -> int:
    """Return the number of autoresponder triggers configured for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM autoresponders WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0



async def trim_autoresponders_on_premium_expire(guild_id: int) -> int:
    """
    Called when a guild's premium expires.
    Deletes the *oldest* autoresponders until only GUILD_LIMIT_NORMAL (10) remain.
    Returns the number of autoresponders deleted.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM autoresponders WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0

        if total <= GUILD_LIMIT_NORMAL:
            return 0

        excess = total - GUILD_LIMIT_NORMAL

        await db.execute(
            """
            DELETE FROM autoresponders
            WHERE rowid IN (
                SELECT rowid FROM autoresponders
                WHERE guild_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (guild_id, excess),
        )
        await db.commit()
        return excess



class AutoResponder(commands.Cog):
    """AutoResponder command system — auto-reply to messages matching configured triggers."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_path = DB_PATH
        self.color = EMBED_COLOR


    @commands.group(
        name="autoresponder",
        aliases=["ares"],
        help="Manage autoresponder triggers for this server.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def autoresponder(self, ctx: commands.Context) -> None:
        """Show the autoresponder help menu when invoked without a subcommand."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)



    @autoresponder.command(
        name="add",
        help="Add a new autoresponder trigger.",
        usage="<trigger>, <response>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_add(
        self,
        ctx: commands.Context,
        *,
        args: str,
    ) -> None:
        """
        Add a new autoresponder trigger with a response.
        Usage: autoresponder add <trigger>, <response>
        The trigger and response are separated by a comma.
        """
        try:
            if "," not in args:
                embed = discord.Embed(
                    description=(
                        "<:SynapseExcl:1477234549552320634> Invalid format. Use a comma to separate the trigger and response.\n"
                        "**Usage:** `autoresponder add <trigger>, <response>`"
                    ),
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            parts = args.split(",", 1)
            trigger = parts[0].strip().lower()
            response = parts[1].strip()

            if not trigger:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> You must provide a **trigger** word or phrase.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if not response:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> You must provide a **response** message.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if len(trigger) > MAX_TRIGGER_LENGTH:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Trigger must be **{MAX_TRIGGER_LENGTH}** characters or fewer.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if len(response) > MAX_RESPONSE_LENGTH:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Response must be **{MAX_RESPONSE_LENGTH}** characters or fewer.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                ) as cursor:
                    if await cursor.fetchone():
                        embed = discord.Embed(
                            description=f"<:SynapseExcl:1477234549552320634> Autoresponder with trigger **{trigger}** already exists.",
                            color=self.color,
                        )
                        return await ctx.send(embed=embed)

            current_count = await _get_autoresponder_count(ctx.guild.id)
            guild_limit = await _get_guild_limit(ctx.guild.id)
            is_premium = await _is_premium_guild(ctx.guild.id)

            if current_count >= guild_limit:
                if is_premium:
                    embed = discord.Embed(
                        description=(
                            f"<:SynapseExcl:1477234549552320634> Autoresponder premium limit reached. "
                            f"You can only have **{GUILD_LIMIT_PREMIUM}** autoresponders with Premium."
                        ),
                        color=self.color,
                    )
                else:
                    embed = discord.Embed(
                        description=(
                            f"<:SynapseExcl:1477234549552320634> Autoresponder limit reached. "
                            f"You can only have **{GUILD_LIMIT_NORMAL}** autoresponders. "
                            f"To Create a new Autoresponder u must have to delete one by using `Autoresponder delete <trigger>` command."
                            f"*<:SynapseNote:1477236015830663324> Note: You can upgrade to **Premium** for up to ``{GUILD_LIMIT_PREMIUM}`` max Autoresponders.*"
                        ),
                        color=self.color,
                    )
                return await ctx.send(embed=embed)

            now = datetime.utcnow().isoformat()

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO autoresponders (guild_id, trigger, response, enabled, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                    (ctx.guild.id, trigger, response, now, now),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=(
                    f"<:emoji_1769867605256:1467155817726873650> Successfully added autoresponder.\n\n"
                    f"**Trigger:** `{trigger}`\n"
                    f"**Response:** {response[:200]}{'...' if len(response) > 200 else ''}"
                ),
                color=self.color,
            )
            embed.set_footer(text=f"Autoresponders: {current_count + 1}/{guild_limit}")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in add command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while adding the autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="remove",
        aliases=["delete", "rm"],
        help="Remove an existing autoresponder trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_remove(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Remove an existing autoresponder trigger."""
        try:
            trigger = trigger.lower().strip()

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                ) as cursor:
                    if not await cursor.fetchone():
                        embed = discord.Embed(
                            description=f"<:SynapseExcl:1477234549552320634> No autoresponder found with trigger **{trigger}**.",
                            color=self.color,
                        )
                        return await ctx.send(embed=embed)

                await db.execute(
                    "DELETE FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed autoresponder for trigger **{trigger}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in remove command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while removing the autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="edit",
        help="Edit the response of an existing autoresponder trigger.",
        usage="<trigger>, <new_response>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_edit(
        self,
        ctx: commands.Context,
        *,
        args: str,
    ) -> None:
        """
        Edit the response of an existing autoresponder.
        Usage: autoresponder edit <trigger>, <new_response>
        """
        try:
            if "," not in args:
                embed = discord.Embed(
                    description=(
                        "<:SynapseExcl:1477234549552320634> Invalid format. Use a comma to separate the trigger and new response.\n"
                        "**Usage:** `autoresponder edit <trigger>, <new_response>`"
                    ),
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            parts = args.split(",", 1)
            trigger = parts[0].strip().lower()
            new_response = parts[1].strip()

            if not trigger:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> You must provide the **trigger** to edit.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if not new_response:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> You must provide a **new response** message.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            if len(new_response) > MAX_RESPONSE_LENGTH:
                embed = discord.Embed(
                    description=f"<:SynapseExcl:1477234549552320634> Response must be **{MAX_RESPONSE_LENGTH}** characters or fewer.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                ) as cursor:
                    if not await cursor.fetchone():
                        embed = discord.Embed(
                            description=f"<:SynapseExcl:1477234549552320634> No autoresponder found with trigger **{trigger}**.",
                            color=self.color,
                        )
                        return await ctx.send(embed=embed)

                now = datetime.utcnow().isoformat()
                await db.execute(
                    "UPDATE autoresponders SET response = ?, updated_at = ? WHERE guild_id = ? AND trigger = ?",
                    (new_response, now, ctx.guild.id, trigger),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=(
                    f"<:emoji_1769867605256:1467155817726873650> Successfully updated autoresponder for trigger **{trigger}**.\n\n"
                    f"**New Response:** {new_response[:200]}{'...' if len(new_response) > 200 else ''}"
                ),
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in edit command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while editing the autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="enable",
        help="Enable a specific autoresponder trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_enable(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Enable a specific autoresponder trigger."""
        try:
            trigger = trigger.lower().strip()

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT enabled FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> No autoresponder found with trigger **{trigger}**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                if row[0] == 1:
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> Autoresponder **{trigger}** is already **enabled**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                now = datetime.utcnow().isoformat()
                await db.execute(
                    "UPDATE autoresponders SET enabled = 1, updated_at = ? WHERE guild_id = ? AND trigger = ?",
                    (now, ctx.guild.id, trigger),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully **enabled** autoresponder for trigger **{trigger}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in enable command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while enabling the autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="disable",
        help="Disable a specific autoresponder trigger.",
        usage="<trigger>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_disable(
        self,
        ctx: commands.Context,
        *,
        trigger: str,
    ) -> None:
        """Disable a specific autoresponder trigger."""
        try:
            trigger = trigger.lower().strip()

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT enabled FROM autoresponders WHERE guild_id = ? AND trigger = ?",
                    (ctx.guild.id, trigger),
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> No autoresponder found with trigger **{trigger}**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                if row[0] == 0:
                    embed = discord.Embed(
                        description=f"<:SynapseExcl:1477234549552320634> Autoresponder **{trigger}** is already **disabled**.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                now = datetime.utcnow().isoformat()
                await db.execute(
                    "UPDATE autoresponders SET enabled = 0, updated_at = ? WHERE guild_id = ? AND trigger = ?",
                    (now, ctx.guild.id, trigger),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully **disabled** autoresponder for trigger **{trigger}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in disable command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while disabling the autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="toggle",
        help="Toggle ALL autoresponders for this guild on or off.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_toggle(self, ctx: commands.Context) -> None:
        """Toggle ALL autoresponders for this guild on or off."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM autoresponders WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    total = row[0] if row else 0

                if total == 0:
                    embed = discord.Embed(
                        description="<:SynapseExcl:1477234549552320634> This guild currently doesn't have any autoresponders.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                async with db.execute(
                    "SELECT COUNT(*) FROM autoresponders WHERE guild_id = ? AND enabled = 1",
                    (ctx.guild.id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    enabled_count = row[0] if row else 0

                if enabled_count > 0:
                    new_state = 0
                    state_text = "disabled"
                else:
                    new_state = 1
                    state_text = "enabled"

                now = datetime.utcnow().isoformat()
                await db.execute(
                    "UPDATE autoresponders SET enabled = ?, updated_at = ? WHERE guild_id = ?",
                    (new_state, now, ctx.guild.id),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=(
                    f"<:emoji_1769867605256:1467155817726873650> Successfully **{state_text}** all **{total}** autoresponder(s) for this guild."
                ),
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in toggle command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while toggling autoresponders.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.command(
        name="show",
        aliases=["list", "all"],
        help="Show all autoresponder triggers in this guild.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_show(self, ctx: commands.Context) -> None:
        """Show all autoresponder triggers in this guild with pagination."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT trigger, response, enabled, created_at, updated_at FROM autoresponders WHERE guild_id = ? ORDER BY created_at ASC",
                    (ctx.guild.id,),
                ) as cursor:
                    rows = await cursor.fetchall()

            if not rows:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> This guild currently doesn't have any autoresponders.",
                    color=self.color,
                )
                return await ctx.send(embed=embed)

            guild_limit = await _get_guild_limit(ctx.guild.id)
            entries = []
            for idx, (trigger, response, enabled, created_at, updated_at) in enumerate(rows, start=1):
                status = "✅ Enabled" if enabled else "❌ Disabled"
                response_preview = response[:80] + "..." if len(response) > 80 else response
                entries.append(
                    f"`{idx}.` **{trigger}**\n"
                    f"╰ **Response:** {response_preview}\n"
                    f"╰ {status}"
                )

            source = DescriptionEmbedPaginator(
                entries,
                per_page=5,
                title=f"AutoResponder Triggers ({len(rows)}/{guild_limit})",
            )
            paginator = HackerPaginator(source, ctx=ctx)
            await paginator.paginate()

        except Exception as e:
            print(f"[AutoResponder] Error in show command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while listing autoresponders.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.group(
        name="ignore",
        help="Manage ignored channels for autoresponder.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def autoresponder_ignore(self, ctx: commands.Context) -> None:
        """Show ignored channels help when invoked without subcommand."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

        embed = discord.Embed(
            title="AutoResponder Ignore",
            description=(
                "Manage channels where autoresponder is disabled.\n\n"
                "**Subcommands:**\n"
                "`add` — Add a channel to ignore list\n"
                "`remove` — Remove a channel from ignore list\n"
                "`reset` — Reset all ignored channels\n"
                "`show` — Show all ignored channels"
            ),
            color=self.color,
        )
        await ctx.send(embed=embed)


    @autoresponder_ignore.command(
        name="add",
        help="Add a channel to the autoresponder ignore list.",
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
        """Add a channel to the autoresponder ignore list."""
        try:
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

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully added {channel.mention} to the autoresponder ignore list.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in ignore add command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while adding the ignored channel.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder_ignore.command(
        name="remove",
        help="Remove a channel from the autoresponder ignore list.",
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
        """Remove a channel from the autoresponder ignore list."""
        try:
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

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed {channel.mention} from the autoresponder ignore list.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in ignore remove command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while removing the ignored channel.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder_ignore.command(
        name="reset",
        aliases=["clear"],
        help="Reset all ignored channels for autoresponder.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_reset(self, ctx: commands.Context) -> None:
        """Reset all ignored channels for autoresponder in this guild."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM ignored_channels WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    count = row[0] if row else 0

                if count == 0:
                    embed = discord.Embed(
                        description="<:SynapseExcl:1477234549552320634> This guild currently doesn't have any ignored channels.",
                        color=self.color,
                    )
                    return await ctx.send(embed=embed)

                await db.execute(
                    "DELETE FROM ignored_channels WHERE guild_id = ?",
                    (ctx.guild.id,),
                )
                await db.commit()

            self.bot.dispatch("autoresponder_update", ctx.guild.id)

            embed = discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Successfully reset **{count}** ignored channel(s) for autoresponder.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[AutoResponder] Error in ignore reset command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while resetting ignored channels.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder_ignore.command(
        name="show",
        aliases=["list"],
        help="Show all ignored channels for autoresponder.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_show(self, ctx: commands.Context) -> None:
        """Show all ignored channels for autoresponder with pagination."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT channel_id FROM ignored_channels WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    rows = await cursor.fetchall()

            if not rows:
                embed = discord.Embed(
                    description="<:SynapseExcl:1477234549552320634> This guild currently doesn't have any ignored channels.",
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

        except Exception as e:
            print(f"[AutoResponder] Error in ignore show command: {e}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred while listing ignored channels.",
                color=self.color,
            )
            await ctx.send(embed=embed)


    @autoresponder.error
    @autoresponder_add.error
    @autoresponder_remove.error
    @autoresponder_edit.error
    @autoresponder_enable.error
    @autoresponder_disable.error
    @autoresponder_toggle.error
    @autoresponder_show.error
    @autoresponder_ignore.error
    @ignore_add.error
    @ignore_remove.error
    @ignore_reset.error
    @ignore_show.error
    async def autoresponder_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Custom error handler for all autoresponder commands."""
        error = getattr(error, "original", error)

        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> You are missing the following permission(s): **{missing}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> Missing required argument: **{error.param.name}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> Invalid argument provided. Please check the command usage.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.ChannelNotFound):
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> Channel not found. Please provide a valid text channel.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> Command is on cooldown. Try again in **{error.retry_after:.1f}** seconds.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.NoPrivateMessage):
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> This command can only be used in a server.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> I am missing the following permission(s): **{missing}**.",
                color=self.color,
            )
            await ctx.send(embed=embed)

        else:
            print(f"[AutoResponder] Unhandled error: {type(error).__name__}: {error}")
            embed = discord.Embed(
                description="<:SynapseExcl:1477234549552320634> An unexpected error occurred. Please try again later.",
                color=self.color,
            )
            await ctx.send(embed=embed)



async def setup(bot: commands.Bot) -> None:
    """Initialize the autoresponder database and load the AutoResponder cog."""
    await _init_autoresponder_db()
    await bot.add_cog(AutoResponder(bot))
