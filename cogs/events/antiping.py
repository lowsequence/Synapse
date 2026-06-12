from utils import getConfig  
import discord
from discord.ext import commands
from utils.Tools import get_ignore_data
import aiosqlite
import wavelink
import datetime
import platform
import sys
import logging
from core import Synapse
import psutil
import asyncio

start_time = datetime.datetime.now()

def get_uptime():
    now = datetime.datetime.now()
    uptime = now - start_time
    days, seconds = uptime.days, uptime.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{days} day, {hours}:{minutes}:{seconds}"

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)

block_db = None

async def initialize_block_db():
    """Initialize the block.db connection."""
    global block_db
    if block_db is None:
        block_db = await aiosqlite.connect('database/block.db')
        await block_db.execute("PRAGMA journal_mode=WAL")
        await block_db.commit()

async def close_block_db():
    """Close the block.db connection."""
    global block_db
    if block_db:
        await block_db.close()
        block_db = None   

class antipinginv(commands.Cog):
    def __init__(self, client: Synapse):
        self.bot = client
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 12.0, commands.BucketType.user)

    async def is_blacklisted(self, message):
        try:
            await initialize_block_db()
            async with block_db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (message.guild.id,)) as cursor:
                if await cursor.fetchone():
                    return True

            async with block_db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?", (message.author.id,)) as cursor:
                if await cursor.fetchone():
                    return True

            return False
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e):
                await asyncio.sleep(1)
                return await self.is_blacklisted(message)
            else:
                raise

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if await self.is_blacklisted(message):
            return

        ignore_data = await get_ignore_data(message.guild.id)
        if str(message.author.id) in ignore_data["user"] or str(message.channel.id) in ignore_data["channel"]:
            return

        if message.reference and message.reference.resolved:
            if isinstance(message.reference.resolved, discord.Message):
                if message.reference.resolved.author.id == self.bot.user.id:
                    return

        guild_id = message.guild.id
        data = await getConfig(guild_id) 
        prefix = data["prefix"]

        if self.bot.user in message.mentions:
            if len(message.content.strip().split()) == 1:

                embed = discord.Embed(
                        description=(
                            f"Hey {message.author.mention}: My prefix is: {prefix}"
                        )
                    )


                await message.reply(embed=embed,  mention_author=False)

async def setup(client):
    await client.add_cog(antipinginv(client))