import discord
import asyncio
import datetime
from datetime import datetime, timedelta
import re
import typing
import typing as t
from checks.colorcheck import get_embed_color
from discord import ui
from typing import *
import sqlite3
from utils.Tools import *
from core import Cog, Synapse, Context
from discord.ext.commands import Converter
from discord.ext import commands, tasks
from discord.ui import Button, View
from typing import Union, Optional
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from typing import Union, Optional
from io import BytesIO
import requests
import aiohttp
import time
from datetime import datetime, timezone, timedelta
import sqlite3
from typing import *
from difflib import get_close_matches


time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}

class PrefixChangeView(discord.ui.View):
    def __init__(self, ctx, default_prefix, current_prefix, data, update_config):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.default_prefix = default_prefix
        self.current_prefix = current_prefix
        self.data = data
        self.update_config = update_config

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red)
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You are not authorized to perform this action.", ephemeral=True
            )

        self.data["prefix"] = self.default_prefix
        self.update_config(self.ctx.guild.id, self.data)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"<:emoji_1769867605256:1467155817726873650> Prefix has been reset to default: `{self.default_prefix}`",
                color=discord.Color.green()
            )
        )
        self.stop()

    @discord.ui.button(label="Set", style=discord.ButtonStyle.primary)
    async def set_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You are not authorized to perform this action.", ephemeral=True
            )
        embed = discord.Embed()
        embed.description = "Please type the new prefix you'd like to set."

        await interaction.response.send_message(embed=embed, ephemeral=False)

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel

        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=30)
            new_prefix = msg.content.strip()
            self.data["prefix"] = new_prefix
            self.update_config(self.ctx.guild.id, self.data)
            await self.ctx.send(
                embed=discord.Embed(
                    description=f"<:emoji_1769867605256:1467155817726873650> Prefix has been changed to `{new_prefix}`",
                    color=discord.Color.green()
                )
            )
        except asyncio.TimeoutError:
            await self.ctx.send("You took too long to respond. The operation was canceled.", ephemeral=True)
        self.stop()

def convert(argument):
  args = argument.lower()
  matches = re.findall(time_regex, args)
  time = 0
  for key, value in matches:
    try:
      time += time_dict[value] * float(key)
    except KeyError:
      raise commands.BadArgument(
        f"{value} is an invalid time key! h|m|s|d are valid arguments")
    except ValueError:
      raise commands.BadArgument(f"{key} is not a number!")
  return round(time)

async def do_removal(ctx, limit, predicate, *, before=None, after=None):
    if limit > 2000:
        return await ctx.error(f"Too many messages to search given ({limit}/2000)")

    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)

    if after is not None:
        after = discord.Object(id=after)

    try:
        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
    except discord.Forbidden as e:
        return await ctx.error("I do not have permissions to delete messages.")
    except discord.HTTPException as e:
        return await ctx.error(f"Error: {e} (try a smaller search?)")

    deleted = len(deleted)
    embed = discord.Embed(
        description=f'<:emoji_1769867605256:1467155817726873650> Sucessfully purged {deleted} messages.',
        color=0x2b2d31
    )
    embed.set_footer(text=f"Purged by {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
    embed.set_author(name="Messages Deleted", icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else ctx.bot.user.default_avatar.url)
    await ctx.send(embed=embed, delete_after=10)




class Moderation(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0X2b2d31
    self.default_prefix = "."

  def get_user_avatar(self, user):
    return user.avatar.url if user.avatar else user.default_avatar.url

  def convert(self, time):
    pos = ["s", "m", "h", "d"]

    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
    unit = time[-1]
    if unit not in pos:
      return -1
    try:
      val = int(time[:-1])
    except:
      return -2
    return val * time_dict[unit]



  @commands.command()
  async def enlarge(self, ctx,  emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
    ''' Enlarge any emoji '''
    url = emoji.url
    await ctx.send(url)




  @commands.command(name="unlockall",
                    help="Unlocks down the server.",
                    usage="unlockall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 5, commands.BucketType.channel)
  async def unlockall(self, ctx):
      if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Yes",
                    style=discord.ButtonStyle.green,
                    emoji="<:emoji_1769867605256:1467155817726873650>")
          button1 = Button(label="No",
                     style=discord.ButtonStyle.red,
                     emoji="<:SynapseExcl:1477234549552320634>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.administrator:
                      embed1 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Unlocking all channels in {ctx.guild.name}.")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                          try:
                              await channel.set_permissions(
                                   ctx.guild.default_role,
                                overwrite=discord.PermissionOverwrite(send_messages=True,
                                                 read_messages=True),
                                         reason="Unlockall Command Executed By: {}".format(ctx.author))
                              a += 1  
                          except Exception as e:
                              print(e)
                      await interaction.channel.send(
                              content=f"<:emoji_1769867605256:1467155817726873650> Successfully unlocked {a} channel's .")   
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
                              embed=None,
                                  view=None)
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Okay, I won't unlock any channels.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

          embed = discord.Embed(
                  color=0x2b2d31,
                 description=f'**Are you sure you want to unlock all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text=f"Click on either Yes or No to confirm! You have 20 seconds.")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=20)     


      else:
          hacker5 = discord.Embed(
        description=
        """ You need Administrator permissions.\n Your role must be higher than mine.""",
        color=0x2b2d31)
          hacker5.set_author(name=f"{ctx.author.name}",
                         icon_url=ctx.author.avatar.url
                       if ctx.author.avatar else ctx.author.default_avatar.url)

          await ctx.send(embed=hacker5, mention_author=False)  



  @commands.command(name="lockall",
                    help="locks down the server.",
                    usage="lockall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 5, commands.BucketType.channel)
  async def lockall(self, ctx):
      if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Yes",
                    style=discord.ButtonStyle.green,
                    emoji="<:emoji_1769867605256:1467155817726873650>")
          button1 = Button(label="No",
                     style=discord.ButtonStyle.red,
                     emoji="<:SynapseExcl:1477234549552320634>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.administrator:
                      embed1 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Locking all channels in {ctx.guild.name}.")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                          try:
                              await channel.set_permissions(ctx.guild.default_role,
                                      overwrite=discord.PermissionOverwrite(
                                        send_messages=False,
                                        read_messages=True),
                                         reason="lockall Command Executed By: {}".format(ctx.author))
                              a += 1  
                          except Exception as e:
                              print(e)
                      await interaction.channel.send(
                              content=f"<:emoji_1769867605256:1467155817726873650> Successfully locked {a} channel's.")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
                              embed=None,
                                  view=None)
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Okay, I won't lock any channels.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)


          embed = discord.Embed(
                  color=0x2b2d31,
                 description=f'**Are you sure you want to lock all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text=f"Click on either Yes or No to confirm! You have 20 seconds.")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=20)     

      else:
          hacker5 = discord.Embed(
        description=
        """ You need Administrator permissions.\n Your role must be higher than mine.""",
        color=0x2b2d31)
          hacker5.set_author(name=f"{ctx.author.name}",
                         icon_url=ctx.author.avatar.url
                       if ctx.author.avatar else ctx.author.default_avatar.url)

          await ctx.send(embed=hacker5, mention_author=False)  


  @commands.command(name="hideall", help="Hides all the channels .",
                    usage="hideall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 5, commands.BucketType.channel)
  async def hideall(self, ctx):
      if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Yes",
                    style=discord.ButtonStyle.green,
                    emoji="<:emoji_1769867605256:1467155817726873650>")
          button1 = Button(label="No",
                     style=discord.ButtonStyle.red,
                     emoji="<:SynapseExcl:1477234549552320634>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.administrator:
                      embed1 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Hiding all channels in {ctx.guild.name}.")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                          try:
                              await channel.set_permissions(ctx.guild.default_role, view_channel=False,
                                         reason="Hideall Command Executed By: {}".format(ctx.author))
                              a += 1  
                          except Exception as e:
                              print(e)
                      await interaction.channel.send(
                              content=f"<:emoji_1769867605256:1467155817726873650> Successfully hidden {a} channel's.")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
                              embed=None,
                                  view=None)
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Okay, I won't hide any channels.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
          embed = discord.Embed(
                  color=0x2b2d31,
                 description=f'**Are you sure you want to hide all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text=f"Click on either Yes or No to confirm! You have 20 seconds.")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=20)

  @commands.command(name="unhideall", help="Unhides all the channels .",
                    usage="unhideall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 5, commands.BucketType.channel)
  async def unhideall(self, ctx):
      if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Yes", style=discord.ButtonStyle.green,
                    emoji="<:emoji_1769867605256:1467155817726873650>")
          button1 = Button(label="No",
                     style=discord.ButtonStyle.red,
                     emoji="<:SynapseExcl:1477234549552320634>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.administrator:
                      embed1 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Unhiding all channels in {ctx.guild.name}.")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                          try:
                              await channel.set_permissions(ctx.guild.default_role, view_channel=True,
                                         reason="Unhideall Command Executed By: {}".format(ctx.author))
                              a += 1  
                          except Exception as e:
                              print(e)
                      await interaction.channel.send(
                              content=f"<:emoji_1769867605256:1467155817726873650> Successfully unhidden {a} channel's")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
                              embed=None,
                                  view=None)
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=0x2b2d31,
                    description=f"Okay, I won't unhide any channels.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
          embed = discord.Embed(
                  color=0x2b2d31,
                 description=f'**Are you sure you want to unhide all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text=f"Click on either Yes or No to confirm! You have 20 seconds.")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=20)     

      else:
          hacker5 = discord.Embed(
        description=
        """ You need Administrator permissions.\n Your role must be higher than mine.""",
        color=0x2b2d31)
          hacker5.set_author(name=f"{ctx.author.name}",
                         icon_url=ctx.author.avatar.url
                       if ctx.author.avatar else ctx.author.default_avatar.url)

          await ctx.send(embed=hacker5, mention_author=False)




  @commands.command(name="unhide", help="Unhides the channel")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_channels=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _unhide(self, ctx, channel: discord.TextChannel = None):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            channel = channel or ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.view_channel = True
            try:
                await channel.set_permissions(ctx.guild.default_role,
                                              overwrite=overwrite,
                                              reason=f"Channel Unhidden By {ctx.author}")

                embed = discord.Embed(
                    color=0x2b2d31,
                    description=f"<:emoji_1769867605256:1467155817726873650> Successfully unhidden {channel.mention}."
                )
                await ctx.send(embed=embed)
            except Exception as e:
                print(e)
                return

        else:
            hacker5 = discord.Embed(
                description=
                """ You need Administrator permissions.\n Your role must be higher than mine.""",
                color=0x2b2d31)
            hacker5.set_author(name=f"{ctx.author.name}",
                               icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=hacker5, mention_author=False)           



  @commands.command(name="hide", help="hides the channel .")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_channels=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _hide(self, ctx, channel: discord.TextChannel = None):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            channel = channel or ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.view_channel = False
            try:
                await channel.set_permissions(ctx.guild.default_role,overwrite=overwrite,
                                              reason=f"Channel hidden By {ctx.author}")
                embed = discord.Embed(
                    color=0x2b2d31,
                    description=f"<:emoji_1769867605256:1467155817726873650> Successfully hidden {channel.mention}."
                )
                await ctx.send(embed=embed)
            except Exception as e:
                print(e)
                return 
        else:
            hacker5 = discord.Embed(
                description=
                """ You need Administrator permissions.\n Your role must be higher than mine.""",
                color=0x2b2d31)
            hacker5.set_author(name=f"{ctx.author.name}",
                               icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=hacker5, mention_author=False)          




  @commands.command(
    name="prefix",
    aliases=["setprefix", "prefixset"],
    help="Allows you to change prefix of the bot for this server")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _prefix(self, ctx: commands.Context, prefix: str):
        if not prefix:
            await ctx.reply(embed=discord.Embed(description="Prefix cannot be empty. Please provide a valid prefix.",
                                                color=0x2b2d31
                                               ))
            return

        data = await getConfig(ctx.guild.id)
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            data["prefix"] = str(prefix)
            await updateConfig(ctx.guild.id, data)
            embed1=discord.Embed(
                                 description=f"Prefix has been changed to `{prefix}` for this guild",
                                 color=0x2b2d31
                                )
            await ctx.reply(embed=embed1)
        else:
            denied = discord.Embed(description="Your role should be above my top role.",
                                   color=0x2b2d31)
            denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                              icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=denied, mention_author=False)



  @commands.command(name="clone", help="Clones a channel .")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_channels=True)
  async def clone(self, ctx: commands.Context, channel: discord.TextChannel):
    await channel.clone()
    hacker = discord.Embed(
      color=0x2b2d31,
      description=
      f"<:emoji_1769867605256:1467155817726873650> {channel.name} has been successfully cloned"
    )
    hacker.set_author(name=f"{ctx.author.name}",
                      icon_url=ctx.author.avatar.url
                       if ctx.author.avatar else ctx.author.default_avatar.url)

    await ctx.send(embed=hacker)

  @commands.command(name="nick",
                           aliases=['setnick'],
                           help="To change someone's nickname.",
                           usage="nick [member]")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_nicknames=True)
  @commands.bot_has_permissions(manage_nicknames=True)
  async def changenickname(self, ctx: commands.Context, member: discord.Member,*, name: str = None):
        if member == ctx.guild.owner:
            error = discord.Embed(
                color=0x2b2d31,
                description="I can't change the nickname of the server owner!"
            )
            error.set_author(name="Operation Failed")
            error.set_footer(text=f"Requested by {ctx.author}",
                             icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.send(embed=error)

        if member.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(
                color=0x2b2d31,
                description="I can't change the nickname of a user with a higher or equal role than mine!"
                )
            error.set_author(name="Operation Failed")
            error.set_footer(text=f"Requested by {ctx.author}",
                             icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.send(embed=error)

        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            error = discord.Embed(
                color=0x2b2d31,
                description="You can't change the nickname of a user with a higher or equal role than you!"
                )
            error.set_author(name="Operation Failed")
            error.set_footer(text=f"Requested by {ctx.author}",
                             icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.send(embed=error)

        try:
            await member.edit(nick=name)
            if name:
                success = discord.Embed(
                    color=0x2b2d31,
                    description=f"Successfully changed nickname of {member.mention} to {name}."
                    )
                success.set_author(name="Operation Successfull")
                success.set_footer(text=f"Requested by {ctx.author}",
                                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            else:
                success = discord.Embed(
                    color=0x2b2d31,
                    description=f"Successfully cleared nickname of {member.mention}."
                    )
                success.set_author(name="Nickname Cleared")
                success.set_footer(text=f"Requested by {ctx.author}",
                                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.send(embed=success)
        except discord.Forbidden:
            error = discord.Embed(
                color=0x2b2d31,
                description="<:SynapseExcl:1477234549552320634> I don't have permission to manage this user's nickname!"
        )
            await ctx.send(embed=error)
        except Exception as e:
            error = discord.Embed(
                color=0x2b2d31,
                description=f"<:SynapseExcl:1477234549552320634> An error occurred while trying to change the nickname: {str(e)}"
                )
            await ctx.send(embed=error)

  @commands.command(name="nuke", help="Nukes a channel", usage="")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_channels=True)
  async def _nuke(self, ctx: commands.Context):
    button = Button(label="Yes",
                    style=discord.ButtonStyle.green,
                    emoji="<:emoji_1769867605256:1467155817726873650>")
    button1 = Button(label="No",
                     style=discord.ButtonStyle.red,
                     emoji="<:SynapseExcl:1477234549552320634>")

    async def button_callback(interaction: discord.Interaction):
      if interaction.user == ctx.author:
        if interaction.guild.me.guild_permissions.manage_channels:
          channel = interaction.channel
          newchannel = await channel.clone()
          await newchannel.edit(position=channel.position)

          await channel.delete()
          await newchannel.send(f"Nuked by `%s`" % (ctx.author), delete_after=10)
        else:
          await interaction.response.edit_message(
            content=
            " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
            embed=None,
            view=None)
      else:
        embed = discord.Embed()
        embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
        await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

    async def button1_callback(interaction: discord.Interaction):
      if interaction.user == ctx.author:
        await interaction.response.edit_message(
          content="Okay, I won't nuke any channel.", embed=None, view=None)
      else:
        embed = discord.Embed()
        embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
        await interaction.response.send_message(embed=embed, view=None, ephemeral=True)

    embed = discord.Embed(
      color=0x2b2d31, description='**Are you sure you want to nuke channel**')

    view = View()
    button.callback = button_callback
    button1.callback = button1_callback
    view.add_item(button)
    view.add_item(button1)
    embed.set_footer(text=f"Click on either Yes or No to confirm! You have 20 seconds.")
    await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=20)

  @commands.command(name="unlock",
                           help="Unlocks a channel",
                           usage="unlock <channel> <reason>",
                           aliases=["unlockdown"])
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_channels=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _unlock(self,
                    ctx: commands.Context,
                    channel: discord.TextChannel = None, *,reason=None):
    if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
      if channel is None: channel = ctx.channel
      try:
          await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=discord.PermissionOverwrite(send_messages=True),
            reason=reason)
          embed = discord.Embed(
            color=0x2b2d31,
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully unlocked {channel.mention}."
            )
          await ctx.send(embed=embed)
      except Exception as e:
        print(e)
        return 
    else:
      hacker5 = discord.Embed(
        description=
        " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
        color=0x2b2d31)
      hacker5.set_author(name=f"{ctx.author.name}",
                         icon_url=ctx.author.avatar.url
                         if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.send(embed=hacker5, mention_author=False)            


  @commands.command(name="lock",
                           help="locks a channel .",
                           usage="lock <channel> <reason>",
                           aliases=["lockdown"])
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_channels=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _lock(self,
                    ctx: commands.Context,
                    channel: discord.TextChannel = None, *,reason=None):
    if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
      if channel is None: channel = ctx.channel
      try:
          await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=discord.PermissionOverwrite(send_messages=False),
            reason=reason)
          embed = discord.Embed(
            color=0x2b2d31,
            description=f"<:emoji_1769867605256:1467155817726873650> Successfully locked {channel.mention}."
            )
          await ctx.send(embed=embed)
      except Exception as e:
        print(e)
        return
    else:
      hacker5 = discord.Embed(
        description=
        " Insufficient Privileges: This command cannot be executed due to the absence of required permissions.\n Please ensure the necessary authorization is granted to proceed.",
        color=0x2b2d31)
      hacker5.set_author(name=f"{ctx.author.name}",
                         icon_url=ctx.author.avatar.url
                         if ctx.author.avatar else ctx.author.default_avatar.url)

      await ctx.send(embed=hacker5, mention_author=False)                   



  @commands.command(aliases=['as', 'stealsticker'], description="Adds the sticker to the server")
  @commands.has_permissions(manage_emojis=True)
  async def addsticker(self, ctx: commands.Context, *, name=None):
        if ctx.message.reference is None:
            return await ctx.reply("No replied message found")
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if len(msg.stickers) == 0:
            return await ctx.reply("No sticker found")
        n, url = "", ""
        for i in msg.stickers:
            n = i.name
            url = i.url
        if name is None:
            name = n
        try:
            response = requests.get(url)
            if url.endswith("gif"):
                fname = "Sticker.gif"
            else:
                fname = "Sticker.png"
            file = discord.File(BytesIO(response.content), fname)
            s = await ctx.guild.create_sticker(name=name, description= f"Sticker created by {str(self.bot.user)}", emoji="<:MekoEmoji:1449446336129929390>", file=file)
            await ctx.reply(f"<:emoji_1769867605256:1467155817726873650> Sucessfully created sticker with name `{name}`", stickers=[s])
        except:
            return await ctx.reply("Failed to create the sticker")





  @commands.group(
      name="role",
      usage="<member> <role(s)>",
      invoke_without_command=True,
      )
  @ignore_check()
  @commands.guild_only()
  @blacklist_check()
  @commands.has_permissions(manage_roles=True)
  @commands.bot_has_guild_permissions(manage_roles=True)
  @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
  async def role(self, ctx, member: discord.Member, *, role: str): 
      if ctx.invoked_subcommand is not None:
          return
      user_id = str(ctx.author.id)
      embed_color = get_embed_color(user_id, ctx)
      
      if "," in role:
          raw_roles = [r.strip() for r in role.split(",") if r.strip()]
      else:
          raw_roles = [role.strip()]

      guild_roles = ctx.guild.roles
      added_roles = []
      removed_roles = []

      for role_name in raw_roles:
          target_role = None

          if role_name.startswith("<@&") and role_name.endswith(">"):
              try:
                  role_id = int(role_name.strip("<@&>"))
                  target_role = discord.utils.get(guild_roles, id=role_id)
              except ValueError:
                  continue
          elif role_name.isdigit():
              target_role = discord.utils.get(guild_roles, id=int(role_name))
          else:
              target_role = discord.utils.get(guild_roles, name=role_name)
              if not target_role:
                  role_names = [r.name for r in guild_roles if not r.managed and r != ctx.guild.default_role]
                  close_matches = get_close_matches(role_name, role_names, n=1, cutoff=0.6)
                  if close_matches:
                      target_role = discord.utils.get(guild_roles, name=close_matches[0])

          if not target_role or target_role.managed or target_role == ctx.guild.default_role:
              continue

          try:
              if target_role not in member.roles:
                  await member.add_roles(target_role, reason=f"Synapse • Addrole | Requested By {ctx.author} (ID: {ctx.author.id})")
                  added_roles.append(target_role.name)
              else:
                  await member.remove_roles(target_role, reason=f"Synapse • Removerole | Requested By {ctx.author} (ID: {ctx.author.id})")
                  removed_roles.append(target_role.name)
          except Exception:
              continue

      if added_roles or removed_roles:
          role_changes = []
          role_changes.extend([f"`+{r}`" for r in added_roles])
          role_changes.extend([f"`-{r}`" for r in removed_roles])

          embed = discord.Embed(
              description=f"{ctx.author.mention}: {', '.join(role_changes)} to **{member.name}**",
              color=embed_color)
          await ctx.send(embed=embed)
      else:
          await ctx.send(f"{ctx.author.mention}, no roles were added or removed from **{member.name}**.")

  @role.command(name="humans", help="Gives role to all humans in the guild")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 15, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_humans(self, ctx, *, role: discord.Role):
    if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green,
                        emoji="<:emoji_1769867605256:1467155817726873650>")
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red,
                         emoji="<:SynapseExcl:1477234549552320634>")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    embed1 = discord.Embed(
                        color=0x2b2d31,
                        description=f"Assigning {role.mention} to all humans...")
                    await interaction.response.edit_message(embed=embed1, view=None)
                    for member in interaction.guild.members:
                        if not member.bot and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Role Humans Command Executed By: {ctx.author}")
                                count += 1
                            except Exception as e:
                                print(e)

                    await interaction.channel.send(
                        content=f"<:emoji_1769867605256:1467155817726873650> Successfully assigned {role.mention} to {count} human(s).")
                else:
                    await interaction.response.edit_message(
                        content=" I am missing the required permissions. Please grant the necessary permissions and try again.",
                        embed=None,
                        view=None)
            else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(
                    embed=embed,
                    view=None,
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=0x2b2d31,
                    description=f"Action cancelled. No humans will be assigned the role {role.mention}.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(
                    embed=embed,
                    view=None,
                    ephemeral=True)

        members_without_role = [member for member in ctx.guild.members if not member.bot and role not in member.roles]
        if len(members_without_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f" All humans already have the {role.mention} role.", color=0x2b2d31))
        else:
            embed = discord.Embed(
                color=0x2b2d31,
                description=f"Are you sure you want to assign {role.mention} to {len(members_without_role)} members?")
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    else:
        denied = discord.Embed(
            description="<:SynapseExcl:1477234549552320634> Your role should be above my top role.",
            color=0x2b2d31)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @role.command(name="bots", help="Gives role to all the bots in the guild")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_bots(self, ctx, *, role: discord.Role):
    if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green,
                        emoji="<:emoji_1769867605256:1467155817726873650>")
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red,
                         emoji="<:SynapseExcl:1477234549552320634>")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    embed1 = discord.Embed(
                        color=0x2b2d31,
                        description=f"Adding {role.mention} to all bots...")
                    await interaction.response.edit_message(embed=embed1, view=None)
                    for member in interaction.guild.members:
                        if member.bot and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Role Bots Command Executed By: {ctx.author}")
                                count += 1
                            except Exception as e:
                                print(e)

                    await interaction.channel.send(
                        content=f"<:emoji_1769867605256:1467155817726873650> Successfully added {role.mention} to {count} bot(s).")
                else:
                    await interaction.response.edit_message(
                        content=" I am missing the required permission. Please grant the necessary permissions and try again.",
                        embed=None,
                        view=None)
            else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(
                    embed=embed,
                    view=None,
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=0x2b2d31,
                    description=f"Action cancelled. No bots will be assigned the role {role.mention}.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                embed = discord.Embed()
                embed.description = f" I'm sorry, **{interaction.user.name}**, you cannot access this button.\n<:MekoArrowRight:1449445989436887090> Please use the bot command first then you can access this button"
                await interaction.response.send_message(
                    embed=embed,
                    view=None,
                    ephemeral=True)

        bots_without_role = [member for member in ctx.guild.members if member.bot and role not in member.roles]
        if len(bots_without_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f" All bots already have the {role.mention} role.", color=0x2b2d31))
        else:
            embed = discord.Embed(
                color=0x2b2d31,
                description=f"**Are you sure you want to give {role.mention} to {len(bots_without_role)} bots?**")
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    else:
        denied = discord.Embed(
            description="<:SynapseExcl:1477234549552320634> Your role should be above my top role.",
            color=0x2b2d31)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)

  @commands.command()
  @commands.has_permissions(manage_roles=True)
  async def rolecolor(self, ctx, role: discord.Role, color: str):
      try:
          if not color.startswith("#"):
              await ctx.send("Please provide a valid hex code starting with #.")
              return

          hex_color = int(color[1:], 16)
          await role.edit(colour=discord.Colour(hex_color))
          await ctx.send(embed=discord.Embed(
              description=f"Successfully changed {role.mention} color to `{color}`.",
              color=hex_color
              ))
      except ValueError:
          await ctx.send("Invalid hex code. Please provide a correct hex color code.")
      except discord.Forbidden:
          await ctx.send("I don't have permission to edit this role.")
      except Exception as e:
          await ctx.send(f"An error occurred: {e}")   


  @commands.command(description="Changes the icon for the role .")
  @commands.has_permissions(administrator=True)
  @commands.bot_has_guild_permissions(manage_roles=True)
  async def roleicon(self, ctx: commands.Context, role: discord.Role, *, icon: Union[discord.Emoji, discord.PartialEmoji, str]=None):
        if role.position >= ctx.guild.me.top_role.position:
            em = discord.Embed(description=f" {role.mention} role is higher than my role, move it to the top!", color=0x2b2d31)
        if ctx.author.top_role.position <= role.position:
            em = discord.Embed(description=f" {role.mention} has the same or higher position from your top role!", color=0x2b2d31)
            return await ctx.send(embed=em, delete_after=15)

        if role is None:
            usage_embed = discord.Embed(
                description=("roleicon <role> <emoji>"),
                color=color
            )
            return await ctx.reply(embed=usage_embed, mention_author=False)

        if icon is None:
            c = False
            url = None
            for xd in ctx.message.attachments:
                url = xd.url
                c = True
            if c:
                try:
                    async with aiohttp.request("GET", url) as r:
                        img = await r.read()
                        await role.edit(display_icon=img)
                    em = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully changed icon of {role.mention}", color=0x2b2d31)
                except:
                    return await ctx.reply("Failed to change the icon of the role")
            else:
                await role.edit(display_icon=None)
                em = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed icon from {role.mention}", color=0x2b2d31)
            return await ctx.reply(embed=em, mention_author=False)
        if isinstance(icon, discord.Emoji) or isinstance(icon, discord.PartialEmoji):
            png = f"https://cdn.discordapp.com/emojis/{icon.id}.png"
            try:
              async with aiohttp.request("GET", png) as r:
                img = await r.read()
            except:
              return await ctx.reply("Failed to change the icon of the role")
            await role.edit(display_icon=img)
            em = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully changed the icon for {role.mention} to {icon}", color=0x2b2d31)
            return await ctx.reply(embed=em, mention_author=False)
        else:
            if not icon.startswith("https://"):
                return await ctx.reply("Give a valid link")
            try:
              async with aiohttp.request("GET", icon) as r:
                img = await r.read()
            except:
              return await ctx.reply("An error occured while changing the icon for the role")
            await role.edit(display_icon=img)
            em = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully changed the icon for {role.mention}", color=0x2b2d31)
            return await ctx.reply(embed=em, mention_author=False)




  @commands.group(invoke_without_command=True, aliases=["purge"], description="Clears the messages")
  @commands.has_permissions(manage_messages=True)
  async def clear(self, ctx, Choice: Union[discord.Member, int], Amount: int = None):
        """
        An all in one purge command.
        Choice can be a Member or a number
        """
        await ctx.message.delete()

        if isinstance(Choice, discord.Member):
            search = Amount or 5
            return await do_removal(ctx, search, lambda e: e.author == Choice)

        elif isinstance(Choice, int):
            return await do_removal(ctx, Choice, lambda e: True)

        try:
            embed = discord.Embed(
                title="Purge Commands",
                description="**- How to Use?** You can type `Purge <command>` to execute a command.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n`clear` , `clear all` , `clear bots` , `clear embeds` , `clear files` , `clear mentions` , `clear images` , `clear contains` , `clear reactions` , `clear user` , `clear emoji` , `role`, `role humans`, `role bots`, `nuke` , `lock` , `unlock` , `hide` , `unhide` , `unbanall`, `hideall` , `unhideall`, `rolecolor` ,  `roleicon`, `steal` , `addsticker`",
                color=0x2b2d31 
            )

            await ctx.send(embed=embed)
        except Exception as e:            
            await ctx.send(f"{e}")



  @clear.command(description="Clears the messages containing embeds")
  @commands.has_permissions(manage_messages=True)
  async def embeds(self, ctx, search=100):
        """Removes messages that have embeds in them."""
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds))


  @clear.command(description="Clears the messages containing files")
  @commands.has_permissions(manage_messages=True)
  async def files(self, ctx, search=100):
        """Removes messages that have attachments in them."""

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.attachments))

  @clear.command(description="Clears the messages containg images")
  @commands.has_permissions(manage_messages=True)
  async def images(self, ctx, search=100):
        """Removes messages that have embeds or attachments."""

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))


  @clear.command(name="all", description="Clears all messages")
  @commands.has_permissions(manage_messages=True)
  async def _remove_all(self, ctx, search=100):
        """Removes all messages."""

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: True)

  @clear.command(description="Clears the messages of a specific user")
  @commands.has_permissions(manage_messages=True)
  async def user(self, ctx, member: discord.Member, search=100):
        """Removes all messages by the member."""

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)



  @clear.command(description="Clears the messages containing a specifix string")
  @commands.has_permissions(manage_messages=True)
  async def contains(self, ctx, *, string: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """

        await ctx.message.delete()
        if len(string) < 3:
            await ctx.error("The substring length must be at least 3 characters.")
        else:
            await do_removal(ctx, 100, lambda e: string in e.content)

  @clear.command(name="bot", aliases=["bots","pb"], description="Clears the messages sent by bot")
  @commands.has_permissions(manage_messages=True)
  async def _bot(self, ctx, prefix=None, search=100):
        """Removes a bot user's messages and messages with their optional prefix."""

        await ctx.message.delete()

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await do_removal(ctx, search, predicate)

  @clear.command(name="emoji", aliases=["emojis"], description="Clears the messages having emojis")
  @commands.has_permissions(manage_messages=True)
  async def _emoji(self, ctx, search=100):
        """Removes all messages containing custom emoji."""

        await ctx.message.delete()
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return custom_emoji.search(m.content)

        await do_removal(ctx, search, predicate)

  @clear.command(name="reactions", description="Clears the reaction from the messages")
  @commands.has_permissions(manage_messages=True)
  async def _reactions(self, ctx, search=100):
        """Removes all reactions from messages that have them."""

        await ctx.message.delete()

        if search > 2000:
            return await ctx.send(f"Too many messages to search for ({search}/2000)")

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.success(f"<:emoji_1769867605256:1467155817726873650> Successfully removed {total_reactions} reactions.")


async def setup(client):
    await client.add_cog(Moderation(client))