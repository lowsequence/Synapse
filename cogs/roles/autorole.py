import os
import datetime
import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check

DB_PATH     = os.path.join("database", "autorole.db")
PREMIUM_DB  = "database/premium_codes.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:SynapseExcl:1477234549552320634>"

LIMIT_NORMAL  = 5
LIMIT_PREMIUM = 10


# ─────────────────────────────────────────────────────────────────────────────
# DB init
# ─────────────────────────────────────────────────────────────────────────────

async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS autorole_humans (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            CREATE TABLE IF NOT EXISTS autorole_bots (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            """
        )
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Embed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {desc}", color=0x4dff94)

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)



async def _get_roles(guild_id: int, table: str) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT role_id FROM {table} WHERE guild_id = ? ORDER BY role_id",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def _add_role(guild_id: int, role_id: int, table: str) -> bool:
    """Returns False if already exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT 1 FROM {table} WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        ) as cur:
            if await cur.fetchone():
                return False
        await db.execute(
            f"INSERT INTO {table} (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await db.commit()
    return True


async def _remove_role(guild_id: int, role_id: int, table: str) -> bool:
    """Returns False if it didn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT 1 FROM {table} WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        ) as cur:
            if not await cur.fetchone():
                return False
        await db.execute(
            f"DELETE FROM {table} WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await db.commit()
    return True


async def _is_premium(guild_id: int) -> bool:
    if not os.path.exists(PREMIUM_DB):
        return False
    try:
        async with aiosqlite.connect(PREMIUM_DB) as db:
            async with db.execute(
                "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                (guild_id,),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return False
        expires = datetime.datetime.fromisoformat(row[0])
        return expires > datetime.datetime.utcnow()
    except Exception:
        return False


async def _get_limit(guild_id: int) -> int:
    return LIMIT_PREMIUM if await _is_premium(guild_id) else LIMIT_NORMAL


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class AutoRoleCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ═════════════════════════════════════════════════════════════════════════
    # Group: autorole
    # ═════════════════════════════════════════════════════════════════════════

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autorole(self, ctx):
        """Auto-assign roles when members join."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    # ── autorole config ───────────────────────────────────────────────────

    @autorole.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autorole_config(self, ctx):
        """Show the full autorole configuration for this server."""
        h_ids = await _get_roles(ctx.guild.id, "autorole_humans")
        b_ids = await _get_roles(ctx.guild.id, "autorole_bots")
        limit = await _get_limit(ctx.guild.id)

        if not h_ids and not b_ids:
            return await ctx.send(embed=_err("No autoroles configured. Use `autorole humans add` or `autorole bots add`."))

        h_lines = "\n".join(f"> <@&{rid}>" for rid in h_ids) if h_ids else "> None"
        b_lines = "\n".join(f"> <@&{rid}>" for rid in b_ids) if b_ids else "> None"

        embed = discord.Embed(
            description=(
                f"**AutoRole Configuration**\n\n"
                f"**- Human Roles [{len(h_ids)}/{limit}]**\n{h_lines}\n\n"
                f"**- Bot Roles [{len(b_ids)}/{limit}]**\n{b_lines}"
            ),
            color=EMBED_COLOR,
        )
        embed.set_author(
            name=f"{ctx.guild.name} — AutoRole",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text="Synapse - AutoRole System")
        await ctx.send(embed=embed)

    # ═════════════════════════════════════════════════════════════════════════
    # Subgroup: autorole humans
    # ═════════════════════════════════════════════════════════════════════════

    @autorole.group(name="humans", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autorole_humans(self, ctx):
        """Manage autoroles for human members."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @autorole_humans.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def humans_add(self, ctx, role: discord.Role):
        """Add an autorole for humans."""
        current = await _get_roles(ctx.guild.id, "autorole_humans")
        limit   = await _get_limit(ctx.guild.id)
        if len(current) >= limit:
            tip = " Upgrade to **Premium** for up to **10** roles." if limit == LIMIT_NORMAL else ""
            return await ctx.send(embed=_err(f"You can only have **{limit}** human autoroles.{tip}"))

        ok = await _add_role(ctx.guild.id, role.id, "autorole_humans")
        if not ok:
            return await ctx.send(embed=_err(f"{role.mention} is already a human autorole."))

        # Update event cache
        cog = self.bot.get_cog("AutoRoleEvent")
        if cog:
            cog.cache.setdefault(ctx.guild.id, {"humans": [], "bots": []})
            cog.cache[ctx.guild.id]["humans"] = await _get_roles(ctx.guild.id, "autorole_humans")

        await ctx.send(embed=_ok(f"{role.mention} will now be given to **humans** on join. `[{len(current)+1}/{limit}]`"))

    @autorole_humans.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def humans_remove(self, ctx, role: discord.Role):
        """Remove an autorole for humans."""
        ok = await _remove_role(ctx.guild.id, role.id, "autorole_humans")
        if not ok:
            return await ctx.send(embed=_err(f"{role.mention} is not a human autorole."))

        cog = self.bot.get_cog("AutoRoleEvent")
        if cog and ctx.guild.id in cog.cache:
            cog.cache[ctx.guild.id]["humans"] = await _get_roles(ctx.guild.id, "autorole_humans")

        await ctx.send(embed=_ok(f"{role.mention} has been removed from human autoroles."))

    @autorole_humans.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def humans_config(self, ctx):
        """List all configured human autoroles."""
        ids   = await _get_roles(ctx.guild.id, "autorole_humans")
        limit = await _get_limit(ctx.guild.id)
        if not ids:
            return await ctx.send(embed=_err("No human autoroles configured. Use `autorole humans add <@role>`."))

        lines = "\n".join(f"> <@&{rid}>" for rid in ids)
        embed = discord.Embed(
            description=f"- **Human AutoRoles [{len(ids)}/{limit}]**\n{lines}",
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Synapse - AutoRole System")
        await ctx.send(embed=embed)

    # ═════════════════════════════════════════════════════════════════════════
    # Subgroup: autorole bots
    # ═════════════════════════════════════════════════════════════════════════

    @autorole.group(name="bots", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autorole_bots(self, ctx):
        """Manage autoroles for bots."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @autorole_bots.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def bots_add(self, ctx, role: discord.Role):
        """Add an autorole for bots."""
        current = await _get_roles(ctx.guild.id, "autorole_bots")
        limit   = await _get_limit(ctx.guild.id)
        if len(current) >= limit:
            tip = " Upgrade to **Premium** for up to **10** roles." if limit == LIMIT_NORMAL else ""
            return await ctx.send(embed=_err(f"You can only have **{limit}** bot autoroles.{tip}"))

        ok = await _add_role(ctx.guild.id, role.id, "autorole_bots")
        if not ok:
            return await ctx.send(embed=_err(f"{role.mention} is already a bot autorole."))

        cog = self.bot.get_cog("AutoRoleEvent")
        if cog:
            cog.cache.setdefault(ctx.guild.id, {"humans": [], "bots": []})
            cog.cache[ctx.guild.id]["bots"] = await _get_roles(ctx.guild.id, "autorole_bots")

        await ctx.send(embed=_ok(f"{role.mention} will now be given to **bots** on join. `[{len(current)+1}/{limit}]`"))

    @autorole_bots.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def bots_remove(self, ctx, role: discord.Role):
        """Remove an autorole for bots."""
        ok = await _remove_role(ctx.guild.id, role.id, "autorole_bots")
        if not ok:
            return await ctx.send(embed=_err(f"{role.mention} is not a bot autorole."))

        cog = self.bot.get_cog("AutoRoleEvent")
        if cog and ctx.guild.id in cog.cache:
            cog.cache[ctx.guild.id]["bots"] = await _get_roles(ctx.guild.id, "autorole_bots")

        await ctx.send(embed=_ok(f"{role.mention} has been removed from bot autoroles."))

    @autorole_bots.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def bots_config(self, ctx):
        """List all configured bot autoroles."""
        ids   = await _get_roles(ctx.guild.id, "autorole_bots")
        limit = await _get_limit(ctx.guild.id)
        if not ids:
            return await ctx.send(embed=_err("No bot autoroles configured. Use `autorole bots add <@role>`."))

        lines = "\n".join(f"> <@&{rid}>" for rid in ids)
        embed = discord.Embed(
            description=f"- **Bot AutoRoles [{len(ids)}/{limit}]**\n{lines}",
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Synapse - Role System")
        await ctx.send(embed=embed)


async def setup(bot):
    await _init_db()
    await bot.add_cog(AutoRoleCommands(bot))
