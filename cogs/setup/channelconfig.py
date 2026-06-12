from __future__ import annotations
import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import blacklist_check, ignore_check
from utils import Paginator, DescriptionEmbedPaginator

DB_PATH = "database/channelconfig.db"
COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:SynapseExcl:1477234549552320634>"


async def _init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS antibot_channels ("
            "  guild_id    INTEGER NOT NULL,"
            "  channel_id  INTEGER NOT NULL,"
            "  log_channel_id INTEGER,"
            "  PRIMARY KEY (guild_id, channel_id)"
            ")"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS chatban_users ("
            "  guild_id   INTEGER NOT NULL,"
            "  channel_id INTEGER NOT NULL,"
            "  user_id    INTEGER NOT NULL,"
            "  PRIMARY KEY (guild_id, channel_id, user_id)"
            ")"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS reactban_users ("
            "  guild_id   INTEGER NOT NULL,"
            "  channel_id INTEGER NOT NULL,"
            "  user_id    INTEGER NOT NULL,"
            "  PRIMARY KEY (guild_id, channel_id, user_id)"
            ")"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS vcban_users ("
            "  guild_id   INTEGER NOT NULL,"
            "  channel_id INTEGER NOT NULL,"
            "  user_id    INTEGER NOT NULL,"
            "  PRIMARY KEY (guild_id, channel_id, user_id)"
            ")"
        )
        await db.commit()


def _ok(text: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {text}", color=COLOR)

def _err(text: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {text}", color=COLOR)


class ChannelConfig(commands.Cog):
    """Channel-level moderation: antibot, chatban, reactban, vcban."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        bot.loop.create_task(_init_db())

    async def _send_help(self, ctx: commands.Context):
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @commands.group(
        name="antibot",
        help="Manage antibot channels — delete bot messages automatically.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def antibot(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @antibot.command(name="add", help="Adds a channel to the antibot list.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def antibot_add(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM antibot_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            if await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{channel.mention} is already an antibot channel."),
                    mention_author=False,
                )
            await db.execute(
                "INSERT INTO antibot_channels (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully added {channel.mention} to the antibot list.")
        )

    @antibot.command(name="remove", help="Removes a channel from the antibot list.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def antibot_remove(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM antibot_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{channel.mention} is not in the antibot list."),
                    mention_author=False,
                )
            await db.execute(
                "DELETE FROM antibot_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully removed {channel.mention} from the antibot list.")
        )

    @antibot.command(name="config", help="Shows all antibot channels and their log channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def antibot_config(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT channel_id, log_channel_id FROM antibot_channels WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(
                embed=_err("No antibot channels configured in this server."),
                mention_author=False,
            )
        entries = []
        for idx, (ch_id, log_id) in enumerate(rows, 1):
            ch = ctx.guild.get_channel(ch_id)
            ch_text = ch.mention if ch else f"Channel ID {ch_id}"
            log_ch = ctx.guild.get_channel(log_id) if log_id else None
            log_text = log_ch.mention if log_ch else "Not set"
            entries.append(f"`{idx}.` {ch_text} — Log: {log_text}")
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Antibot Channels — {len(entries)}",
                per_page=10,
            ),
            ctx=ctx,
        )
        await paginator.paginate()

    @antibot.group(
        name="log",
        help="Manage antibot log channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    async def antibot_log(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @antibot_log.command(name="set", help="Sets a log channel for antibot events in a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def antibot_log_set(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        log_channel: discord.TextChannel,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM antibot_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{channel.mention} is not an antibot channel. Add it first with `antibot add`."),
                    mention_author=False,
                )
            await db.execute(
                "UPDATE antibot_channels SET log_channel_id = ? WHERE guild_id = ? AND channel_id = ?",
                (log_channel.id, ctx.guild.id, channel.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Log channel for {channel.mention} set to {log_channel.mention}.")
        )

    @antibot_log.command(name="remove", help="Removes the log channel for an antibot channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def antibot_log_remove(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT log_channel_id FROM antibot_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            row = await cur.fetchone()
            if not row:
                return await ctx.reply(
                    embed=_err(f"{channel.mention} is not an antibot channel."),
                    mention_author=False,
                )
            if row[0] is None:
                return await ctx.reply(
                    embed=_err(f"{channel.mention} has no log channel set."),
                    mention_author=False,
                )
            await db.execute(
                "UPDATE antibot_channels SET log_channel_id = NULL WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Removed the log channel for {channel.mention}.")
        )


    @commands.group(
        name="chatban",
        help="Ban users from chatting in specific channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def chatban(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @chatban.command(name="add", help="Bans a user from chatting in a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def chatban_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM chatban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is already chatbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "INSERT INTO chatban_users (guild_id, channel_id, user_id) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully chatbanned {user.mention} in {channel.mention}.")
        )

    @chatban.command(name="remove", help="Removes a user's chatban from a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def chatban_remove(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM chatban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is not chatbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "DELETE FROM chatban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully removed {user.mention}'s chatban from {channel.mention}.")
        )

    @chatban.command(name="list", help="Lists chatbanned users in a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def chatban_list(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id FROM chatban_users WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(
                embed=_err(f"No users are chatbanned in {channel.mention}."),
                mention_author=False,
            )
        entries = []
        for idx, (uid,) in enumerate(rows, 1):
            member = ctx.guild.get_member(uid)
            entries.append(f"`{idx}.` {member.mention if member else f'User ID {uid}'}")
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Chatbanned Users in #{channel.name} — {len(entries)}",
                per_page=10,
            ),
            ctx=ctx,
        )
        await paginator.paginate()


    @commands.group(
        name="reactban",
        help="Ban users from reacting in specific channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def reactban(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @reactban.command(name="add", help="Bans a user from reacting in a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def reactban_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM reactban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is already reactbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "INSERT INTO reactban_users (guild_id, channel_id, user_id) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully reactbanned {user.mention} in {channel.mention}.")
        )

    @reactban.command(name="remove", help="Removes a user's reactban from a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def reactban_remove(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM reactban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is not reactbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "DELETE FROM reactban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully removed {user.mention}'s reactban from {channel.mention}.")
        )

    @reactban.command(name="list", help="Lists reactbanned users in a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def reactban_list(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id FROM reactban_users WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(
                embed=_err(f"No users are reactbanned in {channel.mention}."),
                mention_author=False,
            )
        entries = []
        for idx, (uid,) in enumerate(rows, 1):
            member = ctx.guild.get_member(uid)
            entries.append(f"`{idx}.` {member.mention if member else f'User ID {uid}'}")
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Reactbanned Users in #{channel.name} — {len(entries)}",
                per_page=10,
            ),
            ctx=ctx,
        )
        await paginator.paginate()


    @commands.group(
        name="vcban",
        help="Ban users from joining specific voice channels.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def vcban(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @vcban.command(name="add", help="Bans a user from joining a voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vcban_add(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM vcban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is already vcbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "INSERT INTO vcban_users (guild_id, channel_id, user_id) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully vcbanned {user.mention} in {channel.mention}.")
        )

    @vcban.command(name="remove", help="Removes a user's vcban from a voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vcban_remove(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
        user: discord.Member,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM vcban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err(f"{user.mention} is not vcbanned in {channel.mention}."),
                    mention_author=False,
                )
            await db.execute(
                "DELETE FROM vcban_users WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (ctx.guild.id, channel.id, user.id),
            )
            await db.commit()
        await ctx.reply(
            embed=_ok(f"Successfully removed {user.mention}'s vcban from {channel.mention}.")
        )

    @vcban.command(name="list", help="Lists vcbanned users in a voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vcban_list(
        self, ctx: commands.Context, channel: discord.VoiceChannel
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id FROM vcban_users WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id),
            )
            rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(
                embed=_err(f"No users are vcbanned in {channel.mention}."),
                mention_author=False,
            )
        entries = []
        for idx, (uid,) in enumerate(rows, 1):
            member = ctx.guild.get_member(uid)
            entries.append(f"`{idx}.` {member.mention if member else f'User ID {uid}'}")
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"VCBanned Users in #{channel.name} — {len(entries)}",
                per_page=10,
            ),
            ctx=ctx,
        )
        await paginator.paginate()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.id == self.bot.user.id:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id

        async with aiosqlite.connect(DB_PATH) as db:
            if message.author.bot:
                cur = await db.execute(
                    "SELECT log_channel_id FROM antibot_channels "
                    "WHERE guild_id = ? AND channel_id = ?",
                    (guild_id, channel_id),
                )
                row = await cur.fetchone()
                if row is not None:
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass
                    log_id = row[0]
                    if log_id:
                        log_ch = message.guild.get_channel(log_id)
                        if log_ch:
                            embed = discord.Embed(
                                description=(
                                    f"**Antibot** — Deleted a message from "
                                    f"{message.author.mention} in "
                                    f"{message.channel.mention}"
                                ),
                                color=COLOR,
                            )
                            embed.set_footer(text=f"Bot ID: {message.author.id}")
                            try:
                                await log_ch.send(embed=embed)
                            except discord.Forbidden:
                                pass
                return

            cur = await db.execute(
                "SELECT 1 FROM chatban_users "
                "WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (guild_id, channel_id, message.author.id),
            )
            if await cur.fetchone():
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.Member | discord.User
    ):
        if not reaction.message.guild or user.bot:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM reactban_users "
                "WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (reaction.message.guild.id, reaction.message.channel.id, user.id),
            )
            if await cur.fetchone():
                try:
                    await reaction.remove(user)
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot or after.channel is None:
            return
        if before.channel == after.channel:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM vcban_users "
                "WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
                (member.guild.id, after.channel.id, member.id),
            )
            if await cur.fetchone():
                try:
                    await member.move_to(None, reason="VCBan — user is banned from this voice channel.")
                except discord.Forbidden:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelConfig(bot))
