import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from datetime import timedelta

class MuteUnmuteView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f"**{interaction.user.name}**, you cannot access this button.\nPlease use the bot command first then you can access this button"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Add Timeout", style=discord.ButtonStyle.danger)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MuteReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)


        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:MekoTrash:1449445909585723454>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class MuteReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Mute Information")
        self.user = user
        self.author = author
        self.view = view
        self.time_input = ui.TextInput(label="Duration (m/h/d)", placeholder="Leave blank for default 24h", required=False, max_length=5)
        self.reason_input = ui.TextInput(label="Reason", placeholder="Provide a reason or leave it blank.", required=False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.time_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        time_str = self.time_input.value or "24h"
        time_seconds = self.parse_duration(time_str)

        if time_seconds is None:
            await interaction.response.send_message(f"Invalid time format! Please provide in m (minutes), h (hours), or d (days).", ephemeral=True)
            return

        try:
            await self.user.edit(timed_out_until=discord.utils.utcnow() + timedelta(seconds=time_seconds))
        except discord.Forbidden:
            await interaction.response.send_message(f"Failed to mute {self.user.mention}. I lack the permissions.", ephemeral=True)
            return


        try:
            await self.user.send(f"You have been muted in **{interaction.guild.name}** for {time_str}. Reason: {reason}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        success_embed = discord.Embed(
            description=f"**<:IMPORT_thumsup:1462777656570413119> | Sucessfully Muted {self.user.mention}", 
            color=0x2b2d31
        )

        await interaction.response.edit_message(embed=success_embed, view=self.view)


        for item in self.view.children:
            if item.label != "Delete":
                item.disabled = True
        await self.view.message.edit(view=self.view)

    def parse_duration(self, duration_str: str) -> int:
        try:
            if duration_str.endswith("m"):
                duration = int(duration_str[:-1])
                return duration * 60
            elif duration_str.endswith("h"):
                duration = int(duration_str[:-1])
                return duration * 3600
            elif duration_str.endswith("d"):
                duration = int(duration_str[:-1])
                return duration * 86400
            else:

                duration = int(duration_str)
                if duration > 60:
                    return (duration // 60) * 3600  
                else:
                    return duration * 60  
        except ValueError:
            return None


class Unmute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="unmute",
        help="Unmutes a user from the Server",
        usage="<member>",
        aliases=["untimeout"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, user: discord.Member):
        if not user.timed_out_until or user.timed_out_until <= discord.utils.utcnow():
            embed = discord.Embed(description="**Requested User is not muted in this server.**", color=self.color)
            embed.add_field(name="__Mute__:", value="Click on the `Add Timeout` button to mute the mentioned user.")
            embed.set_author(name=f"{user.name} is Not Muted!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = MuteUnmuteView(user=user, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        try:
            await user.edit(timed_out_until=None)


            try:
                await user.send(f"<:emoji_1769867605256:1467155817726873650> You have been unmuted in **{ctx.guild.name}**.")
                dm_status = "Yes"
            except discord.Forbidden:
                dm_status = "No"
            except discord.HTTPException:
                dm_status = "No"

        except discord.Forbidden:
            error = discord.Embed(color=self.color, description="I can't unmute a user with higher permissions!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            error.set_author(name="Error Occured")
            return await ctx.send(embed=error)

        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Member Unmuted",
            description=(
                f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n"
                f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                f"<:ArrowBottom:1479489659255132464> **Action:** Timeout Removed"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.get_user_avatar(user))

        message = await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Unmute(client))