import discord
from discord.ext import commands
from discord import ui
import aiosqlite
import os
import json
import asyncio
from typing import Optional, Union, Dict, Any, List
import re

from utils.Tools import blacklist_check, ignore_check

E_OK     = "<:emoji_1769867605256:1467155817726873650>"
E_ERR    = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL   = "<:SynapseExcl:1477234549552320634>"
E_STAR   = "<:SynapseNote:1477236015830663324>"
E_SHIELD = "<:frozenstar:1478070088119750799>"

EMBED_COLOR  = 0x2b2d31
COLOR_OK     = 0x2b2d31
COLOR_ERR    = 0x2b2d31
COLOR_INFO   = 0x2b2d31
COLOR_WARN   = 0xfca903
COLOR_DARK   = 0x2b2d31

FOOTER = "Synapse · Welcomer System"
DB_PATH = os.path.join("database", "welcomer.db")


def _ok(desc: str, title: str = None) -> discord.Embed:
    """Green success embed."""
    e = discord.Embed(description=f"{E_OK} {desc}", color=COLOR_OK)
    if title:
        e.title = title
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str, title: str = None) -> discord.Embed:
    """Red error embed."""
    e = discord.Embed(description=f"{E_ERR} {desc}", color=COLOR_ERR)
    if title:
        e.title = title
    e.set_footer(text=FOOTER)
    return e

def _info(desc: str, title: str = None) -> discord.Embed:
    """Blue informational/prompt embed."""
    e = discord.Embed(description=desc, color=COLOR_INFO)
    if title:
        e.title = title
    e.set_footer(text=FOOTER)
    return e

def _warn(desc: str, title: str = None) -> discord.Embed:
    """Orange warning embed."""
    e = discord.Embed(description=f"{E_EXCL} {desc}", color=COLOR_WARN)
    if title:
        e.title = title
    e.set_footer(text=FOOTER)
    return e


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS welcomer_setups (
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                mode TEXT NOT NULL,
                config_json TEXT NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                enable_autodelete BOOLEAN DEFAULT 0,
                autodelete_time INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, name)
            );
            CREATE TABLE IF NOT EXISTS welcomer_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                setup_name TEXT NOT NULL,
                PRIMARY KEY (guild_id, channel_id, setup_name)
            );
        """)
        await db.commit()

async def get_setup_count(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM welcomer_setups WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_channel_count(guild_id: int, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM welcomer_channels WHERE guild_id = ? AND setup_name = ?", (guild_id, name)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


VARS_LIST = (
    "`{user}` `{user_id}` `{user_name}` `{user_tag}` `{user_avatar}` `{user_avatar_png}`\n"
    "`{user_mention}` `{server}` `{server_id}` `{server_membercount}` `{server_icon}`\n"
    "`{server_icon_png}` `{joined_at}` `{created_at}` `{guild_owner}` `{guild_owner_id}`\n"
    "`{guild_owner_mention}` `{boost_count}` `{boost_tier}` `{member_position}`\n"
    "`{member_count_ordinal}` `{user_discriminator}` `{server_banner}` `{server_banner_png}`"
)

ALLOWED_VARS = [
    "{user}", "{user_id}", "{user_name}", "{user_tag}", "{user_avatar}", "{user_avatar_png}",
    "{user_mention}", "{server}", "{server_id}", "{server_membercount}", "{server_icon}",
    "{server_icon_png}", "{joined_at}", "{created_at}", "{guild_owner}", "{guild_owner_id}",
    "{guild_owner_mention}", "{boost_count}", "{boost_tier}", "{member_position}",
    "{member_count_ordinal}", "{user_discriminator}", "{server_banner}", "{server_banner_png}"
]


class EmbedBuilderDropdown(ui.Select):
    def __init__(self, builder_view: "EmbedBuilderView"):
        options = [
            discord.SelectOption(label="Message",     description="Set plain text above embed"),
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

                def __init__(self, builder_view):
                    super().__init__()
                    self.builder_view = builder_view

                async def on_submit(self, modal_interaction: discord.Interaction):
                    fields = self.builder_view.config.setdefault("fields", [])
                    if len(fields) >= 25:
                        return await modal_interaction.response.send_message(
                            embed=_err("Embeds can have a maximum of **25 fields**."), ephemeral=True
                        )
                    fields.append({"name": self.name_input.value, "value": self.value_input.value, "inline": False})
                    await modal_interaction.response.defer()
                    await self.builder_view.update_preview()

            return await interaction.response.send_modal(AddFieldModal(self.builder_view))

        prompts = {
            "Message": "message", "Title": "title", "Description": "description",
            "Author": "author_name", "Author Icon": "author_icon", "Thumbnail": "thumbnail",
            "Image": "image", "Footer": "footer_text", "Footer Icon": "footer_icon", "Color": "color"
        }
        key = prompts[choice]

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
                        await interaction.channel.send(embed=_err("Invalid hex color. Example: `#5865F2`"), delete_after=5)
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


class EmbedBuilderView(ui.View):
    def __init__(self, ctx, setup_name: str, existing_config: dict = None):
        super().__init__(timeout=300)
        self.ctx         = ctx
        self.setup_name  = setup_name
        self.author_id   = ctx.author.id
        self.config      = existing_config or {"color": EMBED_COLOR}
        self.preview_msg = None
        self.add_item(EmbedBuilderDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(embed=_err("This isn't your embed builder."), ephemeral=True)
            return False
        return True

    def build_embed(self):
        embed = discord.Embed(
            title=self.config.get("title"),
            description=self.config.get("description"),
            color=self.config.get("color", EMBED_COLOR)
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
                timeout_embed = _warn(
                    "Embed builder timed out. Run `greet edit` again to continue.",
                    title="Builder Timed Out"
                )
                await self.preview_msg.edit(embed=timeout_embed, view=self)
        except: pass

    @ui.button(label="Variables", style=discord.ButtonStyle.secondary, emoji="<:synapselist:1478319545772146698>", row=1)
    async def vars_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = _info(
            f"**Available Variables:**\n\n{VARS_LIST}",
            title="<:synapselist:1478319545772146698> Embed Variables"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Save", style=discord.ButtonStyle.green, emoji="<:emoji_1769867605256:1467155817726873650>", row=1)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO welcomer_setups (guild_id, name, mode, config_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, name) DO UPDATE SET config_json=excluded.config_json, mode=excluded.mode",
                (self.ctx.guild.id, self.setup_name, "embed", json.dumps(self.config))
            )
            await db.commit()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=_ok(f"Embed setup **`{self.setup_name}`** has been saved successfully!"),
            view=self
        )
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="<:emoji_1769867589372:1467155751456735326>", row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=_err("Embed setup cancelled."), view=self)
        self.stop()



class ImageCardPaginator(ui.View):
    def __init__(self, ctx, setup_name: str, card_count: int = 4):
        super().__init__(timeout=300)
        self.ctx         = ctx
        self.setup_name  = setup_name
        self.author_id   = ctx.author.id
        self.current_idx = 1
        self.card_count  = card_count
        self.config      = {"card_type": self.current_idx, "card_text": "Welcome", "content": "Welcome {user_mention} to {server}!"}
        self.msg         = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(embed=_err("This isn't your card builder."), ephemeral=True)
            return False
        return True

    def get_embed(self):
        embed = discord.Embed(
            title="Image Card Builder",
            description=(
                f"**Selected Layout:** `{self.current_idx}` of `{self.card_count}`\n\n"
                f"{E_STAR} Use **Back / Next** to browse card layouts.\n"
                f"{E_STAR} Use **Set Content** to set the message above the card.\n"
                f"{E_STAR} Use **Set Card Text** to change the text on the card.\n"
                f"{E_STAR} Click **Preview Card** to see how it will look.\n\n"
                f"*Cards are generated at join time using member data.*"
            ),
            color=COLOR_INFO
        )
        embed.set_footer(text=FOOTER)
        return embed

    async def update_view(self, interaction: discord.Interaction):
        self.config["card_type"] = self.current_idx
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.msg:
                await self.msg.edit(embed=_warn("Card builder timed out. Run `greet edit` again."), view=self)
        except: pass

    @ui.button(label="Back", style=discord.ButtonStyle.primary, row=0)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        self.current_idx = max(1, self.current_idx - 1)
        await self.update_view(interaction)

    @ui.button(label="Next", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        self.current_idx = min(self.card_count, self.current_idx + 1)
        await self.update_view(interaction)

    @ui.button(label="Set Content", style=discord.ButtonStyle.secondary, emoji="<:Synapsemsg:1478320489796734989>", row=1)
    async def content_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=_info("Type the **message text** that appears above the card in chat.\n*(Type `cancel` to abort)*")
        )
        def check(m): return m.author.id == self.author_id and m.channel.id == interaction.channel.id
        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=120)
            if msg.content.lower() != "cancel":
                self.config["content"] = msg.content
                await interaction.followup.send(embed=_ok("Message content updated!"), ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(embed=_warn("Timed out waiting for message text."), ephemeral=True)

    @ui.button(label="Set Card Text", style=discord.ButtonStyle.secondary, emoji="<:SynapsePencil:1478314728395898995>", row=1)
    async def cardtext_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=_info("Type the text to display **on top of the card image**.\n*(Type `cancel` to abort)*")
        )
        def check(m): return m.author.id == self.author_id and m.channel.id == interaction.channel.id
        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=120)
            if msg.content.lower() != "cancel":
                self.config["card_text"] = msg.content
                await interaction.followup.send(embed=_ok("Card text updated!"), ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(embed=_warn("Timed out waiting for card text."), ephemeral=True)

    @ui.button(label="Variables", style=discord.ButtonStyle.secondary, emoji="<:synapselist:1478319545772146698>", row=2)
    async def vars_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = _info(
            f"**Available Variables:**\n\n{VARS_LIST}",
            title="<:synapselist:1478319545772146698> Card Variables"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Preview Card", style=discord.ButtonStyle.secondary, emoji="<:SynapseEye:1478322293238272011>", row=2)
    async def preview_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        greet_cog = self.ctx.bot.get_cog("GreetEvents")
        if greet_cog:
            file = await greet_cog.generate_card(interaction.user, self.config)
            await interaction.followup.send(content="**Card Preview:**", file=file, ephemeral=True)
        else:
            await interaction.followup.send(embed=_err("Greet event cog is not loaded."), ephemeral=True)

    @ui.button(label="Confirm & Save", style=discord.ButtonStyle.green, emoji="<:emoji_1769867605256:1467155817726873650>", row=2)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO welcomer_setups (guild_id, name, mode, config_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, name) DO UPDATE SET config_json=excluded.config_json, mode=excluded.mode",
                (self.ctx.guild.id, self.setup_name, "image", json.dumps(self.config))
            )
            await db.commit()
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(
            embed=_ok(f"Image setup **`{self.setup_name}`** saved successfully!"),
            view=self
        )
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="<:emoji_1769867589372:1467155751456735326>", row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(embed=_err("Image card setup cancelled."), view=self)
        self.stop()



class ModeSelectionView(ui.View):
    def __init__(self, ctx, setup_name: str, bot):
        super().__init__(timeout=60)
        self.ctx        = ctx
        self.setup_name = setup_name
        self.bot        = bot
        self.author_id  = ctx.author.id
        self.msg        = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.msg:
                await self.msg.edit(
                    embed=_warn("Mode selection timed out. Run `greet create` again.", title="Timed Out"),
                    view=self
                )
        except: pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(embed=_err("This isn't your setup panel."), ephemeral=True)
            return False
        return True

    @ui.button(label="Message Mode", style=discord.ButtonStyle.secondary)
    async def msg_btn(self, interaction: discord.Interaction, button: ui.Button):
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(
            embed=_info(
                "Type the **welcome message** content in this channel.\nSupports all variables listed in the Variables button.\n*(Type `cancel` to abort)*",
                title="Message Mode Setup"
            ),
            view=self
        )
        self.stop()
        def check(m): return m.author.id == self.author_id and m.channel.id == interaction.channel.id
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
            if msg.content.lower() != "cancel":
                config = {"message": msg.content}
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO welcomer_setups (guild_id, name, mode, config_json) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(guild_id, name) DO UPDATE SET config_json=excluded.config_json, mode=excluded.mode",
                        (self.ctx.guild.id, self.setup_name, "message", json.dumps(config))
                    )
                    await db.commit()
                await interaction.followup.send(
                    embed=_ok(f"Message setup **`{self.setup_name}`** saved successfully!")
                )
            else:
                await interaction.followup.send(embed=_err("Setup cancelled."))
        except asyncio.TimeoutError:
            await interaction.followup.send(embed=_warn("Timed out waiting for message content."))

    @ui.button(label="Embed Mode", style=discord.ButtonStyle.secondary)
    async def embed_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = EmbedBuilderView(self.ctx, self.setup_name)
        builder_embed = discord.Embed(
            title="Embed Builder",
            description=(
                f"- Use the **dropdown** below to edit each part of your embed.\n"
                f"- Your changes will **live-update** this preview message.\n"
                f"- Press **Variables** to see what placeholders you can use.\n"
                f"- Press **Confirm & Save** when you're happy with it."
            ),
            color=COLOR_INFO
        )
        builder_embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=builder_embed, view=view)
        view.preview_msg = await interaction.original_response()
        self.stop()

    @ui.button(label="Image Mode", style=discord.ButtonStyle.secondary)
    async def img_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ImageCardPaginator(self.ctx, self.setup_name, card_count=4)
        await interaction.response.edit_message(embed=view.get_embed(), view=view)
        view.msg = await interaction.original_response()
        self.stop()



class Welcomer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(init_db())

    @commands.group(name="greet", help="Welcomer configuration commands", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def greet(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)


    @greet.command(name="create", help="Interactive setup to create a greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_create(self, ctx, name: str):
        count = await get_setup_count(ctx.guild.id)
        if count >= 5:
            return await ctx.send(embed=_err("This server has reached the **maximum of 5** greet setups."))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM welcomer_setups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as c:
                if await c.fetchone():
                    return await ctx.send(embed=_err(f"A greet setup named **`{name}`** already exists."))

        mode_embed = discord.Embed(
            title=f"{E_SHIELD}  New Greet Setup — `{name}`",
            description=(
                f"Choose a **welcome mode** for this setup:\n\n"
                f"**Message Mode**\n"
                f"> Simple text-only greeting. Lightweight and fast.\n\n"
                f"**Embed Mode**\n"
                f"> Rich embed with colors, title, fields, and images.\n\n"
                f"**Image Mode**\n"
                f"> Eye-catching welcome card with avatar integration."
            ),
            color=COLOR_INFO
        )
        mode_embed.set_footer(text=FOOTER)
        mode_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

        view = ModeSelectionView(ctx, name, self.bot)
        view.msg = await ctx.send(embed=mode_embed, view=view)


    @greet.command(name="delete", help="Deletes a specified greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_delete(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM welcomer_setups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))
            await db.execute("DELETE FROM welcomer_channels WHERE guild_id = ? AND setup_name = ?", (ctx.guild.id, name))
            await db.commit()
        await ctx.send(embed=_ok(f"Greet setup **`{name}`** has been deleted."))


    @greet.command(name="enable", help="Enables a specified greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_enable(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE welcomer_setups SET is_enabled = 1 WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))
            await db.commit()
        await ctx.send(embed=_ok(f"Greet setup **`{name}`** is now **enabled**."))

    @greet.command(name="disable", help="Disables a specified greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_disable(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("UPDATE welcomer_setups SET is_enabled = 0 WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))
            await db.commit()
        await ctx.send(embed=_ok(f"Greet setup **`{name}`** is now **disabled**."))


    @greet.group(name="channel", help="Manage greet target channels.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def greet_channel(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @greet_channel.command(name="set", help="Assigns a channel to a greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_channel_set(self, ctx, name: str, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM welcomer_setups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as c:
                if not await c.fetchone():
                    return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))

        count = await get_channel_count(ctx.guild.id, name)
        if count >= 3:
            return await ctx.send(embed=_err("This setup already has the **maximum of 3** channels assigned."))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO welcomer_channels (guild_id, channel_id, setup_name) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, name)
            )
            await db.commit()
        await ctx.send(embed=_ok(f"{channel.mention} has been added to setup **`{name}`**."))

    @greet_channel.command(name="reset", help="Removes all channels from a greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_channel_reset(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("DELETE FROM welcomer_channels WHERE guild_id = ? AND setup_name = ?", (ctx.guild.id, name))
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"No channels are assigned to setup **`{name}`**."))
            await db.commit()
        await ctx.send(embed=_ok(f"All channels for setup **`{name}`** have been reset."))


    @greet.command(name="config", help="Lists all greet setups in the server.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_config(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, mode, is_enabled FROM welcomer_setups WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send(embed=_err("This server has no greet setups configured yet."))

        mode_icons = {"embed": "📝", "message": "💬", "image": "🖼️"}
        lines = []
        for idx, (name, mode, is_enabled) in enumerate(rows, 1):
            status_icon = E_OK if is_enabled else E_ERR
            lines.append(
                f"`{idx}.` **`{name}`**  —  {status_icon} `{'Enabled' if is_enabled else 'Disabled'}`  ·  Mode: `{mode.title()}`"
            )

        embed = discord.Embed(
            title=f"<:synapselist:1478319545772146698> Greet Setups — {ctx.guild.name}",
            description="\n".join(lines),
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed)


    @greet.group(name="autodelete", help="Manage autodelete for greet setups.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def greet_autodelete(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @greet_autodelete.command(name="enable", help="Configure autodelete behavior and timing for a setup.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_autodelete_enable(self, ctx, state: str, name: str, time_str: str = "0s"):
        state = state.lower()
        if state not in ("enable", "disable"):
            return await ctx.send(embed=_err("Invalid state. Use `enable` or `disable`."))

        time_multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        seconds = 0
        if state == "enable":
            matches = re.findall(r'(\d+)([smhd])', time_str.lower())
            if not matches:
                return await ctx.send(embed=_err("Invalid time format. Examples: `30s`, `5m`, `1h`"))
            for val, unit in matches:
                seconds += int(val) * time_multipliers[unit]
            if seconds <= 0:
                return await ctx.send(embed=_err("Autodelete time must be greater than 0."))

        async with aiosqlite.connect(DB_PATH) as db:
            enable_val = 1 if state == "enable" else 0
            c = await db.execute(
                "UPDATE welcomer_setups SET enable_autodelete = ?, autodelete_time = ? WHERE guild_id = ? AND name = ?",
                (enable_val, seconds, ctx.guild.id, name)
            )
            if c.rowcount == 0:
                return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))
            await db.commit()

        if state == "enable":
            await ctx.send(embed=_ok(f"Autodelete for **`{name}`** enabled — messages will delete after **{seconds}s**."))
        else:
            await ctx.send(embed=_ok(f"Autodelete for **`{name}`** has been **disabled**."))


    @greet.command(name="edit", help="Modifies an existing greet configuration.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_edit(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT mode, config_json FROM welcomer_setups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as c:
                row = await c.fetchone()
                if not row:
                    return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))

        mode, config_str = row
        config = json.loads(config_str)

        if mode == "embed":
            view = EmbedBuilderView(ctx, name, existing_config=config)
            builder_embed = discord.Embed(
                title="<:SynapsePencil:1478314728395898995> Embed Builder",
                description=(
                    f"- Use the **dropdown** below to edit each part of your embed.\n"
                    f"- Your changes will **live-update** this preview.\n"
                    f"- Press **Confirm & Save** when done."
                ),
                color=COLOR_INFO
            )
            builder_embed.set_footer(text=FOOTER)
            msg = await ctx.send(embed=builder_embed, view=view)
            view.preview_msg = msg

        elif mode == "message":
            await ctx.send(
                embed=_info(
                    "This is a **Message Mode** setup.\nType your new welcome message content below.\n*(Type `cancel` to abort)*",
                    title="<:Synapsemsg:1478320489796734989> Editing Message Setup"
                )
            )
            def check(m): return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=120)
                if msg.content.lower() != "cancel":
                    config["message"] = msg.content
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "UPDATE welcomer_setups SET config_json = ? WHERE guild_id = ? AND name = ?",
                            (json.dumps(config), ctx.guild.id, name)
                        )
                        await db.commit()
                    await ctx.send(embed=_ok(f"Setup **`{name}`** has been updated."))
                else:
                    await ctx.send(embed=_err("Edit cancelled."))
            except asyncio.TimeoutError:
                await ctx.send(embed=_warn("Timed out waiting for new message content."))

        elif mode == "image":
            view = ImageCardPaginator(ctx, name, card_count=4)
            view.config      = config
            view.current_idx = config.get("card_type", 1)
            msg = await ctx.send(embed=view.get_embed(), view=view)
            view.msg = msg


    @greet.command(name="test", help="Tests a greet configuration locally.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def greet_test(self, ctx, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT mode, config_json FROM welcomer_setups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as c:
                row = await c.fetchone()
                if not row:
                    return await ctx.send(embed=_err(f"No greet setup named **`{name}`** was found."))

        mode, config_str = row

        if "{server_icon}" in config_str and not ctx.guild.icon:
            return await ctx.send(embed=_err("This setup uses `{server_icon}` but the server has no icon."))

        for match in re.findall(r"\{[a-z_]+\}", config_str):
            if match not in ALLOWED_VARS:
                return await ctx.send(embed=_err(f"Invalid variable found: `{match}`"))

        if mode == "embed":
            config = json.loads(config_str)
            valid_keys = {"message", "title", "description", "author_name", "author_icon", "thumbnail", "image", "footer_text", "footer_icon", "color", "fields"}
            for k in config.keys():
                if k not in valid_keys and k != "card_type":
                    return await ctx.send(embed=_err(f"Invalid embed field found: `{k}`"))

        test_embed = discord.Embed(
            title="Test Triggered",
            description=(
                f"{E_OK} Setup **`{name}`** passed all checks.\n\n"
                f"> **Mode:** `{mode.title()}`\n"
                f"> A mock join event has been dispatched."
            ),
            color=COLOR_OK
        )
        test_embed.set_footer(text=FOOTER)
        test_embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=test_embed)

        self.bot.dispatch("member_join_test_mock", ctx.author, name, ctx.channel.id)


async def setup(bot):
    await bot.add_cog(Welcomer(bot))
