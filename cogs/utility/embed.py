import os
import json
import asyncio
import discord
import aiosqlite
from discord.ext import commands
from discord import ui
from utils.Tools import blacklist_check, ignore_check


DB_PATH     = os.path.join("database", "embeds.db")
EMBED_COLOR = 0x2b2d31
E_OK        = "<:SynapseDoubleTick:1477237283286679647>"
E_ERR       = "<:emoji_1769867589372:1467155751456735326>"
FOOTER      = "Synapse - Embed System"
MAX_EMBEDS  = 15
WAIT_TIMEOUT = 60
VIEW_TIMEOUT = 300



async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS embed_data (
                guild_id   INTEGER NOT NULL,
                name       TEXT    NOT NULL,
                embed_json TEXT    NOT NULL,
                PRIMARY KEY (guild_id, name)
            );
            """
        )
        await db.commit()



def _ok(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_OK} {desc}", color=EMBED_COLOR)
    e.set_footer(text=FOOTER)
    return e

def _err(desc: str) -> discord.Embed:
    e = discord.Embed(description=f"{E_ERR} {desc}", color=EMBED_COLOR)
    e.set_footer(text=FOOTER)
    return e



async def _save_embed(guild_id: int, name: str, embed_dict: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO embed_data (guild_id, name, embed_json) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, name) DO UPDATE SET embed_json = excluded.embed_json",
            (guild_id, name.lower(), json.dumps(embed_dict)),
        )
        await db.commit()


async def _get_embed(guild_id: int, name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT embed_json FROM embed_data WHERE guild_id = ? AND name = ?",
            (guild_id, name.lower()),
        ) as cur:
            row = await cur.fetchone()
    return json.loads(row[0]) if row else None


async def _get_all_embeds(guild_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM embed_data WHERE guild_id = ? ORDER BY name",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def _delete_embed(guild_id: int, name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM embed_data WHERE guild_id = ? AND name = ?",
            (guild_id, name.lower()),
        ) as cur:
            if not await cur.fetchone():
                return False
        await db.execute(
            "DELETE FROM embed_data WHERE guild_id = ? AND name = ?",
            (guild_id, name.lower()),
        )
        await db.commit()
    return True


async def _count_embeds(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM embed_data WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0]



def _dict_to_embed(data: dict) -> discord.Embed:
    """Build a discord.Embed from our storage dict."""
    embed = discord.Embed(
        title=data.get("title"),
        description=data.get("description"),
        color=data.get("color", EMBED_COLOR),
    )
    if data.get("author_name"):
        embed.set_author(
            name=data["author_name"],
            icon_url=data.get("author_icon") or None,
        )
    if data.get("footer_text"):
        embed.set_footer(
            text=data["footer_text"],
            icon_url=data.get("footer_icon") or None,
        )
    if data.get("image"):
        embed.set_image(url=data["image"])
    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"])
    for field in data.get("fields", []):
        embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))
    return embed


def _embed_to_dict(embed: discord.Embed) -> dict:
    """Serialize a discord.Embed to our storage dict."""
    data: dict = {}
    if embed.title:
        data["title"] = embed.title
    if embed.description:
        data["description"] = embed.description
    data["color"] = embed.color.value if embed.color else EMBED_COLOR
    if embed.author and embed.author.name:
        data["author_name"] = embed.author.name
        if embed.author.icon_url:
            data["author_icon"] = str(embed.author.icon_url)
    if embed.footer and embed.footer.text:
        data["footer_text"] = embed.footer.text
        if embed.footer.icon_url:
            data["footer_icon"] = str(embed.footer.icon_url)
    if embed.image and embed.image.url:
        data["image"] = str(embed.image.url)
    if embed.thumbnail and embed.thumbnail.url:
        data["thumbnail"] = str(embed.thumbnail.url)
    if embed.fields:
        data["fields"] = [
            {"name": f.name, "value": f.value, "inline": f.inline}
            for f in embed.fields
        ]
    return data


def _build_preview(data: dict, plain_message: str | None = None) -> tuple[str | None, discord.Embed]:
    """Build the live preview (content, embed) from current builder state."""
    has_embed_data = any(data.get(k) for k in ("title", "description", "author_name", "footer_text", "image", "thumbnail", "fields"))

    if not has_embed_data and not plain_message:
        e = discord.Embed(
            title="Embed Preview",
            description=(
                "*Your embed is empty.*\n"
                "> Use the **dropdown below** to start adding content.\n"
                "> Select a component → type your value in chat."
            ),
            color=data.get("color", EMBED_COLOR),
        )
        e.set_footer(text="Live Preview — Use the dropdown to edit")
        return None, e

    embed_obj = _dict_to_embed(data) if has_embed_data else None

    if plain_message and not has_embed_data:
        e = discord.Embed(
            description="*(You have set a message, but the embed is still empty. Add embed components using the dropdown.)*",
            color=data.get("color", EMBED_COLOR)
        )
        e.set_footer(text="Live Preview — Use the dropdown to edit")
        embed_obj = e

    return plain_message, embed_obj



class AddFieldModal(ui.Modal, title="Add Embed Field"):
    field_name = ui.TextInput(
        label="Field Name",
        placeholder="Enter the field title…",
        max_length=256,
        style=discord.TextStyle.short,
    )
    field_value = ui.TextInput(
        label="Field Value",
        placeholder="Enter the field content…",
        max_length=1024,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, builder_view: "EmbedBuilderView"):
        super().__init__(timeout=120)
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        fields = self.builder_view.embed_data.setdefault("fields", [])
        if len(fields) >= 25:
            return await interaction.response.send_message(
                embed=_err("Embeds can have a maximum of **25 fields**."),
                ephemeral=True,
            )
        fields.append({"name": self.field_name.value, "value": self.field_value.value, "inline": False})
        content, preview = _build_preview(self.builder_view.embed_data, self.builder_view.plain_message)
        await interaction.response.edit_message(content=content, embed=preview, view=self.builder_view)



DROPDOWN_OPTIONS = [
    discord.SelectOption(label="Message", description="Set plain text above the embed."),
    discord.SelectOption(label="Title", description="Set the embed title."),
    discord.SelectOption(label="Description", description="Set the embed description."),
    discord.SelectOption(label="Color", description="Set the embed color (hex code)."),
    discord.SelectOption(label="Author Text", description="Set the author name."),
    discord.SelectOption(label="Author Icon", description="Set the author icon URL."),
    discord.SelectOption(label="Footer Text", description="Set the footer text."),
    discord.SelectOption(label="Footer Icon", description="Set the footer icon URL."),
    discord.SelectOption(label="Image", description="Set the large image URL."),
    discord.SelectOption(label="Thumbnail", description="Set the thumbnail URL."),
    discord.SelectOption(label="Add Field", description="Add a field (name + value) via popup."),
]


class BuilderDropdown(ui.Select):
    def __init__(self, builder_view: "EmbedBuilderView"):
        super().__init__(
            placeholder="Select a component to edit…",
            min_values=1,
            max_values=1,
            options=DROPDOWN_OPTIONS,
        )
        self.builder_view = builder_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder_view.author_id:
            return await interaction.response.send_message(
                "This builder doesn't belong to you.", ephemeral=True
            )

        choice = self.values[0]

        if choice == "Add Field":
            modal = AddFieldModal(self.builder_view)
            return await interaction.response.send_modal(modal)

        field_map = {
            "Message":     ("message",     "Please enter the **message text** (plain text above the embed):"),
            "Title":       ("title",       "Please enter the **title**:"),
            "Description": ("description", "Please enter the **description**:"),
            "Color":       ("color",       "Please enter the **color** as a hex code (e.g. `#FF5733` or `FF5733`):"),
            "Author Text": ("author_name", "Please enter the **author text**:"),
            "Author Icon": ("author_icon", "Please enter the **author icon URL**:"),
            "Footer Text": ("footer_text", "Please enter the **footer text**:"),
            "Footer Icon": ("footer_icon", "Please enter the **footer icon URL**:"),
            "Image":       ("image",       "Please enter the **image URL**:"),
            "Thumbnail":   ("thumbnail",   "Please enter the **thumbnail URL**:"),
        }

        key, prompt_text = field_map[choice]

        prompt_embed = discord.Embed(
            description=f" {prompt_text}\n\n> *Type your value below or `cancel` to abort. Times out in {WAIT_TIMEOUT}s.*",
            color=EMBED_COLOR,
        )
        prompt_embed.set_footer(text=FOOTER)

        await interaction.response.send_message(embed=prompt_embed)
        prompt_msg = await interaction.original_response()

        def check(m: discord.Message) -> bool:
            return m.author.id == self.builder_view.author_id and m.channel.id == interaction.channel.id

        try:
            reply = await interaction.client.wait_for("message", check=check, timeout=WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                description=f"{E_ERR} Timed out. Select the dropdown again to continue editing.",
                color=EMBED_COLOR,
            )
            timeout_embed.set_footer(text=FOOTER)
            try:
                await prompt_msg.edit(embed=timeout_embed)
            except discord.HTTPException:
                pass
            return

        value = reply.content.strip()

        try:
            await prompt_msg.delete()
        except discord.HTTPException:
            pass
        try:
            await reply.delete()
        except discord.HTTPException:
            pass

        if value.lower() == "cancel":
            return

        if key == "color":
            value = value.lstrip("#")
            try:
                color_int = int(value, 16)
                if color_int > 0xffffff:
                    raise ValueError
                self.builder_view.embed_data["color"] = color_int
            except ValueError:
                return await interaction.channel.send(
                    embed=_err("Invalid hex color. Use a format like `#FF5733`."),
                    delete_after=8,
                )
        elif key in ("author_icon", "footer_icon", "image", "thumbnail"):
            if not (value.startswith("http://") or value.startswith("https://")):
                return await interaction.channel.send(
                    embed=_err("Please provide a valid URL starting with `http://` or `https://`."),
                    delete_after=8,
                )
            self.builder_view.embed_data[key] = value
        elif key == "message":
            self.builder_view.plain_message = value
        else:
            self.builder_view.embed_data[key] = value

        content, preview = _build_preview(self.builder_view.embed_data, self.builder_view.plain_message)
        try:
            await self.builder_view.preview_message.edit(content=content, embed=preview, view=self.builder_view)
        except discord.HTTPException:
            pass



class EmbedBuilderView(ui.View):
    def __init__(self, ctx: commands.Context, name: str):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.ctx = ctx
        self.name = name.lower()
        self.author_id = ctx.author.id
        self.embed_data: dict = {"color": EMBED_COLOR}
        self.plain_message: str | None = None
        self.preview_message: discord.Message | None = None
        self.saved = False

        self.add_item(BuilderDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This builder doesn't belong to you.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            timeout_embed = discord.Embed(
                description=f"{E_ERR} Embed builder timed out due to inactivity.\n> Changes were **not saved**.",
                color=EMBED_COLOR,
            )
            timeout_embed.set_footer(text=FOOTER)
            if self.preview_message:
                await self.preview_message.edit(embed=timeout_embed, view=None)
        except discord.HTTPException:
            pass

    @ui.button(label="Save", style=discord.ButtonStyle.green, row=2)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        has_content = any(
            self.embed_data.get(k)
            for k in ("title", "description", "author_name", "footer_text", "image", "thumbnail", "fields")
        )
        if not has_content and not self.plain_message:
            return await interaction.response.send_message(
                embed=_err("Your embed is **empty**. Add at least one component before saving."),
                ephemeral=True,
            )

        if self.plain_message:
            self.embed_data["_message"] = self.plain_message

        await _save_embed(self.ctx.guild.id, self.name, self.embed_data)
        self.saved = True

        for item in self.children:
            item.disabled = True

        save_embed = discord.Embed(
            description=(
                f"{E_OK} **Embed Saved Successfully**\n\n"
                f"> **Name:** `{self.name}`\n"
                f"> **Send it:** `embed send {self.name} #channel`\n"
                f"> **Export:** `embed export {self.name}`"
            ),
            color=EMBED_COLOR,
        )
        save_embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=save_embed, view=self)
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        cancel_embed = discord.Embed(
            description=f"{E_ERR} Embed builder **cancelled**. No changes were saved.",
            color=EMBED_COLOR,
        )
        cancel_embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=cancel_embed, view=self)
        self.stop()



class EmbedBuilder(commands.Cog):
    """Interactive embed builder & management system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def embed(self, ctx: commands.Context):
        """Interactive embed builder & management."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @embed.command(name="guide")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def embed_guide(self, ctx: commands.Context):
        """Display a usage guide for the embed builder."""
        guide = discord.Embed(
            title="<:SynapseNote:1477236015830663324> Embed Builder — Guide",
            description=(
                "Create, manage, and send beautiful custom embeds.\n\n"
                "**Getting Started**\n"
                "> `embed create <name>` — Opens the interactive builder\n"
                "> Use the **dropdown** to select a component\n"
                "> Type your value in chat when prompted\n"
                "> Click **Save** when done\n\n"
                "**Managing Embeds**\n"
                "> `embed show` — List all saved embeds\n"
                "> `embed show <name>` — Preview a saved embed\n"
                "> `embed delete <name>` — Delete a saved embed\n"
                "> `embed send <name> [#channel]` — Send embed to a channel\n\n"
                "**Import & Export**\n"
                "> `embed export <name>` — Get the embed as JSON\n"
                "> `embed import <name>` — Import embed from pasted JSON\n\n"
                "**Builder Components**\n"
                "> `Message` — Plain text above the embed\n"
                "> `Title` — The embed title\n"
                "> `Description` — The embed description\n"
                "> `Color` — Hex color code (e.g. `#FF5733`)\n"
                "> `Author Text` — Author name line\n"
                "> `Author Icon` — Author icon URL\n"
                "> `Footer Text` — Footer line\n"
                "> `Footer Icon` — Footer icon URL\n"
                "> `Image` — Large image URL\n"
                "> `Thumbnail` — Smaller thumbnail URL\n"
                "> `Add Field` — Opens a popup with name & value fields\n\n"
                f"**Limits**\n"
                f"> Max saved embeds per server: **{MAX_EMBEDS}**\n"
                f"> Max fields per embed: **25**\n"
                f"> Builder timeout: **{VIEW_TIMEOUT // 60} minutes**"
            ),
            color=EMBED_COLOR,
        )
        guide.set_footer(text=FOOTER)
        await ctx.send(embed=guide)


    @embed.command(name="create")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def embed_create(self, ctx: commands.Context, name: str):
        """Open the interactive embed builder: `embed create <name>`"""
        name = name.lower().strip()

        if not name.isalnum():
            return await ctx.send(embed=_err("Embed name must be **alphanumeric** (no spaces or symbols)."))
        if len(name) > 30:
            return await ctx.send(embed=_err("Embed name must be **30 characters** or fewer."))

        count = await _count_embeds(ctx.guild.id)
        existing = await _get_embed(ctx.guild.id, name)
        if not existing and count >= MAX_EMBEDS:
            return await ctx.send(embed=_err(
                f"You have reached the maximum of **{MAX_EMBEDS}** saved embeds.\n"
                "> Delete an existing one with `embed delete <name>`."
            ))

        view = EmbedBuilderView(ctx, name)

        if existing:
            view.embed_data = existing.copy()
            view.plain_message = existing.pop("_message", None)

        content, preview = _build_preview(view.embed_data, view.plain_message)
        msg = await ctx.send(content=content, embed=preview, view=view)
        view.preview_message = msg


    @embed.command(name="edit")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def embed_edit(self, ctx: commands.Context, name: str):
        """Edit an existing saved embed: `embed edit <name>`"""
        name = name.lower().strip()
        data = await _get_embed(ctx.guild.id, name)
        if data is None:
            return await ctx.send(embed=_err(f"No embed named **`{name}`** exists."))

        view = EmbedBuilderView(ctx, name)
        view.embed_data = data.copy()
        view.plain_message = data.pop("_message", None)

        content, preview = _build_preview(view.embed_data, view.plain_message)
        msg = await ctx.send(content=content, embed=preview, view=view)
        view.preview_message = msg


    @embed.command(name="show")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def embed_show(self, ctx: commands.Context, name: str = None):
        """List saved embeds or preview one: `embed show [name]`"""
        if name is None:
            names = await _get_all_embeds(ctx.guild.id)
            if not names:
                return await ctx.send(embed=_err(
                    "No embeds saved.\n> Use `embed create <name>` to get started."
                ))
            lines = "\n".join(f"> `{idx}.` **`{n}`**" for idx, n in enumerate(names, 1))
            embed = discord.Embed(
                description=(
                    f"** Saved Embeds [{len(names)}/{MAX_EMBEDS}]**\n\n"
                    f"{lines}\n\n"
                    f"> Use `embed show <name>` to preview."
                ),
                color=EMBED_COLOR,
            )
            embed.set_author(
                name=f"{ctx.guild.name} — Embeds",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            embed.set_footer(text=FOOTER)
            return await ctx.send(embed=embed)

        data = await _get_embed(ctx.guild.id, name.lower())
        if data is None:
            return await ctx.send(embed=_err(f"No embed named **`{name}`** exists."))

        plain = data.pop("_message", None)
        preview = _dict_to_embed(data)
        content = plain if plain else None
        await ctx.send(content=content, embed=preview)


    @embed.command(name="delete")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def embed_delete(self, ctx: commands.Context, name: str):
        """Delete a saved embed: `embed delete <name>`"""
        ok = await _delete_embed(ctx.guild.id, name)
        if not ok:
            return await ctx.send(embed=_err(f"No embed named **`{name}`** exists."))
        await ctx.send(embed=_ok(f"Embed **`{name.lower()}`** has been **deleted**."))


    @embed.command(name="send")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def embed_send(self, ctx: commands.Context, name: str, channel: discord.TextChannel = None):
        """Send a saved embed to a channel: `embed send <name> [#channel]`"""
        channel = channel or ctx.channel

        data = await _get_embed(ctx.guild.id, name.lower())
        if data is None:
            return await ctx.send(embed=_err(f"No embed named **`{name}`** exists."))

        plain = data.pop("_message", None)

        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send(embed=_err(
                f"I don't have permission to send embeds in {channel.mention}.\n"
                "> I need **Send Messages** and **Embed Links**."
            ))

        embed_obj = _dict_to_embed(data)
        content = plain if plain else None
        await channel.send(content=content, embed=embed_obj)

        if channel.id != ctx.channel.id:
            await ctx.send(embed=_ok(f"Embed **`{name.lower()}`** sent to {channel.mention}."))


    @embed.command(name="export")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def embed_export(self, ctx: commands.Context, name: str):
        """Export a saved embed as JSON: `embed export <name>`"""
        data = await _get_embed(ctx.guild.id, name.lower())
        if data is None:
            return await ctx.send(embed=_err(f"No embed named **`{name}`** exists."))

        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        if len(json_str) > 1900:
            file = discord.File(
                fp=__import__("io").BytesIO(json_str.encode()),
                filename=f"{name.lower()}_embed.json",
            )
            embed = discord.Embed(
                description=f"{E_OK} Embed **`{name.lower()}`** exported as a file.",
                color=EMBED_COLOR,
            )
            embed.set_footer(text=FOOTER)
            await ctx.send(embed=embed, file=file)
        else:
            embed = discord.Embed(
                description=(
                    f"{E_OK} **Embed Export — `{name.lower()}`**\n\n"
                    f"```json\n{json_str}\n```\n"
                    f"> Copy the JSON and use `embed import <name>` to re‑import."
                ),
                color=EMBED_COLOR,
            )
            embed.set_footer(text=FOOTER)
            await ctx.send(embed=embed)


    @embed.command(name="import", aliases=["load"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def embed_import(self, ctx: commands.Context, name: str):
        """Import an embed from JSON: `embed import <name>`"""
        name = name.lower().strip()

        if not name.isalnum():
            return await ctx.send(embed=_err("Embed name must be **alphanumeric**."))
        if len(name) > 30:
            return await ctx.send(embed=_err("Embed name must be **30 characters** or fewer."))

        count = await _count_embeds(ctx.guild.id)
        existing = await _get_embed(ctx.guild.id, name)
        if not existing and count >= MAX_EMBEDS:
            return await ctx.send(embed=_err(
                f"You have reached the maximum of **{MAX_EMBEDS}** saved embeds."
            ))

        prompt = discord.Embed(
            description=(
                f"📥 **Paste your JSON below** to import as **`{name}`**.\n\n"
                f"> You can get JSON from `embed export` or external embed builders.\n"
                f"> Type `cancel` to abort. Times out in {WAIT_TIMEOUT}s."
            ),
            color=EMBED_COLOR,
        )
        prompt.set_footer(text=FOOTER)
        prompt_msg = await ctx.send(embed=prompt)

        def check(m: discord.Message) -> bool:
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            return await prompt_msg.edit(embed=_err("Import timed out."))

        if reply.content.strip().lower() == "cancel":
            try:
                await prompt_msg.delete()
                await reply.delete()
            except discord.HTTPException:
                pass
            return

        raw = reply.content.strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return await ctx.send(embed=_err(
                "Invalid JSON. Make sure to paste valid JSON data.\n"
                "> Use `embed guide` for help."
            ))

        if not isinstance(data, dict):
            return await ctx.send(embed=_err("JSON must be an **object** (dictionary), not an array or scalar."))

        allowed_keys = {"title", "description", "color", "author_name", "author_icon",
                        "footer_text", "footer_icon", "image", "thumbnail", "fields", "_message"}
        data = {k: v for k, v in data.items() if k in allowed_keys}

        if not data:
            return await ctx.send(embed=_err("The JSON didn't contain any valid embed properties."))

        await _save_embed(ctx.guild.id, name, data)

        try:
            await prompt_msg.delete()
            await reply.delete()
        except discord.HTTPException:
            pass

        preview_data = data.copy()
        plain = preview_data.pop("_message", None)
        preview = _dict_to_embed(preview_data)

        success = discord.Embed(
            description=(
                f"{E_OK} **Embed Imported Successfully**\n\n"
                f"> **Name:** `{name}`\n"
                f"> **Send it:** `embed send {name} #channel`"
            ),
            color=EMBED_COLOR,
        )
        success.set_footer(text=FOOTER)
        await ctx.send(embed=success)
        await ctx.send(content=plain, embed=preview)



async def setup(bot: commands.Bot):
    await _init_db()
    await bot.add_cog(EmbedBuilder(bot))
