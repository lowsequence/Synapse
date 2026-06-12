import os
import json
import asyncio
import discord
import aiosqlite
from discord.ext import commands
from discord import ui
from typing import Optional
from utils.Tools import blacklist_check, ignore_check


DB_PATH = os.path.join("database", "boost.db")

E_OK   = "<:emoji_1769867605256:1467155817726873650>"
E_ERR  = "<:SynapseExcl:1477234549552320634>"
E_NOTE = "<:SynapseNote:1477236015830663324>"
E_STAR = "<:frozenstar:1478070088119750799>"

COLOR_OK   = 0x2b2d31
COLOR_ERR  = 0x2b2d31
COLOR_INFO = 0x2b2d31
COLOR_WARN = 0x2b2d31
COLOR_BOOST = 0x2b2d31
COLOR_DARK = 0x2b2d31

FOOTER = "Synapse · Boost System"

BOOST_VARS_LIST = (
    "`{user}` `{user_id}` `{user_name}` `{user_tag}` `{user_avatar}` `{user_avatar_png}`\n"
    "`{user_mention}` `{server}` `{server_id}` `{server_membercount}` `{server_icon}`\n"
    "`{server_icon_png}` `{boost_count}` `{boost_tier}` `{guild_owner}` `{guild_owner_id}`\n"
    "`{guild_owner_mention}` `{server_banner}` `{server_banner_png}`"
)



def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=COLOR_OK)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=COLOR_ERR)
    e.set_footer(text=FOOTER)
    return e

def _info(desc: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=desc, color=COLOR_INFO)
    if title:
        e.title = title
    e.set_footer(text=FOOTER)
    return e

def _warn(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=COLOR_WARN)
    e.set_footer(text=FOOTER)
    return e



async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS boost_config (
                guild_id    INTEGER PRIMARY KEY,
                channel_id  INTEGER DEFAULT 0,
                role_id     INTEGER DEFAULT 0,
                mode        TEXT    DEFAULT '',
                config_json TEXT    DEFAULT '{}',
                is_enabled  INTEGER DEFAULT 0,
                delete_after INTEGER DEFAULT 0
            );
        """)
        await db.commit()


async def _get_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM boost_config WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return dict(row)


async def _upsert(guild_id: int, **kwargs) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO boost_config (guild_id) VALUES (?)", (guild_id,))
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [guild_id]
            await db.execute(f"UPDATE boost_config SET {sets} WHERE guild_id = ?", vals)
        await db.commit()


async def _delete(guild_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM boost_config WHERE guild_id = ?", (guild_id,))
        await db.commit()



class BoostEmbedDropdown(ui.Select):
    def __init__(self, builder_view: "BoostEmbedBuilder"):
        options = [
            discord.SelectOption(label="Message",     description="Set plain text above the embed"),
            discord.SelectOption(label="Title",        description="Set the embed title"),
            discord.SelectOption(label="Description",  description="Set the embed description"),
            discord.SelectOption(label="Author",       description="Set the author name"),
            discord.SelectOption(label="Author Icon",  description="Set the author icon URL"),
            discord.SelectOption(label="Thumbnail",    description="Set the thumbnail URL"),
            discord.SelectOption(label="Image",        description="Set the main image URL"),
            discord.SelectOption(label="Footer",       description="Set the footer text"),
            discord.SelectOption(label="Footer Icon",  description="Set the footer icon URL"),
            discord.SelectOption(label="Color",        description="Set the embed color (hex)"),
            discord.SelectOption(label="Add Field",    description="Add a new embed field"),
        ]
        super().__init__(placeholder="Select a component to edit...", min_values=1, max_values=1, options=options)
        self.builder_view = builder_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder_view.author_id:
            return await interaction.response.send_message(embed=_err("This isn't your embed builder."), ephemeral=True)

        choice = self.values[0]

        if choice == "Add Field":
            class AddFieldModal(ui.Modal, title="Add Embed Field"):
                name_input  = ui.TextInput(label="Field Name",  max_length=256)
                value_input = ui.TextInput(label="Field Value", max_length=1024, style=discord.TextStyle.paragraph)

                def __init__(modal_self, bv):
                    super().__init__()
                    modal_self.bv = bv

                async def on_submit(modal_self, modal_interaction: discord.Interaction):
                    fields = modal_self.bv.config.setdefault("fields", [])
                    if len(fields) >= 25:
                        return await modal_interaction.response.send_message(embed=_err("Embeds can have a maximum of **25 fields**."), ephemeral=True)
                    fields.append({"name": modal_self.name_input.value, "value": modal_self.value_input.value, "inline": False})
                    await modal_interaction.response.defer()
                    await modal_self.bv.update_preview()

            return await interaction.response.send_modal(AddFieldModal(self.builder_view))

        key_map = {
            "Message": "message", "Title": "title", "Description": "description",
            "Author": "author_name", "Author Icon": "author_icon", "Thumbnail": "thumbnail",
            "Image": "image", "Footer": "footer_text", "Footer Icon": "footer_icon", "Color": "color"
        }
        key = key_map[choice]

        prompt_embed = _info(
            f"Type the value for **{choice}** in this channel.\n"
            f"Type `cancel` to abort.",
            title=f"<:SynapsePencil:1478314728395898995> Editing: {choice}"
        )
        await interaction.response.send_message(embed=prompt_embed)
        prompt_msg = await interaction.original_response()

        def check(m):
            return m.author.id == self.builder_view.author_id and m.channel.id == interaction.channel.id

        try:
            reply = await interaction.client.wait_for("message", check=check, timeout=120)
            value = reply.content.strip()

            try: await prompt_msg.delete()
            except: pass
            try: await reply.delete()
            except: pass

            if value.lower() != "cancel":
                if key == "color":
                    value = value.lstrip("#")
                    try:
                        color_int = int(value, 16)
                        if color_int > 0xffffff: raise ValueError
                        self.builder_view.config["color"] = color_int
                    except ValueError:
                        await interaction.channel.send(embed=_err("Invalid hex color. Example: `#f47fff`"), delete_after=5)
                        return
                elif key in ("author_icon", "footer_icon", "image", "thumbnail"):
                    if not value.startswith("http"):
                        await interaction.channel.send(embed=_err("Invalid URL. Must start with `http`."), delete_after=5)
                        return
                    self.builder_view.config[key] = value
                else:
                    self.builder_view.config[key] = value

                await self.builder_view.update_preview()

        except asyncio.TimeoutError:
            try: await prompt_msg.edit(content=None, embed=_warn("Timed out waiting for your input."))
            except: pass


class BoostEmbedBuilder(ui.View):
    def __init__(self, ctx, existing_config: dict = None):
        super().__init__(timeout=300)
        self.ctx         = ctx
        self.author_id   = ctx.author.id
        self.config      = existing_config or {"color": COLOR_BOOST}
        self.preview_msg = None
        self.add_item(BoostEmbedDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(embed=_err("This isn't your embed builder."), ephemeral=True)
            return False
        return True

    def build_embed(self):
        embed = discord.Embed(
            title=self.config.get("title"),
            description=self.config.get("description"),
            color=self.config.get("color", COLOR_BOOST)
        )
        if self.config.get("author_name"):
            embed.set_author(name=self.config["author_name"], icon_url=self.config.get("author_icon") or None)
        if self.config.get("footer_text"):
            embed.set_footer(text=self.config["footer_text"], icon_url=self.config.get("footer_icon") or None)
        if self.config.get("image"):
            embed.set_image(url=self.config["image"])
        if self.config.get("thumbnail"):
            embed.set_thumbnail(url=self.config["thumbnail"])
        for field in self.config.get("fields", []):
            embed.add_field(name=field.get("name"), value=field.get("value"), inline=field.get("inline", False))
        return embed

    async def update_preview(self):
        if not self.preview_msg:
            return
        embed = self.build_embed()
        content = self.config.get("message")
        try:
            await self.preview_msg.edit(content=content, embed=embed, view=self)
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.preview_msg:
                await self.preview_msg.edit(embed=_warn("Embed builder timed out. Run `boost edit` again to continue."), view=self)
        except: pass

    @ui.button(label="Variables", style=discord.ButtonStyle.secondary, emoji="<:synapselist:1478319545772146698>", row=1)
    async def vars_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = _info(
            f"**Available Variables:**\n\n{BOOST_VARS_LIST}",
            title="<:synapselist:1478319545772146698> Boost Variables"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Save", style=discord.ButtonStyle.green, emoji="<:emoji_1769867605256:1467155817726873650>", row=1)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        await _upsert(self.ctx.guild.id, mode="embed", config_json=json.dumps(self.config), is_enabled=1)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=_ok("Boost embed has been saved and **enabled** successfully!"),
            view=self
        )
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="<:emoji_1769867589372:1467155751456735326>", row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=_err("Boost embed setup cancelled."), view=self)
        self.stop()



class BoostModeSelection(ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=60)
        self.ctx       = ctx
        self.bot       = bot
        self.author_id = ctx.author.id
        self.msg       = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(embed=_err("This isn't your setup panel."), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.msg:
                await self.msg.edit(embed=_warn("Mode selection timed out. Run `boost setup` again."), view=self)
        except: pass

    @ui.button(label="Message Mode", style=discord.ButtonStyle.secondary)
    async def msg_btn(self, interaction: discord.Interaction, button: ui.Button):
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(
            embed=_info(
                "Type your **boost announcement message** in this channel.\n"
                f"Supports all variables — use `boost variables` to view them.\n"
                "*(Type `cancel` to abort)*",
                title="- Message Mode Setup"
            ),
            view=self
        )
        self.stop()

        def check(m): return m.author.id == self.author_id and m.channel.id == interaction.channel.id
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
            if msg.content.lower() != "cancel":
                config = {"message": msg.content}
                await _upsert(self.ctx.guild.id, mode="message", config_json=json.dumps(config), is_enabled=1)
                await interaction.followup.send(embed=_ok("Boost message saved and **enabled** successfully!"))
            else:
                await interaction.followup.send(embed=_err("Setup cancelled."))
        except asyncio.TimeoutError:
            await interaction.followup.send(embed=_warn("Timed out waiting for message content."))

    @ui.button(label="Embed Mode", style=discord.ButtonStyle.secondary)
    async def embed_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = BoostEmbedBuilder(self.ctx)
        builder_embed = discord.Embed(
            title="<:SynapsePencil:1478314728395898995> Boost Embed Builder",
            description=(
                f"- Use the **dropdown** below to edit each part of your embed.\n"
                f"- Your changes will **live-update** this preview message.\n"
                f"- Press **Variables** to see what placeholders you can use.\n"
                f"- Press **Save** when you're happy with it."
            ),
            color=COLOR_BOOST
        )
        builder_embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=builder_embed, view=view)
        view.preview_msg = await interaction.original_response()
        self.stop()



class BoostCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_error(self, ctx, msg):
        await ctx.send(embed=_err(msg))


    @commands.group(name="boost", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost(self, ctx):
        """Boost message announcement system."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @boost.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def boost_setup(self, ctx):
        """Interactive wizard to create a boost announcement."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if cfg and cfg["mode"]:
                return await ctx.send(embed=_err("A boost setup already exists. Use `boost edit` to modify or `boost reset` to start over."))

            mode_embed = discord.Embed(
                title=f"Boost Message Setup",
                description=(
                    "Choose a **message mode** for boost announcements:\n\n"
                    "**- Message Mode**\n"
                    "> Simple text-only announcement. Lightweight and fast.\n\n"
                    "**- Embed Mode**\n"
                    "> Rich embed with colors, title, fields, images, and full customization."
                ),
                color=COLOR_BOOST
            )
            mode_embed.set_footer(text=FOOTER)
            mode_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

            view = BoostModeSelection(ctx, self.bot)
            view.msg = await ctx.send(embed=mode_embed, view=view)
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="edit")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def boost_edit(self, ctx):
        """Re-edit the existing boost announcement."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["mode"]:
                return await ctx.send(embed=_err("No boost setup found. Use `boost setup` first."))

            mode = cfg["mode"]
            config = json.loads(cfg["config_json"])

            if mode == "embed":
                view = BoostEmbedBuilder(ctx, existing_config=config)
                builder_embed = discord.Embed(
                    title="<:SynapsePencil:1478314728395898995> Editing Boost Embed",
                    description=(
                        f"- Use the **dropdown** below to edit each part of your embed.\n"
                        f"- Your changes will **live-update** this preview.\n"
                        f"- Press **Save** when done."
                    ),
                    color=COLOR_BOOST
                )
                builder_embed.set_footer(text=FOOTER)
                msg = await ctx.send(embed=builder_embed, view=view)
                view.preview_msg = msg

            elif mode == "message":
                await ctx.send(embed=_info(
                    "Type your **new boost message** content below.\n*(Type `cancel` to abort)*",
                    title="- Editing Boost Message"
                ))
                def check(m): return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=120)
                    if msg.content.lower() != "cancel":
                        config["message"] = msg.content
                        await _upsert(ctx.guild.id, config_json=json.dumps(config))
                        await ctx.send(embed=_ok("Boost message has been **updated**."))
                    else:
                        await ctx.send(embed=_err("Edit cancelled."))
                except asyncio.TimeoutError:
                    await ctx.send(embed=_warn("Timed out waiting for message content."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.group(name="channel", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the boost announcement channel."""
        if ctx.invoked_subcommand is not None:
            return
        if channel is None:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                return await help_cog.send_group_help_auto(ctx, ctx.command)
        try:
            await _upsert(ctx.guild.id, channel_id=channel.id)
            await ctx.send(embed=_ok(f"Boost messages will be sent to {channel.mention}."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @boost_channel.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_channel_reset(self, ctx):
        """Remove the boost announcement channel."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["channel_id"]:
                return await ctx.send(embed=_err("No boost channel is currently set."))
            await _upsert(ctx.guild.id, channel_id=0)
            await ctx.send(embed=_ok("Boost announcement channel has been **removed**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_role(self, ctx, role: discord.Role = None):
        """Set a role to auto-assign when a member boosts."""
        if ctx.invoked_subcommand is not None:
            return
        if role is None:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                return await help_cog.send_group_help_auto(ctx, ctx.command)
        try:
            if role.is_default():
                return await ctx.send(embed=_err("You cannot use the **@everyone** role."))
            if role >= ctx.guild.me.top_role:
                return await ctx.send(embed=_err(f"{role.mention} is **above or equal** to my top role. I won't be able to assign it."))
            await _upsert(ctx.guild.id, role_id=role.id)
            await ctx.send(embed=_ok(f"{role.mention} will be given to members when they **boost**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @boost_role.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_role_reset(self, ctx):
        """Remove the boost reward role."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["role_id"]:
                return await ctx.send(embed=_err("No boost role is currently set."))
            await _upsert(ctx.guild.id, role_id=0)
            await ctx.send(embed=_ok("Boost reward role has been **removed**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_enable(self, ctx):
        """Enable the boost message system."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["mode"]:
                return await ctx.send(embed=_err("No boost setup found. Use `boost setup` first."))
            if cfg["is_enabled"]:
                return await ctx.send(embed=_err("Boost system is already **enabled**."))
            await _upsert(ctx.guild.id, is_enabled=1)
            await ctx.send(embed=_ok("Boost message system has been **enabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @boost.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_disable(self, ctx):
        """Disable the boost message system."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["is_enabled"]:
                return await ctx.send(embed=_err("Boost system is already **disabled**."))
            await _upsert(ctx.guild.id, is_enabled=0)
            await ctx.send(embed=_ok("Boost message system has been **disabled**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="config")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_config(self, ctx):
        """View the current boost message configuration."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["mode"]:
                return await ctx.send(embed=_err("No boost setup configured yet. Use `boost setup` to get started."))

            status = f"{E_OK} Enabled" if cfg["is_enabled"] else f"{E_ERR} Disabled"
            ch = ctx.guild.get_channel(cfg["channel_id"])
            ch_text = ch.mention if ch else "`Not set`"
            role = ctx.guild.get_role(cfg["role_id"]) if cfg["role_id"] else None
            role_text = role.mention if role else "`Not set`"
            mode_text = cfg["mode"].title()
            del_text = f"`{cfg['delete_after']}s`" if cfg["delete_after"] else "`Off`"

            config_data = json.loads(cfg["config_json"])
            if cfg["mode"] == "message":
                preview = f"```\n{config_data.get('message', 'No message set')[:200]}\n```"
            else:
                preview = f"*Embed with {len(config_data.get('fields', []))} field(s) — use `boost test` to preview*"

            embed = discord.Embed(
                description=(
                    f"**Boost System Configuration**\n\n"
                    f"- **Status:** {status}\n"
                    f"- **Channel:** {ch_text}\n"
                    f"- **Boost Role:** {role_text}\n"
                    f"- **Mode:** `{mode_text}`\n"
                    f"- **Auto-Delete:** {del_text}\n\n"
                    f"**Preview:**\n{preview}"
                ),
                color=COLOR_BOOST
            )
            embed.set_author(
                name=f"{ctx.guild.name} — Boost System",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            embed.set_footer(text=FOOTER)
            embed.timestamp = discord.utils.utcnow()
            await ctx.send(embed=embed)
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="test")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def boost_test(self, ctx):
        """Send a mock boost message to the current channel."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["mode"]:
                return await ctx.send(embed=_err("No boost setup found. Use `boost setup` first."))

            ev_cog = self.bot.get_cog("BoostEvents")
            if not ev_cog:
                return await ctx.send(embed=_err("Boost event cog is not loaded."))

            await ev_cog.send_boost_message(ctx.author, cfg, test_channel=ctx.channel)
            await ctx.send(embed=_ok("Test boost message sent above! ↑"), delete_after=5)
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def boost_reset(self, ctx):
        """Delete all boost configuration for this server."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg:
                return await ctx.send(embed=_err("No boost configuration to reset."))
            await _delete(ctx.guild.id)
            await ctx.send(embed=_ok("All boost configuration has been **wiped**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


    @boost.command(name="variables")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_variables(self, ctx):
        """Show all supported boost message variables."""
        embed = discord.Embed(
            title="<:synapselist:1478319545772146698> Boost Variables",
            description=f"Use these placeholders in your boost message or embed.\n\n{BOOST_VARS_LIST}",
            color=COLOR_BOOST
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)


    @boost.group(name="delete", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_delete(self, ctx, seconds: int = None):
        """Set auto-delete timer for boost messages (in seconds)."""
        if ctx.invoked_subcommand is not None:
            return
        if seconds is None:
            help_cog = ctx.bot.get_cog("Help")
            if help_cog:
                return await help_cog.send_group_help_auto(ctx, ctx.command)
        try:
            if seconds <= 0 or seconds > 86400:
                return await ctx.send(embed=_err("Auto-delete time must be between **1** and **86400** seconds (24h)."))
            await _upsert(ctx.guild.id, delete_after=seconds)
            await ctx.send(embed=_ok(f"Boost messages will auto-delete after **{seconds}** seconds."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")

    @boost_delete.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def boost_delete_reset(self, ctx):
        """Remove the auto-delete timer."""
        try:
            cfg = await _get_config(ctx.guild.id)
            if not cfg or not cfg["delete_after"]:
                return await ctx.send(embed=_err("No auto-delete timer is currently set."))
            await _upsert(ctx.guild.id, delete_after=0)
            await ctx.send(embed=_ok("Auto-delete timer has been **removed**."))
        except Exception as e:
            await self.send_error(ctx, f"An unexpected error occurred: `{e}`")


async def setup(bot):
    await _init_db()
    await bot.add_cog(BoostCommands(bot))
