from __future__ import annotations
import discord
from discord.ext import commands
import aiosqlite
import re

from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/counting.db"
E_TICK = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_WARN = "<:IconsDanger:1477315376982397018>"
COLOR = 0x2b2d31

def safe_eval(expr: str):
    if not re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', expr):
        return None
    try:
        val = eval(expr, {"__builtins__": {}})
        if isinstance(val, (int, float)) and int(val) == float(val):
            return int(val)
        return None
    except Exception:
        return None

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                current_count INTEGER DEFAULT 0,
                highest_count INTEGER DEFAULT 0,
                last_counter INTEGER,
                fail_role INTEGER,
                pass_role INTEGER,
                math_allowed INTEGER DEFAULT 0,
                hardmode_enabled INTEGER DEFAULT 1,
                allow_multi INTEGER DEFAULT 0,
                auto_delete INTEGER DEFAULT 0,
                react_tick TEXT,
                react_cross TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_users (
                guild_id INTEGER,
                user_id INTEGER,
                correct_counts INTEGER DEFAULT 0,
                mistakes INTEGER DEFAULT 0,
                highest_streak INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(init_db())

    async def get_config(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM counting_config WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone()

    async def update_config(self, guild_id: int, **kwargs):
        async with aiosqlite.connect(DB_PATH) as db:
            cols = ", ".join(f"{k} = ?" for k in kwargs.keys())
            vals = list(kwargs.values()) + [guild_id]
            await db.execute(f"UPDATE counting_config SET {cols} WHERE guild_id = ?", vals)
            await db.commit()

    async def get_user(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM counting_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await db.execute("INSERT INTO counting_users (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
                    await db.commit()
                    async with db.execute("SELECT * FROM counting_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cur:
                        row = await cur.fetchone()
                return row

    async def update_user(self, guild_id: int, user_id: int, **kwargs):
        async with aiosqlite.connect(DB_PATH) as db:
            cols = ", ".join(f"{k} = ?" for k in kwargs.keys())
            vals = list(kwargs.values()) + [guild_id, user_id]
            await db.execute(f"UPDATE counting_users SET {cols} WHERE guild_id = ? AND user_id = ?", vals)
            await db.commit()

    @commands.group(name="counting", aliases=["count", "c"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def counting(self, ctx):
        """Manage and play with the aesthetic counting system."""
        help_cog = self.bot.get_cog("Help")
        if help_cog:
            await help_cog.send_group_help_auto(ctx, ctx.command)

    @counting.command(name="setup")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_setup(self, ctx, channel: discord.TextChannel):
        """Sets up the active counting channel for the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO counting_config (guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=?", 
                (ctx.guild.id, channel.id, channel.id)
            )
            await db.commit()
        embed = discord.Embed(description=f"{E_TICK} **Counting channel set to {channel.mention}**", color=COLOR)
        await ctx.send(embed=embed)

    @counting.command(name="disable")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_disable(self, ctx):
        """Disables the counting system entirely for this server."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM counting_config WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        embed = discord.Embed(description=f"{E_TICK} **Counting disabled for this server**", color=COLOR)
        await ctx.send(embed=embed)

    @counting.command(name="channel")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_channel(self, ctx, channel: discord.TextChannel):
        """Changes the active counting channel."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup. Use `counting setup`", color=COLOR))
        await self.update_config(ctx.guild.id, channel_id=channel.id)
        embed = discord.Embed(description=f"{E_TICK} **Counting channel updated to {channel.mention}**", color=COLOR)
        await ctx.send(embed=embed)

    @counting.command(name="failrole")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_failrole(self, ctx, role: discord.Role = None):
        """Sets a role given to users who mess up the count."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        role_id = role.id if role else None
        await self.update_config(ctx.guild.id, fail_role=role_id)
        msg = f"{E_TICK} **Fail role set to {role.mention}**" if role else f"{E_TICK} **Fail role removed**"
        await ctx.send(embed=discord.Embed(description=msg, color=COLOR))

    @counting.command(name="passrole")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_passrole(self, ctx, role: discord.Role = None):
        """Sets a role given to the user who currently holds the right count."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        role_id = role.id if role else None
        await self.update_config(ctx.guild.id, pass_role=role_id)
        msg = f"{E_TICK} **Pass role set to {role.mention}**" if role else f"{E_TICK} **Pass role removed**"
        await ctx.send(embed=discord.Embed(description=msg, color=COLOR))

    @counting.command(name="math")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_math(self, ctx, state: str):
        """Toggles whether users can use math expressions to count."""
        if state.lower() not in ["on", "off"]:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Provide `on` or `off`", color=COLOR))
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        st = 1 if state.lower() == "on" else 0
        await self.update_config(ctx.guild.id, math_allowed=st)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Math evaluations turned {state.upper()}**", color=COLOR))

    @counting.command(name="hardmode")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_hardmode(self, ctx, state: str):
        """Toggles hardmode (mistakes reset count to 0)."""
        if state.lower() not in ["on", "off"]:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Provide `on` or `off`", color=COLOR))
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        st = 1 if state.lower() == "on" else 0
        await self.update_config(ctx.guild.id, hardmode_enabled=st)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Hardmode turned {state.upper()}**", color=COLOR))

    @counting.command(name="autodelete")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_autodelete(self, ctx, state: str):
        """Toggles auto-deletion of invalid counting messages."""
        if state.lower() not in ["on", "off"]:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Provide `on` or `off`", color=COLOR))
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        st = 1 if state.lower() == "on" else 0
        await self.update_config(ctx.guild.id, auto_delete=st)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Auto-delete turned {state.upper()}**", color=COLOR))

    @counting.command(name="allowmulti")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_allowmulti(self, ctx, state: str):
        """Toggles if a user can count multiple times consecutively."""
        if state.lower() not in ["on", "off"]:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Provide `on` or `off`", color=COLOR))
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        st = 1 if state.lower() == "on" else 0
        await self.update_config(ctx.guild.id, allow_multi=st)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Multiple counting turned {state.upper()}**", color=COLOR))

    @counting.command(name="reacttick")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_reacttick(self, ctx, emoji: str):
        """Sets the custom reaction emoji for correct counts."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        em = None if emoji.lower() == "none" else emoji
        await self.update_config(ctx.guild.id, react_tick=em)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Success reaction set to {emoji}**", color=COLOR))

    @counting.command(name="reactcross")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_reactcross(self, ctx, emoji: str):
        """Sets the custom reaction emoji for incorrect counts."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        em = None if emoji.lower() == "none" else emoji
        await self.update_config(ctx.guild.id, react_cross=em)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Fail reaction set to {emoji}**", color=COLOR))

    @counting.command(name="resetcount")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_resetcount(self, ctx):
        """Resets the current count back to 0."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        await self.update_config(ctx.guild.id, current_count=0, last_counter=None)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Current count has been reset to 0**", color=COLOR))

    @counting.command(name="restore")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_restore(self, ctx, number: int):
        """Forcibly sets the current count to a specific value."""
        if not await self.get_config(ctx.guild.id):
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        await self.update_config(ctx.guild.id, current_count=number, last_counter=None)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **Current count manually set to {number}**", color=COLOR))

    @counting.command(name="resetstats")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def c_resetstats(self, ctx):
        """Resets all user counting statistics in the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM counting_users WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} **All user statistics have been reset**", color=COLOR))

    @counting.command(name="current")
    @blacklist_check()
    @ignore_check()
    async def c_current(self, ctx):
        """Displays the current count and next expected number."""
        cfg = await self.get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        embed = discord.Embed(
            title="Current Status",
            description=f"**Current Number:** `{cfg['current_count']}`\n"
                        f"**Next Number:** `{cfg['current_count'] + 1}`\n"
                        f"**Last User:** <@{cfg['last_counter']}>" if cfg['last_counter'] else "None",
            color=COLOR
        )
        await ctx.send(embed=embed)

    @counting.command(name="highscore")
    @blacklist_check()
    @ignore_check()
    async def c_highscore(self, ctx):
        """Displays the server's highest counting score."""
        cfg = await self.get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        embed = discord.Embed(description=f"🏆 **Highest Score:** `{cfg['highest_count']}`", color=COLOR)
        await ctx.send(embed=embed)

    @counting.command(name="personalbest", aliases=["pb"])
    @blacklist_check()
    @ignore_check()
    async def c_personalbest(self, ctx, member: discord.Member = None):
        """Displays a user's highest counting streak."""
        member = member or ctx.author
        user = await self.get_user(ctx.guild.id, member.id)
        embed = discord.Embed(description=f"🏅 **{member.display_name}'s Highest Streak:** `{user['highest_streak']}`", color=COLOR)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @counting.command(name="leaderboard", aliases=["lb"])
    @blacklist_check()
    @ignore_check()
    async def c_leaderboard(self, ctx):
        """Displays the top count contributors in the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id, correct_counts FROM counting_users WHERE guild_id = ? ORDER BY correct_counts DESC LIMIT 10", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} No ranks available.", color=COLOR))
        desc = ""
        for i, r in enumerate(rows, 1):
            desc += f"**{i}.** <@{r['user_id']}> - `{r['correct_counts']}` correctly counted\n"
        embed = discord.Embed(title="Top Counters", description=desc, color=COLOR)
        await ctx.send(embed=embed)

    @counting.command(name="stats")
    @blacklist_check()
    @ignore_check()
    async def c_stats(self, ctx):
        """Displays global server counting statistics."""
        cfg = await self.get_config(ctx.guild.id)
        if not cfg:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} Counting is not setup.", color=COLOR))
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT SUM(correct_counts), SUM(mistakes) FROM counting_users WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                totals = await cursor.fetchone()
        t_correct = totals[0] or 0
        t_mistakes = totals[1] or 0
        embed = discord.Embed(title="Server Stats", color=COLOR)
        embed.add_field(name="Current Count", value=str(cfg['current_count']), inline=True)
        embed.add_field(name="High Score", value=str(cfg['highest_count']), inline=True)
        embed.add_field(name="Total Counts", value=str(t_correct), inline=True)
        embed.add_field(name="Total Mistakes", value=str(t_mistakes), inline=True)
        await ctx.send(embed=embed)

    @counting.command(name="ruiner")
    @blacklist_check()
    @ignore_check()
    async def c_ruiner(self, ctx, member: discord.Member = None):
        """Displays the top users who messed up the count."""
        if member:
            user = await self.get_user(ctx.guild.id, member.id)
            embed = discord.Embed(description=f"👻 **{member.display_name} has ruined the count `{user['mistakes']}` times.**", color=COLOR)
            return await ctx.send(embed=embed)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id, mistakes FROM counting_users WHERE guild_id = ? ORDER BY mistakes DESC LIMIT 10", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return await ctx.send(embed=discord.Embed(description=f"{E_WARN} No ruiners available.", color=COLOR))
        desc = ""
        for i, r in enumerate(rows, 1):
            desc += f"**{i}.** <@{r['user_id']}> - `{r['mistakes']}` mistakes\n"
        embed = discord.Embed(title="Top Ruiners", description=desc, color=COLOR)
        await ctx.send(embed=embed)

    @commands.Cog.listener("on_message")
    async def counting_message_handler(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        cfg = await self.get_config(message.guild.id)
        if not cfg or cfg['channel_id'] != message.channel.id:
            return

        expected = cfg['current_count'] + 1
        num = None

        if cfg['math_allowed']:
            num = safe_eval(message.content)
            if num is None and message.content.isdigit():
                num = int(message.content)
        elif message.content.isdigit():
            num = int(message.content)

        if num is None:
            if cfg['auto_delete']:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
            return

        user = await self.get_user(message.guild.id, message.author.id)

        if not cfg['allow_multi'] and cfg['last_counter'] == message.author.id:
            embed = discord.Embed(description=f"{E_WARN} {message.author.mention} You cannot count twice in a row!", color=COLOR)
            await message.reply(embed=embed, delete_after=5)
            if cfg['auto_delete']:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
            return

        tick_react = cfg['react_tick'] or E_TICK
        cross_react = cfg['react_cross'] or E_CROSS

        if num == expected:
            new_highscore = max(cfg['highest_count'], expected)
            await self.update_config(message.guild.id, current_count=expected, highest_count=new_highscore, last_counter=message.author.id)
            
            c_streak = user['current_streak'] + 1
            h_streak = max(user['highest_streak'], c_streak)
            await self.update_user(message.guild.id, message.author.id, correct_counts=user['correct_counts']+1, current_streak=c_streak, highest_streak=h_streak)

            if cfg['pass_role']:
                r = message.guild.get_role(int(cfg['pass_role']))
                if r:
                    try:
                        if cfg['last_counter'] and cfg['last_counter'] != message.author.id:
                            last_mem = message.guild.get_member(cfg['last_counter'])
                            if last_mem and r in last_mem.roles:
                                await last_mem.remove_roles(r, reason="Counting pass role removed")
                        if r not in message.author.roles:
                            await message.author.add_roles(r, reason="Counting pass role gained")
                    except Exception:
                        pass

            try:
                await message.add_reaction(tick_react)
            except discord.HTTPException:
                pass

        else:
            await self.update_user(message.guild.id, message.author.id, mistakes=user['mistakes']+1, current_streak=0)
            
            if cfg['fail_role']:
                r = message.guild.get_role(int(cfg['fail_role']))
                if r and r not in message.author.roles:
                    try:
                        await message.author.add_roles(r, reason="Counting mistake")
                    except Exception:
                        pass

            if cfg['hardmode_enabled']:
                await self.update_config(message.guild.id, current_count=0, last_counter=None)
                embed = discord.Embed(description=f"{E_CROSS} {message.author.mention} ruined the count at **{cfg['current_count']}**. Starting over from **0**.", color=COLOR)
                await message.reply(embed=embed)
                try:
                    await message.add_reaction(cross_react)
                except discord.HTTPException:
                    pass
            else:
                try:
                    await message.add_reaction(cross_react)
                except discord.HTTPException:
                    pass

async def setup(bot):
    await bot.add_cog(Counting(bot))
