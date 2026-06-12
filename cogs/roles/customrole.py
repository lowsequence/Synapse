import os
import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check
from utils.paginators import DescriptionEmbedPaginator
from utils.paginator import Paginator


DB_PATH     = os.path.join("database", "customroles.db")
EMBED_COLOR = 0x2b2d31
E_OK        = "<:emoji_1769867605256:1467155817726873650>"
E_ERR       = "<:emoji_1769867589372:1467155751456735326>"
FOOTER      = "Synapse - CustomRole System"
MAX_SETUPS  = 15

PRESET_NAMES = ("staff", "girl", "friend", "vip", "guest")

PRESET_EMOJIS = {
    "staff":  "<:SynapseCstaff:1477243879349813359>",
    "girl":   "<:SynapseCgirl:1477243973360943104>",
    "friend": "<:SynapseCBuddy:1477243948463558777>",
    "vip":    "<:SynapseCvip:1477243927600828427>",
    "guest":  "<:SynapseCguest:1477243908508487802>",
}



async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS cr_config (
                guild_id   INTEGER PRIMARY KEY,
                reqrole_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS cr_setups (
                guild_id   INTEGER NOT NULL,
                setup_name TEXT    NOT NULL,
                role_id    INTEGER NOT NULL,
                PRIMARY KEY (guild_id, setup_name)
            );
            """
        )
        await db.commit()



def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=0x2b2d31)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=0x2b2d31)
    e.set_footer(text=FOOTER)
    return e

def _info(desc: str, *, title: str | None = None, author_name: str | None = None,
          author_icon: str | None = None) -> discord.Embed:
    e = discord.Embed(description=desc, color=EMBED_COLOR)
    if title:
        e.title = title
    if author_name:
        e.set_author(name=author_name, icon_url=author_icon)
    e.set_footer(text=FOOTER)
    return e



async def _get_reqrole(guild_id: int) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT reqrole_id FROM cr_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else None


async def _set_reqrole(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO cr_config (guild_id, reqrole_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET reqrole_id = excluded.reqrole_id",
            (guild_id, role_id),
        )
        await db.commit()


async def _get_setup(guild_id: int, name: str) -> int | None:
    """Return role_id for a setup name, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role_id FROM cr_setups WHERE guild_id = ? AND setup_name = ?",
            (guild_id, name.lower()),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else None


async def _get_all_setups(guild_id: int) -> list[tuple[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT setup_name, role_id FROM cr_setups WHERE guild_id = ? ORDER BY setup_name",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()


async def _count_setups(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM cr_setups WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0]


async def _create_setup(guild_id: int, name: str, role_id: int) -> bool:
    """Return False if already exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM cr_setups WHERE guild_id = ? AND setup_name = ?",
            (guild_id, name.lower()),
        ) as cur:
            if await cur.fetchone():
                return False
        await db.execute(
            "INSERT INTO cr_setups (guild_id, setup_name, role_id) VALUES (?, ?, ?)",
            (guild_id, name.lower(), role_id),
        )
        await db.commit()
    return True


async def _delete_setup(guild_id: int, name: str) -> bool:
    """Return False if it didn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM cr_setups WHERE guild_id = ? AND setup_name = ?",
            (guild_id, name.lower()),
        ) as cur:
            if not await cur.fetchone():
                return False
        await db.execute(
            "DELETE FROM cr_setups WHERE guild_id = ? AND setup_name = ?",
            (guild_id, name.lower()),
        )
        await db.commit()
    return True


async def _reset_guild(guild_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cr_config WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM cr_setups WHERE guild_id = ?", (guild_id,))
        await db.commit()



async def _check_reqrole(ctx: commands.Context) -> bool:
    """
    Validates that the invoker has the reqrole.
    Administrators still MUST have the reqrole — no bypass.
    Returns True if OK, else sends an error embed and returns False.
    """
    reqrole_id = await _get_reqrole(ctx.guild.id)
    if reqrole_id is None:
        await ctx.send(embed=_err(
            "No **required role** has been set.\n"
            "An administrator must run `setup reqrole <@role>` first."
        ))
        return False

    role = ctx.guild.get_role(reqrole_id)
    if role is None:
        await ctx.send(embed=_err(
            "The configured required role no longer exists.\n"
            "An administrator must set a new one with `setup reqrole <@role>`."
        ))
        return False

    if role not in ctx.author.roles:
        await ctx.send(embed=_err(
            f"You need the {role.mention} role to use custom‑role commands."
        ))
        return False

    return True


async def _validate_hierarchy(ctx: commands.Context, role: discord.Role) -> bool:
    """Verify bot's top role is above the target role."""
    if ctx.guild.me.top_role <= role:
        await ctx.send(embed=_err(
            f"I cannot manage {role.mention} — it is **above** or **equal** to my highest role.\n"
            f"> Move my role higher in *Server Settings → Roles*."
        ))
        return False
    return True



async def _assign_role(ctx: commands.Context, member: discord.Member, setup_name: str) -> None:
    """Toggle the role for *member* using the given *setup_name*."""
    role_id = await _get_setup(ctx.guild.id, setup_name)
    if role_id is None:
        return await ctx.send(embed=_err(
            f"The setup **`{setup_name}`** does not exist.\n"
            f"> Use `setup create {setup_name} <@role>` to create it."
        ))

    role = ctx.guild.get_role(role_id)
    if role is None:
        return await ctx.send(embed=_err(
            f"The role linked to **`{setup_name}`** no longer exists.\n"
            f"> Delete and recreate the setup."
        ))

    if not await _validate_hierarchy(ctx, role):
        return

    emoji = PRESET_EMOJIS.get(setup_name, "<:SyanapsePechkas:1477246737776377856>")

    if role in member.roles:
        await member.remove_roles(role, reason=f"CustomRole: {setup_name} removed by {ctx.author}")
        embed = discord.Embed(
            description=(
                f"{E_OK} **{emoji} {setup_name.title()} — Role Removed**\n\n"
                f"> **Member:** {member.mention}\n"
                f"> **Role:** {role.mention}\n"
                f"> **Action:** Removed"
            ),
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)
    else:
        await member.add_roles(role, reason=f"CustomRole: {setup_name} assigned by {ctx.author}")
        embed = discord.Embed(
            description=(
                f"{E_OK} **{emoji} {setup_name.title()} — Role Assigned**\n\n"
                f"> **Member:** {member.mention}\n"
                f"> **Role:** {role.mention}\n"
                f"> **Action:** Assigned"
            ),
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)




class CustomRole(commands.Cog):
    """Custom Role system with assignable setups."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self._register_dynamic_commands())

    _dynamic_commands: set[str] = set()

    def cog_unload(self):
        """Remove all dynamically injected top‑level commands on cog unload."""
        for name in list(self._dynamic_commands):
            cmd = self.bot.get_command(name)
            if cmd:
                self.bot.remove_command(name)
        self._dynamic_commands.clear()


    async def _register_dynamic_commands(self) -> None:
        """
        On cog load, read every guild's setups from the DB and ensure
        a top‑level command exists for each custom (non‑preset) setup name.
        Preset commands (staff, girl, …) are always present as hard-coded
        top‑level commands; custom ones are added dynamically.
        """
        await self.bot.wait_until_ready()
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT DISTINCT setup_name FROM cr_setups") as cur:
                    rows = await cur.fetchall()
                    names = [r[0] for r in rows]

            for name in names:
                if name in PRESET_NAMES:
                    continue
                self._inject_dynamic_command(name)
        except Exception:
            pass

    def _inject_dynamic_command(self, name: str) -> None:
        """Register a top‑level bot command for a custom setup name."""
        if self.bot.get_command(name):
            return

        @commands.command(name=name, help=f"Assign/remove the **{name}** role to a member.")
        @blacklist_check()
        @ignore_check()
        @commands.cooldown(1, 5, commands.BucketType.user)
        @commands.guild_only()
        async def _dynamic(ctx: commands.Context, member: discord.Member, _n=name):
            if not await _check_reqrole(ctx):
                return
            await _assign_role(ctx, member, _n)

        self.bot.add_command(_dynamic)
        self._dynamic_commands.add(name)

    def _remove_dynamic_command(self, name: str) -> None:
        """Remove a dynamically registered top‑level command."""
        cmd = self.bot.get_command(name)
        if cmd:
            self.bot.remove_command(name)
        self._dynamic_commands.discard(name)


    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def setup(self, ctx: commands.Context):
        """Manage custom role setups."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @setup.command(name="reqrole")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def setup_reqrole(self, ctx: commands.Context, role: discord.Role):
        """Set the role required to use custom‑role commands: `setup reqrole <@role>`"""
        await _set_reqrole(ctx.guild.id, role.id)
        embed = discord.Embed(
            description=(
                f"{E_OK} **Required Role Updated**\n\n"
                f"> <:SynapseReqRole:1477246535447089192> **Role:** {role.mention}\n"
                f"> Only members with this role can assign/remove custom roles."
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @setup.command(name="create")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def setup_create(self, ctx: commands.Context, name: str, role: discord.Role):
        """Create a custom setup: `setup create <name> <@role>`"""
        name = name.lower().strip()

        if not name.isalnum():
            return await ctx.send(embed=_err("Setup name must be **alphanumeric** (no spaces or symbols)."))
        if len(name) > 20:
            return await ctx.send(embed=_err("Setup name must be **20 characters** or fewer."))

        reserved = {"setup", "config", "reset", "list", "reqrole", "help", "create", "delete"}
        if name in reserved:
            return await ctx.send(embed=_err(f"`{name}` is a **reserved** command name."))

        count = await _count_setups(ctx.guild.id)
        if count >= MAX_SETUPS:
            return await ctx.send(embed=_err(
                f"You have reached the maximum of **{MAX_SETUPS}** setups.\n"
                "> Delete an existing one with `setup delete <name>`."
            ))

        if not await _validate_hierarchy(ctx, role):
            return

        ok = await _create_setup(ctx.guild.id, name, role.id)
        if not ok:
            return await ctx.send(embed=_err(f"A setup named **`{name}`** already exists."))

        if name not in PRESET_NAMES:
            self._inject_dynamic_command(name)

        emoji = PRESET_EMOJIS.get(name, "<:SyanapsePechkas:1477246737776377856>")
        embed = discord.Embed(
            description=(
                f"{E_OK} **Setup Created**\n\n"
                f"> {emoji} **Name:** `{name}`\n"
                f"> <:SynapseMask:1477246382812172328> **Role:** {role.mention}\n"
                f"> <:SynapsePin:1477246480598175815> **Usage:** `{name} <@user>`\n\n"
                f"> *Setups:* `[{count + 1}/{MAX_SETUPS}]`"
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @setup.command(name="delete")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def setup_delete(self, ctx: commands.Context, name: str):
        """Delete a custom setup: `setup delete <name>`"""
        name = name.lower().strip()
        ok = await _delete_setup(ctx.guild.id, name)
        if not ok:
            return await ctx.send(embed=_err(f"No setup named **`{name}`** exists."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM cr_setups WHERE setup_name = ? LIMIT 1", (name,)
            ) as cur:
                still_used = await cur.fetchone()

        if not still_used and name not in PRESET_NAMES:
            self._remove_dynamic_command(name)

        await ctx.send(embed=_ok(f"Setup **`{name}`** has been **deleted**."))


    @setup.command(name="list")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_list(self, ctx: commands.Context):
        """List all setups for this server."""
        setups = await _get_all_setups(ctx.guild.id)
        if not setups:
            return await ctx.send(embed=_err(
                "No setups configured.\n> Use `setup create <name> <@role>` to get started."
            ))

        lines: list[str] = []
        for idx, (sname, rid) in enumerate(setups, 1):
            role = ctx.guild.get_role(rid)
            emoji = PRESET_EMOJIS.get(sname, "<:SyanapsePechkas:1477246737776377856>")
            role_display = role.mention if role else "`deleted role`"
            tag = " `preset`" if sname in PRESET_NAMES else ""
            lines.append(f"{emoji} **`{idx}`.** **`{sname}`** → {role_display}{tag}")

        source = DescriptionEmbedPaginator(
            lines,
            title=f"Custom Role Setups [{len(setups)}/{MAX_SETUPS}]",
            per_page=10
        )
        paginator = Paginator(source, ctx=ctx)
        await paginator.paginate()


    @setup.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_config(self, ctx: commands.Context):
        """Show the full custom‑role configuration."""
        reqrole_id = await _get_reqrole(ctx.guild.id)
        setups     = await _get_all_setups(ctx.guild.id)

        if reqrole_id:
            role = ctx.guild.get_role(reqrole_id)
            reqrole_line = role.mention if role else "`deleted role`"
        else:
            reqrole_line = "`not set`"

        preset_lines: list[str] = []
        custom_lines: list[str] = []
        for sname, rid in setups:
            role = ctx.guild.get_role(rid)
            emoji = PRESET_EMOJIS.get(sname, "<:SyanapsePechkas:1477246737776377856>")
            display = role.mention if role else "`deleted role`"
            line = f"> {emoji} **`{sname}`** → {display}"
            if sname in PRESET_NAMES:
                preset_lines.append(line)
            else:
                custom_lines.append(line)

        desc_parts = [
            f"**CustomRole Configuration**\n",
            f"<:SynapseReqRole:1477246535447089192> **Required Role:** {reqrole_line}\n",
        ]

        if preset_lines:
            desc_parts.append(f"**Preset Setups [{len(preset_lines)}]**\n" + "\n".join(preset_lines) + "\n")
        if custom_lines:
            desc_parts.append(f"**Custom Setups [{len(custom_lines)}]**\n" + "\n".join(custom_lines) + "\n")
        if not preset_lines and not custom_lines:
            desc_parts.append("> *No setups configured.*\n")

        desc_parts.append(f"**Total:** `{len(setups)}/{MAX_SETUPS}`")

        embed = discord.Embed(description="\n".join(desc_parts), color=EMBED_COLOR)
        embed.set_author(
            name=f"{ctx.guild.name} — CustomRole",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @setup.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def setup_reset(self, ctx: commands.Context):
        """Wipe all custom‑role setups and config for this server."""
        setups = await _get_all_setups(ctx.guild.id)
        await _reset_guild(ctx.guild.id)

        for sname, _ in setups:
            if sname in PRESET_NAMES:
                continue
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT 1 FROM cr_setups WHERE setup_name = ? LIMIT 1", (sname,)
                ) as cur:
                    still_used = await cur.fetchone()
            if not still_used:
                self._remove_dynamic_command(sname)

        await ctx.send(embed=_ok(
            "All custom‑role **setups** and **configuration** have been **reset** for this server."
        ))


    @setup.command(name="staff")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_staff(self, ctx: commands.Context):
        """Show the staff preset setup info."""
        await self._show_preset_info(ctx, "staff")

    @setup.command(name="girl")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_girl(self, ctx: commands.Context):
        """Show the girl preset setup info."""
        await self._show_preset_info(ctx, "girl")

    @setup.command(name="friend")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_friend(self, ctx: commands.Context):
        """Show the friend preset setup info."""
        await self._show_preset_info(ctx, "friend")

    @setup.command(name="vip")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_vip(self, ctx: commands.Context):
        """Show the vip preset setup info."""
        await self._show_preset_info(ctx, "vip")

    @setup.command(name="guest")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def setup_guest(self, ctx: commands.Context):
        """Show the guest preset setup info."""
        await self._show_preset_info(ctx, "guest")

    async def _show_preset_info(self, ctx: commands.Context, name: str) -> None:
        """Display info about a preset setup for this guild."""
        emoji   = PRESET_EMOJIS[name]
        role_id = await _get_setup(ctx.guild.id, name)

        if role_id is None:
            embed = discord.Embed(
                description=(
                    f"**{emoji} {name.title()} Preset**\n\n"
                    f"> **Status:** `not configured`\n"
                    f"> **Setup:** `setup create {name} <@role>`\n"
                    f"> **Usage:** `{name} <@user>` *(after setup)*"
                ),
                color=EMBED_COLOR,
            )
        else:
            role = ctx.guild.get_role(role_id)
            role_display = role.mention if role else "`deleted role`"
            embed = discord.Embed(
                description=(
                    f"**{emoji} {name.title()} Preset**\n\n"
                    f"> **Status:** `configured` \n"
                    f"> **Role:** {role_display}\n"
                    f"> **Usage:** `{name} <@user>`"
                ),
                color=EMBED_COLOR,
            )

        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @commands.command(name="staff")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def assign_staff(self, ctx: commands.Context, member: discord.Member):
        """Assign/remove the **staff** role to a member."""
        if not await _check_reqrole(ctx):
            return
        await _assign_role(ctx, member, "staff")

    @commands.command(name="girl")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def assign_girl(self, ctx: commands.Context, member: discord.Member):
        """Assign/remove the **girl** role to a member."""
        if not await _check_reqrole(ctx):
            return
        await _assign_role(ctx, member, "girl")

    @commands.command(name="friend")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def assign_friend(self, ctx: commands.Context, member: discord.Member):
        """Assign/remove the **friend** role to a member."""
        if not await _check_reqrole(ctx):
            return
        await _assign_role(ctx, member, "friend")

    @commands.command(name="vip")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def assign_vip(self, ctx: commands.Context, member: discord.Member):
        """Assign/remove the **vip** role to a member."""
        if not await _check_reqrole(ctx):
            return
        await _assign_role(ctx, member, "vip")

    @commands.command(name="guest")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def assign_guest(self, ctx: commands.Context, member: discord.Member):
        """Assign/remove the **guest** role to a member."""
        if not await _check_reqrole(ctx):
            return
        await _assign_role(ctx, member, "guest")





async def setup(bot: commands.Bot):
    await _init_db()
    await bot.add_cog(CustomRole(bot))
