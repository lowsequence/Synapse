import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
from typing import Optional

from utils.Tools import blacklist_check, ignore_check

E_OK = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"
FOOTER = "Synapse - Confessions"

DB_PATH = os.path.join("database", "confessions.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                log_channel_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS counters (
                guild_id INTEGER PRIMARY KEY,
                last_id INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS logs (
                guild_id INTEGER,
                confession_id INTEGER,
                author_id INTEGER,
                message_id INTEGER,
                log_message_id INTEGER,
                content TEXT,
                timestamp INTEGER,
                PRIMARY KEY (guild_id, confession_id)
            );
            CREATE TABLE IF NOT EXISTS bans (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        try:
            await db.execute("ALTER TABLE config ADD COLUMN last_msg_id INTEGER")
        except Exception:
            pass
        await db.commit()

def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=0x2b2d31)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str, color: int = 0x2b2d31) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=color)
    e.set_footer(text=FOOTER)
    return e


class ConfessionModal(discord.ui.Modal, title='Send a Confession'):
    def __init__(self, bot, guild, reply_id=None):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.reply_id = reply_id

        self.confession_text = discord.ui.TextInput(
            label='Your Confession' if not reply_id else f'Reply to #{reply_id}',
            style=discord.TextStyle.paragraph,
            placeholder='Type your secret here... It will be completely anonymous!',
            required=True,
            max_length=3000
        )
        self.add_item(self.confession_text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = self.bot.get_cog("Confessions")
        if not cog:
            return await interaction.followup.send(embed=_err("Confession system is currently unavailable."))

        success, msg = await cog.process_confession(
            interaction.user,
            self.guild,
            self.confession_text.value,
            self.reply_id
        )
        if success:
             await interaction.followup.send(embed=_ok(msg), ephemeral=True)
        else:
             await interaction.followup.send(embed=_err(msg), ephemeral=True)


class ConfessionPanel(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Send Confession", style=discord.ButtonStyle.primary, custom_id="confess_btn_send")
    async def send_confession(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM bans WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id)) as c:
                if await c.fetchone():
                    return await interaction.response.send_message(embed=_err("You have been blocked from using confessions in this server."), ephemeral=True)

        modal = ConfessionModal(self.bot, interaction.guild)
        await interaction.response.send_modal(modal)


class ConfessionPostView(discord.ui.View):
    def __init__(self, bot, confession_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.confession_id = confession_id

    @discord.ui.button(label="Submit Confession", style=discord.ButtonStyle.primary)
    async def send_confession(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM bans WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id)) as c:
                if await c.fetchone():
                    return await interaction.response.send_message(embed=_err("You have been blocked from using confessions in this server."), ephemeral=True)
        modal = ConfessionModal(self.bot, interaction.guild)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.secondary)
    async def reply_confession(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM bans WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id)) as c:
                if await c.fetchone():
                    return await interaction.response.send_message(embed=_err("You have been blocked from using confessions in this server."), ephemeral=True)
        modal = ConfessionModal(self.bot, interaction.guild, reply_id=self.confession_id)
        await interaction.response.send_modal(modal)


class Confessions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(init_db())
        self.bot.add_view(ConfessionPanel(self.bot))

    async def get_next_id(self, guild_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO counters (guild_id, last_id) VALUES (?, 0)", (guild_id,))
            await db.execute("UPDATE counters SET last_id = last_id + 1 WHERE guild_id = ?", (guild_id,))
            async with db.execute("SELECT last_id FROM counters WHERE guild_id = ?", (guild_id,)) as c:
                row = await c.fetchone()
                new_id = row[0]
            await db.commit()
            return new_id

    async def process_confession(self, author: discord.Member, guild: discord.Guild, text: str, reply_id: Optional[int] = None):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM bans WHERE guild_id = ? AND user_id = ?", (guild.id, author.id)) as c:
                if await c.fetchone():
                    return False, "You have been blocked from using confessions in this server."

            async with db.execute("SELECT channel_id, log_channel_id, last_msg_id FROM config WHERE guild_id = ?", (guild.id,)) as c:
                row = await c.fetchone()
                if not row or not row[0]:
                    return False, "The confession system is not fully set up. Admins must set a channel using `confession setup`."

                channel_id = row[0]
                log_channel_id = row[1]
                last_msg_id = row[2] if len(row) > 2 else None

        chan = guild.get_channel(channel_id)
        if not chan:
            return False, "The configured confession channel could not be found."

        confession_id = await self.get_next_id(guild.id)

        title = f"Anonymous Confession #{confession_id}"
        if reply_id:
            title = f"Anonymous Reply to #{reply_id}"

        embed = discord.Embed(title=title, description=text, color=0x2b2d31)
        embed.set_footer(text="To reply: click the Reply button below!")
        embed.timestamp = discord.utils.utcnow()

        if last_msg_id:
            try:
                old_msg = await chan.fetch_message(last_msg_id)
                await old_msg.edit(view=None)
            except Exception:
                pass

        view = ConfessionPostView(self.bot, confession_id)
        try:
            public_msg = await chan.send(embed=embed, view=view)
        except discord.Forbidden:
            return False, "I do not have permissions to send messages in the confession channel."

        log_msg_id = None
        if log_channel_id:
            log_chan = guild.get_channel(log_channel_id)
            if log_chan:
                log_embed = discord.Embed(title=f"Confession #{confession_id} Log", color=0x2b2d31)
                log_embed.add_field(name="Author", value=f"{author.mention} (`{author.id}`)")
                if reply_id:
                    log_embed.add_field(name="Reply To", value=f"#{reply_id}")
                log_embed.add_field(name="Content", value=text[:1000])
                log_embed.set_footer(text=f"Confession ID: {confession_id}")
                log_embed.timestamp = discord.utils.utcnow()
                try:
                    log_msg = await log_chan.send(embed=log_embed)
                    log_msg_id = log_msg.id
                except Exception:
                    pass

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO logs (guild_id, confession_id, author_id, message_id, log_message_id, content, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (guild.id, confession_id, author.id, public_msg.id, log_msg_id, text, int(discord.utils.utcnow().timestamp())))
            await db.execute("UPDATE config SET last_msg_id = ? WHERE guild_id = ?", (public_msg.id, guild.id))
            await db.commit()

        return True, f"Successfully sent your confession anonymously! ID: `#{confession_id}`"

    @commands.hybrid_group(name="confession", aliases=["confessions"], help="Anonymous confession system", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def confession(self, ctx, *, message: str = None):
        if message:
            await self.confess_subcmd(ctx, message=message)
        else:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                return await help_cog.send_group_help_auto(ctx, ctx.command)

    @commands.hybrid_command(name="confess", help="Submit an anonymous confession.")
    @blacklist_check()
    @ignore_check()
    async def confess_subcmd(self, ctx, *, message: str):
        if isinstance(ctx.channel, discord.TextChannel):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        success, msg = await self.process_confession(ctx.author, ctx.guild, message)

        if success:
             try:
                 await ctx.author.send(embed=_ok(msg))
             except discord.Forbidden:
                 d_msg = await ctx.send(embed=_ok(msg))
                 await asyncio.sleep(3)
                 try: await d_msg.delete()
                 except: pass
        else:
             try:
                 await ctx.author.send(embed=_err(msg))
             except discord.Forbidden:
                 d_msg = await ctx.send(embed=_err(msg))
                 await asyncio.sleep(5)
                 try: await d_msg.delete()
                 except: pass

    @confession.command(name="reply", help="Anonymously reply to a confession by ID.")
    @blacklist_check()
    @ignore_check()
    async def confession_reply(self, ctx, confession_id: int, *, message: str):
        if isinstance(ctx.channel, discord.TextChannel):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT message_id FROM logs WHERE guild_id = ? AND confession_id = ?", (ctx.guild.id, confession_id)) as c:
                if not await c.fetchone():
                    err_msg = f"Confession `#{confession_id}` does not exist in this server."
                    try: return await ctx.author.send(embed=_err(err_msg))
                    except: return await ctx.send(embed=_err(err_msg), delete_after=5)

        success, msg = await self.process_confession(ctx.author, ctx.guild, message, reply_id=confession_id)

        try:
             await ctx.author.send(embed=_ok(msg) if success else _err(msg))
        except discord.Forbidden:
             d_msg = await ctx.send(embed=_ok(msg) if success else _err(msg))
             await asyncio.sleep(3)
             try: await d_msg.delete()
             except: pass

    @confession.command(name="setup", help="Sets the public confession channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def confession_setup(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO config (guild_id, channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id
            """, (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Public confession channel set to {channel.mention}."))

    @confession.command(name="log", help="Sets the private logging channel to track authors of confessions.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def confession_log(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO config (guild_id, log_channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET log_channel_id=excluded.log_channel_id
            """, (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Confession logging channel set to {channel.mention}. Authors will be revealed here."))

    @confession.command(name="ban", help="Bans a user from sending confessions.")
    @commands.has_permissions(manage_messages=True)
    @blacklist_check()
    @ignore_check()
    async def confession_ban(self, ctx, user: discord.Member, *, reason: str = "No reason provided"):
        if user.id == ctx.guild.owner_id or user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=_err("You cannot ban this user."))

        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT 1 FROM bans WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
            if await c.fetchone():
                return await ctx.send(embed=_err(f"{user.mention} is already banned from confessions."))

            await db.execute("INSERT INTO bans (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id))
            await db.commit()

        await ctx.send(embed=_ok(f"Banned {user.mention} from using confessions. | Reason: {reason}"))

    @confession.command(name="unban", help="Unbans a user from sending confessions.")
    @commands.has_permissions(manage_messages=True)
    @blacklist_check()
    @ignore_check()
    async def confession_unban(self, ctx, user: discord.User):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM bans WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"{user.mention} is not banned from confessions."))
            await db.commit()

        await ctx.send(embed=_ok(f"Unbanned {user.mention} from using confessions."))

    @confession.command(name="sendpanel", help="Sends an interactive panel with a button to submit confessions.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def confession_sendpanel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        embed = discord.Embed(
            title="Anonymous Confessions",
            description="Got a secret to share or a crush to confess? Click the button below to submit your confession completely anonymously!",
            color=0x2b2d31
        )
        embed.set_footer(text="Your identity is safe with us 🤫")

        try:
            await channel.send(embed=embed, view=ConfessionPanel(self.bot))
            if channel != ctx.channel:
                await ctx.send(embed=_ok(f"Confession panel sent to {channel.mention}."))
        except discord.Forbidden:
            return await ctx.send(embed=_err(f"I don't have permission to send messages in {channel.mention}."))


async def setup(bot):
    await bot.add_cog(Confessions(bot))
