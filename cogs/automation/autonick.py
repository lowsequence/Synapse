import os
import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check

DB_PATH     = os.path.join("database", "autonick.db")
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:SynapseExcl:1477234549552320634>"



async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS autonick_join (
                guild_id INTEGER PRIMARY KEY,
                prefix   TEXT    DEFAULT '',
                suffix   TEXT    DEFAULT '',
                prefix_enabled INTEGER DEFAULT 0,
                suffix_enabled INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS autonick_role (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                prefix   TEXT    DEFAULT '',
                suffix   TEXT    DEFAULT '',
                prefix_enabled INTEGER DEFAULT 0,
                suffix_enabled INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, role_id)
            );
            """
        )
        await db.commit()



def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {desc}", color=0x4dff94)

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)



async def _get_join_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT prefix, suffix, prefix_enabled, suffix_enabled FROM autonick_join WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "prefix": row["prefix"],
        "suffix": row["suffix"],
        "prefix_enabled": bool(row["prefix_enabled"]),
        "suffix_enabled": bool(row["suffix_enabled"]),
    }


async def _ensure_join_row(guild_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO autonick_join (guild_id) VALUES (?)",
            (guild_id,),
        )
        await db.commit()


async def _update_join(guild_id: int, **kwargs) -> None:
    await _ensure_join_row(guild_id)
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [guild_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE autonick_join SET {sets} WHERE guild_id = ?", vals
        )
        await db.commit()


async def _delete_join(guild_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM autonick_join WHERE guild_id = ?", (guild_id,))
        await db.commit()



async def _get_role_config(guild_id: int, role_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT prefix, suffix, prefix_enabled, suffix_enabled "
            "FROM autonick_role WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "prefix": row["prefix"],
        "suffix": row["suffix"],
        "prefix_enabled": bool(row["prefix_enabled"]),
        "suffix_enabled": bool(row["suffix_enabled"]),
    }


async def _get_all_role_configs(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role_id, prefix, suffix, prefix_enabled, suffix_enabled "
            "FROM autonick_role WHERE guild_id = ? ORDER BY role_id",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "role_id": r["role_id"],
            "prefix": r["prefix"],
            "suffix": r["suffix"],
            "prefix_enabled": bool(r["prefix_enabled"]),
            "suffix_enabled": bool(r["suffix_enabled"]),
        }
        for r in rows
    ]


async def _ensure_role_row(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO autonick_role (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await db.commit()


async def _update_role(guild_id: int, role_id: int, **kwargs) -> None:
    await _ensure_role_row(guild_id, role_id)
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [guild_id, role_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE autonick_role SET {sets} WHERE guild_id = ? AND role_id = ?", vals
        )
        await db.commit()


async def _delete_role(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM autonick_role WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await db.commit()


async def _delete_all_roles(guild_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM autonick_role WHERE guild_id = ?", (guild_id,))
        await db.commit()


def _invalidate_cache(bot, guild_id: int) -> None:
    """Tell the event cog to reload its cache for this guild."""
    cog = bot.get_cog("AutoNickEvent")
    if cog:
        bot.loop.create_task(cog.reload_guild(guild_id))



class AutoNickCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def send_error(self, ctx, error_message):
        embed = discord.Embed(description=f"{E_ERR} {error_message}", color=0x2b2d31)
        await ctx.send(embed=embed)


    @commands.command(name="autonick")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autonick(self, ctx, member: discord.Member, *, nickname: str):
        """Manually set a member's nickname."""
        try:
            if member.id == ctx.guild.owner_id:
                return await ctx.send(embed=_err("I cannot change the **server owner's** nickname."))
            if member.top_role >= ctx.guild.me.top_role:
                return await ctx.send(embed=_err(f"{member.mention}'s highest role is **above or equal** to mine. I can't change their nickname."))
            if member.id == ctx.guild.me.id:
                return await ctx.send(embed=_err("I cannot change my own nickname through this command."))
            if len(nickname) > 32:
                return await ctx.send(embed=_err("Nickname must be **32 characters** or fewer."))
            try:
                await member.edit(nick=nickname, reason=f"AutoNick by {ctx.author}")
                await ctx.send(embed=_ok(f"{member.mention}'s nickname has been set to **{nickname}**."))
            except discord.Forbidden:
                await ctx.send(embed=_err(f"I don't have permission to change {member.mention}'s nickname."))
            except discord.HTTPException as e:
                await self.send_error(ctx, f"Failed to change nickname: `{e}`")
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @commands.group(name="autonickjoin", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autonickjoin(self, ctx):
        """Auto-apply prefix/suffix to nicknames on join."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @autonickjoin.command(name="view")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_view(self, ctx):
        """Show the current autonickjoin configuration."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or (not cfg["prefix"] and not cfg["suffix"]):
                return await ctx.send(embed=_err("No join autonick configured. Use `autonickjoin prefix add` or `autonickjoin suffix add`."))

            p_status = "Enabled" if cfg["prefix_enabled"] else "Disabled"
            s_status = "Enabled" if cfg["suffix_enabled"] else "Disabled"
            p_text = f"`{cfg['prefix']}`" if cfg["prefix"] else "`None`"
            s_text = f"`{cfg['suffix']}`" if cfg["suffix"] else "`None`"

            embed = discord.Embed(
                description=(
                    f"**AutoNick Join Configuration**\n\n"
                    f"- **Prefix:** {p_text} — {p_status}\n"
                    f"- **Suffix:** {s_text} — {s_status}"
                ),
                color=EMBED_COLOR,
            )
            embed.set_author(
                name=f"{ctx.guild.name} — AutoNick Join",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            embed.set_footer(text="Synapse - AutoNick System")
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickjoin.command(name="resetall")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_resetall(self, ctx):
        """Clear all join autonick configuration."""
        try:
            await _delete_join(ctx.guild.id)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("All **join autonick** configuration has been reset."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickjoin.group(name="prefix", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_prefix(self, ctx):
        """Manage the join nickname prefix."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @join_prefix.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_prefix_add(self, ctx, *, text: str):
        """Set the join nickname prefix."""
        try:
            if len(text) > 20:
                return await ctx.send(embed=_err("Prefix must be **20 characters** or fewer."))
            cfg = await _get_join_config(ctx.guild.id)
            if cfg and cfg["prefix"] == text:
                return await ctx.send(embed=_err(f"Join prefix is already set to `{text}`."))
            await _update_join(ctx.guild.id, prefix=text, prefix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Join prefix set to `{text}` and **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_prefix.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_prefix_reset(self, ctx):
        """Clear the join nickname prefix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["prefix"]:
                return await ctx.send(embed=_err("No join prefix is currently set."))
            await _update_join(ctx.guild.id, prefix="", prefix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("Join prefix has been **reset**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_prefix.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_prefix_enable(self, ctx):
        """Enable the join nickname prefix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["prefix"]:
                return await ctx.send(embed=_err("No prefix is set. Use `autonickjoin prefix add <text>` first."))
            if cfg["prefix_enabled"]:
                return await ctx.send(embed=_err("Join prefix is already **enabled**."))
            await _update_join(ctx.guild.id, prefix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Join prefix `{cfg['prefix']}` has been **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_prefix.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_prefix_disable(self, ctx):
        """Disable the join nickname prefix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["prefix_enabled"]:
                return await ctx.send(embed=_err("Join prefix is already **disabled**."))
            await _update_join(ctx.guild.id, prefix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("Join prefix has been **disabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickjoin.group(name="suffix", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_suffix(self, ctx):
        """Manage the join nickname suffix."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @join_suffix.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_suffix_add(self, ctx, *, text: str):
        """Set the join nickname suffix."""
        try:
            if len(text) > 20:
                return await ctx.send(embed=_err("Suffix must be **20 characters** or fewer."))
            cfg = await _get_join_config(ctx.guild.id)
            if cfg and cfg["suffix"] == text:
                return await ctx.send(embed=_err(f"Join suffix is already set to `{text}`."))
            await _update_join(ctx.guild.id, suffix=text, suffix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Join suffix set to `{text}` and **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_suffix.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_suffix_reset(self, ctx):
        """Clear the join nickname suffix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["suffix"]:
                return await ctx.send(embed=_err("No join suffix is currently set."))
            await _update_join(ctx.guild.id, suffix="", suffix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("Join suffix has been **reset**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_suffix.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_suffix_enable(self, ctx):
        """Enable the join nickname suffix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["suffix"]:
                return await ctx.send(embed=_err("No suffix is set. Use `autonickjoin suffix add <text>` first."))
            if cfg["suffix_enabled"]:
                return await ctx.send(embed=_err("Join suffix is already **enabled**."))
            await _update_join(ctx.guild.id, suffix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Join suffix `{cfg['suffix']}` has been **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @join_suffix.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def join_suffix_disable(self, ctx):
        """Disable the join nickname suffix."""
        try:
            cfg = await _get_join_config(ctx.guild.id)
            if not cfg or not cfg["suffix_enabled"]:
                return await ctx.send(embed=_err("Join suffix is already **disabled**."))
            await _update_join(ctx.guild.id, suffix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("Join suffix has been **disabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @commands.group(name="autonickrole", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def autonickrole(self, ctx):
        """Auto-apply prefix/suffix when a member gains a role."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @autonickrole.command(name="list")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_list(self, ctx):
        """List all configured role autonick entries."""
        try:
            configs = await _get_all_role_configs(ctx.guild.id)
            if not configs:
                return await ctx.send(embed=_err("No role autonicks configured. Use `autonickrole prefix add` or `autonickrole suffix add`."))

            lines = []
            for c in configs:
                p_text = f"`{c['prefix']}`" if c["prefix"] else "`—`"
                s_text = f"`{c['suffix']}`" if c["suffix"] else "`—`"
                p_st = "✓" if c["prefix_enabled"] else "✗"
                s_st = "✓" if c["suffix_enabled"] else "✗"
                lines.append(f"> <@&{c['role_id']}> — Prefix: {p_text} [{p_st}] | Suffix: {s_text} [{s_st}]")

            embed = discord.Embed(
                description=f"**AutoNick Role Configuration**\n\n" + "\n".join(lines),
                color=EMBED_COLOR,
            )
            embed.set_author(
                name=f"{ctx.guild.name} — AutoNick Role",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            embed.set_footer(text="Synapse - AutoNick System")
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickrole.command(name="resetall")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_resetall(self, ctx):
        """Clear all role autonick configuration."""
        try:
            await _delete_all_roles(ctx.guild.id)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok("All **role autonick** configuration has been reset."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickrole.group(name="prefix", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_prefix(self, ctx):
        """Manage role-based nickname prefixes."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @role_prefix.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_prefix_add(self, ctx, role: discord.Role, *, text: str):
        """Set a nickname prefix for a specific role."""
        try:
            if role.is_default():
                return await ctx.send(embed=_err("You cannot set a prefix for the **@everyone** role."))
            if len(text) > 20:
                return await ctx.send(embed=_err("Prefix must be **20 characters** or fewer."))
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if cfg and cfg["prefix"] == text:
                return await ctx.send(embed=_err(f"Prefix for {role.mention} is already set to `{text}`."))
            await _update_role(ctx.guild.id, role.id, prefix=text, prefix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Prefix for {role.mention} set to `{text}` and **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_prefix.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_prefix_reset(self, ctx, role: discord.Role):
        """Clear the nickname prefix for a role."""
        try:
            await _update_role(ctx.guild.id, role.id, prefix="", prefix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Prefix for {role.mention} has been **reset**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_prefix.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_prefix_enable(self, ctx, role: discord.Role):
        """Enable the nickname prefix for a role."""
        try:
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if not cfg or not cfg["prefix"]:
                return await ctx.send(embed=_err(f"No prefix set for {role.mention}. Use `autonickrole prefix add` first."))
            if cfg["prefix_enabled"]:
                return await ctx.send(embed=_err(f"Prefix for {role.mention} is already **enabled**."))
            await _update_role(ctx.guild.id, role.id, prefix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Prefix for {role.mention} has been **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_prefix.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_prefix_disable(self, ctx, role: discord.Role):
        """Disable the nickname prefix for a role."""
        try:
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if not cfg or not cfg["prefix_enabled"]:
                return await ctx.send(embed=_err(f"Prefix for {role.mention} is already **disabled**."))
            await _update_role(ctx.guild.id, role.id, prefix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Prefix for {role.mention} has been **disabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @autonickrole.group(name="suffix", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_suffix(self, ctx):
        """Manage role-based nickname suffixes."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @role_suffix.command(name="add")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_suffix_add(self, ctx, role: discord.Role, *, text: str):
        """Set a nickname suffix for a specific role."""
        try:
            if role.is_default():
                return await ctx.send(embed=_err("You cannot set a suffix for the **@everyone** role."))
            if len(text) > 20:
                return await ctx.send(embed=_err("Suffix must be **20 characters** or fewer."))
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if cfg and cfg["suffix"] == text:
                return await ctx.send(embed=_err(f"Suffix for {role.mention} is already set to `{text}`."))
            await _update_role(ctx.guild.id, role.id, suffix=text, suffix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Suffix for {role.mention} set to `{text}` and **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_suffix.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_suffix_reset(self, ctx, role: discord.Role):
        """Clear the nickname suffix for a role."""
        try:
            await _update_role(ctx.guild.id, role.id, suffix="", suffix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Suffix for {role.mention} has been **reset**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_suffix.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_suffix_enable(self, ctx, role: discord.Role):
        """Enable the nickname suffix for a role."""
        try:
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if not cfg or not cfg["suffix"]:
                return await ctx.send(embed=_err(f"No suffix set for {role.mention}. Use `autonickrole suffix add` first."))
            if cfg["suffix_enabled"]:
                return await ctx.send(embed=_err(f"Suffix for {role.mention} is already **enabled**."))
            await _update_role(ctx.guild.id, role.id, suffix_enabled=1)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Suffix for {role.mention} has been **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @role_suffix.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def role_suffix_disable(self, ctx, role: discord.Role):
        """Disable the nickname suffix for a role."""
        try:
            cfg = await _get_role_config(ctx.guild.id, role.id)
            if not cfg or not cfg["suffix_enabled"]:
                return await ctx.send(embed=_err(f"Suffix for {role.mention} is already **disabled**."))
            await _update_role(ctx.guild.id, role.id, suffix_enabled=0)
            _invalidate_cache(self.bot, ctx.guild.id)
            await ctx.send(embed=_ok(f"Suffix for {role.mention} has been **disabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


async def setup(bot):
    await _init_db()
    await bot.add_cog(AutoNickCommands(bot))
