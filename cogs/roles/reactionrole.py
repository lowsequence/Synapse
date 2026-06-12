import discord
from discord.ext import commands
import aiosqlite
from typing import Union
from utils import Paginator, DescriptionEmbedPaginator
from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/reactionrole.db"


def _ok(description: str, title: str = "") -> discord.Embed:
    embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | {description}", color=0x4dff94)
    if title:
        embed.title = title
    return embed

def _err(description: str, title: str = "") -> discord.Embed:
    embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | {description}", color=0xff4646)
    if title:
        embed.title = title
    return embed

def _info(description: str, title: str = "") -> discord.Embed:
    embed = discord.Embed(description=description, color=0x313338)
    if title:
        embed.title = title
    return embed


class ReactionRoles(commands.Cog, name="ReactionRoles"):
    """Advanced Reaction Role system using traditional message reactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.init_db())

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    PRIMARY KEY (message_id, emoji)
                )
            ''')
            await db.commit()


    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def rr(self, ctx: commands.Context):
        """Manage traditional reaction roles for the server."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            await help_cog.send_group_help_auto(ctx, ctx.command)
        else:
            await ctx.send_help(ctx.command)

    @rr.command(name="add", help="Add a reaction role to an existing message.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def rr_add(self, ctx: commands.Context, message_id: int, emoji: Union[discord.Emoji, discord.PartialEmoji, str], role: discord.Role, channel: Union[discord.TextChannel, discord.Thread] = None):
        """Add a reaction role to a message."""

        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=_err("I cannot assign a role higher than or equal to my own top role."))
        if role.position >= ctx.author.top_role.position and ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply(embed=_err("You cannot manage a role higher than or equal to your own top role."))

        emoji_str = str(emoji)
        target_channel = channel or ctx.channel

        try:
            message = await target_channel.fetch_message(message_id)
        except discord.NotFound:
            if channel:
                return await ctx.reply(embed=_err(f"Message not found. Please ensure the message ID is correct and is in {channel.mention}."))
            else:
                return await ctx.reply(embed=_err("Message not found. Please run this command in the same channel as the target message or specify the channel."))
        except discord.Forbidden:
            return await ctx.reply(embed=_err("I do not have permission to fetch that message."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji_str)) as cursor:
                if await cursor.fetchone():
                    return await ctx.reply(embed=_err(f"A reaction role for {emoji_str} already exists on that message!"))

            await db.execute(
                "INSERT INTO reaction_roles (message_id, guild_id, channel_id, emoji, role_id) VALUES (?, ?, ?, ?, ?)",
                (message_id, ctx.guild.id, target_channel.id, emoji_str, role.id)
            )
            await db.commit()

        try:
            await message.add_reaction(emoji)
        except discord.Forbidden:
            return await ctx.reply(embed=_err("I successfully saved the reaction role, but I lack permissions to add the reaction to the message."))
        except discord.HTTPException:
            pass

        await ctx.reply(embed=_ok(f"Successfully added {emoji_str} for {role.mention} on [this message]({message.jump_url})."))

    @rr.command(name="remove", help="Remove a reaction role from a message.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def rr_remove(self, ctx: commands.Context, message_id: int, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Remove a reaction role from a message."""
        emoji_str = str(emoji)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji_str)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply(embed=_err("No matching reaction role found for that message and emoji."))

            await db.execute("DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji_str))
            await db.commit()

        try:
            message = await ctx.channel.fetch_message(message_id)
            await message.remove_reaction(emoji, ctx.guild.me)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        await ctx.reply(embed=_ok(f"Successfully removed the {emoji_str} reaction role from the message ID `{message_id}`."))

    @rr.command(name="list", help="List all reaction roles configured in the server.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def rr_list(self, ctx: commands.Context):
        """List all reaction roles for the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT message_id, channel_id, emoji, role_id FROM reaction_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.reply(embed=_err("There are no reaction roles configured for this server."))

        entries = []
        for index, (msg_id, ch_id, emoji, role_id) in enumerate(rows, start=1):
            role_mention = f"<@&{role_id}>"
            channel_mention = f"<#{ch_id}>"
            message_link = f"https://discord.com/channels/{ctx.guild.id}/{ch_id}/{msg_id}"

            entries.append(
                f"**{index}.** {emoji} {role_mention} in {channel_mention}\n"
                f"└ [Jump to Message]({message_link}) (`{msg_id}`)"
            )

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title="Reaction Roles List",
                description="",
                per_page=10,
                color=0x313338
            ),
            ctx=ctx
        )
        await paginator.paginate()


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        if payload.member and payload.member.bot:
            return

        emoji_str = str(payload.emoji)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (payload.message_id, emoji_str)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        role_id = row[0]
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return

        role = guild.get_role(role_id)
        if not role: return

        member = guild.get_member(payload.user_id)
        if not member: return

        try:
            await member.add_roles(role, reason="Reaction Role added.")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return

        emoji_str = str(payload.emoji)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (payload.message_id, emoji_str)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        role_id = row[0]
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return

        role = guild.get_role(role_id)
        if not role: return

        member = guild.get_member(payload.user_id)
        if not member: return
        if member.bot: return

        try:
            await member.remove_roles(role, reason="Reaction Role removed.")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Cleanup reaction roles if message is deleted."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM reaction_roles WHERE message_id = ?", (payload.message_id,))
            await db.commit()

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
