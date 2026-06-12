import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *

class BanView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f"**{interaction.user.name}**, you cannot access this button.\n Please use the bot command first then you can access this button"
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

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Trash:1462771196885074002>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class AlreadyBannedView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            embed = discord.Embed()
            embed.description = f"**{interaction.user.name}**, you cannot access this button.\n Please use the bot command first then you can access this button"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Trash:1462771196885074002>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Unban Reason")
        self.user = user
        self.author = author
        self.view = view
        self.reason_input = ui.TextInput(label="Why do you want to unban?", placeholder="Provide a reason to unban or leave it blank for no reason.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            await self.user.send(f"<:emoji_1769867605256:1467155817726873650> You have been Unbanned from **{self.author.guild.name}** by **{self.author}**. Reason: {reason or 'Not Provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        embed = discord.Embed(description=f"<:IMPORT_thumsup:1462777656570413119> Sucessfully banned [{self.user.display_name}](https://discord.com/users/{self.user.id})", color=0x000000)

        try:
            await interaction.guild.unban(self.user, reason=f"Unban requested by {self.author}")

        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        try:
            await interaction.response.edit_message(embed=embed, view=self.view)
            for item in self.view.children:
                item.disabled = True
                await interaction.message.edit(view=self.view)
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass



class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="ban",
        help="Bans a user from the Server",
        usage="<member> [reason]",
        aliases=["fuckban", "hackban"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.User, *, reason=None):

        member = ctx.guild.get_member(user.id)
        if not member:
            embed = discord.Embed(description=f"**{user} is not a member of this server.**", color=self.color)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=embed)

        bans = [entry async for entry in ctx.guild.bans()]
        if any(ban_entry.user.id == user.id for ban_entry in bans):
            embed = discord.Embed(description=f"**Requested User is already banned in this server.**", color=self.color)
            embed.add_field(name="__Unban__:", value="Click on the `Unban` button to unban the mentioned user.")
            embed.set_author(name=f"User is Already Banned!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = AlreadyBannedView(user=user, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message 
            return

        if member == ctx.guild.owner:
            error = discord.Embed(color=self.color, description="I can't ban the Server Owner!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if isinstance(member, discord.Member) and member.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(color=self.color, description="I can't ban a user with a higher or equal role!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if isinstance(member, discord.Member):
            if ctx.author != ctx.guild.owner:
                if member.top_role >= ctx.author.top_role:
                    error = discord.Embed(color=self.color, description="You can't ban a user with a higher or equal role!")
                    error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
                    return await ctx.send(embed=error)

        try:
            await user.send(f" You have been banned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        await ctx.guild.ban(user, reason=f"Ban requested by {ctx.author} for reason: {reason or 'No reason provided'}")

        reasonn = reason or "No reason provided"
        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Member Banned",
            description=(
                f"<:ArrowTop:1479489599989485742> **User:** {user.mention}\n"
                f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                f"<:ArrowBottom:1479489659255132464> **Reason:** {reasonn}"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.get_user_avatar(user))
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Ban(client))