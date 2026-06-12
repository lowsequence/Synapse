from __future__ import annotations
import discord
from discord.ext import commands
from core import *
from utils.Tools import *
from typing import Optional
import aiosqlite

class Ignore(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.db_path = "database/ignore.db"
    self.color = 0x2b2d31 
    bot.loop.create_task(self.initialize_db())

  async def initialize_db(self):
    async with aiosqlite.connect(self.db_path) as db:
      await db.execute("CREATE TABLE IF NOT EXISTS ignored_commands (guild_id INTEGER, command_name TEXT)")
      await db.execute("CREATE TABLE IF NOT EXISTS ignored_channels (guild_id INTEGER, channel_id INTEGER)")
      await db.execute("CREATE TABLE IF NOT EXISTS ignored_users (guild_id INTEGER, user_id INTEGER)")
      await db.execute("CREATE TABLE IF NOT EXISTS bypassed_users (guild_id INTEGER, user_id INTEGER)")
      await db.commit()

  @commands.group(name="ignore", help="Manage ignored commands, channels, users, and bypassed users.", invoke_without_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _ignore(self, ctx):
        if ctx.invoked_subcommand is not None:

            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)


  @_ignore.group(name="channel", help="Manage ignored channels in this guild.", invoke_without_command=True)
  @blacklist_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _channel(self, ctx):
        if ctx.invoked_subcommand is not None:

            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)


  @_channel.command(name="add", help="Adds a channel to the ignore list.")
  @blacklist_check()
  @commands.has_permissions(administrator=True)
  async def channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT COUNT(*) FROM ignored_channels WHERE guild_id = ?", (ctx.guild.id,))
      count = await cursor.fetchone()

      if count[0] >= 30:
        embed = discord.Embed(description="You can only add up to 30 channels to the ignore list.", color=self.color)
        await ctx.reply(embed=embed)
        return

      cursor = await db.execute("SELECT channel_id FROM ignored_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
      result = await cursor.fetchone()

      if result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {channel.mention} is already in the ignore channels list.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        await db.execute("INSERT INTO ignored_channels (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully added {channel.mention} to the ignore channels list.", color=self.color)
        await ctx.reply(embed=embed)

  @_channel.command(name="remove", help="Removes a channel from the ignore list.")
  @blacklist_check()
  @commands.has_permissions(administrator=True)
  async def channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT channel_id FROM ignored_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
      result = await cursor.fetchone()

      if not result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {channel.mention} is not in the ignore channels list.", color=self.color)
        await ctx.reply(embed=embed)
      else:
        await db.execute("DELETE FROM ignored_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed {channel.mention} from the ignore channels list.", color=self.color)
        await ctx.reply(embed=embed)

  @_channel.command(name="show", help="Displays the list of ignored channels.")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  async def channel_show(self, ctx: commands.Context):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT channel_id FROM ignored_channels WHERE guild_id = ?", (ctx.guild.id,))
      channels = await cursor.fetchall()

      if not channels:
        embed = discord.Embed(description="No channels are currently ignored in this server.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        channel_mentions = [ctx.guild.get_channel(channel_id).mention if ctx.guild.get_channel(channel_id) else f"Channel ID {channel_id}" for channel_id, in channels]
        description = "\n".join(channel_mentions)
        embed = discord.Embed(title="Ignored Channels", description=description, color=self.color)
        await ctx.reply(embed=embed, mention_author=False)

  @_ignore.group(name="user", help="Manage ignored users in this guild.", invoke_without_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _user(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)

  @_user.command(name="add", help="Adds a user to the ignore list.")
  @commands.has_permissions(administrator=True)
  @blacklist_check()

  async def user_add(self, ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT COUNT(*) FROM ignored_users WHERE guild_id = ?", (ctx.guild.id,))
      count = await cursor.fetchone()

      if count[0] >= 30:
        embed = discord.Embed(description="You can only add up to 30 users to the ignore list.", color=self.color)
        await ctx.reply(embed=embed)
        return

      cursor = await db.execute("SELECT user_id FROM ignored_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
      result = await cursor.fetchone()

      if result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {user.mention} is already in the ignore users list.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        await db.execute("INSERT INTO ignored_users (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully added {user.mention} to the ignore users list.", color=self.color)
        await ctx.reply(embed=embed)

  @_user.command(name="remove", help="Removes a user from the ignore list.")
  @blacklist_check()

  @commands.has_permissions(administrator=True)
  async def user_remove(self, ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT user_id FROM ignored_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
      result = await cursor.fetchone()

      if not result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {user.mention} is not in the ignore users list.", color=self.color)
        await ctx.reply(embed=embed)
      else:
        await db.execute("DELETE FROM ignored_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed {user.mention} from the ignore users list.", color=self.color)
        await ctx.send(embed=embed)

  @_user.command(name="show", help="Displays the list of ignored users.")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  async def user_show(self, ctx: commands.Context):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT user_id FROM ignored_users WHERE guild_id = ?", (ctx.guild.id,))
      users = await cursor.fetchall()

      if not users:
        embed = discord.Embed(description="No users are currently ignored in this server.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        user_mentions = [ctx.guild.get_member(user_id).mention if ctx.guild.get_member(user_id) else f"User ID {user_id}" for user_id, in users]
        description = "\n".join(user_mentions)
        embed = discord.Embed(title="Ignored Users", description=description, color=self.color)
        await ctx.reply(embed=embed, mention_author=False)

  @_ignore.group(name="bypass", help="Manage bypassed users in this guild.", invoke_without_command=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _bypass(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)



  @_bypass.command(name="add", help="Adds a user to the bypass list.")
  @blacklist_check()
  @ignore_check()

  @commands.has_permissions(administrator=True)
  async def bypass_add(self, ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT COUNT(*) FROM bypassed_users WHERE guild_id = ?", (ctx.guild.id,))
      count = await cursor.fetchone()

      if count[0] >= 30:
        embed = discord.Embed(description="You can only add up to 30 users to the bypass list.", color=self.color)
        await ctx.reply(embed=embed)
        return

      cursor = await db.execute("SELECT user_id FROM bypassed_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
      result = await cursor.fetchone()

      if result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {user.mention} is already in the bypass users list.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        await db.execute("INSERT INTO bypassed_users (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully added {user.mention} to the bypass users list.", color=self.color)
        await ctx.reply(embed=embed)

  @_bypass.command(name="remove", help="Removes a user from the bypass list.")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  async def bypass_remove(self, ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT user_id FROM bypassed_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
      result = await cursor.fetchone()

      if not result:
        embed = discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {user.mention} is not in the bypass users list.", color=self.color)
        await ctx.reply(embed=embed)
      else:
        await db.execute("DELETE FROM bypassed_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
        await db.commit()
        embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> Successfully removed {user.mention} from the bypass users list.", color=self.color)
        await ctx.reply(embed=embed)

  @_bypass.command(name="show", aliases=["list"], help="Displays the list of bypassed users.")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  async def bypass_show(self, ctx: commands.Context):
    async with aiosqlite.connect(self.db_path) as db:
      cursor = await db.execute("SELECT user_id FROM bypassed_users WHERE guild_id = ?", (ctx.guild.id,))
      users = await cursor.fetchall()

      if not users:
        embed = discord.Embed(description="No users are currently bypassed in this server.", color=self.color)
        await ctx.reply(embed=embed, mention_author=False)
      else:
        user_mentions = [ctx.guild.get_member(user_id).mention if ctx.guild.get_member(user_id) else f"User ID {user_id}" for user_id, in users]
        description = "\n".join(user_mentions)
        embed = discord.Embed(title="Bypassed Users", description=description, color=self.color)
        await ctx.reply(embed=embed, mention_author=False)

async def setup(client):
    await client.add_cog(Ignore(client))
