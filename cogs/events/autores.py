from __future__ import annotations

from datetime import datetime
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks


DB_PATH = "database/autoresponder.db"
PREMIUM_DB = "database/premium_codes.db"

GUILD_LIMIT_NORMAL = 10



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



async def _trim_autoresponders(guild_id: int) -> int:
    """
    Delete the *oldest* autoresponders until only GUILD_LIMIT_NORMAL (10) remain.
    Returns the number of entries deleted.
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



class AutoResponderEvents(commands.Cog):
    """Event listener cog that handles autoresponder replies on_message."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_path = DB_PATH

        self._autoresponder_cache: dict[int, dict[str, str]] = {}
        self._ignored_cache: dict[int, set[int]] = {}

        self._premium_checked: set[int] = set()

        self.bot.loop.create_task(self._load_caches())

        self.premium_cleanup_loop.start()

    def cog_unload(self) -> None:
        """Cancel the background loop when the cog is unloaded."""
        self.premium_cleanup_loop.cancel()


    async def _load_caches(self) -> None:
        """Load all autoresponder triggers and ignored channels into memory."""
        await self.bot.wait_until_ready()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id, trigger, response FROM autoresponders WHERE enabled = 1"
                ) as cursor:
                    rows = await cursor.fetchall()

                self._autoresponder_cache.clear()
                for guild_id, trigger, response in rows:
                    if guild_id not in self._autoresponder_cache:
                        self._autoresponder_cache[guild_id] = {}
                    self._autoresponder_cache[guild_id][trigger] = response

                async with db.execute(
                    "SELECT guild_id, channel_id FROM ignored_channels"
                ) as cursor:
                    ignored_rows = await cursor.fetchall()

                self._ignored_cache.clear()
                for guild_id, channel_id in ignored_rows:
                    if guild_id not in self._ignored_cache:
                        self._ignored_cache[guild_id] = set()
                    self._ignored_cache[guild_id].add(channel_id)

            print(
                f"[AutoResponderEvents] Cache loaded: "
                f"{sum(len(v) for v in self._autoresponder_cache.values())} triggers across "
                f"{len(self._autoresponder_cache)} guilds"
            )

        except Exception as e:
            print(f"[AutoResponderEvents] Failed to load caches: {e}")

    async def refresh_guild_cache(self, guild_id: int) -> None:
        """
        Refresh the cache for a specific guild.
        Call this after any modification to autoresponders or ignored channels.
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT trigger, response FROM autoresponders WHERE guild_id = ? AND enabled = 1",
                    (guild_id,),
                ) as cursor:
                    rows = await cursor.fetchall()

                self._autoresponder_cache[guild_id] = {}
                for trigger, response in rows:
                    self._autoresponder_cache[guild_id][trigger] = response

                async with db.execute(
                    "SELECT channel_id FROM ignored_channels WHERE guild_id = ?",
                    (guild_id,),
                ) as cursor:
                    ignored_rows = await cursor.fetchall()

                self._ignored_cache[guild_id] = {
                    channel_id for (channel_id,) in ignored_rows
                }

        except Exception as e:
            print(f"[AutoResponderEvents] Failed to refresh cache for guild {guild_id}: {e}")


    async def _check_premium_cleanup(self, guild_id: int) -> None:
        """
        Check if a guild's premium expired and trim excess autoresponders.
        Only runs once per guild per session to avoid spamming DB checks.
        """
        if guild_id in self._premium_checked:
            return

        try:
            is_premium = await _is_premium_guild(guild_id)
            if not is_premium:
                deleted = await _trim_autoresponders(guild_id)
                if deleted > 0:
                    print(
                        f"[AutoResponderEvents] Premium expired for guild {guild_id}: "
                        f"trimmed {deleted} autoresponder(s) to {GUILD_LIMIT_NORMAL}."
                    )
                    await self.refresh_guild_cache(guild_id)

            self._premium_checked.add(guild_id)

        except Exception as e:
            print(f"[AutoResponderEvents] Premium cleanup check error for guild {guild_id}: {e}")


    @tasks.loop(minutes=5)
    async def premium_cleanup_loop(self) -> None:
        """
        Background loop that periodically checks all cached guilds
        for premium expiry and trims excess autoresponders.
        """
        try:
            guild_ids = list(self._autoresponder_cache.keys())
            for guild_id in guild_ids:
                try:
                    is_premium = await _is_premium_guild(guild_id)
                    if not is_premium:
                        deleted = await _trim_autoresponders(guild_id)
                        if deleted > 0:
                            print(
                                f"[AutoResponderEvents] Background cleanup for guild {guild_id}: "
                                f"trimmed {deleted} autoresponder(s)."
                            )
                            await self.refresh_guild_cache(guild_id)
                except Exception as e:
                    print(f"[AutoResponderEvents] Background cleanup error for guild {guild_id}: {e}")

            self._premium_checked.clear()

        except Exception as e:
            print(f"[AutoResponderEvents] Background cleanup loop error: {e}")

    @premium_cleanup_loop.before_loop
    async def before_premium_cleanup_loop(self) -> None:
        """Wait until the bot is ready before starting the cleanup loop."""
        await self.bot.wait_until_ready()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Respond to messages that exactly match an autoresponder trigger."""
        if message.author.bot:
            return

        if not message.guild:
            return

        guild_id = message.guild.id

        guild_triggers = self._autoresponder_cache.get(guild_id)
        if not guild_triggers:
            return

        ignored_channels = self._ignored_cache.get(guild_id, set())
        if message.channel.id in ignored_channels:
            return

        await self._check_premium_cleanup(guild_id)

        guild_triggers = self._autoresponder_cache.get(guild_id)
        if not guild_triggers:
            return

        content = message.content.lower().strip()

        response = guild_triggers.get(content)
        if not response:
            return

        try:
            await message.channel.send(response)
            print(
                f"[AutoResponderEvents] Triggered '{content}' in "
                f"{message.guild.name} (#{message.channel.name}) by {message.author}"
            )
        except discord.Forbidden:
            print(
                f"[AutoResponderEvents] Missing permissions to send in "
                f"#{message.channel.name} ({message.guild.name})"
            )
        except discord.HTTPException as e:
            print(f"[AutoResponderEvents] HTTP error sending response: {e}")
        except Exception as e:
            print(f"[AutoResponderEvents] Unexpected error: {e}")


    @commands.Cog.listener()
    async def on_autoresponder_update(self, guild_id: int) -> None:
        """
        Custom event dispatched after any autoresponder modification.
        Refreshes the cache for the specific guild.

        Dispatch with: self.bot.dispatch('autoresponder_update', ctx.guild.id)
        """
        await self.refresh_guild_cache(guild_id)

        self._premium_checked.discard(guild_id)


    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Clean up caches when the bot leaves a guild."""
        self._autoresponder_cache.pop(guild.id, None)
        self._ignored_cache.pop(guild.id, None)
        self._premium_checked.discard(guild.id)

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM autoresponders WHERE guild_id = ?",
                    (guild.id,),
                )
                await db.execute(
                    "DELETE FROM ignored_channels WHERE guild_id = ?",
                    (guild.id,),
                )
                await db.commit()
            print(f"[AutoResponderEvents] Cleaned up data for guild {guild.name} ({guild.id})")
        except Exception as e:
            print(f"[AutoResponderEvents] Failed to cleanup guild {guild.id}: {e}")



async def setup(bot: commands.Bot) -> None:
    """Load the AutoResponderEvents cog."""
    await bot.add_cog(AutoResponderEvents(bot))
