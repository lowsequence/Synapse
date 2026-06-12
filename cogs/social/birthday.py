import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import datetime
import calendar
from typing import Optional

from utils.Tools import blacklist_check, ignore_check

E_OK = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"

DB_PATH = os.path.join("database", "birthday.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                day INTEGER,
                month INTEGER
            );
            CREATE TABLE IF NOT EXISTS config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                role_id INTEGER,
                message TEXT
            );
            CREATE TABLE IF NOT EXISTS active_roles (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()

def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {desc}", color=0x2b2d31)

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)

def get_month_name(month: int) -> str:
    try:
        return calendar.month_name[month]
    except IndexError:
        return str(month)

class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(init_db())
        self.birthday_loop.start()

    def cog_unload(self):
        self.birthday_loop.cancel()

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def birthday_loop(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        today_day = now.day
        today_month = now.month

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, user_id FROM active_roles") as c:
                active = await c.fetchall()
                
            for guild_id, user_id in active:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    async with db.execute("SELECT role_id FROM config WHERE guild_id = ?", (guild_id,)) as c:
                        row = await c.fetchone()
                        if row and row[0]:
                            role = guild.get_role(row[0])
                            if role:
                                member = guild.get_member(user_id)
                                if member:
                                    try:
                                        await member.remove_roles(role)
                                    except discord.HTTPException:
                                        pass
            await db.execute("DELETE FROM active_roles")
            await db.commit()

            async with db.execute("SELECT user_id FROM users WHERE day = ? AND month = ?", (today_day, today_month)) as c:
                birthday_users = await c.fetchall()
            
            if not birthday_users:
                return

            user_ids = [row[0] for row in birthday_users]

            async with db.execute("SELECT guild_id, channel_id, role_id, message FROM config") as c:
                configs = await c.fetchall()

            for guild_id, channel_id, role_id, message in configs:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                
                channel = guild.get_channel(channel_id) if channel_id else None
                role = guild.get_role(role_id) if role_id else None
                
                guild_bday_members = []
                for uid in user_ids:
                    member = guild.get_member(uid)
                    if member:
                        guild_bday_members.append(member)
                        
                        if role:
                            try:
                                await member.add_roles(role)
                                await db.execute("INSERT OR IGNORE INTO active_roles (guild_id, user_id) VALUES (?, ?)", (guild_id, uid))
                            except discord.HTTPException:
                                pass
                
                if channel and guild_bday_members:
                    for member in guild_bday_members:
                        msg_text = message or "Happy Birthday to {user.mention}!"
                        msg_text = msg_text.replace("{user}", str(member)).replace("{user.mention}", member.mention).replace("{user.name}", member.name)
                        try:
                            await channel.send(msg_text)
                        except discord.HTTPException:
                            pass
            
            await db.commit()

    @birthday_loop.before_loop
    async def before_birthday_loop(self):
        await self.bot.wait_until_ready()

    @commands.group(name="bday", aliases=["birthday"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def bday(self, ctx):
        if ctx.invoked_subcommand is None:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                return await help_cog.send_group_help_auto(ctx, ctx.command)

    @bday.command(name="set")
    @blacklist_check()
    @ignore_check()
    async def bday_set(self, ctx, day: int, month: int):
        if month < 1 or month > 12:
            return await ctx.send(embed=_err("Month must be between 1 and 12."))
        
        try:
            datetime.date(2024, month, day)
        except ValueError:
            return await ctx.send(embed=_err("Invalid day for that month."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO users (user_id, day, month) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET day=excluded.day, month=excluded.month
            """, (ctx.author.id, day, month))
            await db.commit()
            
        month_str = get_month_name(month)
        await ctx.send(embed=_ok(f"Your birthday is set to **{day} {month_str}**."))

    @bday.command(name="remove", aliases=["delete"])
    @blacklist_check()
    @ignore_check()
    async def bday_remove(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM users WHERE user_id = ?", (ctx.author.id,))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("You haven't set your birthday yet."))
            await db.commit()
            
        await ctx.send(embed=_ok("Your birthday has been removed."))

    @bday.command(name="view", aliases=["user"])
    @blacklist_check()
    @ignore_check()
    async def bday_view(self, ctx, user: Optional[discord.Member]):
        user = user or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT day, month FROM users WHERE user_id = ?", (user.id,)) as c:
                row = await c.fetchone()
                
        if not row:
            if user == ctx.author:
                return await ctx.send(embed=_err("You haven't set your birthday. Use `bday set <day> <month>`."))
            return await ctx.send(embed=_err(f"{user.mention} hasn't set their birthday."))
            
        day, month = row
        month_str = get_month_name(month)
        
        now = datetime.datetime.now(datetime.timezone.utc)
        current_year = now.year
        try:
            next_bday = datetime.datetime(current_year, month, day, tzinfo=datetime.timezone.utc)
        except ValueError:
            next_bday = datetime.datetime(current_year, 3, 1, tzinfo=datetime.timezone.utc)
            
        if next_bday < now:
            try:
                next_bday = datetime.datetime(current_year + 1, month, day, tzinfo=datetime.timezone.utc)
            except ValueError:
                next_bday = datetime.datetime(current_year + 1, 3, 1, tzinfo=datetime.timezone.utc)
                
        days_left = (next_bday - now).days
        
        embed = discord.Embed(title=f"🎂 {user.display_name}'s Birthday", color=0x2b2d31)
        embed.add_field(name="Date", value=f"**{day} {month_str}**", inline=True)
        embed.add_field(name="Countdown", value=f"In **{days_left}** days", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @bday.command(name="upcoming")
    @blacklist_check()
    @ignore_check()
    async def bday_upcoming(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, day, month FROM users") as c:
                rows = await c.fetchall()
                
        if not rows:
            return await ctx.send(embed=_err("No birthdays are set in this server."))
            
        now = datetime.datetime.now(datetime.timezone.utc)
        current_year = now.year
        
        upcoming = []
        for uid, day, month in rows:
            member = ctx.guild.get_member(uid)
            if not member:
                continue
                
            try:
                next_bday = datetime.datetime(current_year, month, day, tzinfo=datetime.timezone.utc)
            except ValueError:
                next_bday = datetime.datetime(current_year, 3, 1, tzinfo=datetime.timezone.utc)
                
            if next_bday.date() < now.date():
                try:
                    next_bday = datetime.datetime(current_year + 1, month, day, tzinfo=datetime.timezone.utc)
                except ValueError:
                    next_bday = datetime.datetime(current_year + 1, 3, 1, tzinfo=datetime.timezone.utc)
                    
            days_left = (next_bday.date() - now.date()).days
            upcoming.append((days_left, member, day, month))
            
        if not upcoming:
            return await ctx.send(embed=_err("None of the server members have set their birthday."))
            
        upcoming.sort(key=lambda x: x[0])
        upcoming = upcoming[:10]
        
        desc = ""
        for i, (days, member, day, month) in enumerate(upcoming, 1):
            m_str = get_month_name(month)
            if days == 0:
                desc += f"**{i}.** {member.mention} — **Today!** ({day} {m_str})\n"
            elif days == 1:
                desc += f"**{i}.** {member.mention} — Tomorrow ({day} {m_str})\n"
            else:
                desc += f"**{i}.** {member.mention} — In {days} days ({day} {m_str})\n"
                
        embed = discord.Embed(title=f"🎂 Upcoming Birthdays in {ctx.guild.name}", description=desc, color=0x2b2d31)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @bday.command(name="channel", aliases=["setup"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def bday_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO config (guild_id, channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id
            """, (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Birthday announcements channel set to {channel.mention}."))

    @bday.command(name="role")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def bday_role(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO config (guild_id, role_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id
            """, (ctx.guild.id, role.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Birthday role set to {role.mention}. I will give this role to users on their birthday!"))

    @bday.command(name="message")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def bday_message(self, ctx, *, text: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO config (guild_id, message) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET message=excluded.message
            """, (ctx.guild.id, text))
            await db.commit()
        await ctx.send(embed=_ok(f"Birthday message updated!\nVariables: `{{user}}`, `{{user.mention}}`, `{{user.name}}`\n\nPreview: {text.replace('{user.mention}', ctx.author.mention).replace('{user}', str(ctx.author)).replace('{user.name}', ctx.author.name)}"))

    @bday.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def bday_config(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id, role_id, message FROM config WHERE guild_id = ?", (ctx.guild.id,)) as c:
                row = await c.fetchone()
                
        if not row:
            return await ctx.send(embed=_err("The birthday system has not been configured in this server."))
            
        channel_id, role_id, message = row
        channel = f"<#{channel_id}>" if channel_id else "Not Set"
        role = f"<@&{role_id}>" if role_id else "Not Set"
        msg = message or "Happy Birthday to {user.mention}!"
        
        embed = discord.Embed(title=f"🎂 Birthday Config for {ctx.guild.name}", color=0x2b2d31)
        embed.add_field(name="Channel", value=channel, inline=True)
        embed.add_field(name="Role", value=role, inline=True)
        embed.add_field(name="Message", value=msg, inline=False)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Birthday(bot))
