import os
import aiohttp
import asyncio
import aiosqlite
import discord
import xml.etree.ElementTree as ET
from discord.ext import commands, tasks
from typing import Optional, Tuple, List, Dict

DB_PATH = os.path.join("database", "youtube.db")

class YouTubeEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.youtube_poller.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        self.youtube_poller.cancel()
        if self.session:
            await self.session.close()

    @tasks.loop(minutes=5)
    async def youtube_poller(self):
        """Checks YouTube RSS feeds every 5 minutes for new videos."""
        await self.bot.wait_until_ready()
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT DISTINCT yt_channel_id FROM youtube_channels") as cursor:
                    rows = await cursor.fetchall()
                    unique_channels = [row["yt_channel_id"] for row in rows]

            for yt_channel_id in unique_channels:
                try:
                    latest_video = await self.fetch_latest_video(yt_channel_id)
                    if not latest_video:
                        continue

                    video_id, video_title, video_url = latest_video

                    async with aiosqlite.connect(DB_PATH) as db:
                        db.row_factory = aiosqlite.Row
                        async with db.execute(
                            "SELECT * FROM youtube_channels WHERE yt_channel_id = ?",
                            (yt_channel_id,)
                        ) as cursor:
                            trackers = await cursor.fetchall()

                        for tracker in trackers:
                            last_video_id = tracker["last_video_id"]

                            if last_video_id == "NONE":
                                await db.execute(
                                    "UPDATE youtube_channels SET last_video_id = ? WHERE guild_id = ? AND yt_channel_id = ?",
                                    (video_id, tracker["guild_id"], yt_channel_id)
                                )
                                await db.commit()
                                continue

                            if video_id != last_video_id:
                                await db.execute(
                                    "UPDATE youtube_channels SET last_video_id = ? WHERE guild_id = ? AND yt_channel_id = ?",
                                    (video_id, tracker["guild_id"], yt_channel_id)
                                )
                                await db.commit()

                                await self.dispatch_notification(tracker, video_title, video_url)

                except Exception as e:
                    print(f"[YouTubeEvents] Error polling {yt_channel_id}: {e}")

                await asyncio.sleep(1)

        except Exception as e:
            print(f"[YouTubeEvents] Loop error: {e}")

    async def fetch_latest_video(self, yt_channel_id: str) -> Optional[Tuple[str, str, str]]:
        """Fetches the latest video from a YouTube channel's RSS feed."""
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_channel_id}"
        try:
            async with self.session.get(feed_url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()

            root = ET.fromstring(text)

            ns = {'yt': 'http://www.youtube.com/xml/schemas/2015', 'atom': 'http://www.w3.org/2005/Atom'}

            entry = root.find('{http://www.w3.org/2005/Atom}entry')
            if entry is None:
                return None

            video_id_el = entry.find('{http://www.youtube.com/xml/schemas/2015}videoId')
            title_el = entry.find('{http://www.w3.org/2005/Atom}title')
            link_el = entry.find('{http://www.w3.org/2005/Atom}link')

            if video_id_el is None or title_el is None or link_el is None:
                return None

            video_id = video_id_el.text
            title = title_el.text
            url = link_el.attrib.get('href', f"https://www.youtube.com/watch?v={video_id}")

            return video_id, title, url

        except Exception as e:
            print(f"[YouTube fetch_latest_video] Error: {e}")
            return None

    async def dispatch_notification(self, tracker: aiosqlite.Row, video_title: str, video_url: str):
        """Sends the YouTube notification to the configured Discord channel."""
        try:
            guild = self.bot.get_guild(tracker["guild_id"])
            if not guild: return

            channel = guild.get_channel(tracker["channel_id"])
            if not channel: return

            yt_channel_name = tracker["yt_channel_name"]
            custom_message = tracker["custom_message"]
            ping_role_id = tracker["ping_role"]

            msg = custom_message.replace("{channel_name}", yt_channel_name)
            msg = msg.replace("{video_title}", video_title)
            msg = msg.replace("{video_url}", video_url)

            content = msg
            if ping_role_id and ping_role_id != 0:
                role = guild.get_role(ping_role_id)
                if role:
                    content = f"{role.mention}\n{content}"

            await channel.send(content=content)

        except Exception as e:
            print(f"[YouTube dispatch_notification] Error: {e}")

async def setup(bot):
    await bot.add_cog(YouTubeEvents(bot))
