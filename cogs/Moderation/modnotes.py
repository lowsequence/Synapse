import discord
from discord.ext import commands
import aiosqlite
import time

from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/modnotes.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS mod_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mod_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mod_flags (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                flag TEXT NOT NULL,
                mod_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()


class ModNotesCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def note(self, ctx):
        """Moderation notes system."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help note` for a list of subcommands.")

    @note.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def note_add(self, ctx, member: discord.Member, *, text: str):
        """Add a moderation note."""
        if len(text) > 1000:
            return await ctx.reply(f"{E_ERR} Note too long (max 1000 chars).")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO mod_notes (guild_id, user_id, mod_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
                             (ctx.guild.id, member.id, ctx.author.id, text, time.time()))
            await db.commit()
        await ctx.reply(f"{E_OK} Note added for {member.mention}.")

    @note.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def note_list(self, ctx, member: discord.Member):
        """View all notes for a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, mod_id, content, created_at FROM mod_notes WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 15", (ctx.guild.id, member.id)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No notes for {member.display_name}.")

        desc = ""
        for nid, mid, content, ts in rows:
            mod = ctx.guild.get_member(mid)
            mod_name = mod.display_name if mod else f"Mod {mid}"
            desc += f"`#{nid}` by **{mod_name}** <t:{int(ts)}:R>\n> {content[:80]}\n\n"

        embed = discord.Embed(title=f"<:notes_emoji:1495398779656867992> Notes for {member.display_name}", description=desc, color=EMBED_COLOR)
        embed.set_footer(text=f"{len(rows)} note(s)")
        await ctx.reply(embed=embed, mention_author=False)

    @note.command(name="delete")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def note_delete(self, ctx, note_id: int):
        """Delete a note by ID."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id FROM mod_notes WHERE id = ? AND guild_id = ?", (note_id, ctx.guild.id)) as cur:
                if not await cur.fetchone():
                    return await ctx.reply(f"{E_ERR} Note `#{note_id}` not found.")
            await db.execute("DELETE FROM mod_notes WHERE id = ? AND guild_id = ?", (note_id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Note `#{note_id}` deleted.")

    @note.command(name="clear")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def note_clear(self, ctx, member: discord.Member):
        """Clear all notes for a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM mod_notes WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} All notes cleared for {member.mention}.")

    @note.command(name="search")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def note_search(self, ctx, *, query: str):
        """Search through notes."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, user_id, content FROM mod_notes WHERE guild_id = ? AND content LIKE ? LIMIT 10", (ctx.guild.id, f"%{query}%")) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No notes matching `{query}`.")
        desc = ""
        for nid, uid, content in rows:
            m = ctx.guild.get_member(uid)
            name = m.display_name if m else f"User {uid}"
            desc += f"`#{nid}` **{name}**: {content[:60]}...\n"
        embed = discord.Embed(title=f"<:sysearch:1495401256485912658> Notes matching '{query}'", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="flag")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def flag_user(self, ctx, member: discord.Member, *, reason: str = "No reason"):
        """Flag a user for moderator attention."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mod_flags (guild_id, user_id, flag, mod_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (ctx.guild.id, member.id, reason, ctx.author.id, time.time())
            )
            await db.commit()
        await ctx.reply(f"<:flaggedsy:1495401728332267631> {member.mention} has been flagged: **{reason}**")

    @commands.command(name="unflag")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def unflag_user(self, ctx, member: discord.Member):
        """Remove a flag from a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM mod_flags WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Flag removed from {member.mention}.")

    @commands.command(name="flagged")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def flagged_list(self, ctx):
        """View all flagged users."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, flag, created_at FROM mod_flags WHERE guild_id = ? ORDER BY created_at DESC", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No flagged users.")
        desc = ""
        for uid, flag, ts in rows:
            m = ctx.guild.get_member(uid)
            name = m.display_name if m else f"User {uid}"
            desc += f"🚩 **{name}** — {flag} (<t:{int(ts)}:R>)\n"
        embed = discord.Embed(title="🚩 Flagged Users", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="flaginfo")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def flag_info(self, ctx, member: discord.Member):
        """View flag details for a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT flag, mod_id, created_at FROM mod_flags WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} {member.display_name} is not flagged.")
        mod = ctx.guild.get_member(row[1])
        embed = discord.Embed(title=f"🚩 Flag: {member.display_name}", color=EMBED_COLOR)
        embed.add_field(name="Reason", value=row[0], inline=False)
        embed.add_field(name="Flagged by", value=mod.mention if mod else f"Mod {row[1]}")
        embed.add_field(name="When", value=f"<t:{int(row[2])}:R>")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(client):
    await init_db()
    await client.add_cog(ModNotesCog(client))
