import time
import json
import aiosqlite
import discord
from discord.ext import commands
import os


EMBED_COLOR = 0x2b2d31
COLOR_OK    = 0x2b2d31
COLOR_ERR   = 0x2b2d31
COLOR_INFO  = 0x5865F2
COLOR_WARN  = 0xfca903

E_OK    = "<:emoji_1769867605256:1467155817726873650>"
E_ERR   = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_STAR  = "<:SynapsePremium:1478068782323990817>"

DB_PATH = "database/joindm.db"
FOOTER = "Synapse · JoinDM System"


def _ok(desc: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=COLOR_OK)
    if title: e.title = title
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=COLOR_ERR)
    if title: e.title = title
    e.set_footer(text=FOOTER)
    return e

def _info(desc: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=desc, color=COLOR_INFO)
    if title: e.title = title
    e.set_footer(text=FOOTER)
    return e

def _warn(desc: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"{E_EXCL} {desc}", color=COLOR_WARN)
    if title: e.title = title
    e.set_footer(text=FOOTER)
    return e


VARIABLES = {
    "{user}": "Mention of the user",
    "{username}": "User name",
    "{userid}": "User ID",
    "{server}": "Server name",
    "{serverid}": "Server ID",
    "{membercount}": "Total server members",
    "{newline}": "Line break",
    "{server_icon}": "Server icon URL",
    "{server_banner}": "Server banner URL",
    "{user_avatar}": "User avatar URL",
    "{user_banner}": "User banner URL",
    "{author_icon}": "Embed author icon URL",
    "{footer_icon}": "Embed footer icon URL"
}

def parse_variables(member: discord.Member, text: str) -> str:
    """Safely replace variables inside text for JoinDM system."""
    if not text:
        return ""

    guild = member.guild

    try:
        server_icon = guild.icon.url if guild.icon else ""
    except:
        server_icon = ""

    try:
        server_banner = guild.banner.url if guild.banner else ""
    except:
        server_banner = ""

    try:
        user_avatar = member.display_avatar.url
    except:
        user_avatar = ""

    try:
        user_banner = member.banner.url if member.banner else ""
    except:
        user_banner = ""

    variables = {
        "{user}": member.mention,
        "{username}": member.name,
        "{userid}": str(member.id),

        "{server}": guild.name,
        "{serverid}": str(guild.id),
        "{membercount}": str(guild.member_count),

        "{newline}": "\n",

        "{server_icon}": server_icon,
        "{servericon}": server_icon,

        "{server_banner}": server_banner,
        "{serverbanner}": server_banner,

        "{user_avatar}": user_avatar,
        "{usericon}": user_avatar,

        "{user_banner}": user_banner,
        "{userbanner}": user_banner
    }

    for key, value in variables.items():
        text = text.replace(key, value)

    return text


def joindm_admin_only():
    async def predicate(ctx: commands.Context):
        perms = ctx.author.guild_permissions
        return perms.administrator or perms.manage_guild
    return commands.check(predicate)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS joindm (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    mode TEXT DEFAULT 'message',
    message TEXT,
    embed_title TEXT,
    embed_description TEXT,
    embed_footer TEXT,
    embed_author TEXT,
    embed_author_icon TEXT,
    embed_footer_icon TEXT,
    embed_color INTEGER,
    embed_thumbnail TEXT,
    embed_image TEXT,
    embed_fields TEXT,
    updated_at INTEGER
);
"""


class JoinDMDatabase:
    def __init__(self):
        self.path = DB_PATH



    async def setup(self):
        """Create table if missing."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()

    async def fetch(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT * FROM joindm WHERE guild_id = ?", (guild_id,))
            row = await cur.fetchone()

        if not row:
            return {
                "guild_id": guild_id,
                "enabled": 0,
                "mode": "message",
                "message": "",
                "embed_title": "",
                "embed_description": "",
                "embed_footer": "",
                "embed_author": "",
                "embed_author_icon": "",
                "embed_footer_icon": "",
                "embed_color": EMBED_COLOR,
                "embed_thumbnail": "",
                "embed_image": "",
                "embed_fields": []
            }

        fields_json = row[13] if row[13] else "[]"

        return {
            "guild_id": row[0],
            "enabled": row[1],
            "mode": row[2],
            "message": row[3],
            "embed_title": row[4],
            "embed_description": row[5],
            "embed_footer": row[6],
            "embed_author": row[7],
            "embed_author_icon": row[8],
            "embed_footer_icon": row[9],
            "embed_color": row[10],
            "embed_thumbnail": row[11],
            "embed_image": row[12],
            "embed_fields": json.loads(fields_json)
        }

    async def upsert(self, guild_id: int, data: dict):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO joindm (
                    guild_id, enabled, mode, message,
                    embed_title, embed_description, embed_footer, embed_author,
                    embed_author_icon, embed_footer_icon, embed_color,
                    embed_thumbnail, embed_image, embed_fields, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    mode=excluded.mode,
                    message=excluded.message,
                    embed_title=excluded.embed_title,
                    embed_description=excluded.embed_description,
                    embed_footer=excluded.embed_footer,
                    embed_author=excluded.embed_author,
                    embed_author_icon=excluded.embed_author_icon,
                    embed_footer_icon=excluded.embed_footer_icon,
                    embed_color=excluded.embed_color,
                    embed_thumbnail=excluded.embed_thumbnail,
                    embed_image=excluded.embed_image,
                    embed_fields=excluded.embed_fields,
                    updated_at=excluded.updated_at
                """,
                (
                    guild_id,
                    data["enabled"],
                    data["mode"],
                    data["message"],
                    data["embed_title"],
                    data["embed_description"],
                    data["embed_footer"],
                    data["embed_author"],
                    data["embed_author_icon"],
                    data["embed_footer_icon"],
                    data["embed_color"],
                    data["embed_thumbnail"],
                    data["embed_image"],
                    json.dumps(data["embed_fields"]),
                    int(time.time())
                )
            )
            await db.commit()

    async def disable(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE joindm SET enabled = 0 WHERE guild_id = ?", (guild_id,))
            await db.commit()



    def validate_url(url: str):
        if not url:
            return None
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return None