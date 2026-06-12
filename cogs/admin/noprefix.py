import time
import discord
from discord.ext import commands, tasks
import aiosqlite
import aiohttp

from utils import Paginator, DescriptionEmbedPaginator
from utils.config import OWNER_IDS, np_webhook

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_STAR  = "<:SynapsePremium:1478068782323990817>"
E_SHIELD= "<:frozenstar:1478070088119750799>"



def parse_time(time_str: str) -> int:
    time_str = time_str.lower().strip()
    if not time_str: return None

    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}

    if time_str[-1] in multipliers:
        try:
            val = int(time_str[:-1])
            return val * multipliers[time_str[-1]]
        except ValueError:
            return None
    try:
        return int(time_str)
    except ValueError:
        return None

async def is_staff(user, staff_ids):
    return user.id in staff_ids

async def is_owner_or_staff(ctx):
    return await is_staff(ctx.author, ctx.cog.staff) or ctx.author.id in OWNER_IDS



class NoPrefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.staff = set()
        self.db = None
        bot.loop.create_task(self.initialize_db())
        self.np_poller.start()

    def cog_unload(self):
        self.np_poller.cancel()

    @tasks.loop(seconds=30)
    async def np_poller(self):
        """Checks for expired np_users and np_guilds every 30 seconds."""
        await self.bot.wait_until_ready()
        if not self.db:
            return

        current_time = time.time()

        try:
            await self.db.execute("DELETE FROM np_users WHERE expires_at IS NOT NULL AND expires_at <= ?", (current_time,))
            await self.db.execute("DELETE FROM np_guilds WHERE expires_at IS NOT NULL AND expires_at <= ?", (current_time,))
            await self.db.commit()
        except BaseException:
            pass


    async def initialize_db(self):
        self.db = await aiosqlite.connect("database/np.db")

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS np_users (
                id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS np_guilds (
                guild_id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        """)

        try: await self.db.execute("ALTER TABLE np_users ADD COLUMN expires_at REAL")
        except: pass

        try: await self.db.execute("ALTER TABLE np_guilds ADD COLUMN expires_at REAL")
        except: pass

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS np_toggle (
                id INTEGER PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY
            )
        """)

        await self.db.execute("INSERT OR IGNORE INTO np_toggle (id, value) VALUES (1, 0)")
        await self.db.commit()

        async with self.db.execute("SELECT id FROM staff") as cursor:
            self.staff = {row[0] for row in await cursor.fetchall()}

    async def send_np_log(self, **kwargs):
        """Send detailed webhook log for No-Prefix actions."""
        if not np_webhook:
            return

        async with aiohttp.ClientSession() as session:
            embed = discord.Embed(
                title=kwargs.get("title"),
                description=kwargs.get("description"),
                color=0x2b2d31
            )

            embed.add_field(name="Moderator", value=kwargs.get("moderator"), inline=False)
            embed.add_field(name="Target", value=kwargs.get("target"), inline=False)
            embed.add_field(name="Target ID", value=kwargs.get("target_id"), inline=False)
            embed.add_field(name="Action Type", value=kwargs.get("action"), inline=False)

            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text="No-Prefix Logs")

            payload = {
                "embeds": [embed.to_dict()],
                "username": kwargs.get("username", "Synapse Logs"),
                "avatar_url": kwargs.get("avatar"),
            }

            await session.post(np_webhook, json=payload)

    @commands.group(name="np", aliases=["noprefix"], invoke_without_command=True)
    @commands.check(is_owner_or_staff)
    async def np(self, ctx):
        await ctx.send_help(ctx.command)


    @np.command(name="toggle")
    @commands.check(is_owner_or_staff)
    async def np_toggle(self, ctx):

        async with self.db.execute("SELECT value FROM np_toggle WHERE id = 1") as c:
            current = (await c.fetchone())[0]

        new_state = 0 if current == 1 else 1

        await self.db.execute("UPDATE np_toggle SET value = ? WHERE id = 1", (new_state,))
        await self.db.commit()

        state_text = "**Enabled**" if new_state == 1 else "**Disabled**"

        embed = discord.Embed(
            description=f"{E_TICK if new_state == 1 else E_CROSS} **No-Prefix System updated!**\n- **Status**: {state_text}",
            color=0x2b2d31
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

        await self.send_np_log(
            title="Global No-Prefix Toggle",
            description=f"System set to {state_text}.",
            moderator=ctx.author.mention,
            target="Global System",
            target_id="N/A",
            action="Toggle",
            avatar=ctx.author.display_avatar.url,
        )


    @np.group(name="user", invoke_without_command=True)
    @commands.check(is_owner_or_staff)
    async def np_user(self, ctx):
        await ctx.send_help(ctx.command)

    @np_user.command(name="add")
    @commands.check(is_owner_or_staff)
    async def np_user_add(self, ctx, user: discord.User, duration: str = None):

        expires_at = None
        if duration:
            duration_secs = parse_time(duration)
            if not duration_secs or duration_secs < 10:
                embed = discord.Embed(
                    description=f"{E_EXCL} Invalid duration! Example: `10m`, `1h`, `1d`.",
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)
            expires_at = time.time() + duration_secs

        async with self.db.execute("SELECT id FROM np_users WHERE id = ?", (user.id,)) as c:
            exists = await c.fetchone()

        if exists:
            embed = discord.Embed(
                description=f"{E_EXCL} {user.mention} is **already** in the No-Prefix user list.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        await self.db.execute("INSERT INTO np_users (id, expires_at) VALUES (?, ?)", (user.id, expires_at))
        await self.db.commit()

        duration_text = f" for **{duration}**" if duration else " **permanently**"

        embed = discord.Embed(
            description=f"{E_TICK} Successfully added **{user.mention}** to **No-Prefix Users**{duration_text}.",
            color=0x2b2d31
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

        try:
            dm_embed = discord.Embed(
                title=f"{E_SHIELD} Synapse Auto-Alert",
                description=f"You have been granted **No-Prefix** privileges in **{ctx.guild.name}**{duration_text}.\nEnjoy bypass access to all valid commands without prefixing!",
                color=0x2b2d31
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await self.send_np_log(
            title="User Added to No-Prefix",
            description=f"{user.mention} is now a No-Prefix user{duration_text}.",
            moderator=ctx.author.mention,
            target=user.name,
            target_id=user.id,
            action="User Add",
            avatar=user.display_avatar.url,
        )

    @np_user.command(name="remove")
    @commands.check(is_owner_or_staff)
    async def np_user_remove(self, ctx, user: discord.User):

        async with self.db.execute("SELECT id FROM np_users WHERE id = ?", (user.id,)) as c:
            exists = await c.fetchone()

        if not exists:
            embed = discord.Embed(
                description=f"{E_EXCL} {user.mention} is **not** a No-Prefix user.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        await self.db.execute("DELETE FROM np_users WHERE id = ?", (user.id,))
        await self.db.commit()

        embed = discord.Embed(
            description=f"{E_CROSS} Successfully removed **{user.mention}** from **No-Prefix Users**.",
            color=0x2b2d31
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

        try:
            dm_embed = discord.Embed(
                description=f"{E_EXCL} Your **No-Prefix** privileges have been revoked in **{ctx.guild.name}**.",
                color=0x2b2d31
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await self.send_np_log(
            title="User Removed from No-Prefix",
            description=f"{user.mention} is no longer a No-Prefix user.",
            moderator=ctx.author.mention,
            target=user.name,
            target_id=user.id,
            action="User Remove",
            avatar=user.display_avatar.url,
        )

    @np_user.command(name="status")
    @commands.check(is_owner_or_staff)
    async def np_user_status(self, ctx, user: discord.User):

        async with self.db.execute("SELECT expires_at FROM np_users WHERE id = ?", (user.id,)) as c:
            row = await c.fetchone()

        if not row:
            embed = discord.Embed(
                description=f"{E_EXCL} {user.mention} is **not** a No-Prefix user.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        expires_at = row[0]
        status_text = f"Expires <t:{int(expires_at)}:R>" if expires_at else "Permanent"

        embed = discord.Embed(
            description=f"**No-Prefix Status for {user.mention}**\n- **Status**: {status_text}",
            color=0x2b2d31
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        await ctx.reply(embed=embed)

    @np_user.command(name="list")
    @commands.check(is_owner_or_staff)
    async def np_user_list(self, ctx):

        async with self.db.execute("SELECT id, expires_at FROM np_users") as c:
            rows = await c.fetchall()

        if not rows:
            embed = discord.Embed(
                description=f"{E_EXCL} There are **no users** in the No-Prefix list.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        entries = []
        for i, (uid, expires_at) in enumerate(rows):
            expiry_str = f" - <t:{int(expires_at)}:R>" if expires_at else ""
            entries.append(f"`{(i+1):02d}` | <@{uid}> `({uid})`{expiry_str}")

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries, 
                per_page=10, 
                title=f"No-Prefix Users ({len(entries)})",
                color=0x2b2d31
            ),
            ctx=ctx
        )
        await paginator.paginate()


    @np.group(name="guild", invoke_without_command=True)
    @commands.check(is_owner_or_staff)
    async def np_guild(self, ctx):
        await ctx.send_help(ctx.command)

    @np_guild.command(name="add")
    @commands.check(is_owner_or_staff)
    async def np_guild_add(self, ctx, guild_id: int, duration: str = None):

        expires_at = None
        if duration:
            duration_secs = parse_time(duration)
            if not duration_secs or duration_secs < 10:
                embed = discord.Embed(
                    description=f"{E_EXCL} Invalid duration! Example: `10m`, `1h`, `1d`.",
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)
            expires_at = time.time() + duration_secs

        guild = self.bot.get_guild(guild_id)
        guild_display = f"**{guild.name}**" if guild else f"Guild ID: **{guild_id}**"

        async with self.db.execute("SELECT guild_id FROM np_guilds WHERE guild_id = ?", (guild_id,)) as c:
            exists = await c.fetchone()

        if exists:
            embed = discord.Embed(
                description=f"{E_EXCL} {guild_display} is already a **No-Prefix Guild**.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        await self.db.execute("INSERT INTO np_guilds (guild_id, expires_at) VALUES (?, ?)", (guild_id, expires_at))
        await self.db.commit()

        duration_text = f" for **{duration}**" if duration else " **permanently**"

        embed = discord.Embed(
            description=f"{E_TICK} Successfully added {guild_display} to **No-Prefix Guilds**{duration_text}.",
            color=0x2b2d31
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

        await self.send_np_log(
            title="Guild Added to No-Prefix",
            description=f"{guild_display} added as No-Prefix Guild{duration_text}.",
            moderator=ctx.author.mention,
            target=guild.name if guild else str(guild_id),
            target_id=guild_id,
            action="Guild Add",
            avatar=guild.icon.url if guild and guild.icon else None,
        )

    @np_guild.command(name="remove")
    @commands.check(is_owner_or_staff)
    async def np_guild_remove(self, ctx, guild: discord.Guild):

        guild_display = f"**{guild.name}**" if guild else f"Guild ID: **{guild.id}**"

        async with self.db.execute("SELECT guild_id FROM np_guilds WHERE guild_id = ?", (guild.id,)) as c:
            exists = await c.fetchone()

        if not exists:
            embed = discord.Embed(
                description=f"{E_EXCL} {guild_display} is **not** a No-Prefix Guild.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        await self.db.execute("DELETE FROM np_guilds WHERE guild_id = ?", (guild.id,))
        await self.db.commit()

        embed = discord.Embed(
            description=f"{E_CROSS} Successfully removed {guild_display} from **No-Prefix Guilds**.",
            color=0x2b2d31
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

        await self.send_np_log(
            title="Guild Removed from No-Prefix",
            description=f"{guild.name} removed from No-Prefix Guilds.",
            moderator=ctx.author.mention,
            target=guild.name,
            target_id=guild.id,
            action="Guild Remove",
            avatar=guild.icon.url if guild.icon else None,
        )

    @np_guild.command(name="status")
    @commands.check(is_owner_or_staff)
    async def np_guild_status(self, ctx, guild_id: int):

        guild = self.bot.get_guild(guild_id)
        guild_display = f"**{guild.name}**" if guild else f"Guild ID: **{guild_id}**"

        async with self.db.execute("SELECT expires_at FROM np_guilds WHERE guild_id = ?", (guild_id,)) as c:
            row = await c.fetchone()

        if not row:
            embed = discord.Embed(
                description=f"{E_EXCL} {guild_display} is **not** a No-Prefix Guild.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        expires_at = row[0]
        status_text = f"Expires <t:{int(expires_at)}:R>" if expires_at else "Permanent"

        embed = discord.Embed(
            description=f"**No-Prefix Status for {guild_display}**\n- **Status**: {status_text}",
            color=0x2b2d31
        )
        if guild and guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=f"Guild {guild_id}")

        await ctx.reply(embed=embed)

    @np_guild.command(name="list")
    @commands.check(is_owner_or_staff)
    async def np_guild_list(self, ctx):

        async with self.db.execute("SELECT guild_id, expires_at FROM np_guilds") as c:
            rows = await c.fetchall()

        if not rows:
            embed = discord.Embed(
                description=f"{E_EXCL} There are **no guilds** in the No-Prefix list.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)

        entries = []
        for i, (gid, expires_at) in enumerate(rows):
            guild = self.bot.get_guild(gid)
            name = f"**{guild.name}**\n↳ " if guild else ""
            expiry_str = f" - <t:{int(expires_at)}:R>" if expires_at else ""
            entries.append(f"`{(i+1):02d}` | {name}`{gid}`{expiry_str}")

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries, 
                per_page=10, 
                title=f"No-Prefix Guilds ({len(entries)})",
                color=0x2b2d31
            ),
            ctx=ctx
        )
        await paginator.paginate()



async def setup(bot):
    await bot.add_cog(NoPrefix(bot))