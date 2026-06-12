from __future__ import annotations

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from utils.paginator import Paginator as HackerPaginator
from utils.paginators import DescriptionEmbedPaginator

DB_PATH = "database/antinuke.db"
COLOR   = 0x2b2d31

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_OK    = "<:emoji_1769867605256:1467155817726873650>"
E_SHIELD= "<:synapseShield:1477548906848981225>"
E_GEAR  = "<:synapseGear:1477546806232743999>"


class ANAdmin:
    FOOTER = "Synapse — Antinuke Admin System"

    @staticmethod
    def success(text: str) -> discord.Embed:
        from datetime import datetime
        return discord.Embed(
            description=f"> {E_OK} **Success:** {text}",
            color=COLOR, timestamp=datetime.utcnow()
        ).set_footer(text=ANAdmin.FOOTER)

    @staticmethod
    def error(text: str) -> discord.Embed:
        from datetime import datetime
        return discord.Embed(
            description=f"> {E_EXCL} **Error:** {text}",
            color=COLOR, timestamp=datetime.utcnow()
        ).set_footer(text=ANAdmin.FOOTER)

    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        from datetime import datetime
        return discord.Embed(
            title=f"{E_SHIELD} {title}",
            description=description,
            color=COLOR, timestamp=datetime.utcnow()
        ).set_footer(text=ANAdmin.FOOTER)


class AntinukeAdmin(commands.Cog):
    """Owner-only antinuke admin management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _owner_only(self, ctx: commands.Context) -> bool:
        return ctx.author.id == ctx.guild.owner_id

    @commands.group(name="admin", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def admin(self, ctx: commands.Context):
        """Antinuke admin management group."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        embed = ANAdmin.info(
            "Antinuke Admin Management",
            f"**Owner-only** commands to manage antinuke admins.\n\n"
            f"Admins can: manage antinuke, whitelist, quickrole, panic mode, mainrole.\n\n"
            f"**Subcommands:** `add` · `remove` · `list` · `reset`"
        )
        await ctx.send(embed=embed)

    @admin.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def admin_add(self, ctx: commands.Context, member: discord.Member):
        """Add a user as an antinuke admin. Owner only."""
        if not self._owner_only(ctx):
            return await ctx.send(embed=ANAdmin.error("Only the **server owner** can use this."))

        if member.id == ctx.guild.owner_id:
            return await ctx.send(embed=ANAdmin.error("The server owner is already the top-level admin."))

        if member.bot:
            return await ctx.send(embed=ANAdmin.error("Bots cannot be added as admins."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, member.id),
            ) as cur:
                if await cur.fetchone():
                    return await ctx.send(embed=ANAdmin.error(f"**{member}** is already an antinuke admin."))
            await db.execute(
                "INSERT INTO antinuke_admins (guild_id, user_id) VALUES (?,?)",
                (ctx.guild.id, member.id),
            )
            await db.commit()

        await ctx.send(embed=ANAdmin.success(f"**{member.mention}** has been added as an **Antinuke Admin**."))

    @admin.command(name="remove", aliases=["rem", "rm"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def admin_remove(self, ctx: commands.Context, member: discord.Member):
        """Remove an antinuke admin. Owner only."""
        if not self._owner_only(ctx):
            return await ctx.send(embed=ANAdmin.error("Only the **server owner** can use this."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, member.id),
            ) as cur:
                if not await cur.fetchone():
                    return await ctx.send(embed=ANAdmin.error(f"**{member}** is not an antinuke admin."))
            await db.execute(
                "DELETE FROM antinuke_admins WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, member.id),
            )
            await db.commit()

        await ctx.send(embed=ANAdmin.success(f"**{member.mention}** has been removed as an **Antinuke Admin**."))

    @admin.command(name="list", aliases=["show", "ls"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def admin_list(self, ctx: commands.Context):
        """List all antinuke admins. Owner only."""
        if not self._owner_only(ctx):
            return await ctx.send(embed=ANAdmin.error("Only the **server owner** can use this."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM antinuke_admins WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=ANAdmin.error("No antinuke admins added yet."))

        entries = []
        for idx, (uid,) in enumerate(rows, 1):
            member = ctx.guild.get_member(uid)
            name = f"{member.mention} (`{uid}`)" if member else f"`{uid}` (left server)"
            entries.append(f"`{idx}.` {E_TICK} {name}")

        source = DescriptionEmbedPaginator(entries, per_page=10, title=f"Antinuke Admins — {ctx.guild.name}")
        await HackerPaginator(source, ctx=ctx).paginate()

    @admin.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def admin_reset(self, ctx: commands.Context):
        """Remove ALL antinuke admins. Owner only."""
        if not self._owner_only(ctx):
            return await ctx.send(embed=ANAdmin.error("Only the **server owner** can use this."))

        view = _ConfirmView(ctx)
        embed = discord.Embed(
            title=f"{E_GEAR} Reset Antinuke Admins?",
            description=f"> {E_EXCL} This will **remove all** antinuke admins from this server.\n> Are you sure?",
            color=0xFF5555,
        )
        embed.set_footer(text=ANAdmin.FOOTER)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM antinuke_admins WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()

        await msg.edit(
            embed=ANAdmin.success("All antinuke admins have been **reset**."),
            view=None,
        )


class _ConfirmView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, Reset", style=discord.ButtonStyle.red, emoji=E_EXCL)
    async def confirm_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji=E_CROSS)
    async def cancel_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=ANAdmin.error("Reset cancelled."), view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntinukeAdmin(bot))
