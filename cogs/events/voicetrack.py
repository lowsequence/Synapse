import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import datetime

DB_PATH = os.path.join("database", "voicetrack.db")

class VoiceTrackEvents(commands.Cog):
    """Core Event Listener for advanced premium voice tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}
        self.update_voice_cache.start()

    def cog_unload(self):
        self.update_voice_cache.cancel()

    async def cog_load(self):
        await self._init_db()

    async def _init_db(self):
        """Initializes the completely new voicetrack.db"""
        os.makedirs("database", exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_counts (
                    guild_id INTEGER,
                    user_id INTEGER,
                    total_time INTEGER DEFAULT 0,
                    daily_time INTEGER DEFAULT 0,
                    weekly_time INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_config (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    @tasks.loop(minutes=5)
    async def update_voice_cache(self):
        """Failsafe loop: Checks all members currently in VC and ensures they are tracked in memory.
        Also flushes incredibly long sessions into the DB in chunks to prevent data loss on bot restart."""
        now = datetime.datetime.now()

        async with aiosqlite.connect(DB_PATH) as db:
            for guild in self.bot.guilds:
                cur = await db.execute("SELECT enabled FROM voice_config WHERE guild_id = ?", (guild.id,))
                config = await cur.fetchone()

                if not config or config[0] == 0:
                    if guild.id in self.active_sessions:
                        del self.active_sessions[guild.id]
                    continue

                if guild.id not in self.active_sessions:
                    self.active_sessions[guild.id] = {}

                for member_id, join_time in list(self.active_sessions[guild.id].items()):
                    member = guild.get_member(member_id)
                    if member and member.voice and member.voice.channel:
                        delta = int((now - join_time).total_seconds())
                        if delta > 0:
                            await self._add_time(db, guild.id, member_id, delta)
                            self.active_sessions[guild.id][member_id] = now
                    else:
                        del self.active_sessions[guild.id][member_id]

                for vc in guild.voice_channels:
                    for member in vc.members:
                        if member.bot: continue
                        if member.id not in self.active_sessions[guild.id]:
                            self.active_sessions[guild.id][member.id] = now

            await db.commit()

    @update_voice_cache.before_loop
    async def before_update_voice_cache(self):
        await self.bot.wait_until_ready()

    async def _add_time(self, db, guild_id, user_id, seconds):
        """Helper to increment raw seconds in the DB"""
        await db.execute("""
            INSERT INTO voice_counts (guild_id, user_id, total_time, daily_time, weekly_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET 
                total_time = total_time + ?,
                daily_time = daily_time + ?,
                weekly_time = weekly_time + ?
        """, (guild_id, user_id, seconds, seconds, seconds, seconds, seconds, seconds))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        guild = member.guild
        now = datetime.datetime.now()

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM voice_config WHERE guild_id = ?", (guild.id,))
            config = await cur.fetchone()

        if not config or config[0] == 0:
            if guild.id in self.active_sessions and member.id in self.active_sessions[guild.id]:
                del self.active_sessions[guild.id][member.id]
            return

        if guild.id not in self.active_sessions:
            self.active_sessions[guild.id] = {}

        if before.channel is None and after.channel is not None:
            self.active_sessions[guild.id][member.id] = now
            return

        if before.channel is not None and after.channel is None:
            if member.id in self.active_sessions[guild.id]:
                join_time = self.active_sessions[guild.id].pop(member.id)
                delta = int((now - join_time).total_seconds())

                if delta > 0:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await self._add_time(db, guild.id, member.id, delta)
                        await db.commit()
            return

        pass

async def setup(bot):
    await bot.add_cog(VoiceTrackEvents(bot))
