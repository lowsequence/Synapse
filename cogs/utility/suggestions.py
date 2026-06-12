import discord
from discord.ext import commands
import aiosqlite
import time

from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/suggestions.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS suggest_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                log_channel_id INTEGER,
                manager_role_id INTEGER,
                anonymous INTEGER NOT NULL DEFAULT 0,
                dm_notify INTEGER NOT NULL DEFAULT 1,
                count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_id INTEGER,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT,
                created_at REAL NOT NULL
            );
        """)
        await db.commit()


async def get_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT channel_id, log_channel_id, manager_role_id, anonymous, dm_notify, count FROM suggest_config WHERE guild_id = ?", (guild_id,)) as cur:
            return await cur.fetchone()


async def ensure_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO suggest_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()


class SuggestionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Upvote", style=discord.ButtonStyle.secondary, custom_id="suggest_upvote")
    async def upvote(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.send_message("Vote recorded!", ephemeral=True)

    @discord.ui.button(label="Downvote", style=discord.ButtonStyle.secondary, custom_id="suggest_downvote")
    async def downvote(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.send_message("Vote recorded!", ephemeral=True)


class SuggestionsCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def suggestion(self, ctx):
        """Suggestion system parent command."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help suggestion` for a list of subcommands.")

    @suggestion.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_setup(self, ctx, channel: discord.TextChannel):
        """Set up the suggestion channel."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion channel set to {channel.mention}.")

    @suggestion.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_channel(self, ctx, channel: discord.TextChannel):
        """Change suggestion channel."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion channel updated to {channel.mention}.")

    @suggestion.command(name="logchannel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_logchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel for suggestion actions."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET log_channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion log channel set to {channel.mention}.")

    @suggestion.command(name="managerrole")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_managerrole(self, ctx, role: discord.Role):
        """Set suggestion manager role."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET manager_role_id = ? WHERE guild_id = ?", (role.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion manager role set to {role.mention}.")

    @suggestion.command(name="anonymous")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_anonymous(self, ctx):
        """Toggle anonymous suggestions."""
        await ensure_config(ctx.guild.id)
        cfg = await get_config(ctx.guild.id)
        new = 0 if cfg and cfg[3] else 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET anonymous = ? WHERE guild_id = ?", (new, ctx.guild.id))
            await db.commit()
        state = "enabled" if new else "disabled"
        await ctx.reply(f"{E_OK} Anonymous suggestions are now **{state}**.")

    @suggestion.command(name="dmnotify")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_dmnotify(self, ctx):
        """Toggle DM notifications for suggestion updates."""
        await ensure_config(ctx.guild.id)
        cfg = await get_config(ctx.guild.id)
        new = 0 if cfg and cfg[4] else 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET dm_notify = ? WHERE guild_id = ?", (new, ctx.guild.id))
            await db.commit()
        state = "enabled" if new else "disabled"
        await ctx.reply(f"{E_OK} DM notifications are now **{state}**.")

    @suggestion.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_config(self, ctx):
        """View suggestion config."""
        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg[0]:
            return await ctx.reply(f"{E_ERR} Suggestions are not configured yet. Use `suggestion setup #channel`.")

        ch = ctx.guild.get_channel(cfg[0])
        log_ch = ctx.guild.get_channel(cfg[1]) if cfg[1] else None
        mgr = ctx.guild.get_role(cfg[2]) if cfg[2] else None

        embed = discord.Embed(title="<:suggest:1495399041129779211> Suggestion Config", color=EMBED_COLOR)
        embed.add_field(name="Channel", value=ch.mention if ch else "Not set")
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        embed.add_field(name="Manager Role", value=mgr.mention if mgr else "Not set")
        embed.add_field(name="Anonymous", value="Enabled" if cfg[3] else "Disabled")
        embed.add_field(name="DM Notify", value="Enabled" if cfg[4] else "Disabled")
        embed.add_field(name="Total Suggestions", value=str(cfg[5]))
        await ctx.reply(embed=embed, mention_author=False)

    @suggestion.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_reset(self, ctx):
        """Reset all suggestion settings."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM suggest_config WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM suggestions WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion system has been fully reset for this server.")

    async def _update_status(self, ctx, suggestion_id: int, status: str, reason: str = None):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, message_id, content FROM suggestions WHERE id = ? AND guild_id = ?", (suggestion_id, ctx.guild.id)) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.reply(f"{E_ERR} Suggestion `#{suggestion_id}` not found.")

            await db.execute("UPDATE suggestions SET status = ?, reason = ? WHERE id = ?", (status, reason, suggestion_id))
            await db.commit()

        color_map = {"approved": 0x57f287, "denied": 0xed4245, "considered": 0xfee75c, "implemented": 0x5865f2}
        color = color_map.get(status, EMBED_COLOR)
        reason_text = reason or "No reason provided."

        embed = discord.Embed(title=f"Suggestion #{suggestion_id} — {status.title()}", description=row[2], color=color)
        embed.add_field(name="Reason", value=reason_text, inline=False)
        embed.set_footer(text=f"Action by {ctx.author.name}")
        await ctx.reply(embed=embed, mention_author=False)

        cfg = await get_config(ctx.guild.id)
        if cfg and cfg[4]:
            user = ctx.guild.get_member(row[0])
            if user:
                try:
                    await user.send(f"Your suggestion `#{suggestion_id}` in **{ctx.guild.name}** has been **{status}**.\nReason: {reason_text}")
                except Exception:
                    pass

    @suggestion.command(name="approve")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_approve(self, ctx, suggestion_id: int, *, reason: str = None):
        """Approve a suggestion."""
        await self._update_status(ctx, suggestion_id, "approved", reason)

    @suggestion.command(name="deny")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_deny(self, ctx, suggestion_id: int, *, reason: str = None):
        """Deny a suggestion."""
        await self._update_status(ctx, suggestion_id, "denied", reason)

    @suggestion.command(name="consider")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_consider(self, ctx, suggestion_id: int, *, reason: str = None):
        """Mark a suggestion as being considered."""
        await self._update_status(ctx, suggestion_id, "considered", reason)

    @suggestion.command(name="implement")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_implement(self, ctx, suggestion_id: int, *, reason: str = None):
        """Mark a suggestion as implemented."""
        await self._update_status(ctx, suggestion_id, "implemented", reason)

    @suggestion.command(name="delete")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def suggestion_delete(self, ctx, suggestion_id: int):
        """Delete a suggestion."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id FROM suggestions WHERE id = ? AND guild_id = ?", (suggestion_id, ctx.guild.id)) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.reply(f"{E_ERR} Suggestion `#{suggestion_id}` not found.")
            await db.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Suggestion `#{suggestion_id}` deleted.")

    @suggestion.command(name="info")
    @blacklist_check()
    @ignore_check()
    async def suggestion_info(self, ctx, suggestion_id: int):
        """View info about a suggestion."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, content, status, reason, created_at FROM suggestions WHERE id = ? AND guild_id = ?", (suggestion_id, ctx.guild.id)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} Suggestion `#{suggestion_id}` not found.")

        uid, content, status, reason, created = row
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"

        embed = discord.Embed(title=f"Suggestion #{suggestion_id}", description=content, color=EMBED_COLOR)
        embed.add_field(name="Author", value=name)
        embed.add_field(name="Status", value=status.title())
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="suggest")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def suggest(self, ctx, *, text: str):
        """Submit a suggestion."""
        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg[0]:
            return await ctx.reply(f"{E_ERR} Suggestions are not configured. Ask an admin to run `suggestion setup`.")

        channel = ctx.guild.get_channel(cfg[0])
        if not channel:
            return await ctx.reply(f"{E_ERR} Suggestion channel not found.")

        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggest_config SET count = count + 1 WHERE guild_id = ?", (ctx.guild.id,))
            async with db.execute("SELECT count FROM suggest_config WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                count = (await cur.fetchone())[0]

            await db.execute(
                "INSERT INTO suggestions (guild_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, ctx.author.id, text, time.time())
            )
            async with db.execute("SELECT last_insert_rowid()") as cur:
                sid = (await cur.fetchone())[0]
            await db.commit()

        is_anon = cfg[3]
        author_text = "Anonymous" if is_anon else ctx.author.display_name

        embed = discord.Embed(
            title=f"<:suggest:1495399041129779211> Suggestion #{sid}",
            description=text,
            color=0xfee75c,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Submitted by {author_text} • Status: Pending")

        msg = await channel.send(embed=embed, view=SuggestionView())

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE suggestions SET message_id = ? WHERE id = ?", (msg.id, sid))
            await db.commit()

        await ctx.reply(f"{E_OK} Your suggestion has been submitted as **#{sid}**!", mention_author=False)


async def setup(client):
    await init_db()
    await client.add_cog(SuggestionsCog(client))
