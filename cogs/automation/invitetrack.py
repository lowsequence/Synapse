import discord
from discord.ext import commands
import aiosqlite
import os
from utils.paginators import DescriptionEmbedPaginator
from utils.paginator import Paginator
from utils.Tools import blacklist_check, ignore_check

DB_PATH = os.path.join("database", "invites.db")
COLOR = 0x2b2d31

class InviteTrackCommands(commands.Cog):
    """Advanced premium invite tracking commands with security and robust error handling."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.command.name in ["enable", "disable"]:
            return True
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM invite_config WHERE guild_id = ?", (ctx.guild.id,))
            row = await cur.fetchone()
            if not row or row[0] == 0:
                embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Invite tracking is currently **disabled** in this server.", color=0x2b2d31)
                await ctx.send(embed=embed)
                return False
        return True
    async def send_error(self, ctx, error_message):
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {error_message}", color=0x2b2d31)
        await ctx.send(embed=embed)

    async def send_success(self, ctx, message):
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> {message}", color=0x4dff94)
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def invitetrack(self, ctx):
        """Manage the invite tracking system config."""
        try:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog: return await help_cog.send_group_help_auto(ctx, ctx.command)
            await ctx.send_help(ctx.command)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @invitetrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def enable(self, ctx):
        """Enable invite tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM invite_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if row and row[0] == 1:
                    return await self.send_error(ctx, "Invite tracking is already enabled for this server.")

                await db.execute("INSERT OR REPLACE INTO invite_config (guild_id, enabled) VALUES (?, 1)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Invite tracking is now **enabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @invitetrack.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disable(self, ctx):
        """Disable invite tracking system."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT enabled FROM invite_config WHERE guild_id = ?", (ctx.guild.id,))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, "Invite tracking is already disabled for this server.")

                await db.execute("INSERT OR REPLACE INTO invite_config (guild_id, enabled) VALUES (?, 0)", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Invite tracking is now **disabled**.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @invitetrack.command()
    @commands.is_owner()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sync(self, ctx):
        """Sync leaderboards by removing users who have left the server."""
        try:
            embed = discord.Embed(description="<a:LodingImg:1464627402662613002> Syncing invite leaderboards...", color=COLOR)
            msg = await ctx.send(embed=embed)

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM invite_counts WHERE guild_id = ?", (ctx.guild.id,))
                rows = await cur.fetchall()

                removed = 0
                for row in rows:
                    if ctx.guild.get_member(row[0]) is None:
                        await db.execute("DELETE FROM invite_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, row[0]))
                        await db.execute("DELETE FROM join_leaves WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, row[0]))
                        removed += 1

                await db.commit()

            embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully synced! Removed **{removed}** users who left the server.", color=0x4dff94)
            await msg.edit(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="setaltthreshold")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def setaltthreshold(self, ctx, days: int):
        """Set the account age threshold (in days) to consider an invite 'Fake'."""
        try:
            if days <= 0:
                return await self.send_error(ctx, "Threshold must be greater than 0 days.")

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO invite_config (guild_id, enabled, alt_threshold) VALUES (?, COALESCE((SELECT enabled FROM invite_config WHERE guild_id = ?), 0), ?)", (ctx.guild.id, ctx.guild.id, days))
                await db.commit()
            await self.send_success(ctx, f"Fake invite account age threshold set to **{days}** days.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="unsetaltthreshold")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unsetaltthreshold(self, ctx):
        """Reset the fake account tracker back to the default 3 days."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE invite_config SET alt_threshold = 3 WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Fake invite account age threshold reset to the default **3** days.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.hybrid_command(name="invites", aliases=["istat"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def invites(self, ctx, member: discord.Member = None):
        """Check your own or another user's invite stats."""
        try:
            member = member or ctx.author
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT total_invites, regular_invites, fake_invites, left_invites FROM invite_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()

            t, r, f, l = row if row else (0, 0, 0, 0)
            embed = discord.Embed(
                description=f"**{member.display_name}** invite statistics in {ctx.guild.name}:",
                color=COLOR
            )
            embed.set_author(name=f"{member.display_name}'s Invites", icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="- Total", value=f"**{t:,}** invites", inline=True)
            embed.add_field(name="- Regular", value=f"**{r:,}** invites", inline=True)
            embed.add_field(name="- Fake", value=f"**{f:,}** invites", inline=True)
            embed.add_field(name="- Left", value=f"**{l:,}** invites", inline=True)

            embed.set_footer(text=f"Score: {r} (Total: {t} - Left: {l} - Fake: {f})")
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="inviter")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def inviter(self, ctx, member: discord.Member):
        """Check who invited a specific member."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT inviter_id FROM join_leaves WHERE guild_id = ? AND member_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()

            if not row:
                return await self.send_error(ctx, f"I have no record of who invited {member.mention}.")

            inviter_id = row[0]
            await ctx.send(embed=discord.Embed(description=f"<:Meko_Leave:1459847428202168362> {member.mention} was invited by <@{inviter_id}>.", color=COLOR))
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="invited")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def invited(self, ctx, member: discord.Member = None):
        """See a list of members that were invited by a specific user."""
        try:
            member = member or ctx.author
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT member_id FROM join_leaves WHERE guild_id = ? AND inviter_id = ?", (ctx.guild.id, member.id))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, f"{member.display_name} has not invited anyone yet (or they have all left).")

            entries = [f"`{idx}.` <@{r[0]}>" for idx, r in enumerate(rows, 1)]
            source = DescriptionEmbedPaginator(
                entries, per_page=15, title="", description=f"**Members Invited By {member.display_name}**\n\n",
                author=ctx.guild.name, author_icon=ctx.guild.icon.url if ctx.guild.icon else None
            )
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()

        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="inviteinfo", aliases=["iinfo"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def inviteinfo(self, ctx, code: str):
        """Get detailed information about a Discord invite code."""
        try:
            if "discord.gg/" in code: code = code.split("discord.gg/")[-1]
            elif "discord.com/invite/" in code: code = code.split("discord.com/invite/")[-1]

            invite = await self.bot.fetch_invite(code)

            embed = discord.Embed(title=f"Invite Code: {invite.code}", color=COLOR)
            embed.add_field(name="Channel", value=f"{invite.channel.mention}" if invite.channel else "Unknown", inline=True)
            embed.add_field(name="Inviter", value=f"{invite.inviter.mention}" if invite.inviter else "Unknown", inline=True)
            embed.add_field(name="Server", value=f"{invite.guild.name}", inline=True)
            embed.add_field(name="Uses", value=f"{invite.uses if invite.uses else 0} / {invite.max_uses if invite.max_uses else '∞'}", inline=True)
            embed.add_field(name="Expires At", value=f"<t:{int(invite.expires_at.timestamp())}:R>" if invite.expires_at else "Never", inline=True)

            if invite.guild.icon:
                embed.set_thumbnail(url=invite.guild.icon.url)

            await ctx.send(embed=embed)
        except discord.NotFound:
            await self.send_error(ctx, "That invite code is invalid or has expired.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.group(invoke_without_command=True, aliases=["ilb", "invitetop"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def inviteleaderboard(self, ctx):
        """View invite leaderboards."""
        try:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog: return await help_cog.send_group_help_auto(ctx, ctx.command)
            await ctx.send_help(ctx.command)
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    async def _paginate_ilb(self, ctx, title, order_by_col):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(f"SELECT user_id, {order_by_col} FROM invite_counts WHERE guild_id = ? AND {order_by_col} > 0 ORDER BY {order_by_col} DESC", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No invite data found for this leaderboard yet.")

            entries = []
            for idx, (uid, val) in enumerate(rows, 1):
                name = f"<@{uid}>"
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`{idx}.`"
                entries.append(f"{medal} {name} — **{val:,}** invites")

            source = DescriptionEmbedPaginator(
                entries, per_page=10, title="", description=f"**{title}**\n\n",
                author=ctx.guild.name, author_icon=ctx.guild.icon.url if ctx.guild.icon else None
            )
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @inviteleaderboard.command(name="total")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ilb_total(self, ctx):
        """View the total invites leaderboard."""
        await self._paginate_ilb(ctx, "Total Invites Leaderboard", "total_invites")

    @inviteleaderboard.command(name="regular")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ilb_regular(self, ctx):
        """View the regular invites leaderboard."""
        await self._paginate_ilb(ctx, "Regular Invites Leaderboard", "regular_invites")

    @inviteleaderboard.command(name="fake")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ilb_fake(self, ctx):
        """View the fake invites leaderboard."""
        await self._paginate_ilb(ctx, "Fake Invites Leaderboard", "fake_invites")

    @inviteleaderboard.command(name="left")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ilb_left(self, ctx):
        """View the left invites leaderboard."""
        await self._paginate_ilb(ctx, "Left Invites Leaderboard", "left_invites")

    @commands.command(name="addinvites")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def addinvites(self, ctx, member: discord.Member, amount: int):
        """Add regular invites to a user's stats manually."""
        try:
            if amount <= 0:
                return await self.send_error(ctx, "Amount must be greater than 0.")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO invite_counts (guild_id, user_id, total_invites, regular_invites, fake_invites, left_invites)
                    VALUES (?, ?, ?, ?, 0, 0)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET 
                        total_invites = total_invites + ?, regular_invites = regular_invites + ?
                """, (ctx.guild.id, member.id, amount, amount, amount, amount))
                await db.commit()
            await self.send_success(ctx, f"Added **{amount:,}** regular invites to {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="removeinvites")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def removeinvites(self, ctx, member: discord.Member, amount: int):
        """Remove regular invites from a user's stats manually."""
        try:
            if amount <= 0:
                return await self.send_error(ctx, "Amount must be greater than 0.")
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT regular_invites FROM invite_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
                row = await cur.fetchone()
                if not row or row[0] == 0:
                    return await self.send_error(ctx, f"{member.display_name} does not have any regular invites to remove.")

                if row[0] < amount:
                    return await self.send_error(ctx, f"{member.display_name} only has {row[0]:,} regular invites. You cannot remove {amount:,}.")

                await db.execute("""
                    UPDATE invite_counts SET 
                        total_invites = MAX(0, total_invites - ?),
                        regular_invites = MAX(0, regular_invites - ?)
                    WHERE guild_id = ? AND user_id = ?
                """, (amount, amount, ctx.guild.id, member.id))
                await db.commit()
            await self.send_success(ctx, f"Removed **{amount:,}** regular invites from {member.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="clearinvites")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clearinvites(self, ctx):
        """Clear all invite stats across the server."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM invite_counts WHERE guild_id = ?", (ctx.guild.id,))
                await db.execute("DELETE FROM join_leaves WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()
            await self.send_success(ctx, "Resetted **all** invite statistics for the server.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="resetmyinvites")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def resetmyinvites(self, ctx):
        """Reset your own invite stats."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM invite_counts WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id))
                await db.execute("DELETE FROM join_leaves WHERE guild_id = ? AND inviter_id = ?", (ctx.guild.id, ctx.author.id))
                await db.commit()
            await self.send_success(ctx, "Your invite statistics have been cleared.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="setinviterole")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def setinviterole(self, ctx, invites: int, role: discord.Role):
        """Set a role to be rewarded at X amount of regular invites."""
        try:
            if invites <= 0:
                return await self.send_error(ctx, "Invites required must be higher than 0.")

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT role_id FROM invite_roles WHERE guild_id = ? AND invites_required = ?", (ctx.guild.id, invites))
                row = await cur.fetchone()
                if row and row[0] == role.id:
                    return await self.send_error(ctx, f"{role.mention} is already set as the reward for {invites:,} invites.")

                await db.execute("INSERT OR REPLACE INTO invite_roles (guild_id, invites_required, role_id) VALUES (?, ?, ?)", (ctx.guild.id, invites, role.id))
                await db.commit()

            await self.send_success(ctx, f"Set reward role {role.mention} at **{invites:,}** regular invites.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="unsetinviterole")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unsetinviterole(self, ctx, role: discord.Role):
        """Remove an invite role reward."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT 1 FROM invite_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
                if not await cur.fetchone():
                    return await self.send_error(ctx, f"{role.mention} is not currently set as an invite reward role.")

                await db.execute("DELETE FROM invite_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
                await db.commit()

            await self.send_success(ctx, f"Removed invite reward for {role.mention}.")
        except Exception as e:
            await self.send_error(ctx, f"An internal error occurred: `{e}`")

    @commands.command(name="viewinviteroles")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def viewinviteroles(self, ctx):
        """View all invite role rewards set for the server."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT invites_required, role_id FROM invite_roles WHERE guild_id = ? ORDER BY invites_required ASC", (ctx.guild.id,))
                rows = await cur.fetchall()

            if not rows:
                return await self.send_error(ctx, "No invite roles are configured yet.")

            entries = [f"**{req:,}** regular invites — <@&{rid}>" for req, rid in rows]
            source = DescriptionEmbedPaginator(entries, per_page=10, title="", description="**Invite Role Rewards**\n\nMilestones that reward users automatically.")
            source.embed.color = COLOR
            menu = Paginator(source, ctx=ctx)
            await menu.paginate()
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
    await bot.add_cog(InviteTrackCommands(bot))
