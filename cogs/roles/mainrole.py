from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from core import *
from utils.Tools import blacklist_check, ignore_check
from utils.paginator import Paginator as HackerPaginator
from utils.paginators import DescriptionEmbedPaginator

DB_PATH = "database/antinuke.db"

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_SHIELD= "<:synapseShield:1477548906848981225>"
E_NOTE  = "<:SynapseNote:1477236015830663324>"

COLOR      = 0x2b2d31
COLOR_OK   = 0x2b2d31
COLOR_ERR  = 0x2b2d31
COLOR_WARN = 0xfca903
FOOTER     = "Synapse · Main Role System"



def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_TICK} {desc}", color=COLOR_OK)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_CROSS} {desc}", color=COLOR_ERR)
    e.set_footer(text=FOOTER)
    return e

def _warn(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_EXCL} {desc}", color=COLOR_WARN)
    e.set_footer(text=FOOTER)
    return e



async def _is_an_admin(guild_id: int, user_id: int, bot: commands.Bot) -> bool:
    guild = bot.get_guild(guild_id)
    if guild and guild.owner_id == user_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ) as cur:
            return await cur.fetchone() is not None


class MainRole(commands.Cog):
    """Main Role system for panic mode recovery."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="mainrole", aliases=["mr"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def mainrole(self, ctx: commands.Context):
        """Main Role documentation."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        embed = discord.Embed(
            description=(
                "**MainRole** system stores important roles that should always be restored after "
                "**Panic Mode**, antinuke recovery, mass role deletion, or permission wipe. "
                "These roles are **protected and auto-restored** by the antinuke system.\n\n"
                f"> Available to **Server Owner** and **Antinuke Admins**\n\n"
                f"**Subcommands:** `add <role>` · `remove <role>` · `list` · `reset`"
            ),
            color=COLOR,
        )
        embed.set_author(
            name="Main Role System",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @mainrole.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def mainrole_add(self, ctx: commands.Context, role: discord.Role):
        """Add a role to the main role list."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        if role.managed:
            return await ctx.send(embed=_err(f"**{role.name}** is a managed/integration role and cannot be added."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM antinuke_mainroles WHERE guild_id=? AND role_id=?",
                (ctx.guild.id, role.id),
            ) as cur:
                if await cur.fetchone():
                    return await ctx.send(embed=_err(f"**{role.name}** is already in the main role list."))

            async with db.execute(
                "SELECT COUNT(*) FROM antinuke_mainroles WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                count = (await cur.fetchone())[0]
            if count >= 20:
                return await ctx.send(embed=_err("You can have a maximum of **20** main roles. Remove one first."))

            await db.execute(
                "INSERT INTO antinuke_mainroles (guild_id, role_id) VALUES (?,?)",
                (ctx.guild.id, role.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"**{role.mention}** has been added to the **Main Role** list."))

    @mainrole.command(name="remove", aliases=["rem", "rm"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def mainrole_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from the main role list."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM antinuke_mainroles WHERE guild_id=? AND role_id=?",
                (ctx.guild.id, role.id),
            ) as cur:
                if not await cur.fetchone():
                    return await ctx.send(embed=_err(f"**{role.name}** is not in the main role list."))
            await db.execute(
                "DELETE FROM antinuke_mainroles WHERE guild_id=? AND role_id=?",
                (ctx.guild.id, role.id),
            )
            await db.commit()

        await ctx.send(embed=_ok(f"**{role.mention}** has been removed from the **Main Role** list."))

    @mainrole.command(name="list", aliases=["show", "ls"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def mainrole_list(self, ctx: commands.Context):
        """List all main roles."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM antinuke_mainroles WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=_err("No main roles have been added yet."))

        entries = []
        for idx, (rid,) in enumerate(rows, 1):
            role = ctx.guild.get_role(rid)
            name = role.mention if role else f"`{rid}` (deleted)"
            perms = []
            if role:
                if role.permissions.administrator:
                    perms.append("Admin")
                elif role.permissions.manage_guild:
                    perms.append("Manage Guild")
                elif role.permissions.ban_members:
                    perms.append("Ban Members")
            perm_str = f" `[{', '.join(perms)}]`" if perms else ""
            entries.append(f"`{idx}.` {E_TICK} {name}{perm_str}")

        source = DescriptionEmbedPaginator(
            entries, per_page=10,
            title=f"Main Roles — {ctx.guild.name} ({len(rows)}/20)"
        )
        await HackerPaginator(source, ctx=ctx).paginate()

    @mainrole.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def mainrole_reset(self, ctx: commands.Context):
        """Clear all main roles. Owner only."""
        if not await _is_an_admin(ctx.guild.id, ctx.author.id, self.bot):
            return await ctx.send(embed=_err("Only the **server owner** or an **Antinuke Admin** can use this."))

        view = _ConfirmView(ctx)
        confirm_embed = discord.Embed(
            description=(
                f"{E_EXCL} This will **remove all** main roles from the protection list.\n"
                f"Are you sure?"
            ),
            color=COLOR_WARN,
        )
        confirm_embed.set_author(name="Reset Main Roles?", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        confirm_embed.set_footer(text=FOOTER)
        msg = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.confirmed:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM antinuke_mainroles WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()

        await msg.edit(embed=_ok("All **Main Roles** have been **reset**."), view=None)


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

    @discord.ui.button(label="Yes, Reset", style=discord.ButtonStyle.red)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=_err("Reset cancelled."), view=None)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MainRole(bot))
