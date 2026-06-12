import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
from typing import Optional, Union
import random

from utils.Tools import blacklist_check, ignore_check
from utils.paginator import Paginator as HackerPaginator
from utils.paginators import DescriptionEmbedPaginator

E_OK = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"
FOOTER = "Synapse - Skullboard System"

DB_PATH = os.path.join("database", "skullboard.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS skullboard_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                required_skulls INTEGER DEFAULT 3,
                is_enabled BOOLEAN DEFAULT 1,
                self_skulls BOOLEAN DEFAULT 0,
                allow_nsfw BOOLEAN DEFAULT 0,
                embed_color INTEGER DEFAULT 10070709,
                embed_ping BOOLEAN DEFAULT 0,
                embed_reply BOOLEAN DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS skullboard_messages (
                message_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                channel_id INTEGER,
                author_id INTEGER,
                board_message_id INTEGER,
                skulls INTEGER
            );
            CREATE TABLE IF NOT EXISTS skullboard_blacklists (
                guild_id INTEGER,
                entity_id INTEGER,
                type TEXT
            );
        """)
        await db.commit()

def _ok(desc: str, color: int = 0x4dff94) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=color)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)
    e.set_footer(text=FOOTER)
    return e

class Skullboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(init_db())
        self.emoji = "<:skullboard:1477316880690708612>"

    @commands.group(name="skullboard", aliases=["sb"], help="Skullboard configuration commands", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def skullboard(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @skullboard.command(name="setup", help="Sets the target skullboard channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_setup(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO skullboard_config (guild_id, channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id, is_enabled=1
            """, (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Skullboard channel set to {channel.mention}."))

    @skullboard.command(name="reset", help="Disables the skullboard and clears its primary config.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_reset(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_config WHERE guild_id = ?", (ctx.guild.id,))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("Skullboard is not configured."))
            await db.commit()
        await ctx.send(embed=_ok("Skullboard configuration has been reset."))

    @skullboard.command(name="limit", help="Sets the required number of skulls (default 3).")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_limit(self, ctx, number: int):
        if number < 1:
            return await ctx.send(embed=_err("Skull limit must be at least 1."))
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET required_skulls = ? WHERE guild_id = ?", (number, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, required_skulls) VALUES (?, ?)", (ctx.guild.id, number))
            await db.commit()
        await ctx.send(embed=_ok(f"Skullboard requirement set to **{number}** skulls."))

    @skullboard.command(name="selfskull", help="Toggles whether users can skull their own messages.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_selfskull(self, ctx, state: str):
        state = state.lower()
        if state not in ('enable', 'disable'):
            return await ctx.send(embed=_err("Please use `enable` or `disable`."))
        val = 1 if state == 'enable' else 0
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET self_skulls = ? WHERE guild_id = ?", (val, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, self_skulls) VALUES (?, ?)", (ctx.guild.id, val))
            await db.commit()
        await ctx.send(embed=_ok(f"Self-skulling set to **{state}**."))

    @skullboard.command(name="nsfw", help="Toggle whether messages from NSFW channels appear on the board.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_nsfw(self, ctx, state: str):
        state = state.lower()
        if state not in ('enable', 'disable'):
            return await ctx.send(embed=_err("Please use `enable` or `disable`."))
        val = 1 if state == 'enable' else 0
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET allow_nsfw = ? WHERE guild_id = ?", (val, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, allow_nsfw) VALUES (?, ?)", (ctx.guild.id, val))
            await db.commit()
        await ctx.send(embed=_ok(f"NSFW mapping set to **{state}**."))

    @skullboard.group(name="embed", help="Customize the skullboard message embed.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def sb_embed(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @sb_embed.command(name="color", help="Sets the hex color of the posted messages.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_embed_color(self, ctx, hex_code: str):
        hex_code = hex_code.lstrip("#")
        try:
            color = int(hex_code, 16)
        except ValueError:
            return await ctx.send(embed=_err("Invalid hex code provided."))
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET embed_color = ? WHERE guild_id = ?", (color, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, embed_color) VALUES (?, ?)", (ctx.guild.id, color))
            await db.commit()
        await ctx.send(embed=_ok(f"Embed color set to `#{hex_code}`.", color=color))

    @sb_embed.command(name="ping", help="Toggles whether the original author is mentioned.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_embed_ping(self, ctx, state: str):
        state = state.lower()
        if state not in ('enable', 'disable'):
            return await ctx.send(embed=_err("Please use `enable` or `disable`."))
        val = 1 if state == 'enable' else 0
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET embed_ping = ? WHERE guild_id = ?", (val, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, embed_ping) VALUES (?, ?)", (ctx.guild.id, val))
            await db.commit()
        await ctx.send(embed=_ok(f"Original author pinging set to **{state}**."))

    @sb_embed.command(name="reply", help="Toggles whether context for replies is attached.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_embed_reply(self, ctx, state: str):
        state = state.lower()
        if state not in ('enable', 'disable'):
            return await ctx.send(embed=_err("Please use `enable` or `disable`."))
        val = 1 if state == 'enable' else 0
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE skullboard_config SET embed_reply = ? WHERE guild_id = ?", (val, ctx.guild.id))
            if c.rowcount == 0:
                await db.execute("INSERT INTO skullboard_config (guild_id, embed_reply) VALUES (?, ?)", (ctx.guild.id, val))
            await db.commit()
        await ctx.send(embed=_ok(f"Reply context indexing set to **{state}**."))

    @skullboard.group(name="ignore", help="Blacklist channels, roles, and users from skullboard.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @sb_ignore.group(name="channel", help="Manage ignored channels.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_channel(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @sb_ignore_channel.command(name="add", help="Ignores skulls from a specific channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_channel_add(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'channel'", (ctx.guild.id, channel.id))
            if await c.fetchone():
                return await ctx.send(embed=_err("Channel is already ignored."))
            await db.execute("INSERT INTO skullboard_blacklists (guild_id, entity_id, type) VALUES (?, ?, 'channel')", (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Ignored channel {channel.mention}."))

    @sb_ignore_channel.command(name="remove", help="Un-ignores a specific channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_channel_remove(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'channel'", (ctx.guild.id, channel.id))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("Channel is not ignored."))
            await db.commit()
        await ctx.send(embed=_ok(f"Unignored channel {channel.mention}."))

    @sb_ignore_channel.command(name="reset", help="Clears the ignored channels list.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_channel_reset(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND type = 'channel'", (ctx.guild.id,))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("No channels are ignored."))
            await db.commit()
        await ctx.send(embed=_ok("Cleared all ignored channels."))

    @sb_ignore_channel.command(name="list", help="Shows all ignored channels.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_channel_list(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT entity_id FROM skullboard_blacklists WHERE guild_id = ? AND type = 'channel'", (ctx.guild.id,))
            rows = await c.fetchall()

        if not rows:
            return await ctx.send(embed=_err("No channels are ignored."))

        entries = [f"<#{row[0]}> (`{row[0]}`)" for row in rows]
        paginator = DescriptionEmbedPaginator(entries, per_page=10, title=f"Ignored Channels in {ctx.guild.name}")
        await HackerPaginator(paginator, ctx=ctx).paginate()

    @sb_ignore.group(name="role", help="Manage ignored roles.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_role(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @sb_ignore_role.command(name="add", help="Ignores messages from a specific role.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_role_add(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'role'", (ctx.guild.id, role.id))
            if await c.fetchone():
                return await ctx.send(embed=_err("Role is already ignored."))
            await db.execute("INSERT INTO skullboard_blacklists (guild_id, entity_id, type) VALUES (?, ?, 'role')", (ctx.guild.id, role.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Ignored role {role.mention}."))

    @sb_ignore_role.command(name="remove", help="Un-ignores a specific role.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_role_remove(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'role'", (ctx.guild.id, role.id))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("Role is not ignored."))
            await db.commit()
        await ctx.send(embed=_ok(f"Unignored role {role.mention}."))

    @sb_ignore_role.command(name="reset", help="Clears the ignored roles list.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_role_reset(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND type = 'role'", (ctx.guild.id,))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("No roles are ignored."))
            await db.commit()
        await ctx.send(embed=_ok("Cleared all ignored roles."))

    @sb_ignore_role.command(name="list", help="Shows all ignored roles.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_role_list(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT entity_id FROM skullboard_blacklists WHERE guild_id = ? AND type = 'role'", (ctx.guild.id,))
            rows = await c.fetchall()

        if not rows:
            return await ctx.send(embed=_err("No roles are ignored."))

        entries = [f"<@&{row[0]}> (`{row[0]}`)" for row in rows]
        paginator = DescriptionEmbedPaginator(entries, per_page=10, title=f"Ignored Roles in {ctx.guild.name}")
        await HackerPaginator(paginator, ctx=ctx).paginate()

    @sb_ignore.group(name="user", help="Manage ignored users.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_user(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @sb_ignore_user.command(name="add", help="Ignores messages from a specific user.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_user_add(self, ctx, user: Union[discord.Member, discord.User]):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'user'", (ctx.guild.id, user.id))
            if await c.fetchone():
                return await ctx.send(embed=_err("User is already ignored."))
            await db.execute("INSERT INTO skullboard_blacklists (guild_id, entity_id, type) VALUES (?, ?, 'user')", (ctx.guild.id, user.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Ignored user {user.mention}."))

    @sb_ignore_user.command(name="remove", help="Un-ignores a specific user.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_ignore_user_remove(self, ctx, user: Union[discord.Member, discord.User]):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'user'", (ctx.guild.id, user.id))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("User is not ignored."))
            await db.commit()
        await ctx.send(embed=_ok(f"Unignored user {user.mention}."))

    @skullboard.command(name="config", help="Displays the current skullboard configuration.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_config(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM skullboard_config WHERE guild_id = ?", (ctx.guild.id,)) as c:
                row = await c.fetchone()
                if not row:
                    return await ctx.send(embed=_err("Skullboard is not configured in this server."))

                async with db.execute("SELECT COUNT(*) FROM skullboard_blacklists WHERE guild_id = ? AND type = 'channel'", (ctx.guild.id,)) as cur:
                    chan_ign = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM skullboard_blacklists WHERE guild_id = ? AND type = 'role'", (ctx.guild.id,)) as cur:
                    role_ign = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM skullboard_blacklists WHERE guild_id = ? AND type = 'user'", (ctx.guild.id,)) as cur:
                    user_ign = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM skullboard_blacklists WHERE guild_id = ? AND type = 'lock'", (ctx.guild.id,)) as cur:
                    locks = (await cur.fetchone())[0]

        channel_id = row[1]
        req_skulls = row[2]
        enabled = "Enabled" if row[3] else "Disabled"
        self_skull = "Enabled" if row[4] else "Disabled"
        nsfw = "Enabled" if row[5] else "Disabled"
        e_color = hex(row[6]) if row[6] else "0x2b2d31"
        e_ping = "Enabled" if row[7] else "Disabled"
        e_reply = "Enabled" if row[8] else "Disabled"

        embed = discord.Embed(title=f"💀 Skullboard Config: {ctx.guild.name}", color=row[6] or 0x2b2d31)
        embed.add_field(name="General", value=f"Channel: <#{channel_id}>\nStatus: `{enabled}`\nRequired Skulls: `{req_skulls}`\nSelf-Skulls: `{self_skull}`\nNSFW Skulls: `{nsfw}`", inline=False)
        embed.add_field(name="Embed Config", value=f"Color: `{e_color}`\nMention Original: `{e_ping}`\nShow Replies: `{e_reply}`", inline=False)
        embed.add_field(name="Blacklists", value=f"Ignored Channels: `{chan_ign}`\nIgnored Roles: `{role_ign}`\nIgnored Users: `{user_ign}`\nLocked Channels: `{locks}`", inline=False)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @skullboard.command(name="lock", help="Temporarily prevents skulls from being tracked in a channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_lock(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'lock'", (ctx.guild.id, channel.id))
            if await c.fetchone():
                return await ctx.send(embed=_err("Channel is already locked from skullboarding."))
            await db.execute("INSERT INTO skullboard_blacklists (guild_id, entity_id, type) VALUES (?, ?, 'lock')", (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(embed=_ok(f"Locked {channel.mention}. No new messages here will be skullboarded."))

    @skullboard.command(name="unlock", help="Removes a skullboard lock from a channel.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_unlock(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'lock'", (ctx.guild.id, channel.id))
            if c.rowcount == 0:
                return await ctx.send(embed=_err("Channel is not locked."))
            await db.commit()
        await ctx.send(embed=_ok(f"Unlocked {channel.mention}. Normal skullboarding resumes."))

    @skullboard.command(name="remove", help="Forcefully removes a message from the skullboard.")
    @commands.has_permissions(manage_messages=True)
    @blacklist_check()
    @ignore_check()
    async def sb_remove(self, ctx, message_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT board_message_id, channel_id FROM skullboard_messages WHERE guild_id = ? AND message_id = ?", (ctx.guild.id, message_id)) as c:
                row = await c.fetchone()
                if not row:
                    return await ctx.send(embed=_err("Message is not on the skullboard."))

                board_msg_id, channel_id = row

                async with db.execute("SELECT channel_id FROM skullboard_config WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                    config_row = await cur.fetchone()
                    if config_row:
                        sb_chan = self.bot.get_channel(config_row[0])
                        if sb_chan:
                            try:
                                msg_to_delete = await sb_chan.fetch_message(board_msg_id)
                                await msg_to_delete.delete()
                            except discord.NotFound:
                                pass

                await db.execute("DELETE FROM skullboard_messages WHERE guild_id = ? AND message_id = ?", (ctx.guild.id, message_id))
                await db.commit()

        await ctx.send(embed=_ok(f"Message ID `{message_id}` forcibly removed from the skullboard."))

    @skullboard.command(name="stats", help="Shows overall skullboard statistics for the server.")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @blacklist_check()
    @ignore_check()
    async def sb_stats(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*), SUM(skulls) FROM skullboard_messages WHERE guild_id = ?", (ctx.guild.id,)) as c:
                row = await c.fetchone()
                total_messages = row[0] or 0
                total_skulls = row[1] or 0

        embed = discord.Embed(title=f"💀 Skullboard Stats: {ctx.guild.name}", color=0x2b2d31)
        embed.add_field(name="Total Messages", value=f"`{total_messages:,}`", inline=True)
        embed.add_field(name="Total Skulls Given", value=f"`{total_skulls:,}`", inline=True)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @skullboard.command(name="top", help="Displays a leaderboard of the most skulled users.", aliases=["lb"])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @blacklist_check()
    @ignore_check()
    async def sb_top(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT author_id, SUM(skulls) as total_skulls
                FROM skullboard_messages
                WHERE guild_id = ?
                GROUP BY author_id
                ORDER BY total_skulls DESC
                LIMIT 10
            """, (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=_err("No skullboard data found for this server yet."))

        desc = ""
        for idx, (author_id, count) in enumerate(rows, 1):
            desc += f"**{idx}.** <@{author_id}> - `💀 {count}`\n"

        embed = discord.Embed(title=f"💀 Skullboard Leaderboard", description=desc, color=0x2b2d31)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @skullboard.command(name="random", help="Pulls a random heavily-skulled message from history.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def sb_random(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id FROM skullboard_config WHERE guild_id = ? AND is_enabled = 1", (ctx.guild.id,)) as c:
                config_row = await c.fetchone()
                if not config_row:
                    return await ctx.send(embed=_err("Skullboard is not configured or enabled."))

            async with db.execute("SELECT board_message_id FROM skullboard_messages WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()

        if not row:
            return await ctx.send(embed=_err("There are no messages on the skullboard yet!"))

        sb_chan = self.bot.get_channel(config_row[0])
        if sb_chan:
            try:
                msg = await sb_chan.fetch_message(row[0])
                await ctx.send(content="💀 Here's a random drop from the archive:", embed=msg.embeds[0] if msg.embeds else None)
                return
            except discord.NotFound:
                pass


        await ctx.send(embed=_err("Could not fetch the random board message (it may have been deleted)."))

    def _build_skull_embed(self, message: discord.Message, config: dict) -> discord.Embed:
        embed = discord.Embed(color=config.get("embed_color", 0x2b2d31))
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.description = message.content or ""

        if message.attachments:
            for attach in message.attachments:
                if attach.url.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'webp')):
                    embed.set_image(url=attach.url)
                    break
                else:
                    embed.description += f"\n\n**Attachment:** [{attach.filename}]({attach.url})"

        if "tenor.com" in embed.description or "giphy.com" in embed.description:
             words = embed.description.split()
             for w in words:
                 if "tenor.com" in w or "giphy.com" in w:
                     embed.description = embed.description.replace(w, "")
                     embed.set_image(url=w)
                     break

        if config.get("embed_reply", 1) and message.reference and isinstance(message.reference.resolved, discord.Message):
            ref = message.reference.resolved
            ref_content = ref.content[:100] + "..." if len(ref.content) > 100 else ref.content
            if not ref_content and ref.attachments:
                ref_content = "[Attachment(s)]"
            embed.description = f"> **Replying to {ref.author.mention}:** {ref_content}\n\n" + embed.description

        embed.add_field(name="Original", value=f"[Jump to Message]({message.jump_url})", inline=False)
        embed.set_footer(text=f"ID: {message.id} | Channel: #{message.channel.name}")
        embed.timestamp = message.created_at
        return embed

    async def _handle_skull_update(self, payload_or_message, is_force=False):
        if isinstance(payload_or_message, discord.RawReactionActionEvent):
            guild_id = payload_or_message.guild_id
            channel_id = payload_or_message.channel_id
            message_id = payload_or_message.message_id
            user_id = payload_or_message.user_id
            is_added = payload_or_message.event_type == "REACTION_ADD"
        else:
            msg = payload_or_message
            guild_id = msg.guild.id
            channel_id = msg.channel.id
            message_id = msg.id
            user_id = None
            is_added = True

        if not guild_id: return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM skullboard_config WHERE guild_id = ?", (guild_id,)) as c:
                row = await c.fetchone()
                if not row: return

                sb_chan_id = row[1]
                req_skulls = row[2]
                is_enabled = row[3]
                self_skulls = row[4]
                allow_nsfw = row[5]
                config = {
                    "embed_color": row[6],
                    "embed_ping": row[7],
                    "embed_reply": row[8]
                }

            if not is_enabled or not sb_chan_id: return

            async with db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type IN ('channel', 'lock')", (guild_id, channel_id)) as cur:
                if await cur.fetchone() and not is_force: return

            chan = self.bot.get_channel(channel_id)
            if not chan: return
            if chan.is_nsfw() and not allow_nsfw: return

            try: msg = await chan.fetch_message(message_id)
            except discord.NotFound: return
            if not msg.author or msg.author.bot: return

            if not is_force:
                async with db.execute("SELECT 1 FROM skullboard_blacklists WHERE guild_id = ? AND entity_id = ? AND type = 'user'", (guild_id, msg.author.id)) as cur:
                    if await cur.fetchone(): return

                role_ids = [r.id for r in msg.author.roles] if hasattr(msg.author, 'roles') else []
                if role_ids:
                    query = f"SELECT 1 FROM skullboard_blacklists WHERE guild_id = {guild_id} AND type = 'role' AND entity_id IN ({','.join('?'*len(role_ids))})"
                    async with db.execute(query, role_ids) as cur:
                        if await cur.fetchone(): return

                if user_id == msg.author.id and not self_skulls and is_added:
                    return

            skull_count = 0
            skull_emoji = None
            for reaction in msg.reactions:
                if str(reaction.emoji) == "💀":
                    skull_count = reaction.count
                    skull_emoji = reaction
                    break

            if is_force:
                skull_count = max(skull_count, req_skulls)
            elif skull_count == 0:
                pass

            sb_chan = self.bot.get_channel(sb_chan_id)
            if not sb_chan: return

            async with db.execute("SELECT board_message_id FROM skullboard_messages WHERE guild_id = ? AND message_id = ?", (guild_id, message_id)) as c:
                db_row = await c.fetchone()
                board_msg_id = db_row[0] if db_row else None

            if skull_count >= req_skulls:
                embed = self._build_skull_embed(msg, config)
                ping_content = msg.author.mention if config["embed_ping"] else f"**{msg.author.display_name}**"
                msg_content = f"<:skullboard:1477316880690708612> **{skull_count}** {ping_content} <#{channel_id}>"

                if board_msg_id:
                    try:
                        b_msg = await sb_chan.fetch_message(board_msg_id)
                        await b_msg.edit(content=msg_content, embed=embed)
                        await db.execute("UPDATE skullboard_messages SET skulls = ? WHERE guild_id = ? AND message_id = ?", (skull_count, guild_id, message_id))
                    except discord.NotFound:
                         b_msg = await sb_chan.send(content=msg_content, embed=embed)
                         await db.execute("UPDATE skullboard_messages SET board_message_id = ?, skulls = ? WHERE guild_id = ? AND message_id = ?", (b_msg.id, skull_count, guild_id, message_id))
                else:
                    b_msg = await sb_chan.send(content=msg_content, embed=embed)
                    await db.execute("INSERT INTO skullboard_messages (message_id, guild_id, channel_id, author_id, board_message_id, skulls) VALUES (?, ?, ?, ?, ?, ?)",
                                     (message_id, guild_id, channel_id, msg.author.id, b_msg.id, skull_count))
            elif board_msg_id and skull_count < req_skulls and not is_force:
                try:
                    b_msg = await sb_chan.fetch_message(board_msg_id)
                    await b_msg.delete()
                except discord.NotFound: pass
                await db.execute("DELETE FROM skullboard_messages WHERE guild_id = ? AND message_id = ?", (guild_id, message_id))

            await db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "💀": return
        await self._handle_skull_update(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "💀": return
        await self._handle_skull_update(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawMessageUpdateEvent):
        evt = discord.RawReactionActionEvent(
            data={"guild_id": payload.guild_id, "channel_id": payload.channel_id, "message_id": payload.message_id, "user_id": self.bot.user.id},
            emoji=discord.PartialEmoji(name="💀"),
            event_type="REACTION_REMOVE"
        )
        await self._handle_skull_update(evt)

    @skullboard.command(name="force", help="Forcefully pushes a message onto the skullboard.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_force(self, ctx, message_link: str):
        try:
             parts = message_link.split("/")
             msg_id = int(parts[-1])
             chan_id = int(parts[-2])
        except (ValueError, IndexError):
             return await ctx.send(embed=_err("Invalid message link provided."))

        chan = self.bot.get_channel(chan_id)
        if not chan or chan.guild.id != ctx.guild.id:
             return await ctx.send(embed=_err("Channel not found in this server."))

        try:
             msg = await chan.fetch_message(msg_id)
        except discord.NotFound:
             return await ctx.send(embed=_err("Message not found."))

        await self._handle_skull_update(msg, is_force=True)
        await ctx.send(embed=_ok(f"Forced message {message_link} onto the Skullboard."))

    @skullboard.command(name="recount", help="Automatically recalculates skulls for a specific message.")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def sb_recount(self, ctx, message_link: str):
        try:
             parts = message_link.split("/")
             msg_id = int(parts[-1])
             chan_id = int(parts[-2])
        except (ValueError, IndexError):
             return await ctx.send(embed=_err("Invalid message link provided."))

        chan = self.bot.get_channel(chan_id)
        if not chan or chan.guild.id != ctx.guild.id:
             return await ctx.send(embed=_err("Channel not found in this server."))

        try:
             msg = await chan.fetch_message(msg_id)
        except discord.NotFound:
             return await ctx.send(embed=_err("Message not found."))

        await self._handle_skull_update(msg, is_force=False)
        await ctx.send(embed=_ok(f"Recounted skulls for {message_link} and synchronized board state."))

async def setup(bot):
    await bot.add_cog(Skullboard(bot))
