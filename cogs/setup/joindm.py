import discord
from discord.ext import commands

from utils.joindm_helpers import (
    _ok, _err, _info, _warn,
    parse_variables,
    VARIABLES,
    JoinDMDatabase,
    joindm_admin_only,
    EMBED_COLOR,
)
from utils.Tools import blacklist_check, ignore_check



class BaseModal(discord.ui.Modal):
    """Base modal with helper add_input() method."""

    def add_input(self, label, default="", style=discord.TextStyle.short, max_length=None):
        input_field = discord.ui.TextInput(
            label=label,
            default=default,
            style=style,
            max_length=max_length
        )
        self.add_item(input_field)
        return input_field



async def clean_icon_url(text: str, member: discord.Member):
    """Remove hints, parse variables, validate URL."""
    if not text:
        return None

    t = text.strip()

    t = t.replace("(You can also add `{author_icon}` placeholder)", "")
    t = t.replace("(You can also add `{footer_icon}` placeholder)", "")
    t = t.strip()

    t = parse_variables(member, t)

    if not t.startswith("http"):
        return None

    return t



class EditMessageModal(BaseModal, title="Edit DM Message"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_msg = self.add_input(
            "Message Text",
            default=view.message,
            style=discord.TextStyle.paragraph
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.message = self.input_msg.value
        await self.view.update_preview(interaction)



class EditTitleModal(BaseModal, title="Edit Embed Title"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_title = self.add_input(
            "Title Text",
            default=view.embed_title
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed_title = self.input_title.value.strip()
        await self.view.update_preview(interaction)



class EditDescriptionModal(BaseModal, title="Edit Description"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_desc = self.add_input(
            "Embed Description",
            default=view.embed_description,
            style=discord.TextStyle.paragraph
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed_description = self.input_desc.value.strip()
        await self.view.update_preview(interaction)



class EditAuthorModal(BaseModal, title="Edit Author"):
    """Edit embed author text + author icon URL."""
    def __init__(self, view):
        super().__init__()
        self.view = view

        author_text = (
            f"{view.embed_author}\n"
            "(You can also add `{author_icon}` placeholder)"
        ) if view.embed_author else ""

        self.input_author = self.add_input(
            "Author Text",
            default=author_text
        )

        self.input_author_icon = self.add_input(
            "Author Icon URL",
            default=view.embed_author_icon or ""
        )

    async def on_submit(self, interaction: discord.Interaction):

        cleaned_author = self.input_author.value.replace(
            "(You can also add `{author_icon}` placeholder)", ""
        ).strip()

        author_icon = await clean_icon_url(self.input_author_icon.value, interaction.user)

        self.view.embed_author = cleaned_author
        self.view.embed_author_icon = author_icon

        await self.view.update_preview(interaction)



class EditFooterModal(BaseModal, title="Edit Footer"):
    """Edit footer text + footer icon URL."""
    def __init__(self, view):
        super().__init__()
        self.view = view

        footer_text = (
            f"{view.embed_footer}\n"
            "(You can also add `{footer_icon}` placeholder)"
        ) if view.embed_footer else ""

        self.input_footer = self.add_input(
            "Footer Text",
            default=footer_text,
            style=discord.TextStyle.paragraph
        )

        self.input_footer_icon = self.add_input(
            "Footer Icon URL",
            default=view.embed_footer_icon or ""
        )

    async def on_submit(self, interaction: discord.Interaction):

        cleaned_footer = self.input_footer.value.replace(
            "(You can also add `{footer_icon}` placeholder)", ""
        ).strip()

        footer_icon = await clean_icon_url(self.input_footer_icon.value, interaction.user)

        self.view.embed_footer = cleaned_footer
        self.view.embed_footer_icon = footer_icon

        await self.view.update_preview(interaction)



class EditColorModal(BaseModal, title="Edit Embed Color"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_color = self.add_input(
            "Hex Color (e.g. #ff0000)",
            default=view.embed_color_raw
        )

    async def on_submit(self, interaction: discord.Interaction):
        color_raw = self.input_color.value.strip()

        if not color_raw.startswith("#"):
            color_raw = "#" + color_raw

        try:
            color_int = int(color_raw.replace("#", ""), 16)
        except:
            return await interaction.response.send_message(
                "❌ Invalid hex color.", ephemeral=True
            )

        self.view.embed_color = color_int
        self.view.embed_color_raw = color_raw

        await self.view.update_preview(interaction)



class AddFieldModal(BaseModal, title="Add Embed Field"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_name = self.add_input("Field Name")
        self.input_value = self.add_input(
            "Field Value",
            style=discord.TextStyle.paragraph
        )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.input_name.value.strip()
        value = self.input_value.value.strip()

        if not name or not value:
            return await interaction.response.send_message(
                "❌ Field name and value cannot be empty.",
                ephemeral=True
            )

        self.view.embed_fields.append({"name": name, "value": value})
        await self.view.update_preview(interaction)



class EditImagesModal(BaseModal, title="Edit Images"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.input_thumb = self.add_input(
            "Thumbnail URL",
            default=view.embed_thumbnail or ""
        )

        self.input_image = self.add_input(
            "Image URL",
            default=view.embed_image or ""
        )

    async def on_submit(self, interaction: discord.Interaction):

        thumb = await clean_icon_url(self.input_thumb.value, interaction.user)
        image = await clean_icon_url(self.input_image.value, interaction.user)

        self.view.embed_thumbnail = thumb
        self.view.embed_image = image

        await self.view.update_preview(interaction)




from discord.ui import View, Button, Select



class LockedButton(Button):
    """Button that only the user who opened the setup can use."""
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.view.executor_id:
            await interaction.response.send_message(
                " This panel does not belong to you.",
                ephemeral=True
            )
            return False
        return True



class EmbedBuilderDropdown(Select):
    def __init__(self, view_obj: "JoinDMSetupView"):
        options = [
            discord.SelectOption(label="Title", description="Set the embed title"),
            discord.SelectOption(label="Description", description="Set the embed description"),
            discord.SelectOption(label="Author", description="Set the author name"),
            discord.SelectOption(label="Color", description="Set the embed color (hex)"),
            discord.SelectOption(label="Footer", description="Set the footer text"),
            discord.SelectOption(label="Images", description="Set Thumbnail and Image"),
            discord.SelectOption(label="Add Field", description="Add a new embed field"),
            discord.SelectOption(label="Variables", description="Show available variables")
        ]
        super().__init__(placeholder="Select a component to edit...", min_values=1, max_values=1, options=options)
        self.view_obj = view_obj

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_obj.executor_id:
            return await interaction.response.send_message(embed=_err("This panel does not belong to you."), ephemeral=True)

        val = self.values[0]

        if val == "Title":
            await interaction.response.send_modal(EditTitleModal(self.view_obj))
        elif val == "Description":
            await interaction.response.send_modal(EditDescriptionModal(self.view_obj))
        elif val == "Footer":
            await interaction.response.send_modal(EditFooterModal(self.view_obj))
        elif val == "Author":
            await interaction.response.send_modal(EditAuthorModal(self.view_obj))
        elif val == "Color":
            await interaction.response.send_modal(EditColorModal(self.view_obj))
        elif val == "Add Field":
            await interaction.response.send_modal(AddFieldModal(self.view_obj))
        elif val == "Images":
            await interaction.response.send_modal(EditImagesModal(self.view_obj))
        elif val == "Variables":
            text = "\n".join([f"`{k}` → {v}" for k, v in VARIABLES.items()])
            embed = _info(text, title="Available Variables")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class MessageBuilderDropdown(Select):
    def __init__(self, view_obj: "JoinDMSetupView"):
        options = [
            discord.SelectOption(label="Message", description="Set plain text to DM"),
            discord.SelectOption(label="Variables", description="Show available variables")
        ]
        super().__init__(placeholder="Select a component to edit...", min_values=1, max_values=1, options=options)
        self.view_obj = view_obj

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_obj.executor_id:
            return await interaction.response.send_message(embed=_err("This panel does not belong to you."), ephemeral=True)

        val = self.values[0]
        if val == "Message":
            await interaction.response.send_modal(EditMessageModal(self.view_obj))
        elif val == "Variables":
            text = "\n".join([f"`{k}` → {v}" for k, v in VARIABLES.items()])
            embed = _info(text, title="Available Variables")
            await interaction.response.send_message(embed=embed, ephemeral=True)

class BtnTestDM(LockedButton):
    def __init__(self):
        super().__init__(label="Test DM", style=discord.ButtonStyle.success, emoji="<:Synapsemsg:1478320489796734989>")

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        parsed = parse_variables(interaction.user, v.embed_description if v.page == "embed" else v.message)

        try:
            if v.page == "message":
                await interaction.user.send(parsed)
            else:
                embed = discord.Embed(
                    title=v.embed_title,
                    description=parsed,
                    color=v.embed_color
                )



                embed.set_footer(text=v.embed_footer or None, icon_url=v.embed_footer_icon or None)

                embed.set_author(name=v.embed_author or None, icon_url=v.embed_author_icon or None)

                if v.embed_thumbnail:
                    embed.set_thumbnail(url=v.embed_thumbnail)

                if v.embed_image:
                    embed.set_image(url=v.embed_image)

                for f in v.embed_fields:
                    embed.add_field(name=f["name"], value=f["value"], inline=False)

                await interaction.user.send(embed=embed)

            await interaction.response.send_message("DM sent!", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(embed=_err("I cannot DM you. Please enable DMs."), ephemeral=True)


class BtnSave(LockedButton):
    def __init__(self):
        super().__init__(label="Save", style=discord.ButtonStyle.green, emoji="<:emoji_1769867605256:1467155817726873650>")

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        data = {
            "guild_id": interaction.guild.id,
            "enabled": 1,
            "mode": v.page,
            "message": v.message,
            "embed_title": v.embed_title,
            "embed_description": v.embed_description,
            "embed_footer": v.embed_footer,
            "embed_author": v.embed_author,
            "embed_author_icon": v.embed_author_icon,
"embed_footer_icon": v.embed_footer_icon,
            "embed_color": v.embed_color,
            "embed_thumbnail": v.embed_thumbnail,
            "embed_image": v.embed_image,
            "embed_fields": v.embed_fields
        }

        await v.db.upsert(interaction.guild.id, data)

        v.cog.release_setup_lock(interaction.guild.id)

        await interaction.response.edit_message(
            embed=_ok("JoinDM settings saved successfully.", "Saved"),
            view=None
        )


class BtnCancel(LockedButton):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, emoji="<:emoji_1769867589372:1467155751456735326>")

    async def callback(self, interaction: discord.Interaction):
        self.view.cog.release_setup_lock(interaction.guild.id)

        await interaction.response.edit_message(
            embed=_info("Setup cancelled.", "Cancelled"),
            view=None
        )



class PageSelector(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select editing mode",
            options=[
                discord.SelectOption(label="Message", value="message"),
                discord.SelectOption(label="Embed", value="embed"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.page = self.values[0]
        await self.view.refresh(interaction)



class JoinDMSetupView(View):
    def __init__(self, ctx, db, cog):
        super().__init__(timeout=120)

        self.ctx = ctx
        self.db = db
        self.cog = cog

        self.executor_id = ctx.author.id
        self.message_obj = None

        self.page = "message"
        self.message = "Welcome {user}!"

        self.embed_title = "Welcome!"
        self.embed_description = "Welcome to the server, {user}!"
        self.embed_footer = ""
        self.embed_author = ""
        self.embed_author_icon = ""
        self.embed_footer_icon = ""
        self.embed_color = EMBED_COLOR
        self.embed_color_raw = f"#{EMBED_COLOR:06x}"

        self.embed_thumbnail = ""
        self.embed_image = ""
        self.embed_fields = []

        self.add_item(PageSelector())
        self.add_item(BtnTestDM())
        self.add_item(BtnSave())
        self.add_item(BtnCancel())


    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.executor_id


    def build_preview(self):
        if self.page == "message":
            preview = _info(self.message, "Preview (Message Mode)")
            return [preview]

        parsed = self.embed_description

        embed = discord.Embed(
            title=self.embed_title,
            description=parsed,
            color=self.embed_color
        )

        embed.set_footer(
            text=self.embed_footer or None,
            icon_url=self.embed_footer_icon or None       
         )

        embed.set_author(
            name=self.embed_author or None,
            icon_url=self.embed_author_icon or None
        )

        if self.embed_thumbnail:
            embed.set_thumbnail(url=self.embed_thumbnail)
        if self.embed_image:
            embed.set_image(url=self.embed_image)

        for f in self.embed_fields:
            embed.add_field(name=f["name"], value=f["value"], inline=False)

        return [embed]


    async def update_preview(self, interaction: discord.Interaction):
        embeds = self.build_preview()
        await interaction.response.edit_message(embeds=embeds, view=self)


    async def refresh(self, interaction: discord.Interaction):
        self.clear_items()

        self.add_item(PageSelector())

        if self.page == "message":
            self.add_item(MessageBuilderDropdown(self))
        else:
            self.add_item(EmbedBuilderDropdown(self))

        self.add_item(BtnTestDM())
        self.add_item(BtnSave())
        self.add_item(BtnCancel())

        await interaction.response.edit_message(
            embeds=self.build_preview(),
            view=self
        )


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        try:
            await self.message_obj.edit(view=self)
        except:
            pass

        self.cog.release_setup_lock(self.ctx.guild.id)



class JoinDM(commands.Cog):
    """
    Complete JoinDM System:
    - Hybrid commands
    - UI-based editor
    - Setup lock per-guild
    - JSON embed fields
    - Full support for variables
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JoinDMDatabase()
        self.active_setups = {}

        bot.loop.create_task(self.db.setup())


    @commands.hybrid_group(name="joindm", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def joindm(self, ctx: commands.Context):
        """Main JoinDM command group."""
        if ctx.invoked_subcommand is not None:
        	return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)


    def has_active_setup(self, guild_id: int):
        return guild_id in self.active_setups

    def start_setup_lock(self, guild_id: int, user_id: int):
        self.active_setups[guild_id] = user_id

    def release_setup_lock(self, guild_id: int):
        if guild_id in self.active_setups:
            del self.active_setups[guild_id]


    @joindm.command(name="setup")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def setup(self, ctx: commands.Context):
        """Open the JoinDM setup UI panel."""

        gid = ctx.guild.id

        existing = await self.db.fetch(gid)
        if existing and (existing["message"] or existing["embed_title"] or existing["embed_description"]):
            owner = self.active_setups.get(gid)
            if owner:
                return await ctx.reply(
                    embed=_err(
                        f"JoinDM setup is currently active.\nOpened by: <@{owner}>",
                        "Setup Already Open"
                    )
                )
            return await ctx.reply(
                embed=_err(
                    "JoinDM is already setup. Use `joindm edit` to edit it.",
                    "Already Configured"
                )
            )

        self.start_setup_lock(gid, ctx.author.id)

        view = JoinDMSetupView(ctx=ctx, db=self.db, cog=self)
        if existing:
            view.message = existing.get("message", "Welcome {user}!")
            view.embed_title = existing.get("embed_title", "Welcome!")
            view.embed_description = existing.get("embed_description", "Welcome to the server, {user}!")
            view.embed_footer = existing.get("embed_footer", "")
            view.embed_author = existing.get("embed_author", "")
            view.embed_author_icon = existing.get("embed_author_icon", "")
            view.embed_footer_icon = existing.get("embed_footer_icon", "")
            view.embed_color = existing.get("embed_color", EMBED_COLOR)
            view.embed_color_raw = f"#{view.embed_color:06x}"
            view.embed_thumbnail = existing.get("embed_thumbnail", "")
            view.embed_image = existing.get("embed_image", "")
            view.embed_fields = existing.get("embed_fields", [])
            view.page = existing.get("mode", "message")

        preview = view.build_preview()

        setup_embed = _info(
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Use the dropdowns below to customize your Join DM message.\n"
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Your changes will **live-update** the preview below.\n"
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Click **Save** to confirm or **Cancel** to discard.",
            "**JoinDM Setup Builder**"
        )

        msg = await ctx.reply(
            embeds=[setup_embed] + preview,
            view=view,
            mention_author=False
        )

        view.message_obj = msg


    @joindm.command(name="toggle")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def toggle(self, ctx: commands.Context):
        """Toggle JoinDM enabled/disabled."""
        data = await self.db.fetch(ctx.guild.id)

        new_state = 0 if data["enabled"] else 1
        data["enabled"] = new_state

        await self.db.upsert(ctx.guild.id, data)

        await ctx.reply(
            embed=_ok(
                f"Join DM is now **{'Enabled' if new_state else 'Disabled'}**.",
                "Join DM Toggled"
            ),
            mention_author=False
        )


    @joindm.command(name="config")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def config(self, ctx: commands.Context):
        """Display the current JoinDM configuration."""
        data = await self.db.fetch(ctx.guild.id)

        embed = _info("Join DM Configuration", "Here is your current setup for Join DMs.")

        status_emoji = "<:emoji_1769867605256:1467155817726873650>" if data["enabled"] else "<:emoji_1769867589372:1467155751456735326>"
        status_text = "Enabled" if data["enabled"] else "Disabled"

        embed.add_field(name="Status", value=f"{status_emoji} {status_text}", inline=True)
        embed.add_field(name="Mode", value=f"`{data['mode'].title()}`", inline=True)

        if data["mode"] == "message":
            embed.add_field(name="Message", value=data["message"] or "*(empty)*", inline=False)
        else:
            embed.add_field(name="Title", value=data["embed_title"] or "*(empty)*", inline=False)
            embed.add_field(name="Description", value=data["embed_description"] or "*(empty)*", inline=False)
            embed.add_field(name="Footer", value=data["embed_footer"] or "*(empty)*", inline=False)
            embed.add_field(name="Author", value=data["embed_author"] or "*(empty)*", inline=False)
            embed.add_field(name="Thumbnail", value=data["embed_thumbnail"] or "*(empty)*", inline=False)
            embed.add_field(name="Image", value=data["embed_image"] or "*(empty)*", inline=False)
            fields_val = "\n".join([f"**{f['name']}**: {f['value']}" for f in data["embed_fields"]])
            embed.add_field(
                name="Fields",
                value=fields_val or "*(empty)*",
                inline=False
            )

        await ctx.reply(embed=embed, mention_author=False)


    @joindm.command(name="edit")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def edit(self, ctx: commands.Context):
        """Edit the existing JoinDM configuration."""
        gid = ctx.guild.id

        existing = await self.db.fetch(gid)
        if not existing or (not existing["message"] and not existing["embed_title"] and not existing["embed_description"]):
            return await ctx.reply(
                embed=_err(
                    "JoinDM is not set up for this server. Use `joindm setup` first.",
                    "Not Configured"
                )
            )

        if self.has_active_setup(gid):
            owner = self.active_setups[gid]
            return await ctx.reply(
                embed=_err(
                    f"JoinDM setup is currently active.\nOpened by: <@{owner}>",
                    "Setup Already Open"
                )
            )

        self.start_setup_lock(gid, ctx.author.id)

        view = JoinDMSetupView(ctx=ctx, db=self.db, cog=self)
        view.message = existing.get("message", "Welcome {user}!")
        view.embed_title = existing.get("embed_title", "Welcome!")
        view.embed_description = existing.get("embed_description", "Welcome to the server, {user}!")
        view.embed_footer = existing.get("embed_footer", "")
        view.embed_author = existing.get("embed_author", "")
        view.embed_author_icon = existing.get("embed_author_icon", "")
        view.embed_footer_icon = existing.get("embed_footer_icon", "")
        view.embed_color = existing.get("embed_color", EMBED_COLOR)
        view.embed_color_raw = f"#{view.embed_color:06x}"
        view.embed_thumbnail = existing.get("embed_thumbnail", "")
        view.embed_image = existing.get("embed_image", "")
        view.embed_fields = existing.get("embed_fields", [])
        view.page = existing.get("mode", "message")

        await view.refresh(ctx)

        view.clear_items()
        view.add_item(PageSelector())
        if view.page == "message":
            view.add_item(MessageBuilderDropdown(view))
        else:
            view.add_item(EmbedBuilderDropdown(view))
        view.add_item(BtnTestDM())
        view.add_item(BtnSave())
        view.add_item(BtnCancel())

        preview = view.build_preview()

        setup_embed = _info(
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Use the dropdowns below to edit your Join DM message.\n"
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Your changes will **live-update** the preview below.\n"
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Click **Save** to confirm or **Cancel** to discard.",
            "**JoinDM Edit Builder**"
        )

        msg = await ctx.reply(
            embeds=[setup_embed] + preview,
            view=view,
            mention_author=False
        )

        view.message_obj = msg


    @joindm.command(name="export", help="Export JoinDM configuration as JSON")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def export_command(self, ctx: commands.Context):
        """Export configuration"""

        data = await self.db.fetch(ctx.guild.id)
        if not data or (not data["message"] and not data["embed_title"] and not data["embed_description"]):
            embed = _err(
                "This guild does not have a JoinDM system configured.",
                "Not Configured"
            )
            await ctx.send(embed=embed)
            return

        export_data = dict(data)
        export_data.pop("guild_id", None)
        export_data.pop("updated_at", None)

        json_data = json.dumps(export_data, indent=2, default=str)

        import io
        file = discord.File(
            io.StringIO(json_data),
            filename=f"joindm_config_{ctx.guild.id}.json"
        )

        embed = _info(
            "Your JoinDM configuration has been exported.",
            "Export Complete"
        )

        await ctx.send(embed=embed, file=file)


    @joindm.command(name="import", help="Import JoinDM configuration from JSON")
    @commands.has_permissions(administrator=True)
    async def import_command(self, ctx: commands.Context):
        """Import configuration"""

        if not ctx.message.attachments:
            embed = _err(
                "Please attach a JSON configuration file.",
                "Missing File"
            )
            await ctx.send(embed=embed)
            return

        attachment = ctx.message.attachments[0]

        if not attachment.filename.endswith(".json"):
            embed = _err(
                "Please provide a .json file.",
                "Invalid File"
            )
            await ctx.send(embed=embed)
            return

        try:
            file_content = await attachment.read()
            import_data = json.loads(file_content.decode('utf-8'))

            required_fields = ["mode", "enabled"]
            if not all(field in import_data for field in required_fields):
                raise ValueError("Missing required fields (mode, enabled)")

            sanitized = {
                "enabled": import_data.get("enabled", 0),
                "mode": import_data.get("mode", "message"),
                "message": import_data.get("message", ""),
                "embed_title": import_data.get("embed_title", ""),
                "embed_description": import_data.get("embed_description", ""),
                "embed_footer": import_data.get("embed_footer", ""),
                "embed_author": import_data.get("embed_author", ""),
                "embed_author_icon": import_data.get("embed_author_icon", ""),
                "embed_footer_icon": import_data.get("embed_footer_icon", ""),
                "embed_color": import_data.get("embed_color", EMBED_COLOR),
                "embed_thumbnail": import_data.get("embed_thumbnail", ""),
                "embed_image": import_data.get("embed_image", ""),
                "embed_fields": import_data.get("embed_fields", [])
            }

            await self.db.upsert(ctx.guild.id, sanitized)

            embed = _ok(
                "JoinDM configuration has been imported successfully.",
                "Configuration Imported"
            )

        except json.JSONDecodeError:
            embed = _err(
                "The file is not valid JSON.",
                "Invalid JSON"
            )
        except ValueError as e:
            embed = _err(
                f"Configuration validation failed: {str(e)}",
                "Invalid Configuration"
            )
        except Exception as e:
            embed = _err(
                f"Failed to import configuration: {str(e)}",
                "Import Error"
            )

        await ctx.send(embed=embed)


    @joindm.command(name="reset")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def reset(self, ctx: commands.Context):
        """Reset JoinDM settings only if something exists."""
        data = await self.db.fetch(ctx.guild.id)

        if (
            not data["message"]
            and not data["embed_title"]
            and not data["embed_description"]
        ):
            return await ctx.reply(
                embed=_err(
                    "JoinDM is not set up for this server.",
                    "Nothing to Reset"
                ),
                mention_author=False
            )

        await self.db.disable(ctx.guild.id)

        await ctx.reply(
            embed=_ok(
                "All JoinDM settings have been reset.",
                "Join DM Reset"
            ),
            mention_author=False
        )



async def setup(bot: commands.Bot):
    await bot.add_cog(JoinDM(bot))