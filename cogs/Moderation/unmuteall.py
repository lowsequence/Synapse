import discord
from discord.ext import commands
from utils.Tools import *
from discord import ui

class UnmuteAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="unmuteall",
        help="Removes timeout (mute) from everyone in the server!",
        aliases=['masstimeoutremove', 'massunmute'],
        usage="Unmuteall",
        with_app_command=True
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @ignore_check()
    @blacklist_check()
    async def unmuteall(self, ctx):
        user_id = str(ctx.author.id)
        embed = discord.Embed(color=0x2f3135)

        button = discord.ui.Button(
            style=discord.ButtonStyle.green,
            label="Yes",
            emoji="<:emoji_1769867605256:1467155817726873650>"
        )
        button1 = discord.ui.Button(
            style=discord.ButtonStyle.red,
            label="No",
            emoji="<:emoji_1769867589372:1467155751456735326>"
        )

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.moderate_members:
                    await interaction.response.edit_message(
                        content="Removing timeout from all muted users...",
                        embed=None,
                        view=None
                    )

                    a = 0
                    for member in interaction.guild.members:
                        if member.timed_out_until is not None:
                            try:
                                await member.timeout(None, reason=f"Requested by {ctx.author}")
                                a += 1
                            except Exception:
                                pass

                    embed_success = discord.Embed(
                        title="<:IMPORT_thumsup:1462777656570413119> Mass Unmute Complete",
                        description=(
                            f"<:ArrowTop:1479489599989485742> **Moderator:** {ctx.author.mention}\n"
                            f"<:ArrowMiddle:1479489625654562896> **Action:** Unmuted All Users\n"
                            f"<:ArrowBottom:1479489659255132464> **Total Affected:** {a} member(s)"
                        ),
                        color=0x2b2d31
                    )
                    embed_success.set_thumbnail(url=ctx.author.display_avatar.url)
                    await interaction.channel.send(embed=embed_success)
                else:
                    await interaction.response.send_message(
                        "I am missing Moderate Members permission, try giving me permissions and use the command again.",
                        ephemeral=True
                    )

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(
                    content="Okay, I will not unmute anyone.",
                    embed=None,
                    view=None
                )

        embed = discord.Embed(
            color=0x2b2d31,
            description="**Are you sure you want to remove timeout (mute) from everyone in this server?**"
        )

        view = discord.ui.View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)

        await ctx.reply(embed=embed, view=view, mention_author=False)

async def setup(bot):
    await bot.add_cog(UnmuteAll(bot))
