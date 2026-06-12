import discord, json
from discord.ext import commands
from utils.config import serverLink
from core import Synapse, Cog, Context
from utils.Tools import *
from utils.Tools import get_ignore_data




def _sep(visible=True):
    return discord.ui.Separator(visible=visible, spacing=discord.SeparatorSpacing.small)

def _error_view(text: str, *, accent: int = 0x2b2d31) -> discord.ui.LayoutView:
    """Quick one-liner error container."""
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(text),
            accent_color=accent,
        )
    )
    return view

def _error_view_with_header(header: str, body: str, *, icon_url: str | None = None, accent: int = 0x2b2d31) -> discord.ui.LayoutView:
    """Error container with a header section + body."""
    view = discord.ui.LayoutView(timeout=None)
    parts = []
    if icon_url:
        parts.append(
            discord.ui.Section(
                discord.ui.TextDisplay(f"### {header}"),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=icon_url)),
            )
        )
    else:
        parts.append(discord.ui.TextDisplay(f"### {header}"))
    parts.append(_sep())
    parts.append(discord.ui.TextDisplay(body))
    view.add_item(discord.ui.Container(*parts, accent_color=accent))
    return view



class Errors(Cog):
  def __init__(self, client:Synapse):
    self.client = client


  @commands.Cog.listener()
  async def on_command_error(self, ctx: Context, error):
    if ctx.command is None:
      return

    if isinstance(error, commands.MissingRequiredArgument):
      view = _error_view_with_header(
          "Synapse Missing Argument",
          f"Please Use it Like this: \n<:1spacer:1469251392924549294><:rightshort:1469251448909861017> ``{ctx.prefix}{ctx.command.qualified_name.title()} {ctx.command.signature}``",
          icon_url=ctx.bot.user.display_avatar.url,
          accent=0x2b2d31,
      )
      await ctx.send(view=view, delete_after=10)

    if isinstance(error, commands.CommandNotFound):
      return

    if isinstance(error, commands.CheckFailure):
      data = await get_ignore_data(ctx.guild.id)
      ch = data["channel"]
      iuser = data["user"]
      cmd = data["command"]
      buser = data["bypassuser"]

      if str(ctx.author.id) in buser:
        return

      if str(ctx.channel.id) in ch:
            view = _error_view(
                f"<:MekoExclamation:1459854955404984372> Hey, {ctx.author.mention} This **channel** is on the **ignored** list. Please try my commands in another channel.",
            )
            await ctx.reply(view=view, delete_after=8)
            return

      if str(ctx.author.id) in iuser:
        view = _error_view(
            f"<:MekoExclamation:1459854955404984372> You are set as a ignored users for {ctx.guild.name} .\nTry my commands or modules in another guild .",
        )
        await ctx.reply(view=view, delete_after=8)
        return

      if ctx.command.name in cmd or any(alias in cmd for alias in ctx.command.aliases):
            view = _error_view(
                f"<:MekoExclamation:1459854955404984372> This **command** is on the **ignored** list.\nTry my commands or modules in another guild .",
            )
            await ctx.reply(view=view, delete_after=8)
            return


    if isinstance(error, commands.NoPrivateMessage):
      avatar = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
      view = _error_view_with_header(
          str(ctx.author),
          f"You can't use my commands in Dms.",
          icon_url=avatar,
          accent=0xffaeae,
      )
      await ctx.reply(view=view, delete_after=20)
      return  

    if isinstance(error, commands.TooManyArguments):
      await ctx.send_help(ctx.command)
      ctx.command.reset_cooldown(ctx)
      return  


    if isinstance(error, commands.CommandOnCooldown):
      view = _error_view(
          f"> <:timeout:1470401370782695536> Hey calm down!! this command is on cooldown. Please try again in `{error.retry_after:.2f}` seconds.",
      )
      await ctx.reply(view=view, delete_after=10)
      return  

    if isinstance(error, commands.MaxConcurrencyReached):
      view = _error_view(
          f"> <:timeout:1470401370782695536> Please use commands slowly, you are currently on cooldown.",
      )
      await ctx.reply(view=view, delete_after=10)
      ctx.command.reset_cooldown(ctx)
      return  

    if isinstance(error, commands.MissingPermissions):
      missing = [
                perm.replace("_", " ").replace("guild", "server").title()
                for perm in error.missing_permissions
            ]
      if len(missing) > 2:
                fmt = "{}, and {}".format(", ".join(missing[:-1]), missing[-1])
      else:
                fmt = " and ".join(missing)
      view = _error_view(
          f"<:1spacer:1469251392924549294><:rightshort:1469251448909861017> You don't have the **{fmt} permissions** to **run {ctx.command.name} command.**",
      )
      await ctx.reply(view=view, delete_after=6)
      ctx.command.reset_cooldown(ctx)
      return  

    if isinstance(error, commands.BadArgument):
        view = _error_view_with_header(
            "Invalid Parameters!!",
            f"<:Lund:1464624797374873611> **Usage:**\n<:1spacer:1469251392924549294><:rightshort:1469251448909861017> ``{ctx.prefix}{ctx.command} {ctx.command.signature}``",
            accent=0x2b2d31,
        )
        await ctx.reply(view=view, delete_after=10)

    if isinstance(error, commands.BotMissingPermissions):
        missing = ", ".join(error.missing_permissions)
        view = _error_view_with_header(
            "Permission Error",
            f"<:exclaim:1469643837789180045> Its Looks like i dont have **enough permission.**\n<:1spacer:1469251392924549294><:rightshort:1469251448909861017> Please **ensure** that i have the **`{missing}` permissions** to run this **command.**",
        )
        await ctx.reply(view=view, delete_after=10)
        return

    if isinstance(error, discord.HTTPException):
      print(f"HTTPException in {ctx.command}: {error}")
      return  
    elif isinstance(error, commands.CommandInvokeError):
      print(f"CommandInvokeError in {ctx.command}: {error.original}")
      import traceback
      traceback.print_exception(type(error.original), error.original, error.original.__traceback__)
      return  

async def setup(client):
    await client.add_cog(Errors(client))