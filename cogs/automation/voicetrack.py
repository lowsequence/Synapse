import discord
from discord.ext import commands
import aiosqlite
import os
import datetime
from utils.paginators import DescriptionEmbedPaginator
from utils.paginator import Paginator
from utils.Tools import blacklist_check, ignore_check

DB_PATH = os.path.join("database", "voicetrack.db")
COLOR = 0x2b2d31

def format_time(seconds):
    """Converts raw seconds into a 00h 00m 00s format."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

class VoiceTrackCommands(commands.Cog):
    """Voice tracking commands."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.command.name in ["enable", "disable"]:
            return True
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM voice_config WHERE guild_id = ?", (ctx.guild.id,))
            row = await cur.fetchone()
            if not row or row[0] == 0:
                embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Voice tracking is currently **disabled** in this server.", color=0x2b2d31)
                await ctx.send(embed=embed)
                return False
        return True

    async def send_error(self, ctx, error_message):
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {error_message}", color=0x2b2d31)
        await ctx.send(embed=embed)

    async def send_success(self, ctx, message):
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> {message}", color=0x4dff94)
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True, aliases=["vt"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def voicetrack(self, ctx):
        """Manage the voice tracking system config."""
        try:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog: return await help_cog.send_group_help_auto(ctx, ctx.command)
            await ctx.send_help(ctx.command)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @voicetrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def enable(self, ctx):
        """Enable voice tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM voice_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if row and row[0] == 1:
                    return await self.send_error(ctx, "Voice tracking is already enabled for this server.")

                await db.execute("INSERT OR REPLACE INTO voice_config (guild_id, enabled) VALUES (?, 1)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Voice tracking is now **enabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @voicetrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disable(self, ctx):
        """Disable voice tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM voice_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, "Voice tracking is already disabled for this server.")

                await db.execute("INSERT OR REPLACE INTO voice_config (guild_id, enabled) VALUES (?, 0)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Voice tracking is now **disabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @voicetrack.command()
    @commands.is_owner()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sync(self, ctx):
        """Sync leaderboards by removing users who have left the server."""
        try:
            embed = discord.Embed(description="<a:LodingImg:1464627402662613002> Syncing voice leaderboards...", color=COLOR)
            msg = await ctx.send(embed=embed)

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM voice_counts WHERE guild_id = ?", (ctx.guild.id,))
                rows = await cur.fetchall()

                removed = 0
                for row in rows:
                    if ctx.guild.get_member(row[0]) is None:
                        await db.execute("DELETE FROM voice_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, row[0]))
                        removed += 1

                await db.commit()

            embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully synced! Removed **{removed}** users who left the server.", color=0x4dff94)
            await msg.edit(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.hybrid_command(name="vcstats", aliases=["voicestats", "vstat"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def vcstats(self, ctx, member: discord.Member = None):
        """Check your own or another user's voice stats."""
        try:
            member = member or ctx.author
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT total_time, daily_time, weekly_time FROM voice_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()

            t, d, w = row if row else (0, 0, 0)

            events_cog = self.bot.get_cog("VoiceTrackEvents")
            if events_cog and ctx.guild.id in events_cog.active_sessions:
                if member.id in events_cog.active_sessions[ctx.guild.id]:
                    join_time = events_cog.active_sessions[ctx.guild.id][member.id]
                    delta = int((datetime.datetime.now() - join_time).total_seconds())
                    if delta > 0:
                        t += delta; d += delta; w += delta

            embed = discord.Embed(
                description=f"**{member.display_name}** voice stats in {ctx.guild.name}:",
                color=COLOR
            )
            embed.set_author(name=f"{member.display_name}'s Voice Time", icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="- All-Time", value=f"**{format_time(t)}**", inline=True)
            embed.add_field(name="- Weekly", value=f"**{format_time(w)}**", inline=True)
            embed.add_field(name="- Daily", value=f"**{format_time(d)}**", inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    async def _paginate_lb(self, ctx, title, order_by_col):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(f"SELECT user_id, {order_by_col} FROM voice_counts WHERE guild_id = ? AND {order_by_col} > 0 ORDER BY {order_by_col} DESC", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No voice data found for this leaderboard yet.")

            entries = []
            for idx, (uid, val) in enumerate(rows, 1):
                name = f"<@{uid}>"
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`{idx}.`"
                entries.append(f"{medal} {name} — **{format_time(val)}**")

            source = DescriptionEmbedPaginator(
                entries, per_page=10, title="", description=f"**{title}**\n\n",
                author=ctx.guild.name, author_icon=ctx.guild.icon.url if ctx.guild.icon else None
            )
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.group(invoke_without_command=True, aliases=["vclb", "voicetop"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def voiceleaderboard(self, ctx):
        """View the total voice leaderboard."""
        await self._paginate_lb(ctx, "All-Time Voice Leaderboard", "total_time")

    @commands.command(name="dailyvoice")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def dailyvoice(self, ctx):
        """View the daily voice leaderboard."""
        await self._paginate_lb(ctx, "Daily Voice Leaderboard", "daily_time")

    @commands.command(name="weeklyvoice")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def weeklyvoice(self, ctx):
        """View the weekly voice leaderboard."""
        await self._paginate_lb(ctx, "Weekly Voice Leaderboard", "weekly_time")

    @commands.command(name="addvctime")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def addvctime(self, ctx, member: discord.Member, minutes: int):
        """Add time (in minutes) to a user's voice stats manually."""
        try:
            if minutes <= 0:
                return await self.send_error(ctx, "Minutes must be greater than 0.")
            seconds = minutes * 60
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO voice_counts (guild_id, user_id, total_time, daily_time, weekly_time)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        total_time = total_time + ?,
                        daily_time = daily_time + ?,
                        weekly_time = weekly_time + ?
                """, (ctx.guild.id, member.id, seconds, seconds, seconds, seconds, seconds, seconds))
                await db.commit()
            await self.send_success(ctx, f"Added **{minutes:,}** minutes of voice time to {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="reducevctime")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def reducevctime(self, ctx, member: discord.Member, minutes: int):
        """Remove time (in minutes) from a user's voice stats manually."""
        try:
            if minutes <= 0:
                return await self.send_error(ctx, "Minutes must be greater than 0.")
            seconds = minutes * 60
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT total_time FROM voice_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, f"{member.display_name} does not have any voice time to reduce.")

                if row[0] < seconds:
                    return await self.send_error(ctx, f"{member.display_name} only has {format_time(row[0])} of total voice time. You cannot remove {minutes} minutes.")

                await db.execute("""
                    UPDATE voice_counts SET
                        total_time = MAX(0, total_time - ?),
                        daily_time = MAX(0, daily_time - ?),
                        weekly_time = MAX(0, weekly_time - ?)
                    WHERE guild_id = ? AND user_id = ?
                """, (seconds, seconds, seconds, ctx.guild.id, member.id))
                await db.commit()
            await self.send_success(ctx, f"Removed **{minutes:,}** minutes of voice time from {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="clearvoice")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clearvoice(self, ctx):
        """Clear all voice stats across the server."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM voice_counts WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            events_cog = self.bot.get_cog("VoiceTrackEvents")
            if events_cog and ctx.guild.id in events_cog.active_sessions:
                for member_id in events_cog.active_sessions[ctx.guild.id]:
                    events_cog.active_sessions[ctx.guild.id][member_id] = datetime.datetime.now()

            await self.send_success(ctx, "Resetted **all** voice statistics for the server.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="resetmyvoice")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def resetmyvoice(self, ctx):
        """Reset your own voice stats."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM voice_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id))
                await db.commit()

            events_cog = self.bot.get_cog("VoiceTrackEvents")
            if events_cog and ctx.guild.id in events_cog.active_sessions and ctx.author.id in events_cog.active_sessions[ctx.guild.id]:
                events_cog.active_sessions[ctx.guild.id][ctx.author.id] = datetime.datetime.now()

            await self.send_success(ctx, "Your voice statistics have been cleared.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                description=f"<:SynapseExcl:1477234549552320634> Invalid arguments! Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                color=0x2b2d31
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VoiceTrackCommands(bot))
