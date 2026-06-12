import discord
from discord.ext import commands
from discord import ui
import aiosqlite
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import re
from utils.Tools import blacklist_check, ignore_check



class FarewellDatabase:
    """Handles all database operations for the farewell system"""

    DB_PATH = "database/farewell.db"

    def __init__(self):
        """Initialize database handler"""
        self.db_path = self.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def initialize(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS farewell_config (
                    guild_id INTEGER PRIMARY KEY,
                    enabled BOOLEAN DEFAULT 1,
                    channel_id INTEGER NOT NULL,
                    farewell_message TEXT,
                    embed_title TEXT,
                    embed_description TEXT,
                    embed_color TEXT DEFAULT '0x2b2d31',
                    embed_thumbnail TEXT,
                    embed_image TEXT,
                    footer_text TEXT,
                    footer_icon TEXT,
                    author_name TEXT,
                    author_icon TEXT,
                    timestamp_toggle BOOLEAN DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            async with db.execute("PRAGMA table_info(farewell_config)") as cursor:
                columns = [row[1] async for row in cursor]
                if "timestamp_toggle" not in columns:
                    await db.execute(
                "ALTER TABLE farewell_config ADD COLUMN timestamp_toggle BOOLEAN DEFAULT 0"
            )
                    await db.commit()





    async def get_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve farewell configuration for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM farewell_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        return None

    async def set_config(self, guild_id: int, **kwargs) -> bool:
        """Create or update farewell configuration"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                existing = await self.get_config(guild_id)

                if existing:
                    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                    values = list(kwargs.values()) + [guild_id]
                    await db.execute(
                        f"UPDATE farewell_config SET {set_clause}, last_updated = CURRENT_TIMESTAMP WHERE guild_id = ?",
                        values
                    )
                else:
                    columns = ", ".join(kwargs.keys())
                    placeholders = ", ".join(["?" for _ in kwargs])
                    values = list(kwargs.values())
                    await db.execute(
                        f"INSERT INTO farewell_config (guild_id, {columns}) VALUES (?, {placeholders})",
                        [guild_id] + values
                    )

                await db.commit()
                return True
        except Exception as e:
            print(f"Database error in set_config: {e}")
            return False

    async def delete_config(self, guild_id: int) -> bool:
        """Delete farewell configuration for a guild"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM farewell_config WHERE guild_id = ?",
                    (guild_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Database error in delete_config: {e}")
            return False

    async def toggle_enabled(self, guild_id: int, enabled: bool) -> bool:
        """Toggle farewell system enabled/disabled"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE farewell_config SET enabled = ?, last_updated = CURRENT_TIMESTAMP WHERE guild_id = ?",
                    (enabled, guild_id)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Database error in toggle_enabled: {e}")
            return False



class EmbedBuilder:
    """Helper class to build embeds with farewell customization"""

    @staticmethod
    def create_embed(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: str = "0x2b2d31",
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        footer_text: Optional[str] = None,
        footer_icon: Optional[str] = None,
        author_name: Optional[str] = None,
        author_icon: Optional[str] = None,
        timestamp: bool = False
    ) -> discord.Embed:
        """Create a customized embed"""
        try:
            color_int = int(color, 16) if isinstance(color, str) else color
        except ValueError:
            color_int = 0x2b2d31

        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int,
            timestamp=datetime.utcnow() if timestamp else None
        )

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if image_url:
            embed.set_image(url=image_url)

        if footer_text or footer_icon:
            embed.set_footer(text=footer_text or "", icon_url=footer_icon)

        if author_name or author_icon:
            embed.set_author(name=author_name or "", icon_url=author_icon)

        return embed

    @staticmethod
    def create_info_embed(title: str, description: str) -> discord.Embed:
        """Create a standard info embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=0x2b2d31
        )

    @staticmethod
    def create_error_embed(title: str, description: str) -> discord.Embed:
        """Create an error embed"""
        return discord.Embed(
            title=title,
            description=f"<:emoji_1769867589372:1467155751456735326> | {description}",
            color=0xff4646
        )

    @staticmethod
    def create_success_embed(title: str, description: str) -> discord.Embed:
        """Create a success embed"""
        return discord.Embed(
            title=title,
            description=f"<:emoji_1769867605256:1467155817726873650> | {description}",
            color=0x4dff94
        )



class VariableParser:
    """Parses and replaces variables in farewell messages"""

    MEMBER_VARIABLES = {
        "{user}": "member.mention",
        "{mention}": "member.mention",
        "{username}": "member.name",
        "{displayname}": "member.display_name",
        "{id}": "str(member.id)",
        "{avatar}": "member.avatar.url if member.avatar else member.default_avatar.url",
        "{created_at}": "member.created_at.strftime('%Y-%m-%d %H:%M:%S')",
        "{joined_at}": "member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'Unknown'"
    }

    SERVER_VARIABLES = {
        "{server}": "guild.name",
        "{server_id}": "str(guild.id)",
        "{membercount}": "str(guild.member_count)",
        "{boosts}": "str(guild.premium_subscription_count)",
        "{owner}": "guild.owner.mention if guild.owner else 'Unknown'",
        "{owner_name}": "guild.owner.name if guild.owner else 'Unknown'",
        "{created_at}": "guild.created_at.strftime('%Y-%m-%d %H:%M:%S')"
    }

    TIME_VARIABLES = {
        "{date}": "datetime.now().strftime('%Y-%m-%d')",
        "{time}": "datetime.now().strftime('%H:%M:%S')",
        "{timestamp}": "str(int(datetime.now().timestamp()))"
    }

    @staticmethod
    def get_all_variables() -> Dict[str, str]:
        """Get all available variables"""
        return {
            **VariableParser.MEMBER_VARIABLES,
            **VariableParser.SERVER_VARIABLES,
            **VariableParser.TIME_VARIABLES
        }

    @staticmethod
    async def parse(
        text: str,
        member: discord.Member,
        guild: discord.Guild
    ) -> str:
        """Parse variables in text"""
        if not text:
            return text

        try:
            for var, code in VariableParser.MEMBER_VARIABLES.items():
                if var in text:
                    try:
                        value = eval(code)
                        text = text.replace(var, str(value))
                    except Exception:
                        text = text.replace(var, "Unknown")

            for var, code in VariableParser.SERVER_VARIABLES.items():
                if var in text:
                    try:
                        value = eval(code)
                        text = text.replace(var, str(value))
                    except Exception:
                        text = text.replace(var, "Unknown")

            for var, code in VariableParser.TIME_VARIABLES.items():
                if var in text:
                    try:
                        value = eval(code)
                        text = text.replace(var, str(value))
                    except Exception:
                        text = text.replace(var, "Unknown")

        except Exception as e:
            print(f"Error parsing variables: {e}")

        return text



class TitleModal(ui.Modal, title="Edit Embed Title"):
    """Modal for editing embed title"""

    title_input = ui.TextInput(
        label="Embed Title",
        placeholder="Enter embed title",
        max_length=256,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class DescriptionModal(ui.Modal, title="Edit Embed Description"):
    """Modal for editing embed description"""

    description_input = ui.TextInput(
        label="Embed Description",
        placeholder="Enter embed description",
        max_length=4000,
        required=False,
        style=discord.TextStyle.long
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class MessageModal(ui.Modal, title="Edit Farewell Message"):
    """Modal for editing farewell message"""

    message_input = ui.TextInput(
        label="Farewell Message",
        placeholder="Enter farewell message (supports variables)",
        max_length=2000,
        required=False,
        style=discord.TextStyle.long
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class ImageModal(ui.Modal, title="Edit Embed Images"):
    """Modal for editing embed images"""

    thumbnail_input = ui.TextInput(
        label="Thumbnail URL",
        placeholder="https://example.com/image.png",
        required=False
    )

    image_input = ui.TextInput(
        label="Image URL",
        placeholder="https://example.com/image.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class ColorModal(ui.Modal, title="Edit Embed Color"):
    """Modal for editing embed color"""

    color_input = ui.TextInput(
        label="Color (Hex)",
        placeholder="2b2d31",
        max_length=6,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class AuthorModal(ui.Modal, title="Edit Author"):
    """Modal for editing embed author"""

    author_name_input = ui.TextInput(
        label="Author Name",
        placeholder="Author name",
        max_length=256,
        required=False
    )

    author_icon_input = ui.TextInput(
        label="Author Icon URL",
        placeholder="https://example.com/icon.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()


class FooterModal(ui.Modal, title="Edit Footer"):
    """Modal for editing embed footer"""

    footer_text_input = ui.TextInput(
        label="Footer Text",
        placeholder="Footer text",
        max_length=2048,
        required=False
    )

    footer_icon_input = ui.TextInput(
        label="Footer Icon URL",
        placeholder="https://example.com/icon.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()



class EmbedBuilderDropdown(ui.Select):
    def __init__(self, builder_view: "EmbedBuilderView"):
        options = [
            discord.SelectOption(label="Message", description="Set plain text farewell message"),
            discord.SelectOption(label="Title", description="Set the embed title"),
            discord.SelectOption(label="Description", description="Set the embed description"),
            discord.SelectOption(label="Author", description="Set the author name"),
            discord.SelectOption(label="Color", description="Set the embed color (hex)"),
            discord.SelectOption(label="Footer", description="Set the footer text"),
            discord.SelectOption(label="Images", description="Set Thumbnail and Image"),
            discord.SelectOption(label="Variables", description="Show available variables")
        ]
        super().__init__(placeholder="Select a component to edit...", min_values=1, max_values=1, options=options)
        self.builder_view = builder_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder_view.user_id:
            return await interaction.response.send_message(
                embed=EmbedBuilder.create_error_embed("Permission Denied", "Only the command executor can use this."),
                ephemeral=True
            )

        choice = self.values[0]

        if choice == "Title":
            modal = TitleModal()
            modal.title_input.default = self.builder_view.embed_data["title"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["title"] = modal.title_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Description":
            modal = DescriptionModal()
            modal.description_input.default = self.builder_view.embed_data["description"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["description"] = modal.description_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Message":
            modal = MessageModal()
            modal.message_input.default = self.builder_view.embed_data["message"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["message"] = modal.message_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Images":
            modal = ImageModal()
            modal.thumbnail_input.default = self.builder_view.embed_data["thumbnail"]
            modal.image_input.default = self.builder_view.embed_data["image"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["thumbnail"] = modal.thumbnail_input.value
            self.builder_view.embed_data["image"] = modal.image_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Color":
            modal = ColorModal()
            color_value = str(self.builder_view.embed_data["color"]).replace("0x", "")
            modal.color_input.default = color_value
            await interaction.response.send_modal(modal)
            await modal.wait()
            color_value = modal.color_input.value
            if color_value and len(color_value) == 6:
                try:
                    int(color_value, 16)
                    self.builder_view.embed_data["color"] = f"0x{color_value}"
                except ValueError:
                    await interaction.followup.send(
                        embed=EmbedBuilder.create_error_embed("Invalid Color", "Please provide a valid hex color (e.g., 2b2d31)"),
                        ephemeral=True
                    )
                    return
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Author":
            modal = AuthorModal()
            modal.author_name_input.default = self.builder_view.embed_data["author_name"]
            modal.author_icon_input.default = self.builder_view.embed_data["author_icon"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["author_name"] = modal.author_name_input.value
            self.builder_view.embed_data["author_icon"] = modal.author_icon_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Footer":
            modal = FooterModal()
            modal.footer_text_input.default = self.builder_view.embed_data["footer_text"]
            modal.footer_icon_input.default = self.builder_view.embed_data["footer_icon"]
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.builder_view.embed_data["footer_text"] = modal.footer_text_input.value
            self.builder_view.embed_data["footer_icon"] = modal.footer_icon_input.value
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.builder_view.get_preview_embed())

        elif choice == "Variables":
            text = "\n".join([f"`{k}`" for k in VariableParser.get_all_variables().keys()])
            embed = EmbedBuilder.create_info_embed("Available Variables", text)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class EmbedBuilderView(ui.View):
    """Interactive embed builder for farewell system"""

    def __init__(self, cog: "Farewell", user_id: int, config: Dict[str, Any], channel_id: int = None):
        super().__init__(timeout=120)
        self.cog = cog
        self.user_id = user_id
        self.config = config
        self.saved = False
        self.channel_id = channel_id
        self.embed_data = {
            "title": config.get("embed_title", ""),
            "description": config.get("embed_description", ""),
            "color": config.get("embed_color", "0x2b2d31"),
            "thumbnail": config.get("embed_thumbnail", ""),
            "image": config.get("embed_image", ""),
            "footer_text": config.get("footer_text", ""),
            "footer_icon": config.get("footer_icon", ""),
            "author_name": config.get("author_name", ""),
            "author_icon": config.get("author_icon", ""),
            "timestamp": config.get("timestamp_toggle", False),
            "message": config.get("farewell_message", "")
        }
        self.add_item(EmbedBuilderDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command executor can use buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the command executor can use these buttons."
                ),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Handle view timeout"""
        for item in self.children:
            item.disabled = True

    def get_preview_embed(self) -> discord.Embed:
        """Generate preview embed"""
        return EmbedBuilder.create_embed(
            title=self.embed_data["title"] or "Embed Title",
            description=self.embed_data["description"] or "Embed Description",
            color=self.embed_data["color"],
            thumbnail_url=self.embed_data["thumbnail"] or None,
            image_url=self.embed_data["image"] or None,
            footer_text=self.embed_data["footer_text"] or None,
            footer_icon=self.embed_data["footer_icon"] or None,
            author_name=self.embed_data["author_name"] or None,
            author_icon=self.embed_data["author_icon"] or None,
            timestamp=self.embed_data["timestamp"]
        )

    @ui.button(label="Toggle Timestamp", style=discord.ButtonStyle.gray, row=1)
    async def toggle_timestamp_button(self, interaction: discord.Interaction, button: ui.Button):
        """Toggle timestamp"""
        self.embed_data["timestamp"] = not self.embed_data["timestamp"]
        button.label = f"Timestamp: {'ON' if self.embed_data['timestamp'] else 'OFF'}"
        await interaction.response.edit_message(embed=self.get_preview_embed(), view=self)

    @ui.button(label="Save", style=discord.ButtonStyle.green, row=1)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        """Save configuration"""
        await interaction.response.defer()

        config_data = {
            "enabled": True,               
            "channel_id": self.channel_id,         
            "farewell_message": self.embed_data["message"],
            "embed_title": self.embed_data["title"],
            "embed_description": self.embed_data["description"],
            "embed_color": self.embed_data["color"],
            "embed_thumbnail": self.embed_data["thumbnail"],
            "embed_image": self.embed_data["image"],
            "footer_text": self.embed_data["footer_text"],
            "footer_icon": self.embed_data["footer_icon"],
            "author_name": self.embed_data["author_name"],
            "author_icon": self.embed_data["author_icon"],
            "timestamp_toggle": self.embed_data["timestamp"]
        }

        success = await self.cog.db.set_config(
            interaction.guild_id,
            **config_data
        )
        self.saved = True
        self.stop()

        if success:
            await interaction.followup.send(
                embed=EmbedBuilder.create_success_embed(
                    "Configuration Saved",
                    "Your farewell configuration has been saved successfully!"
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=EmbedBuilder.create_error_embed(
                    "Save Failed",
                    "Failed to save configuration. Please try again."
                ),
                ephemeral=True
            )


    @ui.button(label="Cancel", style=discord.ButtonStyle.red, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel and discard changes"""
        await interaction.response.defer()
        await interaction.followup.send(
            embed=EmbedBuilder.create_info_embed(
                "Cancelled",
                "Configuration changes have been discarded."
            ),
            ephemeral=True
        )
        self.stop()


class ChannelSelectView(ui.View):
    """View for selecting channel in setup wizard"""

    def __init__(self, cog: "Farewell", user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.selected_channel: Optional[discord.TextChannel] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only command executor can interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the command executor can use these buttons."
                ),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Handle timeout"""
        for item in self.children:
            item.disabled = True
            self.stop

    @ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a farewell channel...")
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        """Select a channel for farewell"""
        self.selected_channel = select.values[0]
        await interaction.response.defer()
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel setup"""
        await interaction.response.defer()
        self.selected_channel = None
        await self.cog.db.delete_config(interaction.guild_id)
        await interaction.message.edit(
            embed=EmbedBuilder.create_info_embed(
            "Cancelled",
            "Channel selection was cancelled."
        ),
        view=None
    )




class ConfirmView(ui.View):
    """Simple confirm/cancel view"""

    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only command executor can interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the command executor can use these buttons."
                ),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Handle timeout"""
        for item in self.children:
            item.disabled = True

    @ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm action"""
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel action"""
        await interaction.response.defer()
        self.stop()



class Farewell(commands.Cog):
    """Advanced farewell system for Discord servers"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = FarewellDatabase()

    async def cog_load(self):
        """Initialize cog"""
        await self.db.initialize()








    @commands.group(
        name="farewell",
        aliases=["goodbye"],
        invoke_without_command=True,
        help="Manage server farewell messages"
    )
    @blacklist_check()
    @ignore_check()

    async def farewell_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @farewell_group.command(name="setup", help="Interactive setup wizard for farewell system")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def setup_command(self, ctx: commands.Context):
        """Setup farewell system interactively"""


        existing_config = await self.db.get_config(ctx.guild.id)
        if existing_config:
            embed = EmbedBuilder.create_error_embed(
                "This guild already has a farewell system configured.\n",
                "Use `farewell reset` to start over, or `farewell edit` to modify."
            )
            await ctx.send(embed=embed)
            return

        embed = EmbedBuilder.create_info_embed(
            "Farewell Setup - Step 1: Channel Selection",
            "Please select which channel farewell messages should be sent to using the dropdown below."
        )

        view = ChannelSelectView(self, ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        await view.wait()

        await message.edit(view=None)
        channel = view.selected_channel
        if not channel:
            await message.edit(
                embed=EmbedBuilder.create_error_embed(
                    "",
                    "Channel selection was cancelled or timed out."
                )

            )
            return



        config = {
            "enabled": True,
            "channel_id": channel.id,
            "farewell_message": "",
            "embed_title": "Goodbye!",
            "embed_description": "A member has left the server.",
            "embed_color": "0x2b2d31",
            "embed_thumbnail": "",
            "embed_image": "",
            "footer_text": "",
            "footer_icon": "",
            "author_name": "",
            "author_icon": "",
            "timestamp_toggle": False
        }



        updated_config = await self.db.get_config(ctx.guild.id)
        builder_view = EmbedBuilderView(self, ctx.author.id, config, channel_id=channel.id)

        await message.edit(
            embed=builder_view.get_preview_embed(),
            view=builder_view
        )

        await builder_view.wait()
        if not builder_view.saved:
            await message.edit(
                embed=EmbedBuilder.create_info_embed(
            "Setup Cancelled",
            "<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Farewell setup was cancelled."
                    ),
                view=None
                )
            return

        final_config = await self.db.get_config(ctx.guild.id)
        final_embed = EmbedBuilder.create_embed(
            title=final_config.get("embed_title"),
            description=final_config.get("embed_description"),
            color=final_config.get("embed_color"),
            thumbnail_url=final_config.get("embed_thumbnail"),
            image_url=final_config.get("embed_image"),
            footer_text=final_config.get("footer_text"),
            footer_icon=final_config.get("footer_icon"),
            author_name=final_config.get("author_name"),
            author_icon=final_config.get("author_icon"),
            timestamp=final_config.get("timestamp_toggle", False)
        )

        confirmation_embed = discord.Embed(
            title="",
            description=f"<:emoji_1769867605256:1467155817726873650> Setup Complete\nFarewell system configured successfully!\n**Channel**: {channel.mention}\n**Status**: Enabled\nPreview of your farewell embed:",
            color=0x2b2d31
        )

        await message.edit(embed=confirmation_embed, view=None)
        await ctx.send(embed=final_embed)

    @farewell_group.command(name="reset", help="Reset farewell configuration")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def reset_command(self, ctx: commands.Context):
        """Reset farewell configuration"""


        config = await self.db.get_config(ctx.guild.id)
        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured."
            )
            await ctx.send(embed=embed)
            return

        embed = EmbedBuilder.create_info_embed(
            "Confirm Reset",
            "Are you sure you want to delete the farewell configuration?"
        )

        view = ConfirmView(ctx.author.id)
        sigma = await ctx.send(embed=embed, view=view)
        await view.wait()


        await sigma.edit(view=None)

        if not view.confirmed:
            await sigma.edit(
                embed=EmbedBuilder.create_success_embed(
                    "",
                    "Reset has been cancelled."
                )
            )
            return

        success = await self.db.delete_config(ctx.guild.id)

        if success:
            embed = EmbedBuilder.create_success_embed(
                "",
                "Farewell configuration has been deleted successfully."
            )
        else:
            embed = EmbedBuilder.create_error_embed(
                ""
                "Failed to delete configuration. Please try again."
            )

        await sigma.edit(embed=embed, view=None)

    @farewell_group.command(name="config", help="View current farewell configuration")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def config_command(self, ctx: commands.Context):
        """View farewell configuration"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured. Use `farewell setup` to configure it."
            )
            await ctx.send(embed=embed)
            return

        channel = ctx.guild.get_channel(config["channel_id"])
        channel_mention = channel.mention if channel else f"<#{config['channel_id']}> (Deleted)"

        embed = EmbedBuilder.create_info_embed(
            "Farewell Configuration",
            ""
        )
        embed.add_field(name="Status", value="<:emoji_1769867605256:1467155817726873650> Enabled" if config["enabled"] else "<:emoji_1769867589372:1467155751456735326> Disabled", inline=False)
        embed.add_field(name="Channel", value=channel_mention, inline=False)
        embed.add_field(name="Message", value=config.get("farewell_message", "*(empty)*"), inline=False)
        embed.add_field(name="Embed Title", value=config.get("embed_title", "*(empty)*"), inline=False)
        embed.add_field(name="Embed Description", value=config.get("embed_description", "*(empty)*"), inline=False)
        embed.add_field(name="Color", value=config.get("embed_color", "0x2b2d31"), inline=False)
        embed.add_field(name="Timestamp", value="<:emoji_1769867605256:1467155817726873650> Enabled" if config.get("timestamp_toggle") else "<:emoji_1769867589372:1467155751456735326> Disabled", inline=False)
        embed.add_field(name="Created", value=config.get("created_at", "Unknown"), inline=False)
        embed.add_field(name="Last Updated", value=config.get("last_updated", "Unknown"), inline=False)

        await ctx.send(embed=embed)

    @farewell_group.command(name="toggle", help="Enable or disable farewell system")
    @commands.has_permissions(manage_guild=True)
    async def toggle_command(self, ctx: commands.Context):
        """Toggle farewell system"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured."
            )
            await ctx.send(embed=embed)
            return

        new_state = not config["enabled"]
        success = await self.db.toggle_enabled(ctx.guild.id, new_state)

        if success:
            status = "Enabled" if new_state else "Disabled"
            embed = EmbedBuilder.create_success_embed(
                "",
                f"Farewell system is now {status}."
            )
        else:
            embed = EmbedBuilder.create_error_embed(
                "",
                "Failed to toggle system. Please try again."
            )

        await ctx.send(embed=embed)

    @farewell_group.command(name="variables", help="View available variables for farewell messages")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def variables_command(self, ctx: commands.Context):
        """Show all available variables"""
        all_vars = VariableParser.get_all_variables()

        embed = EmbedBuilder.create_info_embed(
            "Farewell System Variables",
            "Use these variables in your farewell message to customize it dynamically."
        )

        member_vars = "\n".join([f"`{var}`" for var in VariableParser.MEMBER_VARIABLES.keys()])
        embed.add_field(name="Member Variables", value=member_vars or "None", inline=False)

        server_vars = "\n".join([f"`{var}`" for var in VariableParser.SERVER_VARIABLES.keys()])
        embed.add_field(name="Server Variables", value=server_vars or "None", inline=False)

        time_vars = "\n".join([f"`{var}`" for var in VariableParser.TIME_VARIABLES.keys()])
        embed.add_field(name="Time Variables", value=time_vars or "None", inline=False)

        await ctx.send(embed=embed)

    @farewell_group.command(name="test", help="Send a test farewell message")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def test_command(self, ctx: commands.Context):
        """Send a test farewell message"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured."
            )
            await ctx.send(embed=embed)
            return

        if not config["enabled"]:
            embed = EmbedBuilder.create_error_embed(
                "",
                "Farewell system is currently disabled."
            )
            await ctx.send(embed=embed)
            return

        channel = ctx.guild.get_channel(config["channel_id"])
        if not channel:
            embed = EmbedBuilder.create_error_embed(
                "",
                f"The configured channel (ID: {config['channel_id']}) no longer exists."
            )
            await ctx.send(embed=embed)
            return

        message = await VariableParser.parse(
            config.get("farewell_message", ""),
            ctx.author,
            ctx.guild
        )

        title = await VariableParser.parse(config.get("embed_title"), ctx.author, ctx.guild)
        description = await VariableParser.parse(config.get("embed_description"), ctx.author, ctx.guild)
        footer_text = await VariableParser.parse(config.get("footer_text"), ctx.author, ctx.guild)
        author_name = await VariableParser.parse(config.get("author_name"), ctx.author, ctx.guild)
        thumbnail_url = await VariableParser.parse(config.get("embed_thumbnail"), ctx.author, ctx.guild)
        image_url = await VariableParser.parse(config.get("embed_image"), ctx.author, ctx.guild)
        author_icon = await VariableParser.parse(config.get("author_icon"), ctx.author, ctx.guild)
        footer_icon = await VariableParser.parse(config.get("footer_icon"), ctx.author, ctx.guild)

        farewell_embed = EmbedBuilder.create_embed(
            title=title,
            description=description,
            color=config.get("embed_color", "0x2b2d31"),
            thumbnail_url=thumbnail_url,
            image_url=image_url,
            footer_text=footer_text,
            footer_icon=footer_icon,
            author_name=author_name,
            author_icon=author_icon,
            timestamp=config.get("timestamp_toggle", False)
        )

        try:
            await channel.send(content=message or None, embed=farewell_embed)
            embed = EmbedBuilder.create_success_embed(
                "",
                f"Test farewell message sent to {channel.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.create_error_embed(
                "",
                f"Failed to send test message: {str(e)}"
            )
            await ctx.send(embed=embed)

    @farewell_group.command(name="edit", help="Edit existing farewell configuration")
    @commands.has_permissions(manage_guild=True)
    async def edit_command(self, ctx: commands.Context):
        """Edit farewell configuration"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured. Use `farewell setup` to create one."
            )
            await ctx.send(embed=embed)
            return


        builder_view = EmbedBuilderView(self, ctx.author.id, config)

        await ctx.send(embed=builder_view.get_preview_embed(), view=builder_view)
        await builder_view.wait()

    @farewell_group.command(name="preview", help="Preview farewell message")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def preview_command(self, ctx: commands.Context):
        """Preview farewell embed"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured."
            )
            await ctx.send(embed=embed)
            return

        title = await VariableParser.parse(config.get("embed_title"), ctx.author, ctx.guild)
        description = await VariableParser.parse(config.get("embed_description"), ctx.author, ctx.guild)
        footer_text = await VariableParser.parse(config.get("footer_text"), ctx.author, ctx.guild)
        author_name = await VariableParser.parse(config.get("author_name"), ctx.author, ctx.guild)
        thumbnail_url = await VariableParser.parse(config.get("embed_thumbnail"), ctx.author, ctx.guild)
        image_url = await VariableParser.parse(config.get("embed_image"), ctx.author, ctx.guild)
        author_icon = await VariableParser.parse(config.get("author_icon"), ctx.author, ctx.guild)
        footer_icon = await VariableParser.parse(config.get("footer_icon"), ctx.author, ctx.guild)

        preview_embed = EmbedBuilder.create_embed(
            title=title,
            description=description,
            color=config.get("embed_color", "0x2b2d31"),
            thumbnail_url=thumbnail_url,
            image_url=image_url,
            footer_text=footer_text,
            footer_icon=footer_icon,
            author_name=author_name,
            author_icon=author_icon,
            timestamp=config.get("timestamp_toggle", False)
        )

        await ctx.send(embed=preview_embed)

    @farewell_group.command(name="export", help="Export farewell configuration as JSON")
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def export_command(self, ctx: commands.Context):
        """Export configuration"""


        config = await self.db.get_config(ctx.guild.id)

        if not config:
            embed = EmbedBuilder.create_error_embed(
                "",
                "This guild does not have a farewell system configured."
            )
            await ctx.send(embed=embed)
            return

        export_data = dict(config)
        export_data.pop("guild_id", None)

        json_data = json.dumps(export_data, indent=2, default=str)

        import io
        file = discord.File(
            io.StringIO(json_data),
            filename=f"farewell_config_{ctx.guild.id}.json"
        )

        embed = EmbedBuilder.create_info_embed(
            "",
            "Your farewell configuration has been exported."
        )

        await ctx.send(embed=embed, file=file)

    @farewell_group.command(name="import", help="Import farewell configuration from JSON")
    @commands.has_permissions(manage_guild=True)
    async def import_command(self, ctx: commands.Context):
        """Import configuration"""


        if not ctx.message.attachments:
            embed = EmbedBuilder.create_error_embed(
                "",
                "Please attach a JSON configuration file."
            )
            await ctx.send(embed=embed)
            return

        attachment = ctx.message.attachments[0]

        if not attachment.filename.endswith(".json"):
            embed = EmbedBuilder.create_error_embed(
                "",
                "Please provide a JSON file."
            )
            await ctx.send(embed=embed)
            return

        try:
            file_content = await attachment.read()
            import_data = json.loads(file_content.decode('utf-8'))

            required_fields = ["channel_id", "enabled"]
            if not all(field in import_data for field in required_fields):
                raise ValueError("Missing required fields")

            success = await self.db.set_config(ctx.guild.id, **import_data)

            if success:
                embed = EmbedBuilder.create_success_embed(
                    "Configuration Imported",
                    "Farewell configuration has been imported successfully."
                )
            else:
                embed = EmbedBuilder.create_error_embed(
                    "Import Failed",
                    "Failed to import configuration."
                )

        except json.JSONDecodeError:
            embed = EmbedBuilder.create_error_embed(
                "Invalid JSON",
                "The file is not valid JSON."
            )
        except ValueError as e:
            embed = EmbedBuilder.create_error_embed(
                "Invalid Configuration",
                f"Configuration validation failed: {str(e)}"
            )
        except Exception as e:
            embed = EmbedBuilder.create_error_embed(
                "Import Error",
                f"Failed to import configuration: {str(e)}"
            )

        await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member removal and send farewell message"""
        try:
            config = await self.db.get_config(member.guild.id)

            if not config or not config["enabled"]:
                return

            channel = member.guild.get_channel(config["channel_id"])
            if not channel:
                return

            message = await VariableParser.parse(
                config.get("farewell_message", ""),
                member,
                member.guild
            )

            title = await VariableParser.parse(config.get("embed_title"), member, member.guild)
            description = await VariableParser.parse(config.get("embed_description"), member, member.guild)
            footer_text = await VariableParser.parse(config.get("footer_text"), member, member.guild)
            author_name = await VariableParser.parse(config.get("author_name"), member, member.guild)
            thumbnail_url = await VariableParser.parse(config.get("embed_thumbnail"), member, member.guild)
            image_url = await VariableParser.parse(config.get("embed_image"), member, member.guild)
            author_icon = await VariableParser.parse(config.get("author_icon"), member, member.guild)
            footer_icon = await VariableParser.parse(config.get("footer_icon"), member, member.guild)

            farewell_embed = EmbedBuilder.create_embed(
                title=title,
                description=description,
                color=config.get("embed_color", "0x2b2d31"),
                thumbnail_url=thumbnail_url,
                image_url=image_url,
                footer_text=footer_text,
                footer_icon=footer_icon,
                author_name=author_name,
                author_icon=author_icon,
                timestamp=config.get("timestamp_toggle", False)
            )

            await channel.send(content=message or None, embed=farewell_embed)

        except Exception as e:
            print(f"Error sending farewell message: {e}")



async def setup(bot: commands.Bot):
    """Setup cog"""
    await bot.add_cog(Farewell(bot))