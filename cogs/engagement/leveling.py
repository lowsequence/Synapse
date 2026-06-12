import random
import time
import math
import discord
from discord.ext import commands
import aiosqlite

from utils.Tools import blacklist_check, ignore_check
from utils.level_cards import fetch_avatar, render_rank_card, render_leaderboard_card, render_levelup_card

DB_PATH = "database/leveling.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"

def _fmt(n: int) -> str:
    return f"{n:,}"

def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS level_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                channel_id INTEGER,
                stack_roles INTEGER NOT NULL DEFAULT 1,
                xp_rate REAL NOT NULL DEFAULT 1.0,
                max_level INTEGER NOT NULL DEFAULT 100,
                no_xp_role_id INTEGER,
                announce_type TEXT NOT NULL DEFAULT 'channel'
            );

            CREATE TABLE IF NOT EXISTS level_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 0,
                messages INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, level)
            );

            CREATE TABLE IF NOT EXISTS level_ignored_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS level_ignored_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );

            CREATE TABLE IF NOT EXISTS level_boosted_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                multiplier REAL NOT NULL DEFAULT 2.0,
                PRIMARY KEY (guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS level_boosted_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                multiplier REAL NOT NULL DEFAULT 2.0,
                PRIMARY KEY (guild_id, role_id)
            );
        """)
        await db.commit()


async def get_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT enabled, channel_id, stack_roles, xp_rate, max_level, no_xp_role_id, announce_type FROM level_config WHERE guild_id = ?", (guild_id,)) as cur:
            return await cur.fetchone()


async def ensure_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO level_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()


class LevelingCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self._cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        cfg = await get_config(message.guild.id)
        if not cfg or not cfg[0]:
            return

        key = (message.guild.id, message.author.id)
        now = time.time()
        if key in self._cooldowns and now - self._cooldowns[key] < 60:
            return
        self._cooldowns[key] = now

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id FROM level_ignored_channels WHERE guild_id = ? AND channel_id = ?", (message.guild.id, message.channel.id)) as cur:
                if await cur.fetchone():
                    return

            for role in message.author.roles:
                async with db.execute("SELECT role_id FROM level_ignored_roles WHERE guild_id = ? AND role_id = ?", (message.guild.id, role.id)) as cur:
                    if await cur.fetchone():
                        return

            if cfg[5]:
                no_xp_role = message.guild.get_role(cfg[5])
                if no_xp_role and no_xp_role in message.author.roles:
                    return

        xp_gain = random.randint(15, 25)
        rate = cfg[3]

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT multiplier FROM level_boosted_channels WHERE guild_id = ? AND channel_id = ?", (message.guild.id, message.channel.id)) as cur:
                row = await cur.fetchone()
                if row:
                    xp_gain = int(xp_gain * row[0])

            for role in message.author.roles:
                async with db.execute("SELECT multiplier FROM level_boosted_roles WHERE guild_id = ? AND role_id = ?", (message.guild.id, role.id)) as cur:
                    row = await cur.fetchone()
                    if row:
                        xp_gain = int(xp_gain * row[0])
                        break

        xp_gain = int(xp_gain * rate)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_users (guild_id, user_id, xp, level, messages) VALUES (?, ?, ?, 0, 1) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?, messages = messages + 1",
                (message.guild.id, message.author.id, xp_gain, xp_gain)
            )
            async with db.execute("SELECT xp, level FROM level_users WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id)) as cur:
                row = await cur.fetchone()

            current_xp, current_level = row
            needed = xp_for_level(current_level)

            if current_xp >= needed and current_level < cfg[4]:
                new_level = current_level + 1
                new_xp = current_xp - needed
                await db.execute("UPDATE level_users SET level = ?, xp = ? WHERE guild_id = ? AND user_id = ?", (new_level, new_xp, message.guild.id, message.author.id))

                async with db.execute("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (message.guild.id, new_level)) as cur:
                    role_row = await cur.fetchone()

                reward_role_name = None
                if role_row:
                    role = message.guild.get_role(role_row[0])
                    if role:
                        reward_role_name = role.name
                        try:
                            await message.author.add_roles(role)
                        except Exception:
                            pass

                        if not cfg[2]:
                            async with db.execute("SELECT role_id FROM level_roles WHERE guild_id = ? AND level < ?", (message.guild.id, new_level)) as cur:
                                old_roles = await cur.fetchall()
                            for (old_rid,) in old_roles:
                                old_role = message.guild.get_role(old_rid)
                                if old_role and old_role in message.author.roles:
                                    try:
                                        await message.author.remove_roles(old_role)
                                    except Exception:
                                        pass

                announce = cfg[6]
                if announce != "off":
                    try:
                        av_bytes = await fetch_avatar(message.author.display_avatar.with_size(256).url)
                        card_buf = render_levelup_card(
                            username=message.author.display_name,
                            avatar_bytes=av_bytes,
                            new_level=new_level,
                            role_name=reward_role_name,
                        )
                        file = discord.File(card_buf, filename="levelup.png")

                        if announce == "channel":
                            ch = message.guild.get_channel(cfg[1]) if cfg[1] else message.channel
                            if ch:
                                await ch.send(content=message.author.mention, file=file)
                        elif announce == "dm":
                            await message.author.send(file=file)
                    except Exception:
                        pass

            await db.commit()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def level(self, ctx):
        """Leveling system commands."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help level` for a list of subcommands.")

    @level.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_enable(self, ctx):
        """Enable the leveling system."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Leveling system **enabled**.")

    @level.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_disable(self, ctx):
        """Disable the leveling system."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Leveling system **disabled**.")

    @level.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_channel(self, ctx, channel: discord.TextChannel):
        """Set the level-up announcement channel."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Level-up announcements will be sent to {channel.mention}.")

    @level.command(name="announce")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_announce(self, ctx, mode: str):
        """Set announce mode: channel, dm, or off."""
        mode = mode.lower()
        if mode not in ("channel", "dm", "off"):
            return await ctx.reply(f"{E_ERR} Mode must be `channel`, `dm`, or `off`.")
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET announce_type = ? WHERE guild_id = ?", (mode, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Announce mode set to **{mode}**.")

    @level.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_config(self, ctx):
        """View leveling config."""
        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.reply(f"{E_ERR} Leveling not configured. Use `level enable`.")

        ch = ctx.guild.get_channel(cfg[1]) if cfg[1] else None
        embed = discord.Embed(title="Leveling Config", color=EMBED_COLOR)
        embed.add_field(name="Status", value="Enabled" if cfg[0] else "Disabled")
        embed.add_field(name="Channel", value=ch.mention if ch else "Current channel")
        embed.add_field(name="Stack Roles", value="Yes" if cfg[2] else "No")
        embed.add_field(name="XP Rate", value=f"{cfg[3]}x")
        embed.add_field(name="Max Level", value=str(cfg[4]))
        embed.add_field(name="Announce", value=cfg[6].title())
        await ctx.reply(embed=embed, mention_author=False)

    @level.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def level_reset(self, ctx):
        """Reset all leveling data for this server."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_config WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_users WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_ignored_channels WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_ignored_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_boosted_channels WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM level_boosted_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} All leveling data has been reset for this server.")

    @level.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def level_role(self, ctx):
        """Manage level reward roles."""
        await ctx.reply(f"Use `level role add <level> <role>`, `level role remove <level>`, or `level role list`.")

    @level_role.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_role_add(self, ctx, lvl: int, role: discord.Role):
        """Add a role reward for reaching a level."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, level) DO UPDATE SET role_id = ?",
                (ctx.guild.id, lvl, role.id, role.id)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} Level **{lvl}** will now reward {role.mention}.")

    @level_role.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_role_remove(self, ctx, lvl: int):
        """Remove a level role reward."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_roles WHERE guild_id = ? AND level = ?", (ctx.guild.id, lvl))
            await db.commit()
        await ctx.reply(f"{E_OK} Role reward for level **{lvl}** removed.")

    @level_role.command(name="list")
    @blacklist_check()
    @ignore_check()
    async def level_role_list(self, ctx):
        """List all level role rewards."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await ctx.reply(f"{E_ERR} No level roles configured.")
        desc = "\n".join(f"Level **{lvl}** → <@&{rid}>" for lvl, rid in rows)
        embed = discord.Embed(title="<:SynapeXp:1495398754491039755> Level Roles", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @level.group(name="ignore", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def level_ignore(self, ctx):
        """Ignore channels or roles from gaining XP."""
        await ctx.reply(f"Use `level ignore channel <ch>` or `level ignore role <role>`.")

    @level_ignore.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_ignore_channel(self, ctx, channel: discord.TextChannel):
        """Ignore a channel from XP gain."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO level_ignored_channels (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.reply(f"{E_OK} {channel.mention} will no longer give XP.")

    @level_ignore.command(name="role")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_ignore_role(self, ctx, role: discord.Role):
        """Ignore a role from XP gain."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO level_ignored_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Users with {role.mention} will no longer gain XP.")

    @level.group(name="unignore", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def level_unignore(self, ctx):
        """Unignore channels or roles."""
        await ctx.reply(f"Use `level unignore channel <ch>` or `level unignore role <role>`.")

    @level_unignore.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_unignore_channel(self, ctx, channel: discord.TextChannel):
        """Unignore a channel."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_ignored_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.reply(f"{E_OK} {channel.mention} will now give XP again.")

    @level_unignore.command(name="role")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_unignore_role(self, ctx, role: discord.Role):
        """Unignore a role."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_ignored_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
            await db.commit()
        await ctx.reply(f"{E_OK} {role.mention} can now gain XP again.")

    @level.group(name="boost", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def level_boost(self, ctx):
        """Set XP multipliers for channels or roles."""
        await ctx.reply(f"Use `level boost channel <ch> [mult]` or `level boost role <role> [mult]`.")

    @level_boost.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_boost_channel(self, ctx, channel: discord.TextChannel, multiplier: float = 2.0):
        """Set an XP multiplier for a channel."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_boosted_channels (guild_id, channel_id, multiplier) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, channel_id) DO UPDATE SET multiplier = ?",
                (ctx.guild.id, channel.id, multiplier, multiplier)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} {channel.mention} now has a **{multiplier}x** XP multiplier.")

    @level_boost.command(name="role")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_boost_role(self, ctx, role: discord.Role, multiplier: float = 2.0):
        """Set an XP multiplier for a role."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_boosted_roles (guild_id, role_id, multiplier) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, role_id) DO UPDATE SET multiplier = ?",
                (ctx.guild.id, role.id, multiplier, multiplier)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} {role.mention} now has a **{multiplier}x** XP multiplier.")

    @level.group(name="unboost", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def level_unboost(self, ctx):
        """Remove XP multipliers."""
        await ctx.reply(f"Use `level unboost channel <ch>` or `level unboost role <role>`.")

    @level_unboost.command(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_unboost_channel(self, ctx, channel: discord.TextChannel):
        """Remove XP multiplier from a channel."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_boosted_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.reply(f"{E_OK} XP multiplier removed from {channel.mention}.")

    @level_unboost.command(name="role")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_unboost_role(self, ctx, role: discord.Role):
        """Remove XP multiplier from a role."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_boosted_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
            await db.commit()
        await ctx.reply(f"{E_OK} XP multiplier removed from {role.mention}.")

    @level.command(name="stack")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_stack(self, ctx):
        """Toggle whether level roles stack or replace."""
        await ensure_config(ctx.guild.id)
        cfg = await get_config(ctx.guild.id)
        new = 0 if cfg[2] else 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET stack_roles = ? WHERE guild_id = ?", (new, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Role stacking is now **{'enabled' if new else 'disabled'}**.")

    @level.command(name="rate")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_rate(self, ctx, rate: float):
        """Set the global XP rate multiplier."""
        if rate < 0.1 or rate > 10.0:
            return await ctx.reply(f"{E_ERR} Rate must be between 0.1 and 10.0.")
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET xp_rate = ? WHERE guild_id = ?", (rate, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Global XP rate set to **{rate}x**.")

    @level.command(name="maxlevel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_maxlevel(self, ctx, max_lvl: int):
        """Set the maximum level cap."""
        if max_lvl < 1 or max_lvl > 500:
            return await ctx.reply(f"{E_ERR} Max level must be between 1 and 500.")
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET max_level = ? WHERE guild_id = ?", (max_lvl, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Max level set to **{max_lvl}**.")

    @level.command(name="noxprole")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def level_noxprole(self, ctx, role: discord.Role = None):
        """Set or clear a role that cannot gain XP."""
        await ensure_config(ctx.guild.id)
        rid = role.id if role else None
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_config SET no_xp_role_id = ? WHERE guild_id = ?", (rid, ctx.guild.id))
            await db.commit()
        if role:
            await ctx.reply(f"{E_OK} {role.mention} will no longer gain XP.")
        else:
            await ctx.reply(f"{E_OK} No-XP role cleared.")

    @commands.command(name="rank")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def rank(self, ctx, member: discord.Member = None):
        """View your or someone's rank card."""
        member = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT xp, level, messages FROM level_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id)) as cur:
                row = await cur.fetchone()

        if not row:
            return await ctx.reply(f"{E_ERR} {'You have' if member == ctx.author else 'They have'} no XP data yet.")

        xp, lvl, msgs = row
        needed = xp_for_level(lvl)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM level_users WHERE guild_id = ? AND (level > ? OR (level = ? AND xp > ?))", (ctx.guild.id, lvl, lvl, xp)) as cur:
                rank_pos = (await cur.fetchone())[0] + 1

        status_map = {
            discord.Status.online: (59, 165, 93),
            discord.Status.idle: (250, 168, 26),
            discord.Status.dnd: (237, 66, 69),
        }
        status_color = status_map.get(member.status, (148, 148, 153))

        av_bytes = await fetch_avatar(member.display_avatar.with_size(256).url)
        disc = member.discriminator if hasattr(member, 'discriminator') else "0"

        card_buf = render_rank_card(
            username=member.display_name,
            discriminator=disc,
            avatar_bytes=av_bytes,
            level=lvl,
            xp=xp,
            needed_xp=needed,
            rank=rank_pos,
            messages=msgs,
            status_color=status_color,
        )
        file = discord.File(card_buf, filename="rank.png")
        await ctx.reply(file=file, mention_author=False)

    @commands.command(name="xpleaderboard", aliases=["xplb", "levels"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def xp_leaderboard(self, ctx):
        """View the XP leaderboard."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, level, xp FROM level_users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.reply(f"{E_ERR} No leveling data yet.")

        entries = []
        for uid, lvl, xp in rows:
            m = ctx.guild.get_member(uid)
            name = m.display_name if m else f"User {uid}"
            av = None
            if m:
                try:
                    av = await fetch_avatar(m.display_avatar.with_size(128).url)
                except Exception:
                    pass
            entries.append({"name": name, "level": lvl, "xp": xp, "needed": xp_for_level(lvl), "avatar": av})

        guild_icon = None
        if ctx.guild.icon:
            try:
                guild_icon = await fetch_avatar(ctx.guild.icon.with_size(128).url)
            except Exception:
                pass

        card_buf = render_leaderboard_card(
            guild_name=ctx.guild.name,
            entries=entries,
            guild_icon_bytes=guild_icon,
        )
        file = discord.File(card_buf, filename="leaderboard.png")
        await ctx.reply(file=file, mention_author=False)

    @commands.command(name="givexp")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def give_xp(self, ctx, member: discord.Member, amount: int):
        """Give XP to a user."""
        if amount <= 0:
            return await ctx.reply(f"{E_ERR} Amount must be > 0.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_users (guild_id, user_id, xp) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
                (ctx.guild.id, member.id, amount, amount)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} Gave **{_fmt(amount)} XP** to {member.mention}.")

    @commands.command(name="removexp")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def remove_xp(self, ctx, member: discord.Member, amount: int):
        """Remove XP from a user."""
        if amount <= 0:
            return await ctx.reply(f"{E_ERR} Amount must be > 0.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE level_users SET xp = max(0, xp - ?) WHERE guild_id = ? AND user_id = ?", (amount, ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Removed **{_fmt(amount)} XP** from {member.mention}.")

    @commands.command(name="setlevel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def set_level(self, ctx, member: discord.Member, lvl: int):
        """Set a user's level."""
        if lvl < 0:
            return await ctx.reply(f"{E_ERR} Level can't be negative.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO level_users (guild_id, user_id, xp, level) VALUES (?, ?, 0, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET level = ?, xp = 0",
                (ctx.guild.id, member.id, lvl, lvl)
            )
            await db.commit()
        await ctx.reply(f"{E_OK} Set {member.mention}'s level to **{lvl}**.")

    @commands.command(name="resetxp")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def reset_xp(self, ctx, member: discord.Member):
        """Reset a user's XP and level."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM level_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Reset all XP data for {member.mention}.")


async def setup(client):
    await init_db()
    await client.add_cog(LevelingCog(client))
