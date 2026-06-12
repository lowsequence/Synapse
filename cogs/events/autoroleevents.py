import os
import discord
import aiosqlite
from discord.ext import commands

DB_PATH = os.path.join("database", "autorole.db")


class AutoRoleEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        bot.loop.create_task(self.load_cache())

    async def load_cache(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, role_id FROM autorole_humans") as cur:
                human_rows = await cur.fetchall()
            async with db.execute("SELECT guild_id, role_id FROM autorole_bots") as cur:
                bot_rows = await cur.fetchall()

        for guild_id, role_id in human_rows:
            self.cache.setdefault(guild_id, {"humans": [], "bots": []})
            self.cache[guild_id]["humans"].append(role_id)

        for guild_id, role_id in bot_rows:
            self.cache.setdefault(guild_id, {"humans": [], "bots": []})
            self.cache[guild_id]["bots"].append(role_id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self.cache.get(member.guild.id)
        if not cfg:
            return

        role_ids = cfg["bots"] if member.bot else cfg["humans"]
        if not role_ids:
            return

        roles_to_add = []
        for rid in role_ids:
            role = member.guild.get_role(rid)
            if role and role not in member.roles:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Synapse AutoRole on join")
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(AutoRoleEvent(bot))
