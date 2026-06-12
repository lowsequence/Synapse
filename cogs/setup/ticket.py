import asyncio
import datetime
import io
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from utils.Tools import blacklist_check, ignore_check
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

DB_PATH = os.path.join("database", "tickets.db")
EMBED_COLOR = 0x2b2d31


@dataclass
class PanelConfig:
    guild_id: int
    panel_name: str
    style: str
    staff_role: Optional[int]
    ping_role: Optional[int]
    category_id: Optional[int]
    embed_title: Optional[str]
    embed_description: Optional[str]
    embed_thumbnail: Optional[str]
    embed_footer: Optional[str]
    embed_color: int
    dropdown_json: str
    extra_json: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "PanelConfig":
        return cls(
            guild_id=row[0],
            panel_name=row[1],
            style=row[2],
            staff_role=row[3],
            ping_role=row[4],
            category_id=row[5],
            embed_title=row[6],
            embed_description=row[7],
            embed_thumbnail=row[8],
            embed_footer=row[9],
            embed_color=row[10],
            dropdown_json=row[11] or "[]",
            extra_json=row[13] or "{}",
        )

    def to_db_tuple(self) -> Tuple[Any, ...]:
        return (
            self.guild_id,
            self.panel_name,
            self.style,
            self.staff_role,
            self.ping_role,
            self.category_id,
            self.embed_title,
            self.embed_description,
            self.embed_thumbnail,
            self.embed_footer,
            self.embed_color,
            self.dropdown_json,
            "[]",
            self.extra_json,
        )


class TicketSetupEmbedTitleModal(discord.ui.Modal, title="Set Embed Title"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.embed_title_input = discord.ui.TextInput(
            label="Embed Title",
            style=discord.TextStyle.short,
            max_length=256,
            required=True,
            default=wizard.config.embed_title or "",
        )
        self.add_item(self.embed_title_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.wizard.config.embed_title = str(self.embed_title_input.value)
        await self.wizard.refresh_message(interaction, "Embed title updated.")


class TicketSetupEmbedDescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.embed_description_input = discord.ui.TextInput(
            label="Embed Description",
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False,
            default=self.wizard.config.embed_description or "",
        )
        self.add_item(self.embed_description_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.wizard.config.embed_description = str(self.embed_description_input.value)
        await self.wizard.refresh_message(interaction, "Embed description updated.")


class TicketSetupThumbnailModal(discord.ui.Modal, title="Set Thumbnail URL"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.thumbnail_input = discord.ui.TextInput(
            label="Thumbnail URL",
            style=discord.TextStyle.short,
            max_length=512,
            required=False,
            default=self.wizard.config.embed_thumbnail or "",
        )
        self.add_item(self.thumbnail_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.thumbnail_input.value).strip()
        self.wizard.config.embed_thumbnail = value or None
        await self.wizard.refresh_message(interaction, "Embed thumbnail updated.")


class TicketSetupFooterModal(discord.ui.Modal, title="Set Footer Text"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.footer_input = discord.ui.TextInput(
            label="Footer Text",
            style=discord.TextStyle.short,
            max_length=256,
            required=False,
            default=self.wizard.config.embed_footer or "",
        )
        self.add_item(self.footer_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.footer_input.value).strip()
        self.wizard.config.embed_footer = value or None
        await self.wizard.refresh_message(interaction, "Embed footer updated.")


class TicketSetupColorModal(discord.ui.Modal, title="Set Embed Color (Hex)"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.color_input = discord.ui.TextInput(
            label="Color (e.g. #2b2d31 or 0x2b2d31)",
            style=discord.TextStyle.short,
            max_length=16,
            required=False,
            default=hex(self.wizard.config.embed_color),
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.color_input.value).strip()
        try:
            if value:
                if value.startswith("#"):
                    value = "0x" + value[1:]
                color_value = int(value, 16)
                self.wizard.config.embed_color = color_value
            else:
                self.wizard.config.embed_color = EMBED_COLOR
            await self.wizard.refresh_message(interaction, "Embed color updated.")
        except ValueError:
            await interaction.response.send_message(
                "Invalid color format. Please use hex (e.g. #2b2d31).",
                ephemeral=True,
            )

class TicketSetupImageModal(discord.ui.Modal, title="Set Embed Image URL"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        try:
            extras = json.loads(self.wizard.config.extra_json or "{}")
        except Exception:
            extras = {}
        self.image_input = discord.ui.TextInput(
            label="Image URL",
            style=discord.TextStyle.short,
            max_length=512,
            required=False,
            default=str(extras.get("embed_image") or ""),
        )
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.image_input.value).strip()
        try:
            extras = json.loads(self.wizard.config.extra_json or "{}")
        except Exception:
            extras = {}
        if value:
            extras["embed_image"] = value
        else:
            extras.pop("embed_image", None)
        self.wizard.config.extra_json = json.dumps(extras)
        await self.wizard.refresh_message(interaction, "Embed image URL updated.")


class TicketSetupFooterIconModal(discord.ui.Modal, title="Set Footer Icon URL"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=300)
        self.wizard = wizard
        try:
            extras = json.loads(self.wizard.config.extra_json or "{}")
        except Exception:
            extras = {}
        self.footer_icon_input = discord.ui.TextInput(
            label="Footer Icon URL",
            style=discord.TextStyle.short,
            max_length=512,
            required=False,
            default=str(extras.get("embed_footer_icon") or ""),
        )
        self.add_item(self.footer_icon_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.footer_icon_input.value).strip()
        try:
            extras = json.loads(self.wizard.config.extra_json or "{}")
        except Exception:
            extras = {}
        if value:
            extras["embed_footer_icon"] = value
        else:
            extras.pop("embed_footer_icon", None)
        self.wizard.config.extra_json = json.dumps(extras)
        await self.wizard.refresh_message(interaction, "Footer icon URL updated.")


class TicketSetupDropdownModal(discord.ui.Modal, title="Configure Dropdown Options"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=600)
        self.wizard = wizard
        existing = ""
        try:
            data = json.loads(self.wizard.config.dropdown_json or "[]")
            lines = []
            for item in data:
                label = item.get("label") or ""
                emoji = item.get("emoji") or ""
                value = item.get("value") or ""
                lines.append(f"{label}|{emoji}|{value}")
            existing = "\n".join(lines[:3])
        except Exception:
            existing = ""
        self.options_input = discord.ui.TextInput(
            label="Dropdown: label|emoji|value per line",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
            default=existing,
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = str(self.options_input.value).strip()
        options: List[Dict[str, Any]] = []
        if text:
            for line in text.splitlines()[:3]:
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                label = parts[0][:45]
                emoji = parts[1] if len(parts) > 1 and parts[1] else None
                value_raw = parts[2] if len(parts) > 2 and parts[2] else label.lower()
                value = value_raw[:100]
                if not (1 <= len(label) <= 45) or not (1 <= len(value) <= 100):
                    continue
                options.append(
                    {
                        "label": label,
                        "emoji": emoji,
                        "value": value,
                    }
                )
        self.wizard.config.dropdown_json = json.dumps(options)
        await self.wizard.refresh_message(interaction, "Dropdown options updated.")


class TicketSetupButtonsModal(discord.ui.Modal, title="Configure Buttons"):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(timeout=600)
        self.wizard = wizard
        existing = ""
        try:
            data = json.loads(self.wizard.config.buttons_json or "[]")
            lines = []
            for item in data:
                label = item.get("label") or ""
                emoji = item.get("emoji") or ""
                style = str(item.get("style") or 2)
                lines.append(f"{label}|{emoji}|{style}")
            existing = "\n".join(lines)
        except Exception:
            existing = ""
        self.buttons_input = discord.ui.TextInput(
            label="Buttons: label|emoji|style per line",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
            default=existing,
        )
        self.add_item(self.buttons_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = str(self.buttons_input.value).strip()
        buttons: List[Dict[str, Any]] = []
        if text:
            for line in text.splitlines()[:5]:
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                label = parts[0][:45]
                emoji = parts[1] if len(parts) > 1 and parts[1] else None
                style_raw = parts[2] if len(parts) > 2 and parts[2] else "2"
                try:
                    style = int(style_raw)
                except ValueError:
                    style = 2
                if style < 1 or style > 5:
                    style = 2
                buttons.append(
                    {
                        "label": label,
                        "emoji": emoji,
                        "style": style,
                    }
                )
        self.wizard.config.buttons_json = json.dumps(buttons)
        await self.wizard.refresh_message(interaction, "Button configuration updated.")


class StaffRoleSelect(discord.ui.RoleSelect):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(
            placeholder="Select staff role",
            min_values=1,
            max_values=1,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        role = self.values[0]
        self.wizard.config.staff_role = role.id
        await self.wizard.refresh_message(interaction, f"Staff role set to {role.mention}.")


class PingRoleSelect(discord.ui.RoleSelect):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(
            placeholder="Select ping role (optional)",
            min_values=0,
            max_values=1,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values:
            role = self.values[0]
            self.wizard.config.ping_role = role.id
            await self.wizard.refresh_message(interaction, f"Ping role set to {role.mention}.")
        else:
            self.wizard.config.ping_role = None
            await self.wizard.refresh_message(interaction, "Ping role cleared.")


class CategoryChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, wizard: "TicketSetupWizard"):
        super().__init__(
            placeholder="Select ticket category",
            channel_types=[discord.ChannelType.category],
            min_values=1,
            max_values=1,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        category = self.values[0]
        self.wizard.config.category_id = category.id
        await self.wizard.refresh_message(interaction, f"Category set to {category.name}.")


class TicketSetupWizard(discord.ui.View):
    def __init__(
        self,
        cog: "TicketCog",
        author: discord.abc.User,
        panel_name: str,
        existing_config: Optional[PanelConfig] = None,
    ):
        self.cog = cog
        self.author = author
        self.panel_name = panel_name
        self.message: Optional[discord.Message] = None
        self.current_page: int = 1
        if existing_config is not None:
            self.config = existing_config
        else:
            self.config = PanelConfig(
                guild_id=0,
                panel_name=panel_name,
                style="button",
                staff_role=None,
                ping_role=None,
                category_id=None,
                embed_title=f"{panel_name} Tickets",
                embed_description="Open a ticket to contact staff.",
                embed_thumbnail=None,
                embed_footer=None,
                embed_color=EMBED_COLOR,
                dropdown_json="[]",
                extra_json="{}",
            )

    def ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            asyncio.create_task(
                interaction.response.send_message(
                    "You are not the owner of this setup wizard.",
                    ephemeral=True,
                )
            )
            return False
        return True

    def build_page1(self, note: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"Setup Wizard: {self.panel_name} — Page 1/3",
            description="Embed Settings",
            color=EMBED_COLOR,
        )
        if note:
            embed.add_field(name="Status", value=note, inline=False)
        embed.add_field(name="Embed Title", value=self.config.embed_title or "Not set", inline=True)
        preview_desc = (self.config.embed_description or "Not set")[:256]
        embed.add_field(name="Embed Description", value=preview_desc, inline=False)
        embed.add_field(name="Thumbnail", value=self.config.embed_thumbnail or "Not set", inline=True)
        embed.add_field(name="Footer", value=self.config.embed_footer or "Not set", inline=True)
        embed.add_field(name="Color", value=f"{hex(self.config.embed_color)}", inline=True)
        try:
            extras = json.loads(self.config.extra_json or "{}")
        except Exception:
            extras = {}
        embed.add_field(name="Image", value=extras.get("embed_image") or "Not set", inline=True)
        embed.add_field(name="Footer Icon URL", value=extras.get("embed_footer_icon") or "Not set", inline=True)
        icon_url = None
        if self.cog.bot.user:
            try:
                icon_url = self.cog.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Use the buttons to configure embed settings.", icon_url=icon_url)
        return embed

    def build_page2(self, note: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"Setup Wizard: {self.panel_name} — Page 2/3",
            description="Panel Settings",
            color=EMBED_COLOR,
        )
        if note:
            embed.add_field(name="Status", value=note, inline=False)
        embed.add_field(name="Style", value=self.config.style.title(), inline=True)
        try:
            dropdown = json.loads(self.config.dropdown_json or "[]")
        except Exception:
            dropdown = []
        embed.add_field(name="Dropdown Options", value=str(len(dropdown)), inline=True)
        icon_url = None
        if self.cog.bot.user:
            try:
                icon_url = self.cog.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Preview to test, Next to continue.", icon_url=icon_url)
        return embed

    def build_page3(self, note: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"Setup Wizard: {self.panel_name} — Page 3/3",
            description="Role & Category Settings",
            color=EMBED_COLOR,
        )
        if note:
            embed.add_field(name="Status", value=note, inline=False)
        embed.add_field(
            name="Staff Role",
            value=f"<@&{self.config.staff_role}>" if self.config.staff_role else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Ping Role",
            value=f"<@&{self.config.ping_role}>" if self.config.ping_role else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Category",
            value=f"<#{self.config.category_id}>" if self.config.category_id else "Not set",
            inline=True,
        )
        icon_url = None
        if self.cog.bot.user:
            try:
                icon_url = self.cog.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Set roles & category.", icon_url=icon_url)
        return embed

    def current_embed(self, note: Optional[str] = None) -> discord.Embed:
        if self.current_page == 1:
            return self.build_page1(note)
        if self.current_page == 2:
            return self.build_page2(note)
        return self.build_page3(note)

    def get_current_view(self) -> discord.ui.View:
        if self.current_page == 1:
            return Page1View(self)
        if self.current_page == 2:
            return Page2View(self)
        return Page3View(self)

    async def refresh_message(self, interaction: discord.Interaction, note: Optional[str] = None) -> None:
        embed = self.current_embed(note)
        view = self.get_current_view()
        if interaction.response.is_done():
            if self.message:
                await self.message.edit(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def goto_page(self, interaction: discord.Interaction, page: int, note: Optional[str] = None) -> None:
        self.current_page = max(1, min(3, page))
        embed = self.current_embed(note)
        view = self.get_current_view()
        if interaction.response.is_done():
            if self.message:
                await self.message.edit(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def cancel(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.send_message("Ticket setup cancelled.", ephemeral=True)
        view = self.get_current_view()
        for child in view.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        if self.message:
            await self.message.edit(view=view)

    async def save_panel(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        self.config.guild_id = interaction.guild.id
        error = await self.cog.save_panel_config(self.config)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        await interaction.response.send_message(
            f"Ticket panel `{self.panel_name}` saved successfully.",
            ephemeral=True,
        )
        view = self.get_current_view()
        for child in view.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        if self.message:
            await self.message.edit(view=view)

class WizardPageView(discord.ui.View):
    def __init__(self, wizard: TicketSetupWizard):
        super().__init__(timeout=900)
        self.wizard = wizard

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.wizard.author.id:
            await interaction.response.send_message(
                "You are not the owner of this setup wizard.",
                ephemeral=True,
            )
            return False
        return True

class Page1View(WizardPageView):
    def __init__(self, wizard: TicketSetupWizard):
        super().__init__(wizard)

    @discord.ui.button(label="Embed Title", style=discord.ButtonStyle.secondary, row=0)
    async def set_embed_title(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupEmbedTitleModal(self.wizard))

    @discord.ui.button(label="Embed Description", style=discord.ButtonStyle.secondary, row=0)
    async def set_embed_description(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupEmbedDescriptionModal(self.wizard))

    @discord.ui.button(label="Thumbnail URL", style=discord.ButtonStyle.secondary, row=1)
    async def set_thumbnail(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupThumbnailModal(self.wizard))

    @discord.ui.button(label="Footer Text", style=discord.ButtonStyle.secondary, row=1)
    async def set_footer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupFooterModal(self.wizard))

    @discord.ui.button(label="Embed Color", style=discord.ButtonStyle.secondary, row=2)
    async def set_color(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupColorModal(self.wizard))

    @discord.ui.button(label="Image URL", style=discord.ButtonStyle.secondary, row=2)
    async def set_image(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupImageModal(self.wizard))

    @discord.ui.button(label="Footer Icon URL", style=discord.ButtonStyle.secondary, row=2)
    async def set_footer_icon(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupFooterIconModal(self.wizard))

    @discord.ui.button(label="Next", emoji="<:rightshort:1469251448909861017>", style=discord.ButtonStyle.primary, row=3)
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.goto_page(interaction, 2)

    @discord.ui.button(label="Cancel", emoji="<:emoji_1769867589372:1467155751456735326>", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.cancel(interaction)

class Page2View(WizardPageView):
    def __init__(self, wizard: TicketSetupWizard):
        super().__init__(wizard)

    @discord.ui.button(label="Toggle Style", style=discord.ButtonStyle.primary, row=0)
    async def toggle_style(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.wizard.config.style = "dropdown" if self.wizard.config.style == "button" else "button"
        await self.wizard.refresh_message(interaction, f"Style set to {self.wizard.config.style.title()}.")

    @discord.ui.button(label="Edit Dropdown Options", style=discord.ButtonStyle.secondary, row=0)
    async def edit_dropdown(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(TicketSetupDropdownModal(self.wizard))

    @discord.ui.button(label="Preview Ticket Panel", style=discord.ButtonStyle.success, row=1)
    async def preview_panel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Preview can only be used in a guild.", ephemeral=True)
            return
        embed = self.wizard.cog.build_panel_embed(self.wizard.config)
        view = self.wizard.cog.build_panel_view(self.wizard.config)
        await interaction.response.send_message(
            "Panel preview:",
            embed=embed,
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Next", emoji="<:rightshort:1469251448909861017>", style=discord.ButtonStyle.primary, row=3)
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.goto_page(interaction, 3)

    @discord.ui.button(label="Cancel", emoji="<:emoji_1769867589372:1467155751456735326>", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.cancel(interaction)

class Page3View(WizardPageView):
    def __init__(self, wizard: TicketSetupWizard):
        super().__init__(wizard)
        staff = StaffRoleSelect(self.wizard)
        staff.row = 0
        ping = PingRoleSelect(self.wizard)
        ping.row = 1
        category = CategoryChannelSelect(self.wizard)
        category.row = 2
        self.add_item(staff)
        self.add_item(ping)
        self.add_item(category)

    @discord.ui.button(label="Save Panel", emoji="<:save:1470758298729840681>", style=discord.ButtonStyle.success, row=3)
    async def save_panel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.save_panel(interaction)

    @discord.ui.button(label="Cancel", emoji="<:emoji_1769867589372:1467155751456735326>", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.wizard.cancel(interaction)


class TicketPanelDropdown(discord.ui.Select):
    def __init__(self, cog: "TicketCog", panel_config: PanelConfig):
        self.cog = cog
        self.panel_config = panel_config
        options_data: List[Dict[str, Any]]
        try:
            options_data = json.loads(panel_config.dropdown_json or "[]")
        except Exception:
            options_data = []
        options: List[discord.SelectOption] = []
        for item in options_data[:3]:
            label = str(item.get("label") or "Open Ticket")[:100]
            value = str(item.get("value") or label.lower())[:100]
            description = item.get("description")
            emoji = item.get("emoji")
            options.append(
                discord.SelectOption(
                    label=label,
                    value=value,
                    description=description,
                    emoji=emoji,
                )
            )
        if not options:
            options.append(discord.SelectOption(label="Open Ticket", value="open_ticket"))
        super().__init__(
            placeholder="Select an option to open a ticket",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"ticket_panel_dropdown:{panel_config.guild_id}:{panel_config.panel_name}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_ticket_panel_interaction(interaction, self.panel_config)


class TicketPanelView(discord.ui.View):
    def __init__(self, cog: "TicketCog", panel_config: PanelConfig):
        super().__init__(timeout=None)
        self.cog = cog
        self.panel_config = panel_config
        if panel_config.style == "dropdown":
            self.add_item(TicketPanelDropdown(cog, panel_config))
        else:
            button = discord.ui.Button(
                label="Open Ticket",
                style=discord.ButtonStyle.primary,
                custom_id=f"ticket_panel_button:{panel_config.guild_id}:{panel_config.panel_name}:0",
            )
            button.callback = self.make_button_callback()
            self.add_item(button)

    def make_button_callback(self):
        async def callback(interaction: discord.Interaction) -> None:
            await self.cog.handle_ticket_panel_interaction(interaction, self.panel_config)

        return callback


class TicketControlsView(discord.ui.View):
    def __init__(self, cog: "TicketCog", guild_id: int, channel_id: int, ticket_owner_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.ticket_owner_id = ticket_owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id:
            return True

        user = interaction.user
        is_admin = False
        is_staff = False

        if isinstance(user, discord.Member):
            if user.guild_permissions.administrator:
                is_admin = True
            if user.guild_permissions.manage_channels:
                is_staff = True

        if not is_admin and not is_staff and self.cog.db and interaction.guild:
            async with self.cog.db.execute(
                "SELECT staff_role FROM guild_panels WHERE guild_id = ?",
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                staff_role = interaction.guild.get_role(int(row[0]))
                if staff_role and isinstance(user, discord.Member) and staff_role in user.roles:
                    is_staff = True

        claimer_id = None
        if self.cog.db:
            async with self.cog.db.execute(
                "SELECT claimer_id FROM ticket_claims WHERE channel_id = ?",
                (self.channel_id,),
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                claimer_id = int(row[0])

        is_claimer = (user.id == claimer_id)
        is_owner = (user.id == self.ticket_owner_id)

        if custom_id == "ticket_close_button":
            if is_owner or is_admin or is_claimer or is_staff:
                return True
            await interaction.response.send_message("You do not have permission to close this ticket.", ephemeral=True)
            return False

        elif custom_id == "ticket_claim_button":
            if is_admin or is_staff:
                return True
            await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)
            return False

        elif custom_id in ("ticket_transcript_button", "ticket_remove_button"):
            if is_admin or is_claimer:
                return True
            if is_staff and not claimer_id:
                await interaction.response.send_message("You must claim the ticket first to use this button.", ephemeral=True)
                return False
            await interaction.response.send_message("Only Administrators or the staff member who claimed this ticket can use this button.", ephemeral=True)
            return False

        return True

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_button",
    )
    async def close_ticket_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_close_ticket(interaction, self.channel_id, via_button=True)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.success,
        custom_id="ticket_claim_button",
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        staff_role = None
        if self.cog.db:
            async with self.cog.db.execute(
                "SELECT staff_role FROM guild_panels WHERE guild_id = ?",
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                staff_role = interaction.guild.get_role(int(row[0]))
        permitted = False
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
            if member.guild_permissions.manage_channels:
                permitted = True
            elif staff_role and staff_role in member.roles:
                permitted = True
        if not permitted:
            await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)
            return
        existing = None
        if self.cog.db:
            async with self.cog.db.execute(
                "SELECT claimer_id FROM ticket_claims WHERE channel_id = ?",
                (self.channel_id,),
            ) as cursor:
                existing = await cursor.fetchone()
        claimer_id = interaction.user.id
        claimer = interaction.user
        if existing and existing[0] and int(existing[0]) != claimer_id:
            await interaction.response.send_message(f"Already claimed by <@{existing[0]}>.", ephemeral=True)
            return
        if self.cog.db:
            await self.cog.db.execute(
                """
                INSERT INTO ticket_claims (guild_id, channel_id, claimer_id, claimed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    claimer_id=excluded.claimer_id,
                    claimed_at=excluded.claimed_at
                """,
                (interaction.guild.id, self.channel_id, claimer_id, datetime.datetime.utcnow().isoformat()),
            )
            await self.cog.db.commit()
        button.label = f"Claimed by {claimer.display_name}"
        button.disabled = True


        transcript_btn = discord.ui.Button(
            label="Transcript",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_transcript_button"
        )
        async def ts_callback(it: discord.Interaction):
            await self.cog.handle_transcript(it, self.channel_id, via_button=True)
        transcript_btn.callback = ts_callback
        self.add_item(transcript_btn)

        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Ticket Claimed",
                    description=f"This ticket has been claimed by {claimer.mention}",
                    color=EMBED_COLOR,
                )
                icon_url = None
                if self.cog.bot.user:
                    try:
                        icon_url = self.cog.bot.user.display_avatar.url
                    except Exception:
                        icon_url = None
                embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
                await channel.send(embed=embed)
        except discord.HTTPException:
            pass
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)


class TicketClosedView(discord.ui.View):
    def __init__(self, cog: "TicketCog", guild_id: int, channel_id: int, ticket_owner_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.ticket_owner_id = ticket_owner_id

    @discord.ui.button(
        label="Reopen",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen_button",
    )
    async def reopen_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_reopen_ticket(interaction, self.channel_id, self.ticket_owner_id)

    @discord.ui.button(
        label="Transcript",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_closed_transcript_button",
    )
    async def transcript_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_transcript(interaction, self.channel_id, via_button=True)

    @discord.ui.button(
        label="Delete",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete_button",
    )
    async def delete_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_remove_ticket(interaction, self.channel_id, via_button=True)


class TicketCog(commands.Cog):
    """Advanced ticket system using discord.py Components v2 and aiosqlite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: Optional[aiosqlite.Connection] = None
        self.ticket_creation_cooldowns: Dict[Tuple[int, int], float] = {}

    async def cog_load(self) -> None:
        await self.initialize()

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.db = await aiosqlite.connect(DB_PATH)
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_panels (
                guild_id INTEGER,
                panel_name TEXT,
                style TEXT,
                staff_role INTEGER,
                ping_role INTEGER,
                category_id INTEGER,
                embed_title TEXT,
                embed_description TEXT,
                embed_thumbnail TEXT,
                embed_footer TEXT,
                embed_color INTEGER,
                dropdown_json TEXT,
                buttons_json TEXT,
                extra_json TEXT
            );
            """
        )
        await self.db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_panel_unique
                ON guild_panels (
                guild_id,
                panel_name
            );
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS panel_messages (
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                panel_name TEXT
            );
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_tickets (
                guild_id INTEGER,
                channel_id INTEGER,
                ticket_id TEXT,
                user_id INTEGER,
                created_at TEXT
            );
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id INTEGER,
                user_id INTEGER
            );
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_dm_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1
            );
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_claims (
                guild_id INTEGER,
                channel_id INTEGER PRIMARY KEY,
                claimer_id INTEGER,
                claimed_at TEXT
            );
            """
        )
        await self.db.commit()
        async with self.db.execute("SELECT * FROM guild_panels") as cursor:
            async for row in cursor:
                config = PanelConfig.from_row(row)
                view = TicketPanelView(self, config)
                self.bot.add_view(view)
        self.bot.loop.create_task(self._limits_maintenance_loop())

    async def is_guild_premium(self, guild_id: int) -> bool:
        try:
            async with aiosqlite.connect(os.path.join("database", "premium_codes.db")) as pdb:
                async with pdb.execute(
                    "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                    (guild_id,),
                ) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return False
            expires_at = str(row[0])
            try:
                expires_dt = datetime.datetime.fromisoformat(expires_at)
            except Exception:
                return False
            return expires_dt >= datetime.datetime.utcnow()
        except Exception:
            return False

    async def get_allowed_panel_limit(self, guild_id: int) -> int:
        premium = await self.is_guild_premium(guild_id)
        return 3 if premium else 1

    async def enforce_guild_limits(self, guild_id: int) -> None:
        if not self.db:
            return
        allowed = await self.get_allowed_panel_limit(guild_id)
        async with self.db.execute(
            "SELECT channel_id, message_id, panel_name FROM panel_messages WHERE guild_id = ? ORDER BY message_id DESC",
            (guild_id,),
        ) as cursor:
            pm_rows = await cursor.fetchall()
        if pm_rows and len(pm_rows) > allowed:
            for channel_id, message_id, panel_name in pm_rows[allowed:]:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    channel = guild.get_channel(int(channel_id))
                    if isinstance(channel, discord.TextChannel):
                        try:
                            msg = await channel.fetch_message(int(message_id))
                            await msg.delete()
                        except Exception:
                            pass
                await self.db.execute(
                    "DELETE FROM panel_messages WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
                    (guild_id, channel_id, message_id),
                )
            await self.db.commit()
        async with self.db.execute(
            "SELECT panel_name FROM panel_messages WHERE guild_id = ? ORDER BY message_id DESC",
            (guild_id,),
        ) as cursor:
            active_names_rows = await cursor.fetchall()
        active_names = [r[0] for r in active_names_rows]
        async with self.db.execute(
            "SELECT panel_name FROM guild_panels WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            all_names_rows = await cursor.fetchall()
        all_names = sorted([r[0] for r in all_names_rows])
        keep = []
        for n in active_names:
            if n not in keep:
                keep.append(n)
            if len(keep) >= allowed:
                break
        if len(keep) < allowed:
            for n in all_names:
                if n not in keep:
                    keep.append(n)
                if len(keep) >= allowed:
                    break
        delete_names = [n for n in all_names if n not in keep]
        if delete_names:
            for name in delete_names:
                await self.db.execute(
                    "DELETE FROM guild_panels WHERE guild_id = ? AND panel_name = ?",
                    (guild_id, name),
                )
            await self.db.commit()

    async def _limits_maintenance_loop(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            try:
                if not self.db:
                    await asyncio.sleep(60)
                    continue
                gids = set()
                async with self.db.execute("SELECT DISTINCT guild_id FROM guild_panels") as cursor:
                    gids.update([r[0] async for r in cursor])
                async with self.db.execute("SELECT DISTINCT guild_id FROM panel_messages") as cursor:
                    gids.update([r[0] async for r in cursor])
                for gid in list(gids):
                    await self.enforce_guild_limits(int(gid))
            except Exception:
                pass
            await asyncio.sleep(60)

    def cog_unload(self) -> None:
        if hasattr(self.db, "close"):
            asyncio.create_task(self.db.close())

    async def get_panel_config(self, guild_id: int, panel_name: str) -> Optional[PanelConfig]:
        if not self.db:
            return None
        async with self.db.execute(
            "SELECT * FROM guild_panels WHERE guild_id = ? AND panel_name = ?",
            (guild_id, panel_name),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return PanelConfig.from_row(row)

    async def save_panel_config(self, config: PanelConfig) -> Optional[str]:
        if not self.db:
            return "Database not initialised."
        async with self.db.execute(
            "SELECT COUNT(*) FROM guild_panels WHERE guild_id = ?",
            (config.guild_id,),
        ) as cursor:
            count_row = await cursor.fetchone()
        total_panels = count_row[0] if count_row else 0
        async with self.db.execute(
            "SELECT COUNT(*) FROM guild_panels WHERE guild_id = ? AND panel_name = ?",
            (config.guild_id, config.panel_name),
        ) as cursor:
            existing_row = await cursor.fetchone()
        is_new = existing_row is None
        allowed = await self.get_allowed_panel_limit(config.guild_id)
        if is_new and total_panels >= allowed:
            return f"You can only have a maximum of {allowed} ticket panel(s) per guild."
        await self.db.execute(
            """
            INSERT INTO guild_panels (
                guild_id, panel_name, style, staff_role, ping_role, category_id,
                embed_title, embed_description, embed_thumbnail, embed_footer,
                embed_color, dropdown_json, buttons_json, extra_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, panel_name) DO UPDATE SET
                style=excluded.style,
                staff_role=excluded.staff_role,
                ping_role=excluded.ping_role,
                category_id=excluded.category_id,
                embed_title=excluded.embed_title,
                embed_description=excluded.embed_description,
                embed_thumbnail=excluded.embed_thumbnail,
                embed_footer=excluded.embed_footer,
                embed_color=excluded.embed_color,
                dropdown_json=excluded.dropdown_json,
                buttons_json=excluded.buttons_json,
                extra_json=excluded.extra_json;
            """,
            config.to_db_tuple(),
        )
        await self.db.commit()
        view = TicketPanelView(self, config)
        self.bot.add_view(view)
        return None

    def build_panel_embed(self, config: PanelConfig) -> discord.Embed:
        embed = discord.Embed(
            title=config.embed_title or "Support Desk",
            description=config.embed_description or "Click the button below to open a support ticket.",
            color=config.embed_color or EMBED_COLOR,
        )
        if config.embed_thumbnail:
            embed.set_thumbnail(url=config.embed_thumbnail)
        try:
            extras = json.loads(config.extra_json or "{}")
        except Exception:
            extras = {}
        image_url = extras.get("embed_image")
        footer_icon = extras.get("embed_footer_icon")
        if not footer_icon and self.bot.user:
            try:
                footer_icon = self.bot.user.display_avatar.url
            except Exception:
                footer_icon = None
        if image_url:
            embed.set_image(url=image_url)
        if config.embed_footer:
            embed.set_footer(text=config.embed_footer, icon_url=footer_icon)
        else:
            embed.set_footer(text="Synapse - Ticketing", icon_url=footer_icon)
        return embed

    def build_panel_view(self, config: PanelConfig) -> discord.ui.View:
        return TicketPanelView(self, config)

    async def is_blacklisted(self, guild_id: int, user_id: int) -> bool:
        if not self.db:
            return False
        async with self.db.execute(
            "SELECT 1 FROM blacklist WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row is not None

    async def get_dm_enabled(self, guild_id: int) -> bool:
        if not self.db:
            return True
        async with self.db.execute(
            "SELECT enabled FROM ticket_dm_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return True
        try:
            return bool(int(row[0]))
        except Exception:
            return True

    async def handle_ticket_panel_interaction(
        self,
        interaction: discord.Interaction,
        panel_config: PanelConfig,
    ) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("Tickets can only be used in a guild.", ephemeral=True)
            return
        guild = interaction.guild
        user = interaction.user
        if await self.is_blacklisted(guild.id, user.id):
            await interaction.response.send_message(
                "You are blacklisted from creating tickets in this server.",
                ephemeral=True,
            )
            return
        cooldown_key = (guild.id, user.id)
        now = time.monotonic()
        last_time = self.ticket_creation_cooldowns.get(cooldown_key, 0.0)
        if now - last_time < 15.0:
            remaining = int(15.0 - (now - last_time))
            await interaction.response.send_message(
                f"You are on cooldown. Please wait {remaining} more seconds before creating another ticket.",
                ephemeral=True,
            )
            return
        self.ticket_creation_cooldowns[cooldown_key] = now
        if not panel_config.category_id:
            await interaction.response.send_message(
                "Ticket panel is misconfigured: no category has been set.",
                ephemeral=True,
            )
            return
        category = guild.get_channel(panel_config.category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "Ticket category no longer exists. Please notify staff.",
                ephemeral=True,
            )
            return
        if not self.db:
            await interaction.response.send_message(
                "Ticket database is not ready. Please try again later.",
                ephemeral=True,
            )
            return
        ticket_id = await self.generate_ticket_id(guild.id)
        if not ticket_id:
            await interaction.response.send_message(
                "Failed to generate a ticket ID. Please try again later.",
                ephemeral=True,
            )
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False,
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            ),
        }
        staff_role = guild.get_role(panel_config.staff_role) if panel_config.staff_role else None
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            )
        try:
            channel_name = ticket_id.replace("ticket-", "ticket-")
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket created by {user} ({user.id})",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to create ticket channels.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "Failed to create the ticket channel due to a Discord error.",
                ephemeral=True,
            )
            return
        await self.db.execute(
            "INSERT INTO guild_tickets (guild_id, channel_id, ticket_id, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                guild.id,
                channel.id,
                ticket_id,
                user.id,
                datetime.datetime.utcnow().isoformat(),
            ),
        )
        await self.db.commit()
        used_label = None
        try:
            data = getattr(interaction, "data", {}) or {}
            custom_id = data.get("custom_id")
            values = data.get("values") or []
            if custom_id and custom_id.startswith("ticket_panel_button"):
                used_label = "General Support"
            elif values:
                selected_value = str(values[0])
                try:
                    dropdown_data = json.loads(panel_config.dropdown_json or "[]")
                except Exception:
                    dropdown_data = []
                for item in dropdown_data:
                    if str(item.get("value")) == selected_value:
                        used_label = str(item.get("label") or selected_value)
                        break
                used_label = used_label or selected_value
        except Exception:
            used_label = None

        desc = f"Welcome {user.mention}, thank you for contacting support."
        if used_label:
            desc += f"\n> **Category**: {used_label}"
        desc += "\n\nA staff member will be with you shortly. Please provide as much detail as possible."

        embed = discord.Embed(
            title=f"Support Ticket • {ticket_id}",
            description=desc,
            color=panel_config.embed_color or EMBED_COLOR,
            timestamp=datetime.datetime.utcnow(),
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text=f"Requested by {user.display_name}", icon_url=user.display_avatar.url if user.display_avatar else icon_url)
        view = TicketControlsView(self, guild.id, channel.id, user.id)
        ping_content = ""
        ping_role = guild.get_role(panel_config.ping_role) if panel_config.ping_role else None
        if ping_role:
            ping_content = ping_role.mention
        try:
            await channel.send(content=ping_content or None, embed=embed, view=view)
        except discord.HTTPException:
            pass
        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True,
        )

    async def generate_ticket_id(self, guild_id: int) -> Optional[str]:
        if not self.db:
            return None
        async with self.db.execute(
            "SELECT ticket_id FROM guild_tickets WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        max_number = 0
        for (ticket_id,) in rows:
            if isinstance(ticket_id, str) and ticket_id.startswith("ticket-"):
                suffix = ticket_id.split("ticket-")[-1]
                try:
                    num = int(suffix)
                    if num > max_number:
                        max_number = num
                except ValueError:
                    continue
        next_number = max_number + 1
        return f"ticket-{next_number:03d}"

    async def get_ticket_record(self, guild_id: int, channel_id: int) -> Optional[Tuple[Any, ...]]:
        if not self.db:
            return None
        async with self.db.execute(
            "SELECT guild_id, channel_id, ticket_id, user_id, created_at FROM guild_tickets WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row

    async def handle_close_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        via_button: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        if not interaction.guild:
            if not interaction.response.is_done():
                await interaction.response.send_message("This can only be used in a guild.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket channel no longer exists.", ephemeral=True)
            return
        ticket_record = await self.get_ticket_record(interaction.guild.id, channel.id)
        if not ticket_record:
            if not interaction.response.is_done():
                await interaction.response.send_message("This channel is not registered as a ticket.", ephemeral=True)
            return
        ticket_owner_id = int(ticket_record[3])
        ticket_owner = interaction.guild.get_member(ticket_owner_id)
        staff_role = None
        if self.db:
            async with self.db.execute(
                """
                SELECT staff_role FROM guild_panels
                WHERE guild_id = ?
                """,
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    staff_role = interaction.guild.get_role(int(row[0]))
        is_staff = False
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
            if member.guild_permissions.manage_channels:
                is_staff = True
            elif staff_role and staff_role in member.roles:
                is_staff = True
            elif member.id == ticket_owner_id:
                is_staff = True
        if not is_staff:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to close this ticket.",
                    ephemeral=True,
                )
            return
        if ticket_owner:
            try:
                await channel.set_permissions(
                    ticket_owner,
                    overwrite=discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        read_message_history=False,
                    ),
                )
            except discord.HTTPException:
                pass
        embed = discord.Embed(
            title="Ticket Closed",
            description="This ticket has been closed by staff.",
            color=EMBED_COLOR,
        )
        if reason:
            embed.add_field(name="Reason", value=str(reason)[:256], inline=False)
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Use the buttons below to reopen, delete, or export a transcript.", icon_url=icon_url)
        view = TicketClosedView(self, interaction.guild.id, channel.id, ticket_owner_id)
        try:
            await channel.send(embed=embed, view=view)
        except discord.HTTPException:
            pass
        if await self.get_dm_enabled(interaction.guild.id):
            try:
                user = interaction.guild.get_member(ticket_owner_id)
                if user:
                    dm_embed = discord.Embed(
                        title="Your Ticket Has Been Closed",
                        color=EMBED_COLOR,
                    )
                    if reason:
                        dm_embed.add_field(name="Reason", value=str(reason)[:256], inline=False)
                    dm_embed.add_field(name="Closed By", value=str(interaction.user), inline=True)
                    jump_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}"
                    icon_url_dm = None
                    if self.bot.user:
                        try:
                            icon_url_dm = self.bot.user.display_avatar.url
                        except Exception:
                            icon_url_dm = None
                    dm_embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url_dm)
                    view_jump = discord.ui.View()
                    view_jump.add_item(discord.ui.Button(label="Jump to Ticket", style=discord.ButtonStyle.link, url=jump_url))
                    try:
                        await user.send(embed=dm_embed, view=view_jump)
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            ticket_id = str(ticket_record[2])
            if ticket_id.startswith("ticket-"):
                suffix = ticket_id.split("ticket-")[-1]
                target_name = f"closed-{suffix}"
                if channel.name != target_name:
                    await channel.edit(name=target_name, reason=f"Ticket closed by {interaction.user}")
        except discord.HTTPException:
            pass
        if via_button:
            if not interaction.response.is_done():
                await interaction.response.defer()
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket closed.", ephemeral=True)

    async def handle_reopen_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        ticket_owner_id: int,
    ) -> None:
        if not interaction.guild:
            if not interaction.response.is_done():
                await interaction.response.send_message("This can only be used in a guild.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket channel no longer exists.", ephemeral=True)
            return
        ticket_owner = interaction.guild.get_member(ticket_owner_id)
        if not ticket_owner:
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket owner is no longer in the server.", ephemeral=True)
            return
        staff_role = None
        if self.db:
            async with self.db.execute(
                """
                SELECT staff_role FROM guild_panels
                WHERE guild_id = ?
                """,
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    staff_role = interaction.guild.get_role(int(row[0]))
        is_staff = False
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
            if member.guild_permissions.manage_channels:
                is_staff = True
            elif staff_role and staff_role in member.roles:
                is_staff = True
        if not is_staff:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to reopen this ticket.",
                    ephemeral=True,
                )
            return
        try:
            record = await self.get_ticket_record(interaction.guild.id, channel.id)
            if record:
                ticket_id = str(record[2])
                if ticket_id.startswith("ticket-"):
                    suffix = ticket_id.split("ticket-")[-1]
                    target_name = f"ticket-{suffix}"
                    if channel.name != target_name:
                        await channel.edit(name=target_name, reason=f"Ticket reopened by {interaction.user}")
        except discord.HTTPException:
            pass
        try:
            await channel.set_permissions(
                ticket_owner,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
            )
        except discord.HTTPException:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Failed to modify channel permissions.",
                    ephemeral=True,
                )
            return
        embed = discord.Embed(
            title="Ticket Reopened",
            description=f"{ticket_owner.mention} has been granted access again.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass
        if await self.get_dm_enabled(interaction.guild.id):
            try:
                user = interaction.guild.get_member(ticket_owner_id)
                if user:
                    dm_embed = discord.Embed(
                        title="Your Ticket Has Been Reopened",
                        color=EMBED_COLOR,
                    )
                    dm_embed.add_field(name="Reopened By", value=str(interaction.user), inline=True)
                    jump_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}"
                    icon_url_dm = None
                    if self.bot.user:
                        try:
                            icon_url_dm = self.bot.user.display_avatar.url
                        except Exception:
                            icon_url_dm = None
                    dm_embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url_dm)
                    view_jump = discord.ui.View()
                    view_jump.add_item(discord.ui.Button(label="Jump to Ticket", style=discord.ButtonStyle.link, url=jump_url))
                    try:
                        await user.send(embed=dm_embed, view=view_jump)
                    except Exception:
                        pass
            except Exception:
                pass
        if not interaction.response.is_done():
            await interaction.response.send_message("Ticket reopened.", ephemeral=True)

    async def handle_remove_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        via_button: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        if not interaction.guild:
            if not interaction.response.is_done():
                await interaction.response.send_message("This can only be used in a guild.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket channel no longer exists.", ephemeral=True)
            return
        ticket_record = await self.get_ticket_record(interaction.guild.id, channel.id)
        if not ticket_record:
            if not interaction.response.is_done():
                await interaction.response.send_message("This channel is not registered as a ticket.", ephemeral=True)
            return
        staff_role = None
        if self.db:
            async with self.db.execute(
                """
                SELECT staff_role FROM guild_panels
                WHERE guild_id = ?
                """,
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    staff_role = interaction.guild.get_role(int(row[0]))
        is_staff = False
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
            if member.guild_permissions.manage_channels:
                is_staff = True
            elif staff_role and staff_role in member.roles:
                is_staff = True
        if not is_staff:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to delete this ticket.",
                    ephemeral=True,
                )
            return
        if self.db:
            await self.db.execute(
                "DELETE FROM guild_tickets WHERE guild_id = ? AND channel_id = ?",
                (interaction.guild.id, channel.id),
            )
            await self.db.commit()
        if await self.get_dm_enabled(interaction.guild.id):
            try:
                ticket_owner_id = int(ticket_record[3])
                user = interaction.guild.get_member(ticket_owner_id)
                if user:
                    dm_embed = discord.Embed(
                        title="Your Ticket Has Been Removed",
                        color=EMBED_COLOR,
                    )
                    if reason:
                        dm_embed.add_field(name="Reason", value=str(reason)[:256], inline=False)
                    dm_embed.add_field(name="Removed By", value=str(interaction.user), inline=True)
                    icon_url_dm = None
                    if self.bot.user:
                        try:
                            icon_url_dm = self.bot.user.display_avatar.url
                        except Exception:
                            icon_url_dm = None
                    dm_embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url_dm)
                    try:
                        await user.send(embed=dm_embed)
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            embed = discord.Embed(
                title="Ticket Removed",
                description="This ticket has been removed by staff.",
                color=EMBED_COLOR,
            )
            if reason:
                embed.add_field(name="Reason", value=str(reason)[:256], inline=False)
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass
        try:
            await channel.delete(reason=f"Ticket removed by {interaction.user}")
        except discord.HTTPException:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Failed to delete the ticket channel.",
                    ephemeral=True,
                )
            return
        if not interaction.response.is_done():
            await interaction.response.send_message("Ticket channel deleted.", ephemeral=True)

    async def handle_transcript(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        via_button: bool = False,
    ) -> None:
        if not interaction.guild:
            if not interaction.response.is_done():
                await interaction.response.send_message("This can only be used in a guild.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            if not interaction.response.is_done():
                await interaction.response.send_message("Ticket channel no longer exists.", ephemeral=True)
            return
        ticket_record = await self.get_ticket_record(interaction.guild.id, channel.id)
        if not ticket_record:
            if not interaction.response.is_done():
                await interaction.response.send_message("This channel is not registered as a ticket.", ephemeral=True)
            return
        staff_role = None
        if self.db:
            async with self.db.execute(
                """
                SELECT staff_role FROM guild_panels
                WHERE guild_id = ?
                """,
                (interaction.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    staff_role = interaction.guild.get_role(int(row[0]))
        permitted = False
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
            if member.guild_permissions.manage_channels:
                permitted = True
            elif staff_role and staff_role in member.roles:
                permitted = True
        if not permitted:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to generate a transcript for this ticket.",
                    ephemeral=True,
                )
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        buffer = io.StringIO()
        header = f"Transcript for #{channel.name} (ID: {channel.id}) in guild {interaction.guild.name} (ID: {interaction.guild.id})\n"
        buffer.write(header)
        buffer.write(f"Generated at: {datetime.datetime.utcnow().isoformat()} UTC\n")
        buffer.write("-" * 64 + "\n\n")
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                created = message.created_at.isoformat()
                author = f"{message.author} ({message.author.id})"
                content = message.content.replace("\n", "\\n")
                buffer.write(f"[{created}] {author}: {content}\n")
                for attachment in message.attachments:
                    buffer.write(f"    Attachment: {attachment.url}\n")
        except discord.HTTPException:
            buffer.write("\n[Error fetching full history]\n")
        buffer.seek(0)
        transcript_file = discord.File(
            fp=io.BytesIO(buffer.getvalue().encode("utf-8")),
            filename=f"transcript-{channel.id}.txt",
        )
        try:
            await channel.send(
                content="Ticket transcript:",
                file=transcript_file,
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send("Transcript generated and uploaded.", ephemeral=True)

    @commands.group(name="ticket", invoke_without_command=True)
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def ticket_group(self, ctx: commands.Context) -> None:
        """Base command group for ticket management."""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

    @ticket_group.command(name="setup")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 30.0, commands.BucketType.user)
    async def ticket_setup(self, ctx: commands.Context, panel: str) -> None:
        """Start the interactive setup wizard for a ticket panel."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        await self.enforce_guild_limits(ctx.guild.id)
        allowed = await self.get_allowed_panel_limit(ctx.guild.id)
        async with self.db.execute(
            "SELECT COUNT(*) FROM guild_panels WHERE guild_id = ?",
            (ctx.guild.id,),
        ) as cursor:
            count_row = await cursor.fetchone()
        total_panels = int(count_row[0]) if count_row else 0
        if total_panels >= allowed:
            embed = discord.Embed(
                title="Panel Limit Reached",
                description=f"This guild can have up to {allowed} ticket panel(s) based on your plan.",
                color=EMBED_COLOR,
            )
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await ctx.reply(embed=embed)
            return
        wizard = TicketSetupWizard(self, ctx.author, panel_name=panel, existing_config=None)
        embed = wizard.build_page1("Use the modals to configure embed settings, then Next.")
        view = Page1View(wizard)
        message = await ctx.reply(embed=embed, view=view)
        wizard.message = message

    @ticket_group.command(name="edit")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 30.0, commands.BucketType.user)
    async def ticket_edit(self, ctx: commands.Context, panel: str) -> None:
        """Edit an existing ticket panel using the setup wizard."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        config = await self.get_panel_config(ctx.guild.id, panel)
        if not config:
            await ctx.reply(f"No ticket panel named `{panel}` exists.")
            return
        wizard = TicketSetupWizard(self, ctx.author, panel_name=panel, existing_config=config)
        embed = wizard.build_page1("Editing existing panel. Configure embed settings, then Next.")
        view = Page1View(wizard)
        message = await ctx.reply(embed=embed, view=view)
        wizard.message = message

    @ticket_group.command(name="delete")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def ticket_delete(self, ctx: commands.Context, panel: str) -> None:
        """Delete an existing ticket panel configuration."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        await self.db.execute(
            "DELETE FROM guild_panels WHERE guild_id = ? AND panel_name = ?",
            (ctx.guild.id, panel),
        )
        await self.db.commit()
        embed = discord.Embed(
            title="Panel Deleted",
            description=f"Ticket panel `{panel}` has been deleted.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_group.command(name="sendpanel")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def ticket_sendpanel(self, ctx: commands.Context, panel: str) -> None:
        """Send a configured ticket panel to the current channel."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        await self.enforce_guild_limits(ctx.guild.id)
        allowed = await self.get_allowed_panel_limit(ctx.guild.id)
        async with self.db.execute(
            "SELECT COUNT(*) FROM panel_messages WHERE guild_id = ?",
            (ctx.guild.id,),
        ) as cursor:
            count_row = await cursor.fetchone()
        active_count = int(count_row[0]) if count_row else 0
        if active_count >= allowed:
            embed = discord.Embed(
                title="Active Panel Exists",
                description=f"This guild can have up to {allowed} active panel message(s). Remove one to send another.",
                color=EMBED_COLOR,
            )
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await ctx.reply(embed=embed)
            return
        config = await self.get_panel_config(ctx.guild.id, panel)
        if not config:
            await ctx.reply(f"No ticket panel named `{panel}` exists.")
            return
        embed = self.build_panel_embed(config)
        view = self.build_panel_view(config)
        try:
            message = await ctx.send(embed=embed, view=view)
        except discord.HTTPException:
            await ctx.reply("Failed to send the ticket panel message.")
            return
        await self.db.execute(
            "INSERT INTO panel_messages (guild_id, channel_id, message_id, panel_name) VALUES (?, ?, ?, ?)",
            (ctx.guild.id, ctx.channel.id, message.id, panel),
        )
        await self.db.commit()
        self.bot.add_view(view, message_id=message.id)
        confirmation = discord.Embed(
            title="Panel Sent",
            description=f"Ticket panel `{panel}` has been sent.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        confirmation.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=confirmation)
    @ticket_group.command(name="paneldelete")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def ticket_paneldelete(self, ctx: commands.Context, channel: discord.TextChannel, message_id: Optional[int] = None) -> None:
        """Delete the ticket panel message in the specified channel and remove its record."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        panel_row = None
        if message_id is None:
            async with self.db.execute(
                "SELECT message_id, panel_name FROM panel_messages WHERE guild_id = ? AND channel_id = ? ORDER BY message_id DESC",
                (ctx.guild.id, channel.id),
            ) as cursor:
                panel_row = await cursor.fetchone()
            if panel_row:
                message_id = int(panel_row[0])
        if message_id is None:
            embed = discord.Embed(
                title="No Panel Found",
                description="No ticket panel record found for this channel.",
                color=EMBED_COLOR,
            )
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await ctx.reply(embed=embed)
            return
        msg = None
        try:
            msg = await channel.fetch_message(message_id)
        except discord.HTTPException:
            msg = None
        if msg:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass
        await self.db.execute(
            "DELETE FROM panel_messages WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
            (ctx.guild.id, channel.id, message_id),
        )
        await self.db.commit()
        embed = discord.Embed(
            title="Panel Deleted",
            description=f"Ticket panel message {message_id} has been deleted from {channel.mention}.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)


    @ticket_group.command(name="list")
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def ticket_panel_list(self, ctx: commands.Context) -> None:
        """List all ticket panels with send locations."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        async with self.db.execute(
            "SELECT panel_name, style FROM guild_panels WHERE guild_id = ? ORDER BY panel_name",
            (ctx.guild.id,),
        ) as cursor:
            panels = await cursor.fetchall()
        if not panels:
            embed = discord.Embed(
                title="Ticket Panels",
                description="No ticket panels found.",
                color=EMBED_COLOR,
            )
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await ctx.reply(embed=embed)
            return
        per_page = 10
        pages = [panels[i : i + per_page] for i in range(0, len(panels), per_page)]
        for idx, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Ticket Panels (Page {idx}/{len(pages)})",
                color=EMBED_COLOR,
            )
            lines = []
            for panel_name, style in page:
                async with self.db.execute(
                    "SELECT channel_id, message_id FROM panel_messages WHERE guild_id = ? AND panel_name = ?",
                    (ctx.guild.id, panel_name),
                ) as msg_cursor:
                    sent_rows = await msg_cursor.fetchall()
                if sent_rows:
                    locations = ", ".join(
                        f"<#{ch_id}> (msg {msg_id})" for (ch_id, msg_id) in sent_rows
                    )
                else:
                    locations = "Not sent"
                lines.append(f"• {panel_name} — Type: {str(style).title()} — {locations}")
            embed.description = "\n".join(lines)
            icon_url = None
            if self.bot.user:
                try:
                    icon_url = self.bot.user.display_avatar.url
                except Exception:
                    icon_url = None
            embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
            await ctx.reply(embed=embed)

    @ticket_group.command(name="close")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ticket_close(self, ctx: commands.Context, *, reason: Optional[str] = None) -> None:
        """Close the current ticket channel."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        interaction = await self._fake_interaction_from_ctx(ctx)
        await self.handle_close_ticket(interaction, ctx.channel.id, via_button=False, reason=reason)

    @ticket_group.command(name="remove")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ticket_remove(self, ctx: commands.Context, *, reason: Optional[str] = None) -> None:
        """Delete the current ticket channel."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        interaction = await self._fake_interaction_from_ctx(ctx)
        await self.handle_remove_ticket(interaction, ctx.channel.id, via_button=False, reason=reason)

    @ticket_group.command(name="transcript")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ticket_transcript(self, ctx: commands.Context) -> None:
        """Generate and upload a transcript for the current ticket."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        interaction = await self._fake_interaction_from_ctx(ctx)
        await self.handle_transcript(interaction, ctx.channel.id, via_button=False)

    @ticket_group.command(name="reopen")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ticket_reopen(self, ctx: commands.Context) -> None:
        """Reopen the current ticket channel (closed tickets only)."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        record = await self.get_ticket_record(ctx.guild.id, ctx.channel.id)
        if not record:
            await ctx.reply("This channel is not registered as a ticket.")
            return
        if not ctx.channel.name.startswith("closed-"):
            await ctx.reply("This ticket is not closed.")
            return
        ticket_owner_id = int(record[3])
        interaction = await self._fake_interaction_from_ctx(ctx)
        await self.handle_reopen_ticket(interaction, ctx.channel.id, ticket_owner_id)

    @ticket_group.command(name="rename")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ticket_rename(self, ctx: commands.Context, *, name: str) -> None:
        """Rename the current ticket channel (usable in ticket channels only)."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        record = await self.get_ticket_record(ctx.guild.id, ctx.channel.id)
        if not record:
            await ctx.reply("This channel is not registered as a ticket.")
            return
        new_name = name.strip()[:100]
        try:
            await ctx.channel.edit(name=new_name, reason=f"Ticket renamed by {ctx.author}")
        except discord.HTTPException:
            await ctx.reply("Failed to rename the channel.")
            return
        embed = discord.Embed(
            title="Ticket Renamed",
            description=f"Channel renamed to {new_name}.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_group.command(name="adduser")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ticket_adduser(self, ctx: commands.Context, user: discord.Member) -> None:
        """Add a user to the current ticket channel."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        interaction = await self._fake_interaction_from_ctx(ctx)
        record = await self.get_ticket_record(ctx.guild.id, ctx.channel.id)
        if not record:
            await ctx.reply("This channel is not registered as a ticket.")
            return
        try:
            await ctx.channel.set_permissions(
                user,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
            )
        except discord.HTTPException:
            await ctx.reply("Failed to modify channel permissions.")
            return
        embed = discord.Embed(
            title="User Added",
            description=f"{user.mention} has been added to this ticket.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_group.command(name="removeuser")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ticket_removeuser(self, ctx: commands.Context, user: discord.Member) -> None:
        """Remove a user's access from the current ticket channel."""
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("This command can only be used inside a ticket channel.")
            return
        record = await self.get_ticket_record(ctx.guild.id, ctx.channel.id)
        if not record:
            await ctx.reply("This channel is not registered as a ticket.")
            return
        try:
            await ctx.channel.set_permissions(user, overwrite=None)
        except discord.HTTPException:
            await ctx.reply("Failed to modify channel permissions.")
            return
        embed = discord.Embed(
            title="User Removed",
            description=f"{user.mention} has been removed from this ticket.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)


    @ticket_group.group(name="dm", invoke_without_command=True)
    @ignore_check()
    @blacklist_check()
    async def ticket_dm_group(self, ctx: commands.Context) -> None:
        """Manage ticket DM notifications."""
        enabled = True
        if ctx.guild and self.db:
            enabled = await self.get_dm_enabled(ctx.guild.id)
        status = "Enabled" if enabled else "Disabled"
        embed = discord.Embed(
            title="Ticket DMs",
            description=f"DM notifications are currently: {status}",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_dm_group.command(name="enable")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def ticket_dm_enable(self, ctx: commands.Context) -> None:
        """Enable DM notifications for ticket events."""
        if not ctx.guild or not self.db:
            await ctx.reply("This command can only be used in a guild.")
            return
        await self.db.execute(
            "INSERT INTO ticket_dm_settings (guild_id, enabled) VALUES (?, 1) ON CONFLICT(guild_id) DO UPDATE SET enabled=1",
            (ctx.guild.id,),
        )
        await self.db.commit()
        embed = discord.Embed(title="DM Notifications", description="Enabled", color=EMBED_COLOR)
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_dm_group.command(name="disable")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def ticket_dm_disable(self, ctx: commands.Context) -> None:
        """Disable DM notifications for ticket events."""
        if not ctx.guild or not self.db:
            await ctx.reply("This command can only be used in a guild.")
            return
        await self.db.execute(
            "INSERT INTO ticket_dm_settings (guild_id, enabled) VALUES (?, 0) ON CONFLICT(guild_id) DO UPDATE SET enabled=0",
            (ctx.guild.id,),
        )
        await self.db.commit()
        embed = discord.Embed(title="DM Notifications", description="Disabled", color=EMBED_COLOR)
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)




    @ticket_group.group(name="blacklist", invoke_without_command=True)
    @ignore_check()
    @blacklist_check()
    async def ticket_blacklist_group(self, ctx: commands.Context) -> None:
        """Manage ticket blacklists for this guild."""
        embed = discord.Embed(
            title="Ticket Blacklist",
            description="Use subcommands: add, remove, list.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_blacklist_group.command(name="add")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def ticket_blacklist(self, ctx: commands.Context, user: discord.Member) -> None:
        """Blacklist a user from creating tickets."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        await self.db.execute(
            "INSERT INTO blacklist (guild_id, user_id) VALUES (?, ?)",
            (ctx.guild.id, user.id),
        )
        await self.db.commit()
        embed = discord.Embed(
            title="User Blacklisted",
            description=f"{user.mention} has been blacklisted from creating tickets.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_blacklist_group.command(name="remove")
    @ignore_check()
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def ticket_unblacklist(self, ctx: commands.Context, user: discord.Member) -> None:
        """Remove a user from the ticket blacklist."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        await self.db.execute(
            "DELETE FROM blacklist WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, user.id),
        )
        await self.db.commit()
        embed = discord.Embed(
            title="User Unblacklisted",
            description=f"{user.mention} has been removed from the blacklist.",
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    @ticket_blacklist_group.command(name="list")
    @ignore_check()
    @blacklist_check()
    async def ticket_blacklisted(self, ctx: commands.Context) -> None:
        """List all users blacklisted from creating tickets."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a guild.")
            return
        if not self.db:
            await ctx.reply("Database is not ready. Please try again later.")
            return
        async with self.db.execute(
            "SELECT user_id FROM blacklist WHERE guild_id = ?",
            (ctx.guild.id,),
        ) as cursor:
            rows = await cursor.fetchall()
        if not rows:
            description = "No users are currently blacklisted."
        else:
            mentions = [f"<@{user_id}>" for (user_id,) in rows]
            description = "\n".join(mentions)
        embed = discord.Embed(
            title="Blacklisted Users",
            description=description,
            color=EMBED_COLOR,
        )
        icon_url = None
        if self.bot.user:
            try:
                icon_url = self.bot.user.display_avatar.url
            except Exception:
                icon_url = None
        embed.set_footer(text="Synapse - Ticketing", icon_url=icon_url)
        await ctx.reply(embed=embed)

    async def _fake_interaction_from_ctx(self, ctx: commands.Context) -> discord.Interaction:
        class FakeResponse:
            def __init__(self, ctx: commands.Context):
                self._ctx = ctx
                self._done = False

            @property
            def is_done(self) -> bool:
                return self._done

            async def send_message(self, content: Optional[str] = None, *, ephemeral: bool = False, **kwargs: Any) -> None:
                self._done = True
                if ephemeral:
                    await self._ctx.reply(content or "", **kwargs)
                else:
                    await self._ctx.reply(content or "", **kwargs)

            async def defer(self, *, ephemeral: bool = False, **kwargs: Any) -> None:
                self._done = True

            async def edit_message(self, **kwargs: Any) -> None:
                self._done = True
                try:
                    await self._ctx.message.edit(**kwargs)
                except discord.HTTPException:
                    pass

        class FakeFollowup:
            def __init__(self, ctx: commands.Context):
                self._ctx = ctx

            async def send(self, content: Optional[str] = None, *, ephemeral: bool = False, **kwargs: Any) -> None:
                await self._ctx.reply(content or "", **kwargs)

        class FakeInteraction:
            def __init__(self, ctx: commands.Context):
                self.user = ctx.author
                self.guild = ctx.guild
                self.channel = ctx.channel
                self.response = FakeResponse(ctx)
                self.followup = FakeFollowup(ctx)

        return FakeInteraction(ctx)


async def setup(bot: commands.Bot) -> None:
    """Load the TicketCog into the provided bot."""
    await bot.add_cog(TicketCog(bot))
