import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import datetime
from typing import Optional

DB_PATH = os.path.join("database", "messages.db")

async def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS message_counts (
                guild_id INTEGER,
                user_id INTEGER,
                count INTEGER DEFAULT 0,
                daily_count INTEGER DEFAULT 0,
                weekly_count INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS msg_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS msg_blacklists (
                guild_id INTEGER,
                entity_id INTEGER,
                entity_type TEXT, 
                PRIMARY KEY (guild_id, entity_id, entity_type)
            );
            CREATE TABLE IF NOT EXISTS msg_roles (
                guild_id INTEGER,
                messages_required INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            );
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        await db.commit()

class MessageTrackEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(_init_db())
        self.reset_intervals.start()

    def cog_unload(self):
        self.reset_intervals.cancel()

    @tasks.loop(minutes=10)
    async def reset_intervals(self):
        """Clears daily and weekly message counts based on stored timestamps."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                now = datetime.datetime.now(datetime.timezone.utc)

                cur = await db.execute("SELECT value FROM system_config WHERE key = 'last_daily'")
                row = await cur.fetchone()
                if not row:
                    await db.execute("INSERT INTO system_config (key, value) VALUES ('last_daily', ?)", (now.isoformat(),))
                    await db.commit()
                else:
                    last_daily = datetime.datetime.fromisoformat(row[0])
                    if (now - last_daily).total_seconds() >= 86400:
                        await db.execute("UPDATE message_counts SET daily_count = 0")
                        await db.execute("UPDATE system_config SET value = ? WHERE key = 'last_daily'", (now.isoformat(),))
                        await db.commit()

                cur = await db.execute("SELECT value FROM system_config WHERE key = 'last_weekly'")
                row = await cur.fetchone()
                if not row:
                    await db.execute("INSERT INTO system_config (key, value) VALUES ('last_weekly', ?)", (now.isoformat(),))
                    await db.commit()
                else:
                    last_weekly = datetime.datetime.fromisoformat(row[0])
                    if (now - last_weekly).total_seconds() >= 604800:
                        await db.execute("UPDATE message_counts SET weekly_count = 0")
                        await db.execute("UPDATE system_config SET value = ? WHERE key = 'last_weekly'", (now.isoformat(),))
                        await db.commit()
        except Exception as e:
            print(f"Error in msg intervals loop: {e}")

    @reset_intervals.before_loop
    async def before_reset_intervals(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.webhook_id:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        chan_id = message.channel.id
        cat_id = message.channel.category_id

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM msg_config WHERE guild_id = ?", (guild_id,))
            config_row = await cur.fetchone()
            if not config_row or config_row[0] == 0:
                return

            cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'channel'", (guild_id, chan_id))
            if await cur.fetchone():
                return

            if cat_id:
                cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'category'", (guild_id, cat_id))
                if await cur.fetchone():
                    return

            await db.execute("""
                INSERT INTO message_counts (guild_id, user_id, count, daily_count, weekly_count)
                VALUES (?, ?, 1, 1, 1)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET 
                    count = count + 1,
                    daily_count = daily_count + 1,
                    weekly_count = weekly_count + 1
            """, (guild_id, user_id))
            await db.commit()

            cur = await db.execute("SELECT count FROM message_counts WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            res = await cur.fetchone()
            if res:
                new_count = res[0]
                cur = await db.execute(
                    "SELECT role_id FROM msg_roles WHERE guild_id = ? AND messages_required = ?",
                    (guild_id, new_count)
                )
                role_rows = await cur.fetchall()
                for (role_id,) in role_rows:
                    role = message.guild.get_role(role_id)
                    if role and role not in message.author.roles:
                        try:
                            await message.author.add_roles(role, reason=f"Message Tracker Milestone reached: {new_count} messages")
                        except discord.Forbidden:
                            pass


async def setup(bot):
    await bot.add_cog(MessageTrackEvents(bot))
