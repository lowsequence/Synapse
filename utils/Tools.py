import json, sys, os
import discord
from discord.ext import commands
from core import Context
import aiosqlite
import asyncio

db_connection = None
ignore_db = None
block_db = None
async def setup_db():
  async with aiosqlite.connect('database/prefix.db') as db:
    await db.execute('''
      CREATE TABLE IF NOT EXISTS prefixes (
        guild_id INTEGER PRIMARY KEY,
        prefix TEXT NOT NULL
      )
    ''')
    await db.commit()


asyncio.run(setup_db())

async def initialize_databases():
    """Initialize all database connections."""
    global ignore_db, block_db, topcheck_db
    if ignore_db is None:
        ignore_db = await aiosqlite.connect('database/ignore.db')
        await ignore_db.execute("PRAGMA journal_mode=WAL")
        await ignore_db.commit()
    if block_db is None:
        block_db = await aiosqlite.connect('database/block.db')
        await block_db.execute("PRAGMA journal_mode=WAL")
        await block_db.commit()

async def close_databases():
    """Close all database connections."""
    global prefix_db, ignore_db, block_db, topcheck_db
    if ignore_db:
        await ignore_db.close()
        ignore_db = None
    if block_db:
        await block_db.close()
        block_db = None
    if topcheck_db:
        await topcheck_db.close()
        topcheck_db = None

async def is_topcheck_enabled(guild_id: int):
    await initialize_databases()
    async with topcheck_db.execute("SELECT enabled FROM topcheck WHERE guild_id = ?", (guild_id,)) as cursor:
        row = await cursor.fetchone()
        return row is not None and row[0] == 1



def read_json(file_path):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"guilds": {}}

def write_json(file_path, data):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def get_or_create_guild_config(file_path, guild_id, default_config):
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}  

    guild_id_str = str(guild_id)
    if guild_id_str not in data["guilds"]:
        data["guilds"][guild_id_str] = default_config
        write_json(file_path, data)
    return data["guilds"][guild_id_str]

def update_guild_config(file_path, guild_id, new_data):
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}  

    data["guilds"][str(guild_id)] = new_data
    write_json(file_path, data)

def getIgnore(guild_id):
    default_config = {
        "channel": [],
        "role": None,
        "user": [],
        "bypassrole": None,
        "bypassuser": [],
        "commands": []
    }
    return get_or_create_guild_config("ignore.json", guild_id, default_config)

def updateignore(guild_id, data):
    update_guild_config("ignore.json", guild_id, data)





async def initialize_db():
    """Initialize the database connection."""
    global db_connection
    if db_connection is None:
        db_connection = await aiosqlite.connect('database/prefix.db')
        await db_connection.execute("PRAGMA journal_mode=WAL")
        await db_connection.commit()

async def close_db():
    """Close the database connection."""
    global db_connection
    if db_connection:
        await db_connection.close()
        db_connection = None

async def getConfig(guildID):
    """Fetch the prefix configuration for a guild."""
    try:
        await initialize_db()
        async with db_connection.execute("SELECT prefix FROM prefixes WHERE guild_id = ?", (guildID,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"prefix": row[0]}
            else:
                defaultConfig = {"prefix": "."}
                await updateConfig(guildID, defaultConfig)
                return defaultConfig
    except aiosqlite.OperationalError as e:
        if "database is locked" in str(e):
            await asyncio.sleep(1)
            return await getConfig(guildID)
        else:
            raise

async def updateConfig(guildID, data):
    """Update the prefix configuration for a guild."""
    try:
        await initialize_db()
        await db_connection.execute(
            "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
            (guildID, data["prefix"])
        )
        await db_connection.commit()
    except aiosqlite.OperationalError as e:
        if "database is locked" in str(e):
            await asyncio.sleep(1)
            await updateConfig(guildID, data)
        else:
            raise



def restart_program():
  python = sys.executable
  os.execl(python, python, *sys.argv)

def blacklist_check():

  async def predicate(ctx):
      try:
          await initialize_databases()
          async with block_db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?", (str(ctx.author.id),)) as cursor:
              user_blacklisted = await cursor.fetchone()
              if user_blacklisted:
                  return False
              if ctx.guild:
                  async with block_db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(ctx.guild.id),)) as cursor:
                      guild_blacklisted = await cursor.fetchone()
                      if guild_blacklisted:
                          return False
              return True

      except aiosqlite.OperationalError as e:
          if "database is locked" in str(e):
              await asyncio.sleep(1)
          else:
              raise

  return commands.check(predicate)


async def get_ignore_data(guild_id: int) -> dict:
    await initialize_databases()
    data = {
        "channel": set(),
        "user": set(),
        "command": set(),
        "bypassuser": set(),
    }

    async with ignore_db.execute("SELECT channel_id FROM ignored_channels WHERE guild_id = ?", (guild_id,)) as cursor:
        channels = await cursor.fetchall()
        data["channel"] = {str(channel_id) for (channel_id,) in channels}

    async with ignore_db.execute("SELECT user_id FROM ignored_users WHERE guild_id = ?", (guild_id,)) as cursor:
        users = await cursor.fetchall()
        data["user"] = {str(user_id) for (user_id,) in users}

    async with ignore_db.execute("SELECT command_name FROM ignored_commands WHERE guild_id = ?", (guild_id,)) as cursor:
        commands = await cursor.fetchall()
        data["command"] = {command_name.strip().lower() for (command_name,) in commands}

    async with ignore_db.execute("SELECT user_id FROM bypassed_users WHERE guild_id = ?", (guild_id,)) as cursor:
        bypass_users = await cursor.fetchall()
        data["bypassuser"] = {str(user_id) for (user_id,) in bypass_users}

    return data

def ignore_check():
    async def predicate(ctx):
        if not ctx.guild:
            return True
        data = await get_ignore_data(ctx.guild.id)
        ch = data["channel"]
        iuser = data["user"]
        cmd = data["command"]
        buser = data["bypassuser"]

        if str(ctx.author.id) in buser:
            return True
        if str(ctx.channel.id) in ch or str(ctx.author.id) in iuser:
            return False

        command_name = ctx.command.name.strip().lower()
        aliases = [alias.strip().lower() for alias in ctx.command.aliases]
        if command_name in cmd or any(alias in cmd for alias in aliases):
            return False

        return True

    return commands.check(predicate)
