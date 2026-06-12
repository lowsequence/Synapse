import discord
from discord.ext import commands
import aiosqlite
import os
from utils.paginators import DescriptionEmbedPaginator
from utils.paginator import Paginator
from utils.Tools import blacklist_check, ignore_check

DB_PATH = os.path.join("database", "messages.db")
COLOR = 0x2b2d31

class MessageTrackCommands(commands.Cog):
    """Advanced premium message tracking commands with security and robust error handling."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.command.name in ["enable", "disable"]:
            return True
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM msg_config WHERE guild_id = ?", (ctx.guild.id,))
            row = await cur.fetchone()
            if not row or row[0] == 0:
                embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Message tracking is currently **disabled** in this server.", color=0x2b2d31)
                await ctx.send(embed=embed)
                return False
        return True

    async def send_error(self, ctx, error_message):
        """Helper to send a formatted error message."""
        embed = discord.Embed(
            description=f"<:SynapseExcl:1477234549552320634> {error_message}",
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    async def send_success(self, ctx, message):
        """Helper to send a formatted success message."""
        embed = discord.Embed(
            description=f"<:emoji_1769867605256:1467155817726873650> {message}",
            color=0x4dff94
        )
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True, aliases=["messagetrack", "mt"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def msgtrack(self, ctx):
        """Manage the message tracking system config."""
        try:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog: return await help_cog.send_group_help_auto(ctx, ctx.command)
            await ctx.send_help(ctx.command)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @msgtrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def enable(self, ctx):
        """Enable message tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM msg_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if row and row[0] == 1:
                    return await self.send_error(ctx, "Message tracking is already enabled for this server.")

                await db.execute("INSERT OR REPLACE INTO msg_config (guild_id, enabled) VALUES (?, 1)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Message tracking is now **enabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @msgtrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disable(self, ctx):
        """Disable message tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM msg_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, "Message tracking is already disabled for this server.")

                await db.execute("INSERT OR REPLACE INTO msg_config (guild_id, enabled) VALUES (?, 0)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Message tracking is now **disabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @msgtrack.command()
    @commands.is_owner()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sync(self, ctx):
        """Sync leaderboards by removing users who have left the server."""
        try:
            embed = discord.Embed(description="<a:LodingImg:1464627402662613002> Syncing message leaderboards...", color=COLOR)
            msg = await ctx.send(embed=embed)

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM message_counts WHERE guild_id = ?", (ctx.guild.id,))
                rows = await cur.fetchall()

                removed = 0
                for row in rows:
                    if ctx.guild.get_member(row[0]) is None:
                        await db.execute("DELETE FROM message_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, row[0]))
                        removed += 1

                await db.commit()

            embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully synced! Removed **{removed}** users who left the server.", color=0x4dff94)
            await msg.edit(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.hybrid_command(name="msgstats", aliases=["mstat", "messages"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def msgstats(self, ctx, member: discord.Member = None):
        """Check your own or another user's message stats."""
        try:
            member = member or ctx.author
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT count, daily_count, weekly_count FROM message_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()

            c, dc, wc = row if row else (0, 0, 0)
            embed = discord.Embed(
                description=f"**{member.display_name}** message stats in {ctx.guild.name}:",
                color=COLOR
            )
            embed.set_author(name=f"{member.display_name}'s Stats", icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="- All-Time", value=f"**{c:,}** messages", inline=True)
            embed.add_field(name="- Weekly", value=f"**{wc:,}** messages", inline=True)
            embed.add_field(name="- Daily", value=f"**{dc:,}** messages", inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.group(invoke_without_command=True, aliases=["lb", "top"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def leaderboard(self, ctx):
        """View message leaderboards."""
        try:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog: return await help_cog.send_group_help_auto(ctx, ctx.command)
            await ctx.send_help(ctx.command)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    async def _paginate_lb(self, ctx, title, order_by_col):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(f"SELECT user_id, {order_by_col} FROM message_counts WHERE guild_id = ? AND {order_by_col} > 0 ORDER BY {order_by_col} DESC", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No message data found for this leaderboard yet.")

            entries = []
            for idx, (uid, val) in enumerate(rows, 1):
                name = f"<@{uid}>"
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`{idx}.`"
                entries.append(f"{medal} {name} — **{val:,}** messages")

            source = DescriptionEmbedPaginator(
                entries,
                per_page=10,
                title="", 
                description=f"**{title}**\n\n",
                author=ctx.guild.name,
                author_icon=ctx.guild.icon.url if ctx.guild.icon else None
            )
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @leaderboard.command(name="messages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lb_all(self, ctx):
        """View the all-time message leaderboard."""
        await self._paginate_lb(ctx, "All-Time Message Leaderboard", "count")

    @leaderboard.command(name="dailymessages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lb_daily(self, ctx):
        """View the daily message leaderboard."""
        await self._paginate_lb(ctx, "Daily Message Leaderboard", "daily_count")

    @leaderboard.command(name="weeklymessages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lb_weekly(self, ctx):
        """View the weekly message leaderboard."""
        await self._paginate_lb(ctx, "Weekly Message Leaderboard", "weekly_count")

    @commands.command(name="addmessages")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def addmessages(self, ctx, member: discord.Member, amount: int):
        """Add messages to a user's stats manually."""
        try:
            if amount <= 0:
                return await self.send_error(ctx, "Amount must be greater than 0.")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO message_counts (guild_id, user_id, count, daily_count, weekly_count)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET 
                        count = count + ?, daily_count = daily_count + ?, weekly_count = weekly_count + ?
                """, (ctx.guild.id, member.id, amount, amount, amount, amount, amount, amount))
                await db.commit()
            await self.send_success(ctx, f"Added **{amount:,}** messages to {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="removemessages")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def removemessages(self, ctx, member: discord.Member, amount: int):
        """Remove messages from a user's stats manually."""
        try:
            if amount <= 0:
                return await self.send_error(ctx, "Amount must be greater than 0.")
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT count FROM message_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, f"{member.display_name} does not have any tracked messages to remove.")

                if row[0] < amount:
                    return await self.send_error(ctx, f"{member.display_name} only has {row[0]:,} messages. You cannot remove {amount:,}.")

                await db.execute("""
                    UPDATE message_counts SET 
                        count = MAX(0, count - ?),
                        daily_count = MAX(0, daily_count - ?),
                        weekly_count = MAX(0, weekly_count - ?)
                    WHERE guild_id = ? AND user_id = ?
                """, (amount, amount, amount, ctx.guild.id, member.id))
                await db.commit()
            await self.send_success(ctx, f"Removed **{amount:,}** messages from {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="clearmsgs")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clearmsgs(self, ctx):
        """Clear all message stats across the server."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT COUNT(*) FROM message_counts WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, "There are no tracked messages in this server to clear.")

                await db.execute("DELETE FROM message_counts WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Resetted **all** message statistics for the server.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="resetmymessages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def resetmymessages(self, ctx):
        """Reset your own message stats."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT count FROM message_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, "You don't have any tracked messages to reset.")

                await db.execute("DELETE FROM message_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id))
                await db.commit()
            await self.send_success(ctx, "Your message statistics have been cleared.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blacklistchannel(self, ctx, channel: discord.TextChannel):
        """Blacklist a channel from rewarding messages."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'channel'", (ctx.guild.id, channel.id))
                if await cur.fetchone():
                    return await self.send_error(ctx, f"{channel.mention} is already blacklisted.")

                await db.execute("INSERT OR IGNORE INTO msg_blacklists (guild_id, entity_id, entity_type) VALUES (?, ?, 'channel')", (ctx.guild.id, channel.id))
                await db.commit()
            await self.send_success(ctx, f"{channel.mention} added to the message tracking blacklist.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unblacklistchannel(self, ctx, channel: discord.TextChannel):
        """Unblacklist a channel from rewarding messages."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'channel'", (ctx.guild.id, channel.id))
                if not await cur.fetchone():
                    return await self.send_error(ctx, f"{channel.mention} is not currently blacklisted.")

                await db.execute("DELETE FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'channel'", (ctx.guild.id, channel.id))
                await db.commit()
            await self.send_success(ctx, f"{channel.mention} removed from the message tracking blacklist.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blacklistedchannels(self, ctx):
        """View blacklisted channels."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT entity_id FROM msg_blacklists WHERE guild_id = ? AND entity_type = 'channel'", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No channels are currently blacklisted for message tracking.")

            entries = [f"<#{r[0]}>" for r in rows]
            source = DescriptionEmbedPaginator(entries, per_page=15, title="", description="**Blacklisted Channels**\n\nChannels ignored by the message tracker.")
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blacklistcategory(self, ctx, category: discord.CategoryChannel):
        """Blacklist an entire category from rewarding messages."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'category'", (ctx.guild.id, category.id))
                if await cur.fetchone():
                    return await self.send_error(ctx, f"Category **{category.name}** is already blacklisted.")

                await db.execute("INSERT OR IGNORE INTO msg_blacklists (guild_id, entity_id, entity_type) VALUES (?, ?, 'category')", (ctx.guild.id, category.id))
                await db.commit()
            await self.send_success(ctx, f"Category **{category.name}** added to the message tracking blacklist.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unblacklistcategory(self, ctx, category: discord.CategoryChannel):
        """Unblacklist an entire category from rewarding messages."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'category'", (ctx.guild.id, category.id))
                if not await cur.fetchone():
                    return await self.send_error(ctx, f"Category **{category.name}** is not currently blacklisted.")

                await db.execute("DELETE FROM msg_blacklists WHERE guild_id = ? AND entity_id = ? AND entity_type = 'category'", (ctx.guild.id, category.id))
                await db.commit()
            await self.send_success(ctx, f"Category **{category.name}** removed from the message tracking blacklist.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blacklistedcategories(self, ctx):
        """View blacklisted categories."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT entity_id FROM msg_blacklists WHERE guild_id = ? AND entity_type = 'category'", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No categories are currently blacklisted for message tracking.")

            entries = []
            for (cid,) in rows:
                cat = ctx.guild.get_channel(cid)
                name = cat.name if cat else f"Unknown ({cid})"
                entries.append(f"**{name}**")

            source = DescriptionEmbedPaginator(entries, per_page=15, title="", description="**Blacklisted Categories**\n\nCategories ignored by the message tracker.")
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def setmessagerole(self, ctx, messages: int, role: discord.Role):
        """Set a role to be rewarded at X amount of messages."""
        try:
            if messages <= 0:
                return await self.send_error(ctx, "Messages required must be higher than 0.")

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT role_id FROM msg_roles WHERE guild_id = ? AND messages_required = ?", (ctx.guild.id, messages))
                row = await cur.fetchone()
                if row and row[0] == role.id:
                    return await self.send_error(ctx, f"{role.mention} is already set as the reward for {messages:,} messages.")

                await db.execute("INSERT OR REPLACE INTO msg_roles (guild_id, messages_required, role_id) VALUES (?, ?, ?)", (ctx.guild.id, messages, role.id))
                await db.commit()

            await self.send_success(ctx, f"Set reward role {role.mention} at **{messages:,}** messages.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unsetmessagerole(self, ctx, role: discord.Role):
        """Remove a role reward."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM msg_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
                if not await cur.fetchone():
                    return await self.send_error(ctx, f"{role.mention} is not currently set as a reward role.")

                await db.execute("DELETE FROM msg_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
                await db.commit()

            await self.send_success(ctx, f"Removed reward for {role.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def viewmessageroles(self, ctx):
        """View all message role rewards set for the server."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT messages_required, role_id FROM msg_roles WHERE guild_id = ? ORDER BY messages_required ASC", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No message roles are configured yet.")

            entries = [f"**{req:,}** messages — <@&{rid}>" for req, rid in rows]
            source = DescriptionEmbedPaginator(entries, per_page=10, title="", description="**Message Role Rewards**\n\nMilestones that reward users automatically.")
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")


async def setup(bot):
    await bot.add_cog(MessageTrackCommands(bot))
