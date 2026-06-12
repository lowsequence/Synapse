import discord
from discord.ext import commands, tasks
import aiosqlite
import datetime
import logging
import asyncio
import io
import json
import traceback
from typing import Optional, Dict, Any, List, Union, Tuple
from collections import defaultdict

try:
    from utils import start_ignore_check as ignore_check, start_blacklist_check as blacklist_check
except ImportError:
    def ignore_check():
        return commands.check(lambda ctx: True)
    def blacklist_check():
        return commands.check(lambda ctx: True)


EMBED_COLOR = 0x2b2d31
DATABASE_PATH = "database/logging.db"

LOG_TYPES = {
    "invite": "Invite Handling (creation, deletion)",
    "emoji": "Emoji Updates (create, delete, update)",
    "sticker": "Sticker Updates (create, delete, update)",
    "guild_event": "Scheduled Events",
    "boost": "Server Boosting Events",
    "icon": "Server Icon/Banner Updates",
    "name": "Server Name/Description Updates",
    "message_edit": "Message Edits (with content diff)",
    "message_delete": "Message Deletions",
    "message_pin": "Message Pin/Unpin Events",
    "message_reaction": "Reaction Add/Remove/Clear",
    "thread": "Thread Creation, Deletion, Updates",
    "voice": "Voice Channel Joins, Leaves, Moves",
    "channel_log": "Channel Creation, Deletion, Permission Updates",
    "role_log": "Role Creation, Deletion, Updates",
    "mod_log": "Moderation Actions (Ban, Kick, Timeout)",
    "member_log": "Member Updates (Nick, Avatar, Join, Leave)",
    "alert": "Critical Server Alerts"
}

LOG_TYPE_TO_COLUMN = {
    "invite": "invite_channel",
    "emoji": "emoji_channel",
    "sticker": "sticker_channel",
    "guild_event": "guild_event_channel",
    "boost": "boost_channel",
    "icon": "icon_channel",
    "name": "name_channel",
    "message_edit": "message_edit_channel",
    "message_delete": "message_delete_channel",
    "message_pin": "message_pin_channel",
    "message_reaction": "message_reaction_channel",
    "thread": "thread_channel",
    "voice": "voice_channel",
    "channel_log": "channel_log_channel",
    "role_log": "role_log_channel",
    "mod_log": "mod_log_channel",
    "member_log": "member_log_channel",
    "alert": "alert_channel"
}


class LoggingSystem(commands.Cog):
    """
    The main logging system cog.
    Handles database connections, configuration, and event dispatching.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        self._cache: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
            'config': {},
            'disabled': set(),
            'webhooks': {}
        })
        self._db_lock = asyncio.Lock()

        self.bot.loop.create_task(self._async_init())

    async def _async_init(self):
        """Initializes the database and loads cache."""
        await self.bot.wait_until_ready()
        try:
            await self._create_tables()
            await self._load_cache()
            print("[LoggingSystem] Database initialized and cache loaded.")
        except Exception as e:
            print(f"[LoggingSystem] CRITICAL ERROR during initialization: {e}")
            traceback.print_exc()

    async def _create_tables(self):
        """Creates the necessary SQLite tables if they do not exist."""
        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS logging_config (
                        guild_id INTEGER PRIMARY KEY,
                        enabled INTEGER DEFAULT 1,
                        invite_channel INTEGER,
                        emoji_channel INTEGER,
                        sticker_channel INTEGER,
                        guild_event_channel INTEGER,
                        boost_channel INTEGER,
                        icon_channel INTEGER,
                        name_channel INTEGER,
                        message_edit_channel INTEGER,
                        message_delete_channel INTEGER,
                        message_pin_channel INTEGER,
                        message_reaction_channel INTEGER,
                        thread_channel INTEGER,
                        voice_channel INTEGER,
                        channel_log_channel INTEGER,
                        role_log_channel INTEGER,
                        mod_log_channel INTEGER,
                        member_log_channel INTEGER,
                        alert_channel INTEGER
                    )
                """)

                try:
                    await db.execute("ALTER TABLE logging_config ADD COLUMN alert_channel INTEGER")
                except Exception:
                    pass

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS disabled_logs (
                        guild_id INTEGER,
                        log_type TEXT,
                        UNIQUE(guild_id, log_type)
                    )
                """)

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS webhooks (
                        guild_id INTEGER,
                        log_type TEXT,
                        webhook_url TEXT,
                        UNIQUE(guild_id, log_type)
                    )
                """)

                await db.commit()

    async def _load_cache(self):
        """Loads configuration from database into memory to reduce SQL queries."""
        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                async with db.execute("SELECT * FROM logging_config") as cursor:
                    async for row in cursor:
                        g_id = row['guild_id']
                        self._cache[g_id]['global_enabled'] = bool(row['enabled'])
                        self._cache[g_id]['config'] = dict(row)

                async with db.execute("SELECT guild_id, log_type FROM disabled_logs") as cursor:
                    async for row in cursor:
                        self._cache[row['guild_id']]['disabled'].add(row['log_type'])

                async with db.execute("SELECT guild_id, log_type, webhook_url FROM webhooks") as cursor:
                    async for row in cursor:
                        self._cache[row['guild_id']]['webhooks'][row['log_type']] = row['webhook_url']


    async def _get_webhook(self, guild: discord.Guild, log_type: str) -> Optional[discord.Webhook]:
        """
        Retrieves or creates a webhook for the specified log type.
        Prioritizes:
        1. Cached webhook URL.
        2. Database lookup.
        3. Creation in the configured channel.
        """
        if not self._cache[guild.id].get('global_enabled', True):
            return None

        if log_type in self._cache[guild.id]['disabled']:
            return None

        col_name = LOG_TYPE_TO_COLUMN.get(log_type)
        if not col_name:
            return None

        config = self._cache[guild.id].get('config', {})
        channel_id = config.get(col_name)

        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not channel:
            return None

        cached_url = self._cache[guild.id]['webhooks'].get(log_type)
        if cached_url:
            try:
                return discord.Webhook.from_url(cached_url, client=self.bot)
            except Exception:
                pass

        target_webhook = None
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.token and wh.name == "Synapse Logging":
                    target_webhook = wh
                    break

            if not target_webhook:
                target_webhook = await channel.create_webhook(name="Synapse Logging", reason=f"Setup for {log_type}")

            await self._save_webhook(guild.id, log_type, target_webhook.url)
            return target_webhook

        except discord.Forbidden:
            return None
        except discord.HTTPException as e:
            print(f"Error managing webhook for {guild.id}:{log_type}: {e}")
            return None

    async def _save_webhook(self, guild_id: int, log_type: str, url: str):
        """Saves a webhook URL to the database and cache."""
        self._cache[guild_id]['webhooks'][log_type] = url
        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO webhooks (guild_id, log_type, webhook_url)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, log_type) DO UPDATE SET webhook_url=excluded.webhook_url
                """, (guild_id, log_type, url))
                await db.commit()

    def safe_embed(self, title: str, description: str, color: int = EMBED_COLOR) -> discord.Embed:
        """
        Creates a standardized embed with the bot's style.
        Ensures limits are met.
        """
        if len(title) > 256:
            title = title[:253] + "..."
        if description and len(description) > 4096:
            description = description[:4093] + "..."

        embed = discord.Embed(
            title=title, 
            description=description.strip() if description else "", 
            color=color, 
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text="Synapse Logging System")
        if self.bot.user.avatar:
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)
        else:
             embed.set_author(name=self.bot.user.name)
        return embed

    def _add_field(self, embed: discord.Embed, name: str, value: Any):
        """Helper to add a 'field' to the description as a blockquote."""
        if not embed.description:
            embed.description = ""
        
        # Add a newline if there's already content
        if embed.description and not embed.description.endswith("\n"):
            embed.description += "\n"
            
        embed.description += f"> **{name}:** {value}\n"
        
        # Guard for length
        if len(embed.description) > 4096:
            embed.description = embed.description[:4093] + "..."

    def _generate_diff(self, before: str, after: str) -> str:
        """
        Generates a readable difference string for logs.
        """
        if before == after:
            return "No changes."
        return f"**Before:** {before}\n**After:** {after}"


    @commands.group(name="logging", invoke_without_command=True, help="Base command for the logging system.")
    @ignore_check()
    @blacklist_check()
    async def logging_group(self, ctx):
        """Base command for the logging system."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)



    @logging_group.command(name="setup", help="Automatically sets up the logging category and channels.")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def logging_setup(self, ctx):
        """Automatically sets up the logging category and channels."""
        if not ctx.guild.me.guild_permissions.manage_channels or not ctx.guild.me.guild_permissions.manage_webhooks:
            return await ctx.send(embed=self.safe_embed("Error", "I need `Manage Channels` and `Manage Webhooks` permissions.", 0xFF0000))

        status_msg = await ctx.send(embed=self.safe_embed("Setup Started", "<a:Loadixd:1469568214169288890> Creating categories and channels... this may take a moment."))

        try:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_webhooks=True)
            }
            category = await ctx.guild.create_category("Synapse Logging", overwrites=overwrites, reason="Logging Setup")

            channel_map = {}


            layout = {
                "alert-logs": ["alert"],
                "server-logs": ["invite", "guild_event", "boost", "icon", "name"],
                "message-logs": ["message_edit", "message_delete", "message_pin", "message_reaction", "thread"],
                "voice-logs": ["voice"],
                "member-logs": ["member_log", "emoji", "sticker"],
                "role-logs": ["role_log"],
                "channel-logs": ["channel_log"],
                "mod-logs": ["mod_log"]
            }

            created_channels = {}

            for channel_name, types in layout.items():
                chan = await ctx.guild.create_text_channel(channel_name, category=category, reason="Logging Setup")
                created_channels[channel_name] = chan.id
                for t in types:
                    channel_map[LOG_TYPE_TO_COLUMN[t]] = chan.id

            async with self._db_lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cols = ", ".join(channel_map.keys())
                    placeholders = ", ".join(["?"] * len(channel_map))
                    values = list(channel_map.values())


                    columns = ["guild_id", "enabled"] + list(channel_map.keys())
                    vals = [ctx.guild.id, 1] + values

                    q_placeholders = ", ".join(["?"] * len(columns))
                    q_columns = ", ".join(columns)

                    await db.execute(f"INSERT OR REPLACE INTO logging_config ({q_columns}) VALUES ({q_placeholders})", vals)
                    await db.commit()

            await self._load_cache()

            await status_msg.edit(embed=self.safe_embed("Setup Complete", f"<:emoji_1769867605256:1467155817726873650> Created **Synapse Logging** category with {len(created_channels)} channels.\nLogging is now **ENABLED**."))

        except Exception as e:
            await status_msg.edit(embed=self.safe_embed("Setup Failed", f"<:emoji_1769867589372:1467155751456735326> An error occurred: {str(e)}", 0xFF0000))
            traceback.print_exc()

    @logging_group.command(name="channel", help="Sets the channel for a specific log type.")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    async def logging_channel(self, ctx, log_type: str, channel: discord.TextChannel):
        """Sets the channel for a specific log type."""
        log_type = log_type.lower()
        if log_type not in LOG_TYPES:
            types_list = ", ".join([f"`{t}`" for t in LOG_TYPES.keys()])
            return await ctx.send(embed=self.safe_embed("Invalid Type", f"Valid types are:\n{types_list}", 0xFF0000))

        col_name = LOG_TYPE_TO_COLUMN[log_type]

        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("INSERT OR IGNORE INTO logging_config (guild_id) VALUES (?)", (ctx.guild.id,))
                await db.execute(f"UPDATE logging_config SET {col_name} = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
                await db.commit()

        if log_type in self._cache[ctx.guild.id]['webhooks']:
            del self._cache[ctx.guild.id]['webhooks'][log_type]
            async with self._db_lock:
                 async with aiosqlite.connect(self.db_path) as db:
                     await db.execute("DELETE FROM webhooks WHERE guild_id = ? AND log_type = ?", (ctx.guild.id, log_type))
                     await db.commit()

        await self._load_cache()
        await ctx.send(embed=self.safe_embed("Channel Updated", f"<:emoji_1769867605256:1467155817726873650> **{LOG_TYPES[log_type]}** will now be logged in {channel.mention}."))

    @logging_group.command(name="disable")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    async def logging_disable(self, ctx, log_type: str):
        """Disables a specific log type."""
        if log_type not in LOG_TYPES:
            return await ctx.send(embed=self.safe_embed("Invalid Type", "Check `logging status` for valid types.", 0xFF0000))

        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("INSERT OR IGNORE INTO disabled_logs (guild_id, log_type) VALUES (?, ?)", (ctx.guild.id, log_type))
                await db.commit()

        self._cache[ctx.guild.id]['disabled'].add(log_type)
        await ctx.send(embed=self.safe_embed("Logging Disabled", f"<:emoji_1769867605256:1467155817726873650> **{LOG_TYPES[log_type]}** has been disabled."))

    @logging_group.command(name="enable")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    async def logging_enable(self, ctx, log_type: str):
        """Enables a previously disabled log type."""
        if log_type not in LOG_TYPES:
             return await ctx.send(embed=self.safe_embed("Invalid Type", "Check `logging status` for valid types.", 0xFF0000))

        async with self._db_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM disabled_logs WHERE guild_id = ? AND log_type = ?", (ctx.guild.id, log_type))
                await db.commit()

        if log_type in self._cache[ctx.guild.id]['disabled']:
            self._cache[ctx.guild.id]['disabled'].remove(log_type)

        await ctx.send(embed=self.safe_embed("Logging Enabled", f"<:emoji_1769867605256:1467155817726873650> **{LOG_TYPES[log_type]}** has been re-enabled."))

    @logging_group.command(name="status")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    async def logging_status(self, ctx):
        """Shows the current logging configuration."""
        config = self._cache[ctx.guild.id].get('config', {})
        disabled = self._cache[ctx.guild.id].get('disabled', set())

        embed = self.safe_embed(f"Logging Configuration for {ctx.guild.name}", "")

        categories = {
            "Server": ["invite", "emoji", "sticker", "guild_event", "boost", "icon", "name"],
            "Message": ["message_edit", "message_delete", "message_pin", "message_reaction", "thread"],
            "Voice": ["voice"],
            "Members & Roles": ["member_log", "role_log", "channel_log", "mod_log"]
        }

        for cat_name, types in categories.items():
            lines = []
            for t in types:
                status_icon = "<:emoji_1769867589372:1467155751456735326>" if t in disabled else "<:emoji_1769867605256:1467155817726873650>"

                col = LOG_TYPE_TO_COLUMN.get(t)
                chan_id = config.get(col)
                chan_mention = f"<#{chan_id}>" if chan_id else "`Not Set`"

                lines.append(f"{status_icon} **{t}**: {chan_mention}")

            embed.add_field(name=cat_name, value="\n".join(lines), inline=False)

        await ctx.send(embed=embed)

    @logging_group.command(name="cleanup", help="DANGER: Completely removes the logging system.")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(administrator=True)
    async def logging_cleanup(self, ctx):
        """DANGER: Completely removes the logging system."""
        async with ctx.typing():
            deleted_channels = 0
            config = self._cache[ctx.guild.id].get('config', {})

            channel_ids = set()
            for chan_id in config.values():
                if chan_id:
                    channel_ids.add(chan_id)

            logging_category = None
            for c_id in channel_ids:
                channel = ctx.guild.get_channel(c_id)
                if channel:
                    if not logging_category and channel.category:
                         if channel.category.name == "Synapse Logging":
                             logging_category = channel.category

                    try:
                        await channel.delete(reason="Logging Cleanup")
                        deleted_channels += 1
                    except:
                        pass

            if logging_category:
                try:
                    if not logging_category.channels:
                        await logging_category.delete(reason="Logging Cleanup")
                    else:
                        await logging_category.delete(reason="Logging Cleanup")
                except:
                    pass

            async with self._db_lock:
                 async with aiosqlite.connect(self.db_path) as db:
                     async with db.execute("SELECT webhook_url FROM webhooks WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                         async for row in cursor:
                             try:
                                 wh = discord.Webhook.from_url(row[0], client=self.bot)
                                 await wh.delete(reason="Logging Cleanup")
                             except:
                                 pass

                     await db.execute("DELETE FROM logging_config WHERE guild_id = ?", (ctx.guild.id,))
                     await db.execute("DELETE FROM webhooks WHERE guild_id = ?", (ctx.guild.id,))
                     await db.execute("DELETE FROM disabled_logs WHERE guild_id = ?", (ctx.guild.id,))
                     await db.commit()

            if ctx.guild.id in self._cache:
                del self._cache[ctx.guild.id]

        await ctx.send(embed=self.safe_embed("System Removed", f"<:emoji_1769867605256:1467155817726873650> Deleted **{deleted_channels}** channels and cleared all configuration definitions."))

    @logging_group.error
    async def logging_error(self, ctx, error):      
        if isinstance(error, commands.BadArgument):
             await ctx.send(embed=self.safe_embed("Invalid Argument", str(error), 0xF04747))
        else:
            await ctx.send(embed=self.safe_embed("Error", f"An unexpected error occurred: {str(error)}", 0xF04747))
            traceback.print_exc()


    async def _get_audit_log_entry(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int) -> Optional[discord.AuditLogEntry]:
        """
        Helper to fetch the most recent audit log entry for a specific action and target.
        Used to identify WHO performed an action.
        """
        try:
            async for entry in guild.audit_logs(limit=5, action=action):
                if entry.target.id == target_id:
                    if (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 10:
                        return entry
        except (discord.Forbidden, discord.HTTPException):
            return None
        return None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        webhook = await self._get_webhook(member.guild, "member_log")
        if not webhook:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        created_at = member.created_at
        age = now - created_at

        embed = self.safe_embed(f"Member Joined: {member.name}", "", 0x43B581)
        embed.set_thumbnail(url=member.display_avatar.url)
        self._add_field(embed, "User", f"{member.mention} (`{member.id}`)")
        self._add_field(embed, "Created At", f"{discord.utils.format_dt(created_at, 'R')} (`{created_at.strftime('%Y-%m-%d %H:%M:%S')}`)")

        if age.total_seconds() < 86400:
            embed.description = "⚠️ **New Account** (Created < 24h ago)"
            embed.color = 0xFFCC00

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        kick_entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.kick, member.id)

        if kick_entry:
            mod_webhook = await self._get_webhook(guild, "mod_log")
            if mod_webhook:
                embed = self.safe_embed(f"Member Kicked: {member.name}", "", 0xF04747)
                embed.set_thumbnail(url=member.display_avatar.url)
                self._add_field(embed, "User", f"{member.mention} (`{member.id}`)")
                self._add_field(embed, "Moderator", f"{kick_entry.user.mention}")
                self._add_field(embed, "Reason", kick_entry.reason or "No reason provided.")
                await mod_webhook.send(embed=embed)
                return

        webhook = await self._get_webhook(guild, "member_log")
        if not webhook:
            return

        embed = self.safe_embed(f"Member Left: {member.name}", "", 0xF04747)
        embed.set_thumbnail(url=member.display_avatar.url)
        self._add_field(embed, "User", f"{member.mention} (`{member.id}`)")

        roles = [r.mention for r in member.roles if r != guild.default_role]
        if roles:
            val = ", ".join(roles) if len(", ".join(roles)) < 1024 else f"{len(roles)} roles"
            self._add_field(embed, "Roles", val)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]):
        webhook = await self._get_webhook(guild, "mod_log")
        if not webhook:
            return

        entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.ban, user.id)
        moderator = entry.user if entry else "Unknown"
        reason = entry.reason if entry else "No reason provided."

        embed = self.safe_embed(f"Member Banned: {user.name}", "", 0xFF0000)
        embed.set_thumbnail(url=user.display_avatar.url)
        self._add_field(embed, "User", f"{user.mention} (`{user.id}`)")
        mod_val = moderator.mention if isinstance(moderator, (discord.Member, discord.User)) else moderator
        self._add_field(embed, "Moderator", mod_val)
        self._add_field(embed, "Reason", reason)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        webhook = await self._get_webhook(guild, "mod_log")
        if not webhook:
            return

        entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.unban, user.id)
        moderator = entry.user if entry else "Unknown"

        embed = self.safe_embed(f"Member Unbanned: {user.name}", "", 0x43B581)
        embed.set_thumbnail(url=user.display_avatar.url)
        self._add_field(embed, "User", f"{user.mention} (`{user.id}`)")
        mod_val = moderator.mention if isinstance(moderator, (discord.Member, discord.User)) else moderator
        self._add_field(embed, "Moderator", mod_val)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild

        if before.nick != after.nick:
            webhook = await self._get_webhook(guild, "member_log")
            if webhook:
                embed = self.safe_embed(f"Nickname Changed: {after.name}", "")
                embed.set_author(name=after.name, icon_url=after.display_avatar.url)
                self._add_field(embed, "User", after.mention)
                self._add_field(embed, "Before", f"`{before.nick}`" if before.nick else "`None`")
                self._add_field(embed, "After", f"`{after.nick}`" if after.nick else "`None`")
                await webhook.send(embed=embed)

        if before.roles != after.roles:
             webhook = await self._get_webhook(guild, "member_log")
             if webhook:
                added = list(set(after.roles) - set(before.roles))
                removed = list(set(before.roles) - set(after.roles))

                if added or removed:
                    embed = self.safe_embed(f"Roles Updated: {after.name}", "")
                    embed.set_author(name=after.name, icon_url=after.display_avatar.url)
                    self._add_field(embed, "User", after.mention)

                    if added:
                        self._add_field(embed, "Added Roles", ", ".join([r.mention for r in added]))
                    if removed:
                        self._add_field(embed, "Removed Roles", ", ".join([r.mention for r in removed]))

                    await webhook.send(embed=embed)

        if before.timed_out_until != after.timed_out_until:
            webhook = await self._get_webhook(guild, "mod_log")
            if webhook:
                if after.timed_out_until:
                    entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.member_update, after.id)
                    mod = entry.user if entry else "Unknown"
                    reason = entry.reason if entry else "No reason provided"

                    embed = self.safe_embed(f"Member Timed Out: {after.name}", "", 0xFFCC00)
                    embed.set_author(name=after.name, icon_url=after.display_avatar.url)
                    self._add_field(embed, "User", after.mention)
                    mod_mention = mod.mention if isinstance(mod, discord.Member) else mod
                    self._add_field(embed, "Moderator", mod_mention)
                    self._add_field(embed, "Until", discord.utils.format_dt(after.timed_out_until, 'F'))
                    self._add_field(embed, "Reason", reason)
                    await webhook.send(embed=embed)
                else:
                    entry = await self._get_audit_log_entry(guild, discord.AuditLogAction.member_update, after.id)
                    mod = entry.user if entry else "Unknown"

                    embed = self.safe_embed(f"Timeout Removed: {after.name}", "", 0x43B581)
                    self._add_field(embed, "User", after.mention)
                    mod_mention = mod.mention if isinstance(mod, discord.Member) else mod
                    self._add_field(embed, "Moderator", mod_mention)
                    await webhook.send(embed=embed)

        if before.guild_avatar != after.guild_avatar:
             webhook = await self._get_webhook(guild, "member_log")
             if webhook:
                embed = self.safe_embed(f"Server Avatar Updated: {after.name}", "")
                embed.set_thumbnail(url=after.display_avatar.url)
                self._add_field(embed, "User", after.mention)
                b_url = before.guild_avatar.url if before.guild_avatar else "None"
                a_url = after.guild_avatar.url if after.guild_avatar else "None"
                self._add_field(embed, "Links", f"[Before]({b_url}) -> [After]({a_url})")
                await webhook.send(embed=embed)


    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.bot or not after.guild:
            return
        if before.content == after.content:
            return

        webhook = await self._get_webhook(after.guild, "message_edit")
        if not webhook:
            return

        embed = self.safe_embed(f"Message Edited in #{after.channel.name}", f"[Jump to Message]({after.jump_url})")
        embed.set_author(name=after.author.name, icon_url=after.author.display_avatar.url)
        self._add_field(embed, "Author", after.author.mention)
        self._add_field(embed, "Channel", after.channel.mention)

        b_content = before.content if before.content else "[No Text Content]"
        a_content = after.content if after.content else "[No Text Content]"
        if len(b_content) > 1024: b_content = b_content[:1021] + "..."
        if len(a_content) > 1024: a_content = a_content[:1021] + "..."

        self._add_field(embed, "Before", b_content)
        self._add_field(embed, "After", a_content)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        webhook = await self._get_webhook(message.guild, "message_delete")
        if not webhook:
            return

        embed = self.safe_embed(f"Message Deleted in #{message.channel.name}", "")
        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
        self._add_field(embed, "Author", message.author.mention)
        self._add_field(embed, "Channel", message.channel.mention)

        content = message.content if message.content else "[No Text Content/Media Only]"
        if len(content) > 1024: content = content[:1021] + "..."
        self._add_field(embed, "Content", content)

        if message.attachments:
            att_list = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
            self._add_field(embed, "Attachments", att_list)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        if not messages:
            return

        sample = messages[0]
        if not sample.guild:
            return

        webhook = await self._get_webhook(sample.guild, "message_delete")
        if not webhook:
            return

        buffer = io.StringIO()
        buffer.write(f"Bulk Delete Report - {datetime.datetime.now()}\n")
        buffer.write(f"Channel: #{sample.channel.name} ({sample.channel.id})\n")
        buffer.write(f"Count: {len(messages)}\n\n")

        for m in sorted(messages, key=lambda x: x.created_at):
            buffer.write(f"[{m.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {m.author} ({m.author.id}): {m.content}\n")
            if m.attachments:
                buffer.write(f"   [Attachments: {', '.join([a.filename for a in m.attachments])}]\n")

        buffer.seek(0)
        file_obj = discord.File(buffer, filename=f"deleted_messages_{int(datetime.datetime.now().timestamp())}.txt")

        embed = self.safe_embed("Bulk Message Delete", f"**{len(messages)}** messages were deleted in {sample.channel.mention}.")
        await webhook.send(embed=embed, file=file_obj)

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel: Union[discord.TextChannel, discord.Thread], last_pin: Optional[datetime.datetime]):
        if not channel.guild:
            return

        webhook = await self._get_webhook(channel.guild, "message_pin")
        if not webhook:
            return

        embed = self.safe_embed(f"Channel Pins Updated", f"Pins were updated in {channel.mention}.")
        await webhook.send(embed=embed)


    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        webhook = await self._get_webhook(thread.guild, "thread")
        if not webhook:
            return

        embed = self.safe_embed(f"Thread Created: {thread.name}", f"In channel: {thread.parent.mention if thread.parent else 'Unknown'}")

        entry = await self._get_audit_log_entry(thread.guild, discord.AuditLogAction.thread_create, thread.id)
        if entry:
             self._add_field(embed, "Created By", entry.user.mention)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        webhook = await self._get_webhook(thread.guild, "thread")
        if not webhook:
            return

        embed = self.safe_embed(f"Thread Deleted: {thread.name}", f"Parent channel: {thread.parent.mention if thread.parent else 'Unknown'}", 0xF04747)
        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.name == after.name and before.archived == after.archived and before.locked == after.locked:
            return

        webhook = await self._get_webhook(after.guild, "thread")
        if not webhook:
            return

        embed = self.safe_embed(f"Thread Updated: {after.name}", f"Thread: {after.mention}")

        if before.name != after.name:
            self._add_field(embed, "Name Change", f"**From:** {before.name}\n**To:** {after.name}")

        if before.archived != after.archived:
            self._add_field(embed, "Archive Status", "Archived" if after.archived else "Unarchived")

        if before.locked != after.locked:
            self._add_field(embed, "Lock Status", "Locked" if after.locked else "Unlocked")

        await webhook.send(embed=embed)



    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        webhook = await self._get_webhook(role.guild, "role_log")
        if not webhook:
            return

        embed = self.safe_embed(f"Role Created: {role.name}", "", 0x43B581)
        self._add_field(embed, "Role", role.mention)

        entry = await self._get_audit_log_entry(role.guild, discord.AuditLogAction.role_create, role.id)
        if entry:
            self._add_field(embed, "Created By", entry.user.mention)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        webhook = await self._get_webhook(role.guild, "role_log")
        if not webhook:
            return

        embed = self.safe_embed(f"Role Deleted: {role.name}", "", 0xF04747)

        entry = await self._get_audit_log_entry(role.guild, discord.AuditLogAction.role_delete, role.id)
        if entry:
             self._add_field(embed, "Deleted By", entry.user.mention)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        webhook = await self._get_webhook(after.guild, "role_log")
        if not webhook:
            return

        if before.name == after.name and before.color == after.color and before.permissions == after.permissions and before.hoist == after.hoist and before.mentionable == after.mentionable:
            return

        embed = self.safe_embed(f"Role Updated: {after.name}", f"Role: {after.mention}")

        if before.name != after.name:
            self._add_field(embed, "Name", self._generate_diff(before.name, after.name))

        if before.color != after.color:
             self._add_field(embed, "Color", f"{before.color} -> {after.color}")

        if before.hoist != after.hoist:
             self._add_field(embed, "Hoisted", f"{before.hoist} -> {after.hoist}")

        if before.mentionable != after.mentionable:
             self._add_field(embed, "Mentionable", f"{before.mentionable} -> {after.mentionable}")

        if before.permissions != after.permissions:
            diff = []
            for perm, val in after.permissions:
                before_val = getattr(before.permissions, perm)
                if val != before_val:
                    diff.append(f"{'+' if val else '-'} {perm.replace('_', ' ').title()}")

            if diff:
                chunked_diff = "\n".join(diff)
                if len(chunked_diff) > 1024: chunked_diff = chunked_diff[:1020] + "..."
                self._add_field(embed, "Permission Changes", f"```diff\n{chunked_diff}\n```")

        await webhook.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        webhook = await self._get_webhook(channel.guild, "channel_log")
        if not webhook:
            return

        embed = self.safe_embed(f"Channel Created: {channel.name}", f"Type: {channel.type}", 0x43B581)
        self._add_field(embed, "Channel", channel.mention)

        entry = await self._get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if entry:
            self._add_field(embed, "Created By", entry.user.mention)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        webhook = await self._get_webhook(channel.guild, "channel_log")
        if not webhook:
            return

        embed = self.safe_embed(f"Channel Deleted: {channel.name}", f"Type: {channel.type}", 0xF04747)

        entry = await self._get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if entry:
             self._add_field(embed, "Deleted By", entry.user.mention)

        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        webhook = await self._get_webhook(after.guild, "channel_log")
        if not webhook:
            return

        if before.name == after.name and before.category == after.category and before.position == after.position and before.overwrites == after.overwrites:
            return

        embed = self.safe_embed(f"Channel Updated: {after.name}", f"Channel: {after.mention}")

        if before.name != after.name:
            self._add_field(embed, "Name", f"`{before.name}` -> `{after.name}`")

        if before.category != after.category:
            self._add_field(embed, "Category", f"{before.category} -> {after.category}")

        if before.overwrites != after.overwrites:
            self._add_field(embed, "Permissions", "Channel permissions/overwrites were updated.")

        await webhook.send(embed=embed)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Logs voice channel joins, leaves, moves, and state changes (mute/deaf/stream).
        """
        webhook = await self._get_webhook(member.guild, "voice")
        if not webhook:
            return

        if not before.channel and after.channel:
            embed = self.safe_embed(f"Voice Join", "", 0x43B581)
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            embed.description = f"{member.mention} joined **{after.channel.name}**"
            await webhook.send(embed=embed)
            return

        if before.channel and not after.channel:
            embed = self.safe_embed(f"Voice Leave", "", 0xF04747)
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            embed.description = f"{member.mention} left **{before.channel.name}**"
            await webhook.send(embed=embed)
            return

        if before.channel and after.channel and before.channel != after.channel:
            embed = self.safe_embed(f"Voice Move", "", EMBED_COLOR)
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            embed.description = f"{member.mention} moved from **{before.channel.name}** to **{after.channel.name}**"
            await webhook.send(embed=embed)
            return

        changes = []
        if before.self_mute != after.self_mute:
            changes.append(f"Self Mute: {'Enabled' if after.self_mute else 'Disabled'}")
        if before.self_deaf != after.self_deaf:
            changes.append(f"Self Deafen: {'Enabled' if after.self_deaf else 'Disabled'}")
        if before.self_stream != after.self_stream:
            changes.append(f"Stream: {'Started' if after.self_stream else 'Stopped'}")
        if before.self_video != after.self_video:
            changes.append(f"Camera: {'Started' if after.self_video else 'Stopped'}")

        if changes:
             embed = self.safe_embed(f"Voice State Update", "\n".join(changes))
             embed.set_author(name=member.name, icon_url=member.display_avatar.url)
             self._add_field(embed, "Channel", after.channel.name if after.channel else "None")
             await webhook.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        webhook = await self._get_webhook(after, "name") 
        if not webhook:
            webhook = await self._get_webhook(after, "icon")

        if not webhook:
            return

        embed = self.safe_embed(f"Server Updated", "")

        if before.name != after.name:
            self._add_field(embed, "Name", f"`{before.name}` -> `{after.name}`")
        if before.description != after.description:
             self._add_field(embed, "Description Updated", "Description was modified.")
        if before.verification_level != after.verification_level:
            self._add_field(embed, "Verification Level", f"{before.verification_level} -> {after.verification_level}")

        if before.icon != after.icon:
             w_icon = await self._get_webhook(after, "icon")
             if w_icon:
                 e_icon = self.safe_embed("Server Icon Updated", "")
                 e_icon.set_thumbnail(url=after.icon.url if after.icon else "")
                 await w_icon.send(embed=e_icon)

        if embed.description and embed.description != "":
            await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        webhook = await self._get_webhook(invite.guild, "invite")
        if not webhook:
            return

        embed = self.safe_embed(f"Invite Created", f"Code: `{invite.code}`", 0x43B581)
        self._add_field(embed, "Channel", invite.channel.mention if invite.channel else "Unknown")
        self._add_field(embed, "Inviter", invite.inviter.mention if invite.inviter else "Unknown")
        self._add_field(embed, "Max Uses", str(invite.max_uses) if invite.max_uses else "Infinite")
        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        webhook = await self._get_webhook(invite.guild, "invite")
        if not webhook:
            return

        embed = self.safe_embed(f"Invite Deleted", f"Code: `{invite.code}`", 0xF04747)
        if invite.channel:
             self._add_field(embed, "Channel", invite.channel.mention)
        await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: List[discord.Emoji], after: List[discord.Emoji]):
        webhook = await self._get_webhook(guild, "emoji")
        if not webhook:
            return

        added = set(after) - set(before)
        removed = set(before) - set(after)

        if added:
             for e in added:
                embed = self.safe_embed(f"Emoji Added: {e.name}", "", 0x43B581)
                embed.set_thumbnail(url=e.url)
                self._add_field(embed, "ID", e.id)
                await webhook.send(embed=embed)

        if removed:
             for e in removed:
                embed = self.safe_embed(f"Emoji Deleted: {e.name}", "", 0xF04747)
                embed.set_thumbnail(url=e.url)
                self._add_field(embed, "ID", e.id)
                await webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: List[discord.Sticker], after: List[discord.Sticker]):
        webhook = await self._get_webhook(guild, "sticker")
        if not webhook:
            return

        added = set(after) - set(before)
        removed = set(before) - set(after)

        if added:
             for s in added:
                embed = self.safe_embed(f"Sticker Added: {s.name}", "", 0x43B581)
                embed.set_thumbnail(url=s.url)
                await webhook.send(embed=embed)

        if removed:
             for s in removed:
                embed = self.safe_embed(f"Sticker Deleted: {s.name}", "", 0xF04747)
                embed.set_thumbnail(url=s.url)
                await webhook.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LoggingSystem(bot))

