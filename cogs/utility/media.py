import asyncio
import datetime
import os
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks
from utils.Tools import blacklist_check, ignore_check
from utils.paginators import DescriptionEmbedPaginator
from utils.paginator import Paginator


DB_PATH = os.path.join("database", "media.db")
EMBED_COLOR = 0x2b2d31

LIMIT_NORMAL = 3
LIMIT_PREMIUM = 5

PREMIUM_DB = "database/premium_codes.db"

E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:SynapseExcl:1477234549552320634>"


async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS media_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS media_bypass_users (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS media_bypass_roles (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            """
        )
        await db.commit()


async def _is_premium(guild_id: int) -> bool:
    """Check if a guild currently has valid premium."""
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



def _embed(description: str, color: int = EMBED_COLOR) -> discord.Embed:
    return discord.Embed(description=description, color=color)


def _ok(desc: str) -> discord.Embed:
    return _embed(f"{E_OK} {desc}")


def _err(desc: str) -> discord.Embed:
    return _embed(f"{E_ERR} {desc}")



async def _channel_count(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM media_channels WHERE guild_id=?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def _get_channels(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT channel_id FROM media_channels WHERE guild_id=? ORDER BY channel_id",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def _is_bypassed(guild_id: int, member: discord.Member) -> bool:
    """Return True if the member is on the bypass list (user or any role)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM media_bypass_users WHERE guild_id=? AND user_id=?",
            (guild_id, member.id),
        ) as cur:
            if await cur.fetchone():
                return True
        if member.roles:
            role_ids = tuple(r.id for r in member.roles)
            placeholders = ",".join("?" * len(role_ids))
            async with db.execute(
                f"SELECT 1 FROM media_bypass_roles WHERE guild_id=? AND role_id IN ({placeholders})",
                (guild_id, *role_ids),
            ) as cur:
                if await cur.fetchone():
                    return True
    return False



class Media(commands.Cog):
    """Media-only channel system with bypass lists and premium-aware limits."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._trim_loop.start()

    def cog_unload(self) -> None:
        self._trim_loop.cancel()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_channels WHERE guild_id=? AND channel_id=?",
                (guild_id, channel_id),
            ) as cur:
                is_media = await cur.fetchone()

        if not is_media:
            return

        member = message.author
        if not isinstance(member, discord.Member):
            return

        if member.guild_permissions.administrator:
            return

        if await _is_bypassed(guild_id, member):
            return

        has_attachment = bool(message.attachments)
        has_embed_media = any(
            e.type in ("image", "gifv", "video") for e in message.embeds
        )
        has_link = bool(message.content) and (
            "http://" in message.content or "https://" in message.content
        )

        if has_attachment or has_embed_media or has_link:
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            return

        try:
            warn = discord.Embed(
                description=(
                    f"<:IconsDanger:1477315376982397018> This is a **media-only** channel.\n"
                    "Only images, videos, links, or file attachments are allowed here."
                ),
                color=EMBED_COLOR,
            )
            warn.set_footer(text="Synapse - Media System")
            await message.channel.send(f"{member.mention}", embed=warn, delete_after=8)
        except discord.Forbidden:
            pass


    @tasks.loop(minutes=5)
    async def _trim_loop(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id, COUNT(*) FROM media_channels GROUP BY guild_id"
            ) as cur:
                rows = await cur.fetchall()

        for guild_id, count in rows:
            if count > LIMIT_NORMAL and not await _is_premium(guild_id):
                channels = await _get_channels(guild_id)
                excess = channels[LIMIT_NORMAL:]
                async with aiosqlite.connect(DB_PATH) as db:
                    for ch_id in excess:
                        await db.execute(
                            "DELETE FROM media_channels WHERE guild_id=? AND channel_id=?",
                            (guild_id, ch_id),
                        )
                    await db.commit()

    @_trim_loop.before_loop
    async def _before_trim(self) -> None:
        await self.bot.wait_until_ready()


    @commands.group(
        name="media",
        help="Manage media-only channels for this server.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def media(self, ctx: commands.Context) -> None:
        """Show the media help menu when invoked without a subcommand."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @media.command(
        name="add",
        help="Add a text channel to the media-only list.",
        usage="<#channel>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def media_add(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Add a text channel to the media-only list."""
        guild_id = ctx.guild.id
        is_premium = await _is_premium(guild_id)
        limit = LIMIT_PREMIUM if is_premium else LIMIT_NORMAL
        count = await _channel_count(guild_id)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_channels WHERE guild_id=? AND channel_id=?",
                (guild_id, channel.id),
            ) as cur:
                already = await cur.fetchone()

        if already:
            return await ctx.send(embed=_err(f"{channel.mention} is already a media-only channel."))

        if count >= limit:
            tip = (
                f" Upgrade to **Premium** for up to **{LIMIT_PREMIUM}** channels."
                if not is_premium else ""
            )
            return await ctx.send(embed=_err(f"You have reached the maximum of **{limit}** media channels.{tip}"))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO media_channels (guild_id, channel_id) VALUES (?, ?)",
                (guild_id, channel.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{channel.mention} is now a **media-only** channel. `[{count + 1}/{limit}]`"))


    @media.command(
        name="remove",
        aliases=["delete", "rm"],
        help="Remove a channel from the media-only list.",
        usage="<#channel>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def media_remove(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Remove a channel from the media-only list."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_channels WHERE guild_id=? AND channel_id=?",
                (guild_id, channel.id),
            ) as cur:
                exists = await cur.fetchone()

        if not exists:
            return await ctx.send(embed=_err(f"{channel.mention} is not a media-only channel."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM media_channels WHERE guild_id=? AND channel_id=?",
                (guild_id, channel.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{channel.mention} is no longer a media-only channel."))


    @media.command(
        name="list",
        aliases=["show", "all"],
        help="List all media-only channels for this guild.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def media_list(self, ctx: commands.Context) -> None:
        """List all media-only channels for this guild."""
        guild_id = ctx.guild.id
        channel_ids = await _get_channels(guild_id)

        if not channel_ids:
            return await ctx.send(embed=_embed("No media-only channels have been configured yet."))

        is_premium = await _is_premium(guild_id)
        limit = LIMIT_PREMIUM if is_premium else LIMIT_NORMAL

        lines = []
        for idx, cid in enumerate(channel_ids, 1):
            lines.append(f"**`{idx}`.** <#{cid}>")

        source = DescriptionEmbedPaginator(
            lines,
            title=f"Media Channels [{len(channel_ids)}/{limit}]",
            per_page=10
        )
        paginator = Paginator(source, ctx=ctx)
        await paginator.paginate()


    @media.group(
        name="bypass",
        help="Manage the media channel bypass list (users and roles).",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def media_bypass(self, ctx: commands.Context) -> None:
        """Show bypass sub-commands help."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @media_bypass.group(
        name="user",
        help="Manage user bypasses for media channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def bypass_user(self, ctx: commands.Context) -> None:
        """Show user bypass sub-commands help."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @bypass_user.command(
        name="add",
        help="Add a user to the media channel bypass list.",
        usage="<@user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_user_add(self, ctx: commands.Context, member: discord.Member) -> None:
        """Add a user to the media bypass list."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass_users WHERE guild_id=? AND user_id=?",
                (guild_id, member.id),
            ) as cur:
                exists = await cur.fetchone()

        if exists:
            return await ctx.send(embed=_err(f"{member.mention} is already on the media bypass list."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO media_bypass_users (guild_id, user_id) VALUES (?, ?)",
                (guild_id, member.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{member.mention} can now post freely in media-only channels."))


    @bypass_user.command(
        name="remove",
        aliases=["delete", "rm"],
        help="Remove a user from the media channel bypass list.",
        usage="<@user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_user_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        """Remove a user from the media bypass list."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass_users WHERE guild_id=? AND user_id=?",
                (guild_id, member.id),
            ) as cur:
                exists = await cur.fetchone()

        if not exists:
            return await ctx.send(embed=_err(f"{member.mention} is not on the media bypass list."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM media_bypass_users WHERE guild_id=? AND user_id=?",
                (guild_id, member.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{member.mention} has been removed from the media bypass list."))


    @bypass_user.command(
        name="list",
        aliases=["show"],
        help="List all users on the media channel bypass list.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_user_list(self, ctx: commands.Context) -> None:
        """List all bypassed users."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM media_bypass_users WHERE guild_id=? ORDER BY user_id",
                (guild_id,),
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=_embed("No users are on the media bypass list."))

        lines = []
        for idx, r in enumerate(rows, 1):
            lines.append(f"**`{idx}`.** <@{r[0]}>")

        source = DescriptionEmbedPaginator(
            lines,
            title=f"Bypassed Users [{len(rows)}]",
            per_page=10
        )
        paginator = Paginator(source, ctx=ctx)
        await paginator.paginate()


    @media_bypass.group(
        name="role",
        help="Manage role bypasses for media channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def bypass_role(self, ctx: commands.Context) -> None:
        """Show role bypass sub-commands help."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @bypass_role.command(
        name="add",
        help="Add a role to the media channel bypass list.",
        usage="<@role>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_role_add(self, ctx: commands.Context, role: discord.Role) -> None:
        """Add a role to the media bypass list."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass_roles WHERE guild_id=? AND role_id=?",
                (guild_id, role.id),
            ) as cur:
                exists = await cur.fetchone()

        if exists:
            return await ctx.send(embed=_err(f"{role.mention} is already on the media bypass list."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO media_bypass_roles (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{role.mention} members can now post freely in media-only channels."))


    @bypass_role.command(
        name="remove",
        aliases=["delete", "rm"],
        help="Remove a role from the media channel bypass list.",
        usage="<@role>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_role_remove(self, ctx: commands.Context, role: discord.Role) -> None:
        """Remove a role from the media bypass list."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass_roles WHERE guild_id=? AND role_id=?",
                (guild_id, role.id),
            ) as cur:
                exists = await cur.fetchone()

        if not exists:
            return await ctx.send(embed=_err(f"{role.mention} is not on the media bypass list."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM media_bypass_roles WHERE guild_id=? AND role_id=?",
                (guild_id, role.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"{role.mention} has been removed from the media bypass list."))


    @bypass_role.command(
        name="list",
        aliases=["show"],
        help="List all roles on the media channel bypass list.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_role_list(self, ctx: commands.Context) -> None:
        """List all bypassed roles."""
        guild_id = ctx.guild.id

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM media_bypass_roles WHERE guild_id=? ORDER BY role_id",
                (guild_id,),
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=_embed("No roles are on the media bypass list."))

        lines = []
        for idx, r in enumerate(rows, 1):
            lines.append(f"**`{idx}`.** <@&{r[0]}>")

        source = DescriptionEmbedPaginator(
            lines,
            title=f"Bypassed Roles [{len(rows)}]",
            per_page=10
        )
        paginator = Paginator(source, ctx=ctx)
        await paginator.paginate()


    @commands.command(
        name="mediaa",
        help="View the current media configuration for this server.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mediaa(self, ctx: commands.Context) -> None:
        """Display the full media configuration for this guild."""
        guild_id = ctx.guild.id
        is_premium = await _is_premium(guild_id)
        limit = LIMIT_PREMIUM if is_premium else LIMIT_NORMAL

        channel_ids = await _get_channels(guild_id)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM media_bypass_users WHERE guild_id=?", (guild_id,)
            ) as cur:
                bypass_users = await cur.fetchall()
            async with db.execute(
                "SELECT role_id FROM media_bypass_roles WHERE guild_id=?", (guild_id,)
            ) as cur:
                bypass_roles = await cur.fetchall()

        embed = discord.Embed(
            description=(
                f"**Premium:** {'✅ Active' if is_premium else '❌ Inactive'} · "
                f"**Channel Limit:** {limit}"
            ),
            color=EMBED_COLOR,
        )
        embed.set_author(
            name=f"{ctx.guild.name} — Media Configuration",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )

        if channel_ids:
            embed.add_field(
                name=f"<:emoji_1769867605256:1467155817726873650> Media Channels [{len(channel_ids)}/{limit}]",
                value="\n".join(f"> <#{cid}>" for cid in channel_ids),
                inline=False,
            )
        else:
            embed.add_field(
                name="<:emoji_1769867589372:1467155751456735326> Media Channels [0]",
                value="> None configured.",
                inline=False,
            )

        bu_val = (
            "\n".join(f"> <@{r[0]}>" for r in bypass_users[:15])
            + (f"\n> *...and {len(bypass_users) - 15} more*" if len(bypass_users) > 15 else "")
            if bypass_users else "> None."
        )
        embed.add_field(
            name=f"Bypassed Users [{len(bypass_users)}]",
            value=bu_val,
            inline=True,
        )

        br_val = (
            "\n".join(f"> <@&{r[0]}>" for r in bypass_roles[:15])
            + (f"\n> *...and {len(bypass_roles) - 15} more*" if len(bypass_roles) > 15 else "")
            if bypass_roles else "> None."
        )
        embed.add_field(
            name=f"Bypassed Roles [{len(bypass_roles)}]",
            value=br_val,
            inline=True,
        )

        embed.set_footer(text="Synapse - Media System")
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.send(embed=embed)





async def setup(bot: commands.Bot) -> None:
    await _init_db()
    await bot.add_cog(Media(bot))
