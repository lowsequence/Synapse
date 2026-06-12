import discord
from discord.ext import commands
import aiosqlite
import asyncio
import random
import string
import aiohttp
from datetime import datetime, timedelta

def is_owner_or_staff():
    async def predicate(ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        async with aiosqlite.connect("database/np.db") as db:
            async with db.execute("SELECT id FROM staff WHERE id = ?", (ctx.author.id,)) as cursor:
                return await cursor.fetchone() is not None
    return commands.check(predicate)

EMBED_COLOR = 0x2b2d31
PREMIUM_LOG_WEBHOOK = "https://discord.com/api/webhooks/1425838057994588253/KCS12W7tV0gAEv2zwLrd1w6N5Uy09JDZ0inSZTyvpe2sftdPHUpjSmtos4NeJODCO9si"
DB_PATH = "database/premium_codes.db"

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_STAR  = "<:SynapsePremium:1478068782323990817>"
E_SHIELD= "<:frozenstar:1478070088119750799>"


async def auto_migrate():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_guilds (
                guild_id INTEGER PRIMARY KEY,
                activated_at TEXT,
                expires_at TEXT,
                code TEXT
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_codes (
                code TEXT PRIMARY KEY,
                duration_seconds INTEGER,
                remaining_guilds INTEGER
            )
            """
        )

        await db.commit()

        async with db.execute("PRAGMA table_info(premium_codes)") as cursor:
            columns = [row[1] async for row in cursor]
        if "remaining_guilds" not in columns:
            await db.execute(
                "ALTER TABLE premium_codes ADD COLUMN remaining_guilds INTEGER DEFAULT 1"
            )
            await db.commit()





async def send_premium_log(title: str, description: str, fields: dict = None):
    """Send premium event logs through webhook."""
    embed = {
        "title": title,
        "description": description,
        "color": 0x2b2d31,
        "fields": [],
    }

    if fields:
        for name, value in fields.items():
            embed["fields"].append({"name": name, "value": value, "inline": False})

    async with aiohttp.ClientSession() as session:
        await session.post(
            PREMIUM_LOG_WEBHOOK,
            json={"embeds": [embed]},
        )
def premium_check():
    async def predicate(ctx):
        premium_cog = ctx.bot.get_cog("Premium")
        if premium_cog is None:
            return False

        async with aiosqlite.connect("database/premium_codes.db") as db:
            async with db.execute(
                "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            embed = discord.Embed(
                title=f"{E_SHIELD} Premium Required",
                description=f"{E_EXCL} This command requires **Premium** to execute.\nYou can buy premium by clicking **[here](https://dsc.gg/astrex-dev)**.",
                color=0x2b2d31
            )

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Buy Premium",
                style=discord.ButtonStyle.link,
                url="https://dsc.gg/astrex-dev"
            ))

            await ctx.send(embed=embed, view=view)
            return False

        expires_at = datetime.fromisoformat(row[0])
        if expires_at < datetime.utcnow():
            embed = discord.Embed(
                title=f"{E_CROSS} Premium Expired",
                description=f"{E_EXCL} The premium subscription for this server has **expired**.\nRenew it by clicking **[here](https://dsc.gg/astrex-dev)**.",
                color=0x2b2d31
            )

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Renew Premium",
                style=discord.ButtonStyle.link,
                url="https://dsc.gg/astrex-dev"
            ))

            await ctx.send(embed=embed, view=view)
            return False

        return True

    return commands.check(predicate)

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.check_expired_premium())


    def parse_duration(self, duration: str):
        try:
            unit = duration[-1]
            amount = int(duration[:-1])

            if unit == "m": return timedelta(minutes=amount)
            if unit == "h": return timedelta(hours=amount)
            if unit == "d": return timedelta(days=amount)
            if unit == "w": return timedelta(weeks=amount)
            if unit == "y": return timedelta(days=amount * 365)
        except:
            return None
        return None


    @commands.group(invoke_without_command=True)
    async def premium(self, ctx):
        """Premium configuration and management commands."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.send_help(ctx.command)

    @premium.command()
    @is_owner_or_staff()
    async def generate(self, ctx, uses: int, duration: str):
        """Generate a new premium code."""
        td = self.parse_duration(duration)
        if td is None:
            return await ctx.send(
                embed=discord.Embed(
                    title=f"{E_CROSS} Invalid Duration",
                    description=f"{E_EXCL} Please provide a valid duration.\n**Examples:** `30m`, `12h`, `7d`, `2w`, `1y`",
                    color=EMBED_COLOR,
                )
            )

        duration_seconds = int(td.total_seconds())
        parts = ["".join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(4)]
        random_part = "-".join(parts)
        code = f"SYNAPSE-PREMIUM-{random_part}"

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO premium_codes VALUES (?, ?, ?)",
                (code, duration_seconds, uses),
            )
            await db.commit()

        embed = discord.Embed(
            title=f"{E_STAR} Premium Code Generated",
            description=f"Successfully generated a new premium code.\nKeep this secure and share it only with the intended user.",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name=f"- Activation Code", value=f"```yml\n{code}\n```", inline=False)
        embed.add_field(name=f"- Duration", value=f"**{duration}**", inline=True)
        embed.add_field(name=f"- Max Uses", value=f"**{uses} Server{'s' if uses > 1 else ''}**", inline=True)
        embed.set_footer(text="Synapse Premium System", icon_url=self.bot.user.display_avatar.url)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)

        await send_premium_log(
            "Premium Code Generated",
            "A new premium code was created.",
            {
                "Generated By": f"{ctx.author} (`{ctx.author.id}`)",
                "Code": code,
                "Usages": str(uses),
                "Duration": duration,
            },
        )



    @premium.command()
    @commands.has_permissions(administrator=True)
    async def activate(self, ctx, code: str):
        """Activate premium for this server."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT duration_seconds, remaining_guilds FROM premium_codes WHERE code = ?",
                (code,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return await ctx.send(
                embed=discord.Embed(
                    title=f"{E_CROSS} Invalid Code",
                    description=f"{E_EXCL} This premium code **does not exist**. Please check and try again.",
                    color=EMBED_COLOR,
                )
            )

        duration_seconds, remaining = row
        if remaining <= 0:
            return await ctx.send(
                embed=discord.Embed(
                    title=f"{E_CROSS} Code Used Up",
                    description=f"{E_EXCL} This code has **no remaining activations**.",
                    color=EMBED_COLOR,
                )
            )

        now = datetime.utcnow()
        expires = now + timedelta(seconds=duration_seconds)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO premium_guilds VALUES (?, ?, ?, ?)",
                (ctx.guild.id, now.isoformat(), expires.isoformat(), code),
            )

            await db.execute(
                "UPDATE premium_codes SET remaining_guilds = remaining_guilds - 1 WHERE code = ?",
                (code,),
            )


            await db.commit()

        async with aiosqlite.connect("database/np.db") as npdb:
            await npdb.execute(
                "INSERT OR IGNORE INTO np_guilds (guild_id) VALUES (?)",                
                (ctx.guild.id,),
            )
            await npdb.commit()



        try:
            await ctx.guild.me.edit(nick="Synapse Prime")
        except:
            pass

        embed = discord.Embed(
            title=f"{E_TICK} Premium Activated",
            description=f"{E_SHIELD} Premium has been activated for **{ctx.guild.name}**!",
            color=EMBED_COLOR,
        )
        embed.add_field(name=f"{E_STAR} Duration", value=f"{duration_seconds // 86400} days")
        embed.add_field(name=f"{E_STAR} Expires", value=f"<t:{int(expires.timestamp())}:R>")

        await ctx.send(embed=embed)

        await send_premium_log(
            "Premium Activated",
            "A guild activated premium.",
            {
                "Guild": f"{ctx.guild.name} (`{ctx.guild.id}`)",
                "Activated By": f"{ctx.author} (`{ctx.author.id}`)",
                "Code": code,
                "Expires": expires.isoformat(),
            },
        )

    @premium.command()
    @premium_check()
    @commands.has_permissions(administrator=True)
    async def setav(self, ctx, url: str):
        """Update my server avatar."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Failed to download image. Make sure the URL is a direct image link.", color=EMBED_COLOR))
                data = await resp.read()
        try:
            await ctx.guild.me.edit(avatar=data)
            await ctx.send(embed=discord.Embed(description=f"{E_TICK} Successfully updated my server avatar!", color=EMBED_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"{E_EXCL} Failed to update avatar: {e}", color=EMBED_COLOR))

    @premium.command()
    @premium_check()
    @commands.has_permissions(administrator=True)
    async def setbanner(self, ctx, url: str):
        """Update my server banner."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Failed to download image. Make sure the URL is a direct image link.", color=EMBED_COLOR))
                data = await resp.read()
        try:
            await ctx.guild.me.edit(banner=data)
            await ctx.send(embed=discord.Embed(description=f"{E_TICK} Successfully updated my server banner!", color=EMBED_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"{E_EXCL} Failed to update banner: {e}", color=EMBED_COLOR))

    @premium.command()
    @premium_check()
    @commands.has_permissions(administrator=True)
    async def setbio(self, ctx, *, text: str):
        """Update my server bio."""
        try:
            await ctx.guild.me.edit(bio=text)
            await ctx.send(embed=discord.Embed(description=f"{E_TICK} Successfully updated my server bio!", color=EMBED_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"{E_EXCL} Failed to update bio: {e}", color=EMBED_COLOR))

    @premium.command()
    @premium_check()
    @commands.has_permissions(administrator=True)
    async def setnick(self, ctx, *, nickname: str):
        """Update my server nickname."""
        try:
            await ctx.guild.me.edit(nick=nickname)
            await ctx.send(embed=discord.Embed(description=f"{E_TICK} Successfully updated my server nickname!", color=EMBED_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"{E_EXCL} Failed to update nickname: {e}", color=EMBED_COLOR))

    @premium.command()
    @is_owner_or_staff()
    async def deactivate(self, ctx):
        """Remove premium from this server."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        async with aiosqlite.connect("database/np.db") as npdb:
            await npdb.execute("DELETE FROM np_guilds WHERE guild_id = ?", (ctx.guild.id,))
            await npdb.commit()

        try:
            await ctx.guild.me.edit(nick="Synapse", avatar=None, banner=None, bio=None)
        except:
            pass

        await ctx.send(
            embed=discord.Embed(
                title=f"{E_CROSS} Premium Deactivated",
                description=f"{E_EXCL} Premium has been **removed** from this server.",
                color=EMBED_COLOR,
            )
        )

        await send_premium_log(
            "Premium Deactivated",
            "Premium manually removed.",
            {
                "Guild": f"{ctx.guild.name} (`{ctx.guild.id}`)",
                "By": f"{ctx.author} (`{ctx.author.id}`)",
            },
        )


    @premium.command()
    @commands.has_permissions(administrator=True)
    async def stats(self, ctx):
        """View this server's premium status."""

        async with aiosqlite.connect("database/premium_codes.db") as db:
            async with db.execute(
                "SELECT activated_at, expires_at, code FROM premium_guilds WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            embed = discord.Embed(
                title=f"{E_SHIELD} Premium Status",
                description=f"{E_CROSS} This server does **not** have an active premium subscription.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        activated_at, expires_at, code = row

        embed = discord.Embed(
            title=f"{E_SHIELD} Premium Status",
            color=EMBED_COLOR
        )
        embed.add_field(name=f"- Activated At", value=activated_at, inline=False)
        embed.add_field(name=f"- Expires At", value=expires_at, inline=False)
        embed.add_field(name=f"- Code Used", value=code, inline=False)

        expired = datetime.fromisoformat(expires_at) < datetime.utcnow()
        embed.add_field(name=f"- Status", value=f"{E_CROSS} Expired" if expired else f"{E_TICK} Active")

        me = ctx.guild.me
        if me.nick and me.nick != me.name:
            embed.add_field(name="- Custom Name", value=f"`{me.nick}`", inline=True)

        if me.display_avatar != me.avatar:
            embed.set_thumbnail(url=me.display_avatar.url)
            embed.add_field(name="- Custom Avatar", value=f"{E_TICK} Set", inline=True)

        await ctx.send(embed=embed)

    @premium.command()
    @is_owner_or_staff()
    async def guilds(self, ctx):
        """List all premium guilds."""

        async with aiosqlite.connect("database/premium_codes.db") as db:
            async with db.execute("SELECT guild_id, expires_at FROM premium_guilds") as cursor:
                rows = await cursor.fetchall()

        desc = ""

        for guild_id, expires_at in rows:
            guild = self.bot.get_guild(guild_id)
            name = guild.name if guild else "Unknown / Bot Not In Guild"
            desc += f"**{name}** (`{guild_id}`)\nExpires: {expires_at}\n\n"

        embed = discord.Embed(
            title="Premium Guilds",
            description=desc if desc else "No guilds with premium.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @premium.command()
    @is_owner_or_staff()
    async def revoke(self, ctx, guild_id: int):
        """Force-revoke premium from a guild."""

        async with aiosqlite.connect("database/premium_codes.db") as db:
            await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (guild_id,))
            await db.commit()

        async with aiosqlite.connect("database/np.db") as npdb:
            await npdb.execute("DELETE FROM np_guilds WHERE guild_id = ?", (guild_id,))
            await npdb.commit()

        if guild:
            try:
                await guild.me.edit(nick="Synapse", avatar=None, banner=None, bio=None)
            except:
                pass

        embed = discord.Embed(
            title=f"{E_CROSS} Premium Revoked",
            description=f"{E_EXCL} Premium has been **force-revoked** from guild `{guild_id}`.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

        await send_premium_log(
            title="Premium Revoked",
            description="Premium force-revoked from a guild by owner.",
            fields={
                "Guild ID": str(guild_id),
                "Revoked By": f"{ctx.author} (`{ctx.author.id}`)"
            }
        )


    async def check_expired_premium(self):
        await self.bot.wait_until_ready()

        while True:
            async with aiosqlite.connect("database/premium_codes.db") as db:

                async with db.execute(
                    "SELECT guild_id, expires_at FROM premium_guilds"
                ) as cursor:
                    rows = await cursor.fetchall()

                expired = [gid for gid, exp in rows if datetime.fromisoformat(exp) < datetime.utcnow()]

                await db.executemany(
                    "DELETE FROM premium_guilds WHERE guild_id = ?",
                    [(gid,) for gid in expired]
                )
                await db.commit()

            async with aiosqlite.connect("database/np.db") as npdb:
                await npdb.executemany(
                    "DELETE FROM np_guilds WHERE guild_id = ?",
                    [(gid,) for gid in expired]
                )
                await npdb.commit()

            for gid in expired:
                guild = self.bot.get_guild(gid)
                if guild:
                    try:
                        await guild.me.edit(nick="Synapse", avatar=None, banner=None, bio=None)
                    except:
                        pass

                    await send_premium_log(
                        title="Premium Expired",
                        description="A guild’s premium subscription has expired.",
                        fields={
                            "Guild": f"{guild.name} (`{guild.id}`)",
                            "Expired At": datetime.utcnow().isoformat()
                        }
                     )

            await asyncio.sleep(60)

async def setup(bot):
    await auto_migrate()
    await bot.add_cog(Premium(bot))