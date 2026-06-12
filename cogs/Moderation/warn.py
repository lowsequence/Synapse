import discord
from discord.ext import commands
from discord import ui
import aiosqlite
import asyncio
from utils.Tools import *
from datetime import datetime, timedelta
import os

def has_warn_permission():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        async with aiosqlite.connect("database/warn.db") as db:
            async with db.execute("SELECT role_id FROM warnroles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                roles = await cursor.fetchall()
                warn_roles = [r[0] for r in roles]
        if any(role.id in warn_roles for role in ctx.author.roles):
            return True
        raise commands.MissingPermissions(["A configured Warn Role (use `warnrole add <role>`)"])
    return commands.check(predicate)

class WarnView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\nPlease use the bot command first then you can access this button"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Trash:1462771196885074002>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class Warn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)
        self.db_path = "database/warn.db"
        asyncio.create_task(self.setup())

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    async def add_warn(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO warns (guild_id, user_id, warns) VALUES (?, ?, 0)", (guild_id, user_id))
            await db.execute("UPDATE warns SET warns = warns + 1 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    async def get_total_warns(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT warns FROM warns WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
                return 0

    async def warn_user(self, user: discord.Member, total_warns: int):
        config = None
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT action, duration, role_id FROM warn_config WHERE guild_id = ? AND warn_count = ?", (user.guild.id, total_warns)) as cursor:
                config = await cursor.fetchone()

        if config:
            action, duration, role_id = config
            punishment_msg = ""
            if action == "timeout" and duration:
                try:
                    until_time = discord.utils.utcnow() + timedelta(seconds=duration)
                    await user.edit(timed_out_until=until_time, reason="Exceeded warning threshold")
                    if duration < 3600:
                        dur_str = f"{duration // 60}m"
                    elif duration < 86400:
                        dur_str = f"{duration // 3600}h"
                    else:
                        dur_str = f"{duration // 86400}d"
                    punishment_msg += f"\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Timed Out for `{dur_str}`"
                except Exception:
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to timeout user (Missing Permissions)"
            elif action == "kick":
                try:
                    await user.kick(reason="Exceeded warning threshold")
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Kicked"
                except Exception:
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to kick user (Missing Permissions)"
            elif action == "ban":
                try:
                    await user.ban(reason="Exceeded warning threshold")
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Banned"
                except Exception:
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to ban user (Missing Permissions)"

            if role_id:
                try:
                    role = user.guild.get_role(role_id)
                    if role:
                        await user.add_roles(role, reason="Exceeded warning threshold")
                        punishment_msg += f"\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Added Role {role.mention}"
                    else:
                        punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to add role (Role Not Found)"
                except Exception:
                    punishment_msg += "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to add role (Missing Permissions)"

            if punishment_msg:
                return punishment_msg
        else:
            timeout_duration = None
            if total_warns == 3:
                timeout_duration = 300
            elif total_warns == 5:
                timeout_duration = 600
            elif total_warns == 10:
                timeout_duration = 3600

            if total_warns > 10:
                try:
                    await user.kick(reason="Exceeded warning threshold (Default)")
                    return "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Kicked (Default)"
                except Exception:
                    return "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to kick user"

            if timeout_duration:
                try:
                    until_time = discord.utils.utcnow() + timedelta(seconds=timeout_duration)
                    await user.edit(timed_out_until=until_time, reason="Exceeded warning threshold (Default)")
                    dur_str = f"{timeout_duration // 60}m" if timeout_duration < 3600 else f"{timeout_duration // 3600}h"
                    return f"\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Timed Out for `{dur_str}` (Default)"
                except Exception:
                    return "\n<:ArrowMiddle:1479489625654562896> **Action Taken:** Failed to timeout the user"

        return ""

    async def reset_warns(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE warns SET warns = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    async def setup(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                CREATE TABLE IF NOT EXISTS warns (
                    guild_id INTEGER,
                    user_id INTEGER,
                    warns INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
                """)
                await db.execute("""
                CREATE TABLE IF NOT EXISTS warn_config (
                    guild_id INTEGER,
                    warn_count INTEGER,
                    action TEXT,
                    duration INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, warn_count)
                )
                """)
                await db.execute("""
                CREATE TABLE IF NOT EXISTS warnroles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
                """)
                await db.execute("""
                CREATE TABLE IF NOT EXISTS warn_alerts (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    message TEXT,
                    is_enabled INTEGER DEFAULT 1
                )
                """)
                try:
                    await db.execute("ALTER TABLE warn_alerts ADD COLUMN is_enabled INTEGER DEFAULT 1")
                except Exception:
                    pass
                await db.commit()
        except Exception as e:
            print(f"Error during database setup: {e}")

    @commands.hybrid_command(
        name="warn",
        help="Warn a user in the server",
        usage="<user> [reason]",
        aliases=["warnuser"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @has_warn_permission()
    async def warn(self, ctx, user: discord.Member, *, reason=None):
        if user == ctx.author:
            return await ctx.reply("You cannot warn yourself.")

        if user == ctx.bot.user:
            return await ctx.reply("You cannot warn me.")

        if not ctx.author == ctx.guild.owner:
            if user == ctx.guild.owner:
                return await ctx.reply("I cannot warn the server owner.")

            if ctx.author.top_role <= user.top_role:
                return await ctx.reply("You cannot Warn a member with a higher or equal role.")

        if ctx.guild.me.top_role <= user.top_role:
            return await ctx.reply("I cannot Warn a member with a higher or equal role.")

        if user not in ctx.guild.members:
            return await ctx.reply("The user is not a member of this server.")

        try:
            await self.add_warn(ctx.guild.id, user.id)
            total_warns = await self.get_total_warns(ctx.guild.id, user.id)

            reason_to_send = reason or "Not Provided"
            try:
                await user.send(f"You have been warned in **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason_to_send}")
                dm_status = "Yes"
            except discord.Forbidden:
                dm_status = "No"
            except discord.HTTPException:
                dm_status = "No"

            punishment_msg = await self.warn_user(user, total_warns)

            embed = discord.Embed(
                title="<:IMPORT_thumsup:1462777656570413119> Member Warned",
                description=(
                    f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n"
                    f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                    f"<:ArrowMiddle:1479489625654562896> **Warns:** {total_warns}\n"
                    f"<:ArrowBottom:1479489659255132464> **Reason:** {reason_to_send}{punishment_msg}"
                ),
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.get_user_avatar(user))

            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute("SELECT channel_id, message, is_enabled FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                        alert_row = await cursor.fetchone()
                
                if alert_row and alert_row[0] and alert_row[2]:
                    alert_channel_id, alert_msg, is_enabled = alert_row
                    alert_channel = ctx.guild.get_channel(alert_channel_id)
                    if alert_channel:
                        next_warns = total_warns + 1
                        async with aiosqlite.connect(self.db_path) as db:
                            async with db.execute("SELECT action, duration FROM warn_config WHERE guild_id = ? AND warn_count = ?", (ctx.guild.id, next_warns)) as cursor:
                                next_config = await cursor.fetchone()
                        
                        next_punish_str = "None"
                        if next_config:
                            naction, nduration = next_config
                            if naction == "timeout":
                                dur_str = f"{nduration // 60}m" if nduration < 3600 else f"{nduration // 3600}h" if nduration < 86400 else f"{nduration // 86400}d"
                                next_punish_str = f"Timeout ({dur_str})"
                            else:
                                next_punish_str = str(naction).capitalize() if naction else "None"
                        else:
                            if next_warns == 3: next_punish_str = "Timeout (5m)"
                            elif next_warns == 5: next_punish_str = "Timeout (10m)"
                            elif next_warns == 10: next_punish_str = "Timeout (1h)"
                            elif next_warns > 10: next_punish_str = "Kick"

                        current_punish_str = "None"
                        if "Timed Out" in punishment_msg: current_punish_str = "Timeout"
                        elif "Kicked" in punishment_msg: current_punish_str = "Kick"
                        elif "Banned" in punishment_msg: current_punish_str = "Ban"
                        elif "Role" in punishment_msg: current_punish_str = "Role Addition"

                        alert_msg = alert_msg.replace("<user>", user.mention)
                        alert_msg = alert_msg.replace("<user.name>", user.name)
                        alert_msg = alert_msg.replace("<user.id>", str(user.id))
                        alert_msg = alert_msg.replace("<moderator>", ctx.author.mention)
                        alert_msg = alert_msg.replace("<moderator.name>", ctx.author.name)
                        alert_msg = alert_msg.replace("<moderator.id>", str(ctx.author.id))
                        alert_msg = alert_msg.replace("<reason>", reason_to_send)
                        alert_msg = alert_msg.replace("<server>", ctx.guild.name)
                        alert_msg = alert_msg.replace("<server.id>", str(ctx.guild.id))
                        alert_msg = alert_msg.replace("<totalwarns>", str(total_warns))
                        alert_msg = alert_msg.replace("<case_id>", str(total_warns))
                        alert_msg = alert_msg.replace("<current_punishment>", current_punish_str)
                        alert_msg = alert_msg.replace("<current punishment>", current_punish_str)
                        alert_msg = alert_msg.replace("<next_punishment>", next_punish_str)
                        alert_msg = alert_msg.replace("<next punishment>", next_punish_str)

                        try:
                            await alert_channel.send(content=alert_msg)
                        except discord.Forbidden:
                            pass
                        except discord.HTTPException as err:
                            print(f"Failed to send warn alert: {err}")
            except Exception as e:
                print(f"Error handling warn alerts logic: {e}")

            view = WarnView(user=user, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            print(f"Error during warn command: {e}")

    @commands.hybrid_command(
        name="warns",
        help="Check warnings for a user",
        aliases=["warnings"],
        usage="[user]")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def warns(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        try:
            total_warns = await self.get_total_warns(ctx.guild.id, user.id)
            embed = discord.Embed(
                title=f"Warnings for {user.name}",
                description=f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n<:ArrowBottom:1479489659255132464> **Total Warns:** {total_warns}",
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.get_user_avatar(user))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            print(f"Error during warns command: {e}")

    @commands.hybrid_command(
        name="clearwarns",
        help="Clear all warnings for a user",
        aliases=["clearwarn" , "clearwarnings"],
        usage="<user>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @has_warn_permission()
    async def clearwarns(self, ctx, user: discord.Member):
        try:
            await self.reset_warns(ctx.guild.id, user.id)
            embed = discord.Embed(
                title="<:emoji_1769867605256:1467155817726873650> Warnings Cleared",
                description=(
                    f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n"
                    f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                    f"<:ArrowBottom:1479489659255132464> **Action:** All Warns Reset"
                ),
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.get_user_avatar(user))

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            print(f"Error during clearwarns command: {e}")

    @commands.group(
        name="warnconfig",
        help="Configure the server warning system",
        aliases=["wc", "warnsettings"],
        invoke_without_command=True
    )
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def warnconfig(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @warnconfig.group(
        name="add",
        help="Add an automatic action for a specific warning count",
        invoke_without_command=True
    )
    @commands.has_permissions(administrator=True)
    async def warnconfig_add(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @warnconfig_add.command(
        name="punishment",
        help="Add a punishment for a specific warning count",
        usage="<warn_count> <timeout/kick/ban> [duration]"
    )
    @commands.has_permissions(administrator=True)
    async def warnconfig_add_punishment(self, ctx, warn_count: int, action: str, *, duration_str: str = None):
        action = action.lower()
        if action not in ["timeout", "kick", "ban"]:
            embed = discord.Embed(color=self.color, description="Invalid action! Choices are `timeout`, `kick`, `ban`.")
            return await ctx.send(embed=embed)

        duration = None
        if action == "timeout":
            if not duration_str:
                embed = discord.Embed(color=self.color, description="You must provide a duration for timeout (e.g., `10m`, `1h`).")
                return await ctx.send(embed=embed)

            import re
            time_pattern = r"(\d+)([mhd])"
            match = re.match(time_pattern, duration_str.split()[0])
            if match:
                time_value = int(match.group(1))
                time_unit = match.group(2)
                if time_unit == 'm': duration = time_value * 60
                elif time_unit == 'h': duration = time_value * 3600
                elif time_unit == 'd': duration = time_value * 86400

            if not duration:
                embed = discord.Embed(color=self.color, description="Invalid time format! Use `<number><m/h/d>`.")
                return await ctx.send(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id FROM warn_config WHERE guild_id = ? AND warn_count = ?", (ctx.guild.id, warn_count)) as cursor:
                row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE warn_config SET action = ?, duration = ? WHERE guild_id = ? AND warn_count = ?", (action, duration, ctx.guild.id, warn_count))
            else:
                await db.execute("""
                    INSERT INTO warn_config (guild_id, warn_count, action, duration, role_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (ctx.guild.id, warn_count, action, duration, None))
            await db.commit()

        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Warn Configuration Added",
            description=f"Action set for `{warn_count}` warnings:\n**Action**: `{action.capitalize()}`",
            color=0x2b2d31
        )
        if duration:
            dur_str = f"{duration // 60}m" if duration < 3600 else f"{duration // 3600}h" if duration < 86400 else f"{duration // 86400}d"
            embed.description += f"\n**Duration**: `{dur_str}`"

        await ctx.send(embed=embed)

    @warnconfig_add.command(
        name="role",
        help="Add a role action for a specific warning count",
        usage="<warn_count> <role>"
    )
    @commands.has_permissions(administrator=True)
    async def warnconfig_add_role(self, ctx, warn_count: int, role: discord.Role):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT action, duration FROM warn_config WHERE guild_id = ? AND warn_count = ?", (ctx.guild.id, warn_count)) as cursor:
                row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE warn_config SET role_id = ? WHERE guild_id = ? AND warn_count = ?", (role.id, ctx.guild.id, warn_count))
            else:
                await db.execute("""
                    INSERT INTO warn_config (guild_id, warn_count, action, duration, role_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (ctx.guild.id, warn_count, None, None, role.id))
            await db.commit()

        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Warn Configuration Added",
            description=f"Action set for `{warn_count}` warnings:\n**Action**: `Role`\n**Role**: {role.mention}",
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @warnconfig.command(
        name="remove",
        help="Remove an automatic action for a specific warning count",
        usage="<warn_count>"
    )
    @commands.has_permissions(administrator=True)
    async def warnconfig_remove(self, ctx, warn_count: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM warn_config WHERE guild_id = ? AND warn_count = ?", (ctx.guild.id, warn_count))
            if cursor.rowcount > 0:
                embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed configuration for {warn_count} warnings.", color=0x2b2d31)
            else:
                embed = discord.Embed(description="No configuration found for that warning count.", color=self.color)
            await db.commit()

        await ctx.send(embed=embed)

    @warnconfig.command(
        name="list",
        help="List all warning configurations for this server"
    )
    @commands.has_permissions(administrator=True)
    async def warnconfig_list(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT warn_count, action, duration, role_id FROM warn_config WHERE guild_id = ? ORDER BY warn_count ASC", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(description="No custom warning configurations set. Using system defaults.", color=self.color)
            return await ctx.send(embed=embed)

        entries = []
        for warn_count, action, duration, role_id in rows:
            details = []
            if action:
                if action == "timeout":
                    dur_str = f"{duration // 60}m" if duration < 3600 else f"{duration // 3600}h" if duration < 86400 else f"{duration // 86400}d"
                    details.append(f"Action: **Timeout** (`{dur_str}`)")
                else:
                    details.append(f"Action: **{action.capitalize()}**")
            if role_id:
                details.append(f"Role: <@&{role_id}>")

            val = " | ".join(details) if details else "None"
            entries.append((f"{warn_count} Warnings", val))

        from utils import FieldPagePaginator, Paginator
        source = FieldPagePaginator(
            entries,
            per_page=10,
            inline=False,
            title=f"Warn Configurations for {ctx.guild.name}",
            color=0x2b2d31
        )
        menu = Paginator(source, ctx=ctx)
        await menu.paginate()

    @commands.group(
        name="warnrole",
        help="Manage roles that can use warn commands",
        invoke_without_command=True
    )
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def warnrole(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @warnrole.command(name="add", help="Add a role that can use warn commands")
    @commands.has_permissions(administrator=True)
    async def warnrole_add(self, ctx, role: discord.Role):
        PREMIUM_DB = "database/premium_codes.db"
        is_premium = False
        if os.path.exists(PREMIUM_DB):
            try:
                async with aiosqlite.connect(PREMIUM_DB) as db:
                    async with db.execute("SELECT expires_at FROM premium_guilds WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                        row = await cur.fetchone()
                if row:
                    expires = datetime.fromisoformat(row[0])
                    if expires > datetime.utcnow():
                        is_premium = True
            except Exception:
                pass

        limit = 10 if is_premium else 5
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id FROM warnroles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                existing = await cursor.fetchall()

            if len(existing) >= limit:
                tip = " Upgrade to **Premium** for up to **10** roles." if limit == 5 else ""
                embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> You can only add up to **{limit}** warn roles.{tip}", color=0x2b2d31)
                return await ctx.send(embed=embed)

            if any(role.id == r[0] for r in existing):
                embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {role.mention} is already a warn role.", color=0x2b2d31)
                return await ctx.send(embed=embed)

            await db.execute("INSERT INTO warnroles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
            await db.commit()

        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> {role.mention} has been added as a warn role! `[{len(existing)+1}/{limit}]`", color=0x4dff94)
        await ctx.send(embed=embed)

    @warnrole.command(name="remove", help="Remove a warn role")
    @commands.has_permissions(administrator=True)
    async def warnrole_remove(self, ctx, role: discord.Role):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM warnroles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
            if cursor.rowcount > 0:
                embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> {role.mention} has been removed from warn roles.", color=0x4dff94)
            else:
                embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {role.mention} is not a warn role.", color=0x2b2d31)
            await db.commit()
        await ctx.send(embed=embed)

    @warnrole.command(name="list", help="List all warn roles")
    @commands.has_permissions(administrator=True)
    async def warnrole_list(self, ctx):
        PREMIUM_DB = "database/premium_codes.db"
        is_premium = False
        if os.path.exists(PREMIUM_DB):
            try:
                async with aiosqlite.connect(PREMIUM_DB) as db:
                    async with db.execute("SELECT expires_at FROM premium_guilds WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                        row = await cur.fetchone()
                if row:
                    expires = datetime.fromisoformat(row[0])
                    if expires > datetime.utcnow():
                        is_premium = True
            except Exception:
                pass
        limit = 10 if is_premium else 5

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id FROM warnroles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                roles = await cursor.fetchall()
        
        if not roles:
            embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> No warn roles configured. Use `warnrole add <@role>`.", color=0x2b2d31)
            return await ctx.send(embed=embed)
        
        lines = "\n".join(f"> <@&{r[0]}>" for r in roles)
        embed = discord.Embed(
            description=f"- **Warn Roles [{len(roles)}/{limit}]**\n{lines}",
            color=0x2b2d31
        )
        embed.set_footer(text="Synapse - Warn Roles")
        await ctx.send(embed=embed)

    @commands.group(
        name="warnalert",
        help="Configure the warning alert system",
        invoke_without_command=True
    )
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def warnalert(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)

    @warnalert.command(name="channel", help="Set the channel for warn alerts", usage="<channel>")
    @commands.has_permissions(administrator=True)
    async def warnalert_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT message FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE warn_alerts SET channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            else:
                default_msg = "<user> You have been warned this time, next punishment <next_punishment>."
                await db.execute("INSERT INTO warn_alerts (guild_id, channel_id, message) VALUES (?, ?, ?)", (ctx.guild.id, channel.id, default_msg))
            await db.commit()
        embed = discord.Embed(description=f"<:IMPORT_thumsup:1462777656570413119> Warn alert channel set to {channel.mention}", color=0x4dff94)
        await ctx.send(embed=embed)

    @warnalert.command(name="message", help="Set the custom message for warn alerts", usage="<message>")
    @commands.has_permissions(administrator=True)
    async def warnalert_message(self, ctx, *, message: str):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE warn_alerts SET message = ? WHERE guild_id = ?", (message, ctx.guild.id))
            else:
                await db.execute("INSERT INTO warn_alerts (guild_id, channel_id, message) VALUES (?, ?, ?)", (ctx.guild.id, None, message))
            await db.commit()
        embed = discord.Embed(title="<:IMPORT_thumsup:1462777656570413119> Warn alert message updated", description=f"New Message:\n```{message}```", color=0x4dff94)
        await ctx.send(embed=embed)

    @warnalert.command(name="enable", help="Enable the warn alert system")
    @commands.has_permissions(administrator=True)
    async def warnalert_enable(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE warn_alerts SET is_enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
            else:
                default_msg = "<user> You have been warned this time, next punishment <next_punishment>."
                await db.execute("INSERT INTO warn_alerts (guild_id, channel_id, message, is_enabled) VALUES (?, ?, ?, 1)", (ctx.guild.id, None, default_msg))
            await db.commit()
        embed = discord.Embed(description="<:emoji_1769867605256:1467155817726873650> Warn alerts have been enabled.", color=0x4dff94)
        await ctx.send(embed=embed)

    @warnalert.command(name="disable", help="Disable the warn alert system")
    @commands.has_permissions(administrator=True)
    async def warnalert_disable(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("UPDATE warn_alerts SET is_enabled = 0 WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                if cursor.rowcount > 0:
                    embed = discord.Embed(description="<:emoji_1769867605256:1467155817726873650> Warn alerts have been disabled.", color=0x4dff94)
                else:
                    embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Warn alerts are not currently configured.", color=0x2b2d31)
            await db.commit()
        await ctx.send(embed=embed)

    @warnalert.command(name="reset", help="Reset and completely delete the warn alert configuration")
    @commands.has_permissions(administrator=True)
    async def warnalert_reset(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,))
            if cursor.rowcount > 0:
                embed = discord.Embed(description="<:emoji_1769867605256:1467155817726873650> Warn alert configuration has been reset and deleted.", color=0x4dff94)
            else:
                embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Warn alerts are not currently configured.", color=0x2b2d31)
            await db.commit()
        await ctx.send(embed=embed)

    @warnalert.command(name="show", help="Show current warn alert configuration", aliases=["config", "view"])
    @commands.has_permissions(administrator=True)
    async def warnalert_show(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id, message, is_enabled FROM warn_alerts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            embed = discord.Embed(description="<:SynapseExcl:1477234549552320634> Warn alerts are not configured. Use `warnalert channel` to set it up.", color=0x2b2d31)
            return await ctx.send(embed=embed)

        channel_id, message, is_enabled = row
        channel_desc = f"<#{channel_id}>" if channel_id else "None"
        status = "✅ Enabled" if is_enabled else "❌ Disabled"

        embed = discord.Embed(title="Warn Alert Configuration", color=0x2b2d31)
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Channel", value=channel_desc, inline=False)
        embed.add_field(name="Message Format", value=f"```{message}```", inline=False)
        embed.set_footer(text="Use `warnalert variables` to see available variables.")
        await ctx.send(embed=embed)

    @warnalert.command(name="variables", help="Show available variables for warn alert messages")
    @commands.has_permissions(administrator=True)
    async def warnalert_variables(self, ctx):
        embed = discord.Embed(title="Warn Alert Variables", description="You can use these variables in your custom warn alert messages:", color=0x2b2d31)
        vars_list = (
            "`<user>` : Mentions the warned user\n"
            "`<user.name>` : Name of the warned user\n"
            "`<user.id>` : ID of the warned user\n"
            "`<moderator>` : Mentions the moderator\n"
            "`<moderator.name>` : Name of the moderator\n"
            "`<moderator.id>` : ID of the moderator\n"
            "`<reason>` : Reason for the warning\n"
            "`<server>` : Name of the server\n"
            "`<server.id>` : ID of the server\n"
            "`<totalwarns>` : Total warnings of the user\n"
            "`<case_id>` : Current case/warn number\n"
            "`<current_punishment>` : Action taken (e.g., Timeout, Kick)\n"
            "`<next_punishment>` : Next automatic action if warned again\n"
        )
        embed.add_field(name="Available Variables", value=vars_list, inline=False)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Warn(client))