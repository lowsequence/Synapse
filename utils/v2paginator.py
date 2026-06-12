import discord
from discord.ext import commands
from math import ceil


def _sep(visible=True):
    return discord.ui.Separator(visible=visible, spacing=discord.SeparatorSpacing.small)


class V2Paginator(discord.ui.LayoutView):
    """Components V2 LayoutView paginator with First, Previous, Next, Last, and Close buttons."""

    def __init__(self, pages, *, author_id, timeout=120):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self.max_pages = len(pages)
        self.message = None
        self._render()

    def _render(self):
        self.clear_items()

        container = discord.ui.Container(
            *self.pages[self.current_page],
            accent_color=0x2b2d31,
        )
        self.add_item(container)

        if self.max_pages > 1:
            first_btn = discord.ui.Button(
                emoji="<:DoubleLeft:1469267782184206442>",
                style=discord.ButtonStyle.secondary,
                custom_id="v2p_first",
                disabled=(self.current_page == 0),
            )
            first_btn.callback = self._first

            prev_btn = discord.ui.Button(
                emoji="<:LeftArrow:1469267806150463488>",
                style=discord.ButtonStyle.secondary,
                custom_id="v2p_prev",
                disabled=(self.current_page == 0),
            )
            prev_btn.callback = self._prev

            next_btn = discord.ui.Button(
                emoji="<:rightarrow:1469267754409529394>",
                style=discord.ButtonStyle.secondary,
                custom_id="v2p_next",
                disabled=(self.current_page >= self.max_pages - 1),
            )
            next_btn.callback = self._next

            last_btn = discord.ui.Button(
                emoji="<:doubleright:1469267725103927316>",
                style=discord.ButtonStyle.secondary,
                custom_id="v2p_last",
                disabled=(self.current_page >= self.max_pages - 1),
            )
            last_btn.callback = self._last

            close_btn = discord.ui.Button(
                emoji="<:close:1469267685714956290>",
                style=discord.ButtonStyle.danger,
                custom_id="v2p_close",
            )
            close_btn.callback = self._close

            self.add_item(discord.ui.ActionRow(first_btn, prev_btn, close_btn, next_btn, last_btn))

    def _build_view(self):
        """Build a fresh view for the current page (used after navigation)."""
        new = V2Paginator.__new__(V2Paginator)
        discord.ui.LayoutView.__init__(new, timeout=self.timeout)
        new.pages = self.pages
        new.author_id = self.author_id
        new.current_page = self.current_page
        new.max_pages = self.max_pages
        new.message = self.message
        new._render()
        self.stop()
        return new

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Um, Looks like you are not the author of the command...", ephemeral=True
            )
            return False
        return True

    async def _first(self, interaction: discord.Interaction):
        self.current_page = 0
        view = self._build_view()
        await interaction.response.edit_message(view=view)
        view.message = interaction.message

    async def _prev(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        view = self._build_view()
        await interaction.response.edit_message(view=view)
        view.message = interaction.message

    async def _next(self, interaction: discord.Interaction):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        view = self._build_view()
        await interaction.response.edit_message(view=view)
        view.message = interaction.message

    async def _last(self, interaction: discord.Interaction):
        self.current_page = self.max_pages - 1
        view = self._build_view()
        await interaction.response.edit_message(view=view)
        view.message = interaction.message

    async def _close(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
            if hasattr(item, 'children'):
                for child in item.children:
                    if hasattr(child, 'disabled'):
                        child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass
