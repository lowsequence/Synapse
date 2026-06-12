import os
import discord
import aiosqlite
from discord.ext import commands

DB_PATH = os.path.join("database", "autonick.db")


class AutoNickEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        bot.loop.create_task(self.load_cache())


    async def load_cache(self):
        await self.bot.wait_until_ready()
        if not os.path.exists(DB_PATH):
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute("SELECT * FROM autonick_join") as cur:
                join_rows = await cur.fetchall()

            async with db.execute("SELECT * FROM autonick_role") as cur:
                role_rows = await cur.fetchall()

        for row in join_rows:
            gid = row["guild_id"]
            self.cache.setdefault(gid, {"join": None, "roles": {}})
            self.cache[gid]["join"] = {
                "prefix": row["prefix"],
                "suffix": row["suffix"],
                "prefix_enabled": bool(row["prefix_enabled"]),
                "suffix_enabled": bool(row["suffix_enabled"]),
            }

        for row in role_rows:
            gid = row["guild_id"]
            rid = row["role_id"]
            self.cache.setdefault(gid, {"join": None, "roles": {}})
            self.cache[gid]["roles"][rid] = {
                "prefix": row["prefix"],
                "suffix": row["suffix"],
                "prefix_enabled": bool(row["prefix_enabled"]),
                "suffix_enabled": bool(row["suffix_enabled"]),
            }

    async def reload_guild(self, guild_id: int):
        """Reload the cache for a single guild (called from command cog)."""
        entry = {"join": None, "roles": {}}

        if not os.path.exists(DB_PATH):
            self.cache.pop(guild_id, None)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT * FROM autonick_join WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                entry["join"] = {
                    "prefix": row["prefix"],
                    "suffix": row["suffix"],
                    "prefix_enabled": bool(row["prefix_enabled"]),
                    "suffix_enabled": bool(row["suffix_enabled"]),
                }

            async with db.execute(
                "SELECT * FROM autonick_role WHERE guild_id = ?", (guild_id,)
            ) as cur:
                rows = await cur.fetchall()
            for r in rows:
                entry["roles"][r["role_id"]] = {
                    "prefix": r["prefix"],
                    "suffix": r["suffix"],
                    "prefix_enabled": bool(r["prefix_enabled"]),
                    "suffix_enabled": bool(r["suffix_enabled"]),
                }

        if entry["join"] or entry["roles"]:
            self.cache[guild_id] = entry
        else:
            self.cache.pop(guild_id, None)


    @staticmethod
    def _build_nick(base_name: str, prefix: str, suffix: str) -> str:
        """Construct the new nickname, capped at 32 characters."""
        nick = f"{prefix}{base_name}{suffix}"
        return nick[:32]


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        cfg = self.cache.get(member.guild.id)
        if not cfg or not cfg["join"]:
            return

        join = cfg["join"]
        prefix = join["prefix"] if join["prefix_enabled"] and join["prefix"] else ""
        suffix = join["suffix"] if join["suffix_enabled"] and join["suffix"] else ""

        if not prefix and not suffix:
            return

        new_nick = self._build_nick(member.name, prefix, suffix)
        try:
            await member.edit(nick=new_nick, reason="Synapse AutoNick on join")
        except discord.Forbidden:
            pass


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot:
            return
        if before.roles == after.roles:
            return

        cfg = self.cache.get(after.guild.id)
        if not cfg or not cfg["roles"]:
            return

        added_roles = set(after.roles) - set(before.roles)
        if not added_roles:
            return

        for role in added_roles:
            rcfg = cfg["roles"].get(role.id)
            if not rcfg:
                continue

            prefix = rcfg["prefix"] if rcfg["prefix_enabled"] and rcfg["prefix"] else ""
            suffix = rcfg["suffix"] if rcfg["suffix_enabled"] and rcfg["suffix"] else ""

            if not prefix and not suffix:
                continue

            base = after.nick or after.name
            new_nick = self._build_nick(base, prefix, suffix)
            try:
                await after.edit(nick=new_nick, reason=f"Synapse AutoNick — role {role.name}")
            except discord.Forbidden:
                pass
            break


async def setup(bot):
    await bot.add_cog(AutoNickEvent(bot))
