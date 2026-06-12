import os
import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check

DB_PATH     = "database/tagroles.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"



async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tag_roles (
                guild_id       INTEGER PRIMARY KEY,
                tag            TEXT    NOT NULL,
                role_id        INTEGER NOT NULL,
                log_channel_id INTEGER NOT NULL,
                mode           TEXT    NOT NULL DEFAULT 'embed',
                enabled        INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        await db.commit()




def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {desc}", color=0x4dff94)

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)



class TagRoleCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def tagrole(self, ctx):
        """Clan tag auto-role system."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @tagrole.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def setup(self, ctx, role: discord.Role, channel: discord.TextChannel):
        """Setup the tagrole system: `tagrole setup <@role> <#channel>`"""
        if not ctx.guild.features or "CLAN" not in ctx.guild.features or getattr(ctx.guild, "clan", None) is None or getattr(ctx.guild.clan, "tag", None) is None:
            return await ctx.send(embed=_err("This server does not have a native Discord Guild Tag set."))
        tag = ctx.guild.clan.tag

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM tag_roles WHERE guild_id = ?", (ctx.guild.id,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                return await ctx.send(embed=_err("TagRole is already configured. Use `tagrole reset` first."))

            await db.execute(
                "INSERT INTO tag_roles (guild_id, tag, role_id, log_channel_id, mode, enabled) "
                "VALUES (?, ?, ?, ?, 'embed', 1)",
                (ctx.guild.id, tag, role.id, channel.id),
            )
            await db.commit()

        cog = self.bot.get_cog("TagRoleEvent")
        if cog:
            cog.cache[ctx.guild.id] = {
                "role_id": role.id,
                "channel_id": channel.id,
                "mode": "embed",
            }

        embed = discord.Embed(
            description=(
                f"{E_OK} **TagRole Setup Complete**\n\n"
                f"> 🏷️ **Guild Tag:** `{tag}`\n"
                f"> 🎭 **Role:** {role.mention}\n"
                f"> 📢 **Channel:** {channel.mention}\n"
                f"> 📋 **Mode:** `embed`"
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Synapse - TagRole System")
        await ctx.send(embed=embed)


    @tagrole.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def config(self, ctx):
        """Shows the current tagrole configuration."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id, log_channel_id, mode, enabled FROM tag_roles WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cur:
                row = await cur.fetchone()

        if not row:
            return await ctx.send(embed=_err("TagRole is not configured. Use `tagrole setup` first."))

        role_id, channel_id, mode, enabled = row
        role    = ctx.guild.get_role(role_id)
        channel = ctx.guild.get_channel(channel_id)
        status  = "✅ Enabled" if enabled else "❌ Disabled"

        tag = ctx.guild.clan.tag if getattr(ctx.guild, "clan", None) and getattr(ctx.guild.clan, "tag", None) else "`No Guild Tag Set`"

        embed = discord.Embed(
            description=(
                f"**TagRole Configuration**\n\n"
                f"> **Tag:** `{tag}`\n"
                f"> **Role:** {role.mention if role else '`deleted`'}\n"
                f"> **Channel:** {channel.mention if channel else '`deleted`'}\n"
                f"> **Mode:** `{mode}`\n"
                f"> **Status:** {status}"
            ),
            color=EMBED_COLOR,
        )
        embed.set_author(
            name=f"{ctx.guild.name} — TagRole",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text="Synapse - TagRole System")
        await ctx.send(embed=embed)


    @tagrole.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def reset(self, ctx):
        """Reset the tagrole configuration."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM tag_roles WHERE guild_id = ?", (ctx.guild.id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.send(embed=_err("TagRole is not configured."))

            await db.execute("DELETE FROM tag_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        cog = self.bot.get_cog("TagRoleEvent")
        if cog and ctx.guild.id in cog.cache:
            del cog.cache[ctx.guild.id]

        await ctx.send(embed=_ok("TagRole configuration has been **reset**."))


    @tagrole.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def toggle(self, ctx, option: str):
        """Enable or disable tagrole: `tagrole toggle <enable/disable>`"""
        option = option.lower()
        if option not in ("enable", "disable"):
            return await ctx.send(embed=_err("Option must be `enable` or `disable`."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM tag_roles WHERE guild_id = ?", (ctx.guild.id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.send(embed=_err("TagRole is not configured. Use `tagrole setup` first."))

            enabled = 1 if option == "enable" else 0
            await db.execute(
                "UPDATE tag_roles SET enabled = ? WHERE guild_id = ?",
                (enabled, ctx.guild.id),
            )
            await db.commit()

        cog = self.bot.get_cog("TagRoleEvent")
        if cog:
            if enabled:
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute(
                        "SELECT role_id, log_channel_id, mode FROM tag_roles WHERE guild_id = ?",
                        (ctx.guild.id,),
                    ) as cur:
                        r = await cur.fetchone()
                    if r:
                        cog.cache[ctx.guild.id] = {
                            "role_id": r[0],
                            "channel_id": r[1],
                            "mode": r[2],
                        }
            else:
                if ctx.guild.id in cog.cache:
                    del cog.cache[ctx.guild.id]

        await ctx.send(embed=_ok(f"TagRole has been **{option}d**."))


    @tagrole.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def mode(self, ctx, mode_type: str):
        """Set notification mode: `tagrole mode <embed/message/image>`"""
        mode_type = mode_type.lower()
        if mode_type not in ("message", "embed", "image"):
            return await ctx.send(embed=_err("Mode must be `message`, `embed`, or `image`."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM tag_roles WHERE guild_id = ?", (ctx.guild.id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.send(embed=_err("TagRole is not configured. Use `tagrole setup` first."))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE tag_roles SET mode = ? WHERE guild_id = ?",
                (mode_type, ctx.guild.id),
            )
            await db.commit()

        cog = self.bot.get_cog("TagRoleEvent")
        if cog and ctx.guild.id in cog.cache:
            cog.cache[ctx.guild.id]["mode"] = mode_type

        await ctx.send(embed=_ok(f"TagRole mode set to **`{mode_type}`**."))


async def setup(bot):
    await _init_db()
    await bot.add_cog(TagRoleCommands(bot))
