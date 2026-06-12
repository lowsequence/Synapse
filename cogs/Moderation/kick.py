import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *

class KickView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=120)
        self.member = member
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:MekoTrash:1449445909585723454>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="kick",
        help="Kicks a member from the server.",
        usage="<member> [reason]",
        aliases=["kickmember"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick_command(self, ctx, member: discord.Member, *, reason: str = None):
        reason = reason or "No reason provided"

        if member == ctx.author:
            return await ctx.reply("You cannot kick yourself.")

        if member == ctx.bot.user:
            return await ctx.reply("You cannot kick me.")

        if not ctx.author == ctx.guild.owner:
            if member == ctx.guild.owner:
                return await ctx.reply("I cannot kick the server owner.")

            if ctx.author.top_role <= member.top_role:
                return await ctx.reply("You cannot kick a member with a higher or equal role.")

        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.reply("I cannot kick a member with a higher or equal role.")

        if member not in ctx.guild.members:
            embed = discord.Embed(
                description=f"**Member Not Found:** The specified member does not exist in this server.",
                color=self.color
            )
            view = KickView(member)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return


        dm_status = "Yes"
        try:
            await member.send(f"You have been kicked from **{ctx.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"


        await member.kick(reason=f"Kicked by {ctx.author} | Reason: {reason}")



        embed = discord.Embed(
            title="<:IMPORT_thumsup:1462777656570413119> Member Kicked",
            description=(
                f"<:ArrowTop:1479489599989485742> **User:** {member.mention}\n"
                f"<:ArrowMiddle:1479489625654562896> **Moderator:** {ctx.author.mention}\n"
                f"<:ArrowBottom:1479489659255132464> **Reason:** {reason}"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Kick(client))