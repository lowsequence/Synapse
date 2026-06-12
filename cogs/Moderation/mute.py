import discord
from discord.ext import commands
from discord import ui
from datetime import timedelta
import re
from utils.Tools import *

class TimeoutView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\nPlease use the bot command first then you can access this button"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Trash:1462771196885074002>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class AlreadyTimedoutView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\nPlease use the bot command first then you can access this button"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Trash:1462771196885074002>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Unmute Reason")
        self.user = user
        self.author = author
        self.view = view
        self.reason_input = ui.TextInput(label="Reason for Unmuting", placeholder="Provide a reason to unmute or leave it blank.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "Not Provided"
        try:
            await self.user.send(f"You have been Unmuted in **{self.author.guild.name}** by **{self.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        embed = discord.Embed(description=f"<:IMPORT_thumsup:1462777656570413119> | Sucessfully unmuted {self.user.mention}", color=0x2b2d31)

        await self.user.edit(timed_out_until=None, reason=f"Unmute requested by {self.author}")
        await interaction.response.edit_message(embed=embed, view=self.view)
        for item in self.view.children:
            item.disabled = True
        await interaction.message.edit(view=self.view)

class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    def parse_time(self, time_str):
        time_pattern = r"(\d+)([mhd])"
        match = re.match(time_pattern, time_str)
        if match:
            time_value = int(match.group(1))
            time_unit = match.group(2)
            if time_unit == 'm' and 0 < time_value <= 60:
                return timedelta(minutes=time_value), f"{time_value} minutes"
            elif time_unit == 'h' and 0 < time_value <= 24:
                return timedelta(hours=time_value), f"{time_value} hours"
            elif time_unit == 'd' and 0 < time_value <= 28:
                return timedelta(days=time_value), f"{time_value} days"
        return None, None

    @commands.hybrid_command(
        name="mute",
        help="Mutes a user with optional time and reason",
        usage="<member> [time] [reason]",
        aliases=["timeout", "stfu"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, time: str = None, *, reason=None):

        if user.is_timed_out():
            embed = discord.Embed(description="**Requested User is already muted in this server.**", color=self.color)
            embed.add_field(name="__Unmute__:", value="Click on the `Unmute` button to remove the timeout from the user.")
            embed.set_author(name=f"{user.name} is Already Timed Out!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = AlreadyTimedoutView(user=user, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        if user == ctx.guild.owner:
            error = discord.Embed(color=self.color, description=" You can't timeout the Server Owner!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if ctx.author != ctx.guild.owner and user.top_role >= ctx.author.top_role:
            error = discord.Embed(color=self.color, description=" You can't timeout users having higher or equal role than yours!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if user.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(color=self.color, description=" I can't timeout users having higher or equal role than mine.")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        time_delta, duration_text = self.parse_time(time) if time else (timedelta(hours=24), "24 hours")

        if not time_delta:
            error = discord.Embed(color=self.color, description="Invalid time format! Use `<number><m/h/d>` where `m` is minutes (max 60), `h` is hours (max 24), and `d` is days (max 28).")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        try:
            await user.send(f" You have been muted in **{ctx.guild.name}** by **{ctx.author}** for {duration_text}. Reason: {reason or 'None'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        await user.edit(timed_out_until=discord.utils.utcnow() + time_delta, reason=f"Muted by {ctx.author} for {duration_text}. Reason: {reason or 'None'}")


        reasonn = reason or "None"
        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Member Muted",
            description=(
                f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n"
                f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                f"<:ArrowMiddle:1479489625654562896> **Duration:** {duration_text}\n"
                f"<:ArrowBottom:1479489659255132464> **Reason:** {reasonn}"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.get_user_avatar(user))

        message = await ctx.send(embed=embed)

    @mute.error
    async def mute_error(self, ctx, error):

        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(title="<:emoji_1769867589372:1467155751456735326> Operation Failed", description="I don't have permission to mute members.", color=self.color)
            await ctx.send(embed=embed)
        elif isinstance(error, discord.Forbidden):
            embed = discord.Embed(title="<:emoji_1769867589372:1467155751456735326> Missing Permissions", description="I can't mute this user as they might have higher privileges (e.g., Admin).", color=self.color)
            await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Mute(client))