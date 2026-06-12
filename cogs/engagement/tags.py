import discord
from discord.ext import commands
import aiosqlite
import time

from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/tags.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS tags (
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                PRIMARY KEY (guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS tag_aliases (
                guild_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                original TEXT NOT NULL,
                PRIMARY KEY (guild_id, alias)
            );

            CREATE TABLE IF NOT EXISTS sticky_messages (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                message_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER,
                content TEXT NOT NULL,
                remind_at REAL NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        await db.commit()


class TagsCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def tag(self, ctx, *, name: str = None):
        """View a tag's content."""
        if not name:
            return await ctx.reply(f"{E_ERR} Usage: `tag <name>` or see `tag list`.")

        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT original FROM tag_aliases WHERE guild_id = ? AND alias = ?", (ctx.guild.id, name)) as cur:
                alias = await cur.fetchone()
            if alias:
                name = alias[0]

            async with db.execute("SELECT content FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")

            await db.execute("UPDATE tags SET uses = uses + 1 WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            await db.commit()
        
        content = row[0].replace("{user}", ctx.author.mention).replace("{server}", ctx.guild.name).replace("{channel}", ctx.channel.mention)
        await ctx.reply(content, mention_author=False)

    @tag.command(name="create")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def tag_create(self, ctx, name: str, *, content: str):
        """Create a new tag."""
        name = name.lower().strip()
        if len(name) > 50:
            return await ctx.reply(f"{E_ERR} Tag name too long.")
        if len(content) > 2000:
            return await ctx.reply(f"{E_ERR} Tag content too long.")

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                if await cur.fetchone():
                    return await ctx.reply(f"{E_ERR} Tag `{name}` already exists.")
            await db.execute("INSERT INTO tags (guild_id, name, content, owner_id, created_at) VALUES (?, ?, ?, ?, ?)",
                             (ctx.guild.id, name, content, ctx.author.id, time.time()))
            await db.commit()
        await ctx.reply(f"{E_OK} Tag `{name}` created.")

    @tag.command(name="edit")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def tag_edit(self, ctx, name: str, *, content: str):
        """Edit a tag's content."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT owner_id FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
            await db.execute("UPDATE tags SET content = ? WHERE guild_id = ? AND name = ?", (content, ctx.guild.id, name))
            await db.commit()
        await ctx.reply(f"{E_OK} Tag `{name}` updated.")

    @tag.command(name="delete")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def tag_delete(self, ctx, *, name: str):
        """Delete a tag."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                if not await cur.fetchone():
                    return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
            await db.execute("DELETE FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            await db.execute("DELETE FROM tag_aliases WHERE guild_id = ? AND original = ?", (ctx.guild.id, name))
            await db.commit()
        await ctx.reply(f"{E_OK} Tag `{name}` deleted.")

    @tag.command(name="list")
    @blacklist_check()
    @ignore_check()
    async def tag_list(self, ctx):
        """List all tags."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, uses FROM tags WHERE guild_id = ? ORDER BY uses DESC", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No tags in this server.")
        desc = ", ".join(f"`{n}` ({u})" for n, u in rows[:50])
        embed = discord.Embed(title="<:icons_tag:1495399163280625774> Tags", description=desc, color=EMBED_COLOR)
        embed.set_footer(text=f"{len(rows)} total tags")
        await ctx.reply(embed=embed, mention_author=False)

    @tag.command(name="info")
    @blacklist_check()
    @ignore_check()
    async def tag_info(self, ctx, *, name: str):
        """View info about a tag."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT owner_id, uses, created_at FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
        owner = ctx.guild.get_member(row[0])
        embed = discord.Embed(title=f"<:icons_tag:1495399163280625774> Tag: {name}", color=EMBED_COLOR)
        embed.add_field(name="Owner", value=owner.mention if owner else f"User {row[0]}")
        embed.add_field(name="Uses", value=str(row[1]))
        embed.add_field(name="Created", value=f"<t:{int(row[2])}:R>")
        await ctx.reply(embed=embed, mention_author=False)

    @tag.command(name="alias")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def tag_alias(self, ctx, alias: str, *, original: str):
        """Create an alias for a tag."""
        alias = alias.lower().strip()
        original = original.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, original)) as cur:
                if not await cur.fetchone():
                    return await ctx.reply(f"{E_ERR} Original tag `{original}` not found.")
            await db.execute("INSERT OR REPLACE INTO tag_aliases (guild_id, alias, original) VALUES (?, ?, ?)", (ctx.guild.id, alias, original))
            await db.commit()
        await ctx.reply(f"{E_OK} Alias `{alias}` → `{original}` created.")

    @tag.command(name="removealias")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def tag_removealias(self, ctx, *, alias: str):
        """Remove a tag alias."""
        alias = alias.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM tag_aliases WHERE guild_id = ? AND alias = ?", (ctx.guild.id, alias))
            await db.commit()
        await ctx.reply(f"{E_OK} Alias `{alias}` removed.")

    @tag.command(name="search")
    @blacklist_check()
    @ignore_check()
    async def tag_search(self, ctx, *, query: str):
        """Search for a tag."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM tags WHERE guild_id = ? AND name LIKE ?", (ctx.guild.id, f"%{query}%")) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No tags matching `{query}`.")
        desc = ", ".join(f"`{r[0]}`" for r in rows[:25])
        await ctx.reply(embed=discord.Embed(title=f"<:sysearch:1495401256485912658> Tags matching '{query}'", description=desc, color=EMBED_COLOR), mention_author=False)

    @tag.command(name="top")
    @blacklist_check()
    @ignore_check()
    async def tag_top(self, ctx):
        """View most used tags."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, uses FROM tags WHERE guild_id = ? ORDER BY uses DESC LIMIT 10", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No tags.")
        desc = "\n".join(f"`{i+1}.` **{n}** — {u} uses" for i, (n, u) in enumerate(rows))
        embed = discord.Embed(title="<:icons_tag:1495399163280625774> Top Tags", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @tag.command(name="claim")
    @blacklist_check()
    @ignore_check()
    async def tag_claim(self, ctx, *, name: str):
        """Claim a tag whose owner left the server."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT owner_id FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
        if ctx.guild.get_member(row[0]):
            return await ctx.reply(f"{E_ERR} The tag owner is still in the server.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tags SET owner_id = ? WHERE guild_id = ? AND name = ?", (ctx.author.id, ctx.guild.id, name))
            await db.commit()
        await ctx.reply(f"{E_OK} You claimed tag `{name}`.")

    @tag.command(name="transfer")
    @blacklist_check()
    @ignore_check()
    async def tag_transfer(self, ctx, member: discord.Member, *, name: str):
        """Transfer a tag you own to another user."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT owner_id FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
        if row[0] != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            return await ctx.reply(f"{E_ERR} You don't own this tag.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tags SET owner_id = ? WHERE guild_id = ? AND name = ?", (member.id, ctx.guild.id, name))
            await db.commit()
        await ctx.reply(f"{E_OK} Tag `{name}` transferred to {member.mention}.")

    @tag.command(name="raw")
    @blacklist_check()
    @ignore_check()
    async def tag_raw(self, ctx, *, name: str):
        """View a tag's raw content (no variable replacement)."""
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT content FROM tags WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} Tag `{name}` not found.")
        await ctx.reply(f"```\n{row[0]}\n```", mention_author=False)

    @tag.command(name="all")
    @blacklist_check()
    @ignore_check()
    async def tag_all(self, ctx, member: discord.Member = None):
        """View all tags owned by a user."""
        member = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM tags WHERE guild_id = ? AND owner_id = ?", (ctx.guild.id, member.id)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No tags owned by {member.display_name}.")
        desc = ", ".join(f"`{r[0]}`" for r in rows)
        embed = discord.Embed(title=f"<:icons_tag:1495399163280625774> {member.display_name}'s Tags", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @tag.command(name="purge")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def tag_purge(self, ctx, member: discord.Member):
        """Delete all tags owned by a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM tags WHERE guild_id = ? AND owner_id = ?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} All tags by {member.mention} have been purged.")

    @tag.command(name="random")
    @blacklist_check()
    @ignore_check()
    async def tag_random(self, ctx):
        """Get a random tag."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, content FROM tags WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (ctx.guild.id,)) as cur:
                row = await cur.fetchone()
        if not row:
            return await ctx.reply(f"{E_ERR} No tags in this server.")
        content = row[1].replace("{user}", ctx.author.mention).replace("{server}", ctx.guild.name).replace("{channel}", ctx.channel.mention)
        await ctx.reply(f"<:icons_tag:1495399163280625774> **{row[0]}**\n{content}", mention_author=False)

    @tag.command(name="count")
    @blacklist_check()
    @ignore_check()
    async def tag_count(self, ctx, member: discord.Member = None):
        """View tag count for the server or a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            if member:
                async with db.execute("SELECT COUNT(*) FROM tags WHERE guild_id = ? AND owner_id = ?", (ctx.guild.id, member.id)) as cur:
                    count = (await cur.fetchone())[0]
                await ctx.reply(f"<:icons_tag:1495399163280625774> {member.display_name} owns **{count}** tag(s).", mention_author=False)
            else:
                async with db.execute("SELECT COUNT(*) FROM tags WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                    count = (await cur.fetchone())[0]
                await ctx.reply(f"<:icons_tag:1495399163280625774> This server has **{count}** tag(s).", mention_author=False)


class StickyCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT content, message_id FROM sticky_messages WHERE guild_id = ? AND channel_id = ?", (message.guild.id, message.channel.id)) as cur:
                row = await cur.fetchone()
        if not row:
            return

        try:
            old_msg = await message.channel.fetch_message(row[1])
            await old_msg.delete()
        except Exception:
            pass

        new_msg = await message.channel.send(f"📌 {row[0]}")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE sticky_messages SET message_id = ? WHERE guild_id = ? AND channel_id = ?", (new_msg.id, message.guild.id, message.channel.id))
            await db.commit()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def sticky(self, ctx):
        """Sticky message system."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help sticky` for a list of subcommands.")

    @sticky.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def sticky_add(self, ctx, *, content: str):
        """Add a sticky message to this channel."""
        msg = await ctx.channel.send(f"📌 {content}")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO sticky_messages (guild_id, channel_id, content, message_id) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, channel_id) DO UPDATE SET content = ?, message_id = ?",
                (ctx.guild.id, ctx.channel.id, content, msg.id, content, msg.id)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} Sticky message set for this channel.", mention_author=False, delete_after=5)

    @sticky.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def sticky_remove(self, ctx):
        """Remove the sticky message from this channel."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sticky_messages WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, ctx.channel.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Sticky message removed.", mention_author=False)

    @sticky.command(name="edit")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    async def sticky_edit(self, ctx, *, content: str):
        """Edit the sticky message."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT message_id FROM sticky_messages WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, ctx.channel.id)) as cur:
                row = await cur.fetchone()
            if not row:
                return await ctx.reply(f"{E_ERR} No sticky message in this channel.")
            await db.execute("UPDATE sticky_messages SET content = ? WHERE guild_id = ? AND channel_id = ?", (content, ctx.guild.id, ctx.channel.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Sticky message updated.", mention_author=False)

    @sticky.command(name="list")
    @blacklist_check()
    @ignore_check()
    async def sticky_list(self, ctx):
        """View all sticky messages."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id, content FROM sticky_messages WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No sticky messages set.")
        desc = "\n".join(f"<#{cid}> — {content[:50]}..." for cid, content in rows)
        embed = discord.Embed(title="📌 Sticky Messages", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @sticky.command(name="clear")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def sticky_clear(self, ctx):
        """Clear all sticky messages."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sticky_messages WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} All sticky messages cleared.", mention_author=False)


class ReminderCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self._task = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._task:
            import asyncio
            self._task = self.client.loop.create_task(self._reminder_loop())

    async def _reminder_loop(self):
        import asyncio
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            now = time.time()
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT id, user_id, channel_id, content FROM reminders WHERE remind_at <= ?", (now,)) as cur:
                    rows = await cur.fetchall()
                for rid, uid, cid, content in rows:
                    ch = self.client.get_channel(cid)
                    if ch:
                        try:
                            await ch.send(f"<:reminder:1495402276981051432> <@{uid}> Reminder: {content}")
                        except Exception:
                            pass
                    await db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
                await db.commit()
            await asyncio.sleep(30)

    @commands.group(invoke_without_command=True, aliases=["remind"])
    @blacklist_check()
    @ignore_check()
    async def reminder(self, ctx, duration: str = None, *, text: str = None):
        """Set a reminder. Duration: 1m, 1h, 1d."""
        if not duration or not text:
            return await ctx.reply(f"{E_ERR} Usage: `reminder <duration> <text>` (e.g. `reminder 30m check oven`)")

        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = duration[-1].lower()
        if unit not in units:
            return await ctx.reply(f"{E_ERR} Invalid duration. Use s/m/h/d.")
        try:
            val = int(duration[:-1])
        except ValueError:
            return await ctx.reply(f"{E_ERR} Invalid duration number.")

        seconds = val * units[unit]
        if seconds > 2592000:
            return await ctx.reply(f"{E_ERR} Max reminder duration is 30 days.")

        remind_at = time.time() + seconds
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO reminders (user_id, channel_id, guild_id, content, remind_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (ctx.author.id, ctx.channel.id, ctx.guild.id if ctx.guild else None, text, remind_at, time.time()))
            await db.commit()
        await ctx.reply(f"{E_OK} I'll remind you <t:{int(remind_at)}:R>: **{text}**")

    @reminder.command(name="list")
    @blacklist_check()
    @ignore_check()
    async def reminder_list(self, ctx):
        """View your active reminders."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, content, remind_at FROM reminders WHERE user_id = ? ORDER BY remind_at ASC", (ctx.author.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} You have no active reminders.")
        desc = "\n".join(f"`#{rid}` <t:{int(rat)}:R> — {content[:50]}" for rid, content, rat in rows)
        embed = discord.Embed(title="⏰ Your Reminders", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @reminder.command(name="delete", aliases=["cancel"])
    @blacklist_check()
    @ignore_check()
    async def reminder_delete(self, ctx, reminder_id: int):
        """Cancel a reminder."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, ctx.author.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Reminder `#{reminder_id}` cancelled.")

    @reminder.command(name="clear")
    @blacklist_check()
    @ignore_check()
    async def reminder_clear(self, ctx):
        """Clear all your reminders."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM reminders WHERE user_id = ?", (ctx.author.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} All your reminders cleared.")


async def setup(client):
    await init_db()
    await client.add_cog(TagsCog(client))
    await client.add_cog(StickyCog(client))
    await client.add_cog(ReminderCog(client))
