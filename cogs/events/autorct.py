from __future__ import annotations

import json
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands


DB_PATH = "database/autoreact.db"



class AutoReactEvents(commands.Cog):
    """Event listener cog that handles autoreact reactions on_message."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_path = DB_PATH

        self._autoreact_cache: dict[int, dict[str, list[str]]] = {}
        self._ignored_cache: dict[int, set[int]] = {}

        self.bot.loop.create_task(self._load_caches())


    async def _load_caches(self) -> None:
        """Load all autoreact triggers and ignored channels into memory."""
        await self.bot.wait_until_ready()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id, trigger, emojis FROM autoreacts WHERE enabled = 1"
                ) as cursor:
                    rows = await cursor.fetchall()

                self._autoreact_cache.clear()
                for guild_id, trigger, emojis_json in rows:
                    if guild_id not in self._autoreact_cache:
                        self._autoreact_cache[guild_id] = {}
                    try:
                        emoji_list = json.loads(emojis_json)
                    except (json.JSONDecodeError, TypeError):
                        emoji_list = []
                    self._autoreact_cache[guild_id][trigger] = emoji_list

                async with db.execute(
                    "SELECT guild_id, channel_id FROM ignored_channels"
                ) as cursor:
                    ignored_rows = await cursor.fetchall()

                self._ignored_cache.clear()
                for guild_id, channel_id in ignored_rows:
                    if guild_id not in self._ignored_cache:
                        self._ignored_cache[guild_id] = set()
                    self._ignored_cache[guild_id].add(channel_id)

        except Exception as e:
            print(f"[AutoReactEvents] Failed to load caches: {e}")

    async def refresh_guild_cache(self, guild_id: int) -> None:
        """
        Refresh the cache for a specific guild.
        Call this after any modification to autoreacts or ignored channels.
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT trigger, emojis FROM autoreacts WHERE guild_id = ? AND enabled = 1",
                    (guild_id,),
                ) as cursor:
                    rows = await cursor.fetchall()

                self._autoreact_cache[guild_id] = {}
                for trigger, emojis_json in rows:
                    try:
                        emoji_list = json.loads(emojis_json)
                    except (json.JSONDecodeError, TypeError):
                        emoji_list = []
                    self._autoreact_cache[guild_id][trigger] = emoji_list

                async with db.execute(
                    "SELECT channel_id FROM ignored_channels WHERE guild_id = ?",
                    (guild_id,),
                ) as cursor:
                    ignored_rows = await cursor.fetchall()

                self._ignored_cache[guild_id] = {
                    channel_id for (channel_id,) in ignored_rows
                }

        except Exception as e:
            print(f"[AutoReactEvents] Failed to refresh cache for guild {guild_id}: {e}")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """React to messages that exactly match an autoreact trigger."""
        if message.author.bot:
            return

        if not message.guild:
            return

        guild_id = message.guild.id

        guild_triggers = self._autoreact_cache.get(guild_id)
        if not guild_triggers:
            return

        ignored_channels = self._ignored_cache.get(guild_id, set())
        if message.channel.id in ignored_channels:
            return

        content = message.content.lower().strip()

        emojis = guild_triggers.get(content)
        if not emojis:
            return

        for emoji_str in emojis:
            try:
                # Use PartialEmoji.from_str for consistent and robust reaction handling
                # This works for both custom and unicode emojis.
                try:
                    emoji_obj = discord.PartialEmoji.from_str(emoji_str)
                    await message.add_reaction(emoji_obj)
                except Exception:
                    # Fallback to raw string if conversion fails
                    await message.add_reaction(emoji_str)
            except discord.HTTPException:
                # Likely invalid emoji or missing permissions for this specific emoji
                continue
            except Exception:
                continue


    @commands.Cog.listener()
    async def on_autoreact_update(self, guild_id: int) -> None:
        """
        Custom event dispatched after any autoreact modification.
        Refreshes the cache for the specific guild.

        Dispatch with: self.bot.dispatch('autoreact_update', ctx.guild.id)
        """
        await self.refresh_guild_cache(guild_id)


    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Clean up caches when the bot leaves a guild."""
        self._autoreact_cache.pop(guild.id, None)
        self._ignored_cache.pop(guild.id, None)

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM autoreacts WHERE guild_id = ?",
                    (guild.id,),
                )
                await db.execute(
                    "DELETE FROM ignored_channels WHERE guild_id = ?",
                    (guild.id,),
                )
                await db.commit()
        except Exception:
            pass



async def setup(bot: commands.Bot) -> None:
    """Load the AutoReactEvents cog."""
    await bot.add_cog(AutoReactEvents(bot))
