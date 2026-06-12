import time
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check

DB_PATH    = "database/afk.db"
EMBED_COLOR = 0x2b2d31

E_AFK  = "<:WickChat:1478069058195689670>"
E_BACK = "<:emoji_1769867605256:1467155817726873650>"
E_PING = "<:SynapseInfo:1478618076961439806>"
E_TICK = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS= "<:emoji_1769867589372:1467155751456735326>"
E_EXCL = "<:SynapseExcl:1477234549552320634>"



async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS afk_users (
                user_id    INTEGER NOT NULL,
                guild_id   INTEGER,
                reason     TEXT    NOT NULL DEFAULT 'AFK',
                started_at REAL    NOT NULL,
                ping_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
            """
        )
        await db.commit()


async def _set_afk(user_id: int, guild_id: Optional[int], reason: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO afk_users (user_id, guild_id, reason, started_at, ping_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                reason=excluded.reason,
                started_at=excluded.started_at,
                ping_count=0
            """,
            (user_id, guild_id, reason, time.time()),
        )
        await db.commit()


async def _get_afk(user_id: int, guild_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT reason, started_at, ping_count, guild_id FROM afk_users WHERE user_id=? AND guild_id=?",
            (user_id, guild_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            async with db.execute(
                "SELECT reason, started_at, ping_count, guild_id FROM afk_users WHERE user_id=? AND guild_id IS NULL",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
    if not row:
        return None
    return {"reason": row[0], "started_at": row[1], "ping_count": row[2], "guild_id": row[3]}


async def _remove_afk(user_id: int, guild_id: int) -> Optional[dict]:
    record = await _get_afk(user_id, guild_id)
    if not record:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        if record["guild_id"] is None:
            await db.execute("DELETE FROM afk_users WHERE user_id=? AND guild_id IS NULL", (user_id,))
        else:
            await db.execute(
                "DELETE FROM afk_users WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            )
        await db.commit()
    return record


async def _increment_ping(user_id: int, guild_id: Optional[int]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if guild_id is None:
            await db.execute(
                "UPDATE afk_users SET ping_count=ping_count+1 WHERE user_id=? AND guild_id IS NULL",
                (user_id,),
            )
        else:
            await db.execute(
                "UPDATE afk_users SET ping_count=ping_count+1 WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            )
        await db.commit()



def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    d, seconds = divmod(seconds, 86400)
    h, seconds = divmod(seconds, 3600)
    m, s = divmod(seconds, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)


def _make_layout(
    description: str,
    *,
    title: str | None = None,
    thumbnail_url: str | None = None,
    color: int = EMBED_COLOR,
) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    text = ""
    if title:
        text += f"**{title}**\n\n"
    text += description

    if thumbnail_url:
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(text),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=thumbnail_url))
            ),
            accent_color=color
        )
    else:
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            accent_color=color
        )
    view.add_item(container)
    return view


class ScopeView(discord.ui.LayoutView):
    def __init__(self, author_id: int, avatar_url: str):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.value: Optional[str] = None
        self.message: Optional[discord.Message] = None

        self.btn_global = discord.ui.Button(label="Global", style=discord.ButtonStyle.primary, custom_id="global_btn")
        self.btn_server = discord.ui.Button(label="This Server", style=discord.ButtonStyle.secondary, custom_id="server_btn")
        self.btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_btn")

        self.btn_global.callback = self.global_btn_cb
        self.btn_server.callback = self.server_btn_cb
        self.btn_cancel.callback = self.cancel_btn_cb

        text = (
            f"**{E_AFK} AFK Setup**\n\n"
            "**Where should your AFK apply?**\n\n"
            "> **Global** \u2014 active in every server you're in\n"
            "> **This Server** \u2014 only applies here\n\n"
            "*Tap a button below, or **Cancel** to abort.*"
        )

        self.action_row = discord.ui.ActionRow(self.btn_global, self.btn_server, self.btn_cancel)
        self.container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(text),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=avatar_url))
            ),
            self.action_row,
            accent_color=EMBED_COLOR
        )
        self.add_item(self.container)

    def _disable_all(self):
        self.btn_global.disabled = True
        self.btn_server.disabled = True
        self.btn_cancel.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{E_EXCL} This isn't your AFK setup!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self._disable_all()
        if self.message:
            self.container = discord.ui.Container(
                discord.ui.TextDisplay(f"**AFK Setup \u2014 Timed Out**\n\n{E_EXCL} AFK setup timed out. Run the command again to set your AFK."),
                self.action_row,
                accent_color=0x2b2d31
            )
            self.clear_items()
            self.add_item(self.container)
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def global_btn_cb(self, interaction: discord.Interaction):
        self.value = "global"
        self.stop()
        await interaction.response.defer()

    async def server_btn_cb(self, interaction: discord.Interaction):
        self.value = "server"
        self.stop()
        await interaction.response.defer()

    async def cancel_btn_cb(self, interaction: discord.Interaction):
        self.value = None
        self.stop()
        await interaction.response.defer()



class AFK(commands.Cog):
    """AFK system — auto-notify and DM on mentions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._recently_set: set[int] = set()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        guild_id  = message.guild.id
        author_id = message.author.id

        if author_id not in self._recently_set:
            record = await _get_afk(author_id, guild_id)
            if record:
                duration = _format_duration(time.time() - record["started_at"])
                await _remove_afk(author_id, guild_id)

                view = _make_layout(
                    f"{E_BACK} Welcome back, {message.author.mention}!\n\n"
                    f"> **Away for:** `{duration}`\n"
                    f"> **Reason:** {record['reason']}\n"
                    f"> **Mentions:** `{record['ping_count']}`",
                    title="You're Back!",
                    thumbnail_url=message.author.display_avatar.url,
                )
                try:
                    await message.reply(view=view, mention_author=False)
                except discord.HTTPException:
                    pass
                return

        if not message.mentions:
            return

        seen: set[int] = set()
        for mentioned in message.mentions:
            if mentioned.bot or mentioned.id == author_id or mentioned.id in seen:
                continue
            seen.add(mentioned.id)

            afk = await _get_afk(mentioned.id, guild_id)
            if not afk:
                continue

            await _increment_ping(mentioned.id, afk["guild_id"])
            duration   = _format_duration(time.time() - afk["started_at"])
            ping_count = afk["ping_count"] + 1
            scope      = "Global" if afk["guild_id"] is None else "This Server"

            view = _make_layout(
                f"{E_AFK} **{mentioned.display_name}** is currently AFK!\n\n"
                f"> **Scope:** {scope}\n"
                f"> **Reason:** {afk['reason']}\n"
                f"> **Away for:** `{duration}`\n"
                f"> **Mentions:** `{ping_count}`",
                title="User is AFK",
                thumbnail_url=mentioned.display_avatar.url,
            )
            try:
                await message.reply(view=view, mention_author=False)
            except discord.HTTPException:
                pass

            pass


    @commands.hybrid_command(
        name="afk",
        description="Set your AFK status with an optional reason.",
    )
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK") -> None:
        import re
        if re.search(r'<@!?\d+>|<@&\d+>|@everyone|@here', reason):
            view = _make_layout(
                f"{E_EXCL} Your AFK reason cannot contain mentions.",
                title="Mentions Not Allowed",
            )
            return await ctx.reply(view=view, mention_author=False)

        existing = await _get_afk(ctx.author.id, ctx.guild.id)
        if existing:
            duration = _format_duration(time.time() - existing["started_at"])
            view = _make_layout(
                f"{E_EXCL} You're **already AFK!**\n\n"
                f"> **Reason:** {existing['reason']}\n"
                f"> **Away for:** `{duration}`",
                title="Already AFK",
                thumbnail_url=ctx.author.display_avatar.url,
            )
            return await ctx.reply(view=view, mention_author=False)

        view = ScopeView(ctx.author.id, ctx.author.display_avatar.url)
        msg = await ctx.reply(view=view, mention_author=False)
        view.message = msg

        await view.wait()

        if view.value is None:
            cancelled_view = _make_layout(
                f"{E_CROSS} AFK setup was **cancelled**.",
                title="Cancelled",
                color=0x2b2d31,
            )
            view._disable_all()
            return await msg.edit(view=cancelled_view)

        guild_id    = None if view.value == "global" else ctx.guild.id
        scope_label = "Global" if guild_id is None else "This Server"

        await _set_afk(ctx.author.id, guild_id, reason)

        self._recently_set.add(ctx.author.id)
        self.bot.loop.call_later(6, lambda: self._recently_set.discard(ctx.author.id))

        confirm_view = _make_layout(
            f"{E_AFK} You're now **AFK [{scope_label}]**!\n\n"
            f"> **Reason:** {reason}\n"
            f"> *Your AFK will be removed when you send your next message.*",
            title="AFK Set",
            thumbnail_url=ctx.author.display_avatar.url,
        )
        view._disable_all()
        await msg.edit(view=confirm_view)



async def setup(bot: commands.Bot) -> None:
    await _init_db()
    await bot.add_cog(AFK(bot))
