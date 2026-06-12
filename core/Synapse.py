from __future__ import annotations
from discord.ext import commands
import discord
import aiohttp
import json
import jishaku
import asyncio
from lavalink import Client
import lavalink
import typing
from typing import List
import aiosqlite
from utils.config import OWNER_IDS
from utils.Tools import getConfig, updateConfig
from .Context import Context
import colorama
from discord.ext import commands, tasks
from colorama import Fore, Style, init
import importlib
import inspect

init(autoreset=True)

np_db = None

async def initialize_np_db():
    """Initialize the np.db connection."""
    global np_db
    if np_db is None:
        np_db = await aiosqlite.connect('database/np.db')
        await np_db.execute("PRAGMA journal_mode=WAL")
        await np_db.commit()

async def close_np_db():
    """Close the np.db connection."""
    global np_db
    if np_db:
        await np_db.close()
        np_db = None

class Synapse(commands.AutoShardedBot):

    def __init__(self, *arg, **kwargs):
        intents = discord.Intents.all()
        intents.presences = True
        intents.members = True
        super().__init__(command_prefix=self.get_prefix,
                         case_insensitive=True,
                         intents=intents,
                         status=discord.Status.do_not_disturb,
                         strip_after_prefix=True,
                         owner_ids=OWNER_IDS,
                         allowed_mentions=discord.AllowedMentions(
                             everyone=False, replied_user=False, roles=False),
                         sync_commands_debug=True,
                         sync_commands=True,
                        shard_count=2)


    async def setup_hook(self):           
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands globally")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def lavalink_event_handler(self, event):
        print(f"{event}")


    async def on_connect(self):
        await self.change_presence(status=discord.Status.do_not_disturb,
                                   activity=discord.Activity(
                                       type=discord.ActivityType.streaming,
                                       name='Synapse - Comeback'))

    async def send_raw(self, channel_id: int, content: str,
                       **kwargs) -> typing.Optional[discord.Message]:
        await self.http.send_message(channel_id, content, **kwargs)

    async def invoke_help_command(self, ctx: Context) -> None:
        """Invoke the help command or default help command if help extensions is not loaded."""
        return await ctx.send_help(ctx.command)

    async def fetch_message_by_channel(
            self, channel: discord.TextChannel,
            messageID: int) -> typing.Optional[discord.Message]:
        async for msg in channel.history(
                limit=1,
                before=discord.Object(messageID + 1),
                after=discord.Object(messageID - 1),
        ):
            return msg

    async def get_prefix(self, message: discord.Message):
        if not message.guild:
            return commands.when_mentioned_or(".")(self, message)

        await initialize_np_db()
        guild_id = message.guild.id

        try:
            data = await getConfig(guild_id)
            prefix = data.get("prefix", ".")
        except Exception:
            prefix = "."

        toggle = 0
        try:
            async with np_db.execute("SELECT value FROM np_toggle WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    toggle = row[0]
        except Exception:
            pass

        if toggle == 0:
            return commands.when_mentioned_or(prefix)(self, message)

        is_np = False
        try:
            async with np_db.execute("SELECT id FROM np_users WHERE id = ?", (message.author.id,)) as cu:
                if await cu.fetchone():
                    is_np = True

            if not is_np:
                async with np_db.execute("SELECT guild_id FROM np_guilds WHERE guild_id = ?", (message.guild.id,)) as cg:
                    if await cg.fetchone():
                        is_np = True
        except Exception:
            pass

        if is_np:
            return commands.when_mentioned_or(prefix, "")(self, message)

        return commands.when_mentioned_or(prefix)(self, message)



    async def on_message_edit(self, before, after):
        ctx: Context = await self.get_context(after, cls=Context)
        if before.content != after.content:
            if after.guild is None or after.author.bot:
                return
            if ctx.command is None:
                return
            if type(ctx.channel) == "public_thread":
                return
            await self.invoke(ctx)
        else:
            return




def setup_bot():
    intents = discord.Intents.all()
    bot = Synapse(intents=intents)
    return bot