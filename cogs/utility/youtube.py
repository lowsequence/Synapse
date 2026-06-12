import os
import aiohttp
import asyncio
import aiosqlite
import discord
import re
from discord.ext import commands
from typing import Optional, Tuple
from utils.Tools import blacklist_check, ignore_check

DB_PATH = os.path.join("database", "youtube.db")

COLOR_YT = 0x2b2d31
FOOTER = "Synapse · YouTube"
E_OK   = "<:emoji_1769867605256:1467155817726873650>"
E_ERR  = "<:SynapseExcl:1477234549552320634>"
E_NOTE = "<:SynapseNote:1477236015830663324>"
E_YOUTUBE = "<:SynapsYoutube:1466044611599302686>"

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"- {desc}", color=COLOR_YT)
    return e

def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"- {desc}", color=COLOR_YT)
    return e


async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS youtube_channels (
                guild_id        INTEGER,
                channel_id      INTEGER,
                yt_channel_id   TEXT,
                yt_channel_name TEXT,
                last_video_id   TEXT    DEFAULT 'NONE',
                custom_message  TEXT    DEFAULT '{video_url}',
                ping_role       INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, channel_id, yt_channel_id)
            );
        """)
        await db.commit()


async def scrape_yt_info(session: aiohttp.ClientSession, url_or_handle: str) -> Optional[Tuple[str, str]]:
    """Resolves a youtube URL or Handle into a precise UC ID and Channel Name."""

    if "youtube.com" not in url_or_handle and "youtu.be" not in url_or_handle:
        if not url_or_handle.startswith("@"):
            url_or_handle = "@" + url_or_handle
        url = f"https://www.youtube.com/{url_or_handle}"
    else:
        url = url_or_handle

    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

            id_match = re.search(r'"browseId":"(UC[a-zA-Z0-9_-]{22})"', html)
            if not id_match:
                id_match = re.search(r'<meta itemprop="identifier" content="(UC[a-zA-Z0-9_-]{22})">', html)

            name_match = re.search(r'<meta itemprop="name" content="([^"]+)">', html)
            if not name_match:
                name_match = re.search(r'"channelMetadataRenderer":\{"title":"([^"]+)"', html)

            if id_match and name_match:
                return id_match.group(1), name_match.group(1)
            return None

    except Exception as e:
        print(f"[YouTube Scrape] Error: {e}")
        return None


class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    @commands.group(name="youtube", aliases=["yt"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def youtube(self, ctx):
        """Advanced YouTube upload notifications."""
        if ctx.invoked_subcommand is None:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                await help_cog.send_group_help_auto(ctx, ctx.command)

    @youtube.command(name="add")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.guild)
    async def yt_add(self, ctx, channel: discord.TextChannel, *, youtube_channel_or_handle: str):
        """Track a YouTube channel's uploads in a specific discord channel."""
        loading = await ctx.send(embed=_err("Searching YouTube..."))

        info = await scrape_yt_info(self.session, youtube_channel_or_handle)
        if not info:
            return await loading.edit(embed=_err("Could not find that YouTube channel. Ensure you provided a valid handle (like `@MrBeast`) or a valid channel URL."))

        yt_id, yt_name = info

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT COUNT(*) FROM youtube_channels WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                    count = (await cur.fetchone())[0]
                    if count >= 15:
                        return await loading.edit(embed=_err("You can only track a maximum of **15** YouTube channels per server."))

                async with db.execute("SELECT 1 FROM youtube_channels WHERE guild_id = ? AND channel_id = ? AND yt_channel_id = ?", (ctx.guild.id, channel.id, yt_id)) as cur:
                    if await cur.fetchone():
                        return await loading.edit(embed=_err(f"**{yt_name}** is already being tracked in {channel.mention}."))

                await db.execute(
                    "INSERT INTO youtube_channels (guild_id, channel_id, yt_channel_id, yt_channel_name) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, channel.id, yt_id, yt_name)
                )
                await db.commit()

            await loading.edit(embed=_ok(f"Successfully tracked **{yt_name}**. New videos will be posted to {channel.mention}."))

        except Exception as e:
            await loading.edit(embed=_err(f"Database Error: `{e}`"))

    @youtube.command(name="remove")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def yt_remove(self, ctx, channel: discord.TextChannel, *, youtube_channel_or_handle: str):
        """Stop tracking a YouTube channel in a specific discord channel."""
        loading = await ctx.send(embed=_err("Searching YouTube to resolve ID..."))

        info = await scrape_yt_info(self.session, youtube_channel_or_handle)
        if not info:
            yt_id = None
            yt_name = youtube_channel_or_handle
        else:
            yt_id, yt_name = info

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                if yt_id:
                    cursor = await db.execute(
                        "DELETE FROM youtube_channels WHERE guild_id = ? AND channel_id = ? AND yt_channel_id = ?",
                        (ctx.guild.id, channel.id, yt_id)
                    )
                else:
                    cursor = await db.execute(
                        "DELETE FROM youtube_channels WHERE guild_id = ? AND channel_id = ? AND yt_channel_name LIKE ?",
                        (ctx.guild.id, channel.id, f"%{yt_name}%")
                    )

                if cursor.rowcount > 0:
                    await db.commit()
                    await loading.edit(embed=_ok(f"Stopped tracking **{yt_name}** in {channel.mention}."))
                else:
                    await loading.edit(embed=_err(f"Could not find a tracker for **{yt_name}** in {channel.mention}. Check `yt list`."))

        except Exception as e:
            await loading.edit(embed=_err(f"Database Error: `{e}`"))


    @youtube.command(name="list")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def yt_list(self, ctx):
        """List all tracked YouTube channels."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM youtube_channels WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send(embed=_err("You are not tracking any YouTube channels."))

        desc = ""
        for idx, row in enumerate(rows, start=1):
            ch = ctx.guild.get_channel(row["channel_id"])
            ch_format = ch.mention if ch else f"`Deleted #{row['channel_id']}`"
            role = ctx.guild.get_role(row["ping_role"]) if row["ping_role"] else None
            role_format = f" (Pings {role.mention})" if role else ""
            desc += f"**{idx}.** [{row['yt_channel_name']}](https://youtube.com/channel/{row['yt_channel_id']}) in {ch_format}{role_format}\n"

        embed = discord.Embed(
            title="Tracked YouTube Channels",
            description=desc,
            color=COLOR_YT
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @youtube.command(name="message")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def yt_message(self, ctx, channel: discord.TextChannel, youtube_channel_or_handle: str, *, message: str):
        """Set a custom notification message for a specific tracked channel.
        Variables: {channel_name}, {video_title}, {video_url}"""

        info = await scrape_yt_info(self.session, youtube_channel_or_handle)
        if not info:
            return await ctx.send(embed=_err("Could not resolve that YouTube channel. Provide the exact handle or URL."))

        yt_id, yt_name = info

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE youtube_channels SET custom_message = ? WHERE guild_id = ? AND channel_id = ? AND yt_channel_id = ?",
                (message, ctx.guild.id, channel.id, yt_id)
            )
            if cursor.rowcount == 0:
                return await ctx.send(embed=_err(f"You aren't tracking **{yt_name}** in {channel.mention}. Provide a valid tracker."))
            await db.commit()

        await ctx.send(embed=_ok(f"Updated notification message for **{yt_name}** in {channel.mention}."))


    @youtube.command(name="role")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def yt_role(self, ctx, channel: discord.TextChannel, youtube_channel_or_handle: str, role: discord.Role):
        """Set a role to ping when a video is uploaded."""

        info = await scrape_yt_info(self.session, youtube_channel_or_handle)
        if not info:
            return await ctx.send(embed=_err("Could not resolve that YouTube channel. Provide the exact handle or URL."))

        yt_id, yt_name = info

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE youtube_channels SET ping_role = ? WHERE guild_id = ? AND channel_id = ? AND yt_channel_id = ?",
                (role.id, ctx.guild.id, channel.id, yt_id)
            )
            if cursor.rowcount == 0:
                return await ctx.send(embed=_err(f"You aren't tracking **{yt_name}** in {channel.mention}. Provide a valid tracker."))
            await db.commit()

        await ctx.send(embed=_ok(f"Will now ping {role.mention} for new videos from **{yt_name}** in {channel.mention}."))


    @youtube.command(name="forcecheck", hidden=True)
    @commands.is_owner()
    async def yt_forcecheck(self, ctx):
        """Force the background task to poll RSS feeds immediately."""
        ev_cog = self.bot.get_cog("YouTubeEvents")
        if not ev_cog:
            return await ctx.send(embed=_err("YouTubeEvents cog not loaded!"))

        await ctx.send(embed=_ok("Forcing YouTube polling iteration..."))
        try:
            await ev_cog.youtube_poller()
            await ctx.send(embed=_ok("Iteration complete."))
        except Exception as e:
            await ctx.send(embed=_err(f"Error during iteration: `{e}`"))


async def setup(bot):
    await _init_db()
    await bot.add_cog(YouTubeCommands(bot))
