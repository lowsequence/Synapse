import os 
import discord
from discord.ext import commands
import datetime
import sys
from discord.ui import Button, View
import psutil
import time
from utils.Tools import *
from discord.ext import commands, menus
from discord.ext.commands import BucketType, cooldown
import requests
from typing import *
from utils import *
from utils.config import BotName, serverLink
from utils.Tools import getConfig
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from core import Cog, Synapse, Context
from typing import Optional
import aiosqlite 
import asyncio
import aiohttp


start_time = time.time()


def datetime_to_seconds(thing: datetime.datetime):
  current_time = datetime.datetime.fromtimestamp(time.time())
  return round(
    round(time.time()) +
    (current_time - thing.replace(tzinfo=None)).total_seconds())

tick = "<:emoji_1769867605256:1467155817726873650>"
cross = "<:emoji_1769867589372:1467155751456735326>"


class RoleInfoView(View):
  def __init__(self, role: discord.Role, author_id):
    super().__init__(timeout=180)
    self.role = role
    self.author_id = author_id

  @discord.ui.button(label='Show Permissions', emoji="<:SynapseOverwrites:1478624613947932804>", style=discord.ButtonStyle.secondary)
  async def show_permissions(self, interaction: discord.Interaction, button: Button):
    if interaction.user.id != self.author_id:
          await interaction.response.send_message("Uh oh! That message doesn't belong to you. You must run this command to interact with it.", ephemeral=True)
          return

    permissions = [perm.replace("_", " ").title() for perm, value in self.role.permissions if value]
    permission_text = ", ".join(permissions) if permissions else "None"
    embed = discord.Embed(title=f"Permissions for {self.role.name}", description=permission_text or "No permissions.", color=self.role.color)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

class Extra(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0x2b2d31
    self.start_time = datetime.datetime.now()

  @commands.hybrid_group(name="banner", aliases=["bn"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def banner(self, ctx):
    if ctx.invoked_subcommand is not None:
        return
    help_cog = ctx.bot.get_cog("Help")
    return await help_cog.send_group_help_auto(ctx, ctx.command)






  @banner.command(name="server", aliases=["s", "guild", "g"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  async def server(self, ctx):
    if not ctx.guild.banner:
      await ctx.reply(f"{cross} This server doesn't have a banner.")
    else:
      webp = ctx.guild.banner.replace(format='webp')
      jpg = ctx.guild.banner.replace(format='jpg')
      png = ctx.guild.banner.replace(format='png')
      embed_desc = f"**Icon Downloads:**\n[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
      if ctx.guild.banner.is_animated():
          embed_desc += f" | [`GIF`]({ctx.guild.banner.replace(format='gif')})"

      embed = discord.Embed(title=f"{ctx.guild.name}'s Banner", description=embed_desc, color=0x2b2d31)
      embed.set_image(url=ctx.guild.banner.url)
      embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png")

      await ctx.reply(embed=embed)


  @banner.command(name="user", aliases=["u", "member", "m"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _user(self,
                  ctx,
                  member: Optional[Union[discord.Member,
                                         discord.User]] = None):
    if member == None or member == "":
      member = ctx.author
    bannerUser = await self.bot.fetch_user(member.id)
    if not bannerUser.banner:
      await ctx.reply("{} | {} doesn't have a banner.".format(cross, member))
    else:
      webp = bannerUser.banner.replace(format='webp')
      jpg = bannerUser.banner.replace(format='jpg')
      png = bannerUser.banner.replace(format='png')
      embed_desc = f"**Banner Downloads:**\n[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
      if bannerUser.banner.is_animated():
          embed_desc += f" | [`GIF`]({bannerUser.banner.replace(format='gif')})"

      embed = discord.Embed(title=f"{member.display_name}'s Banner", description=embed_desc, color=0x2b2d31)
      embed.set_image(url=bannerUser.banner.url)
      embed.set_thumbnail(url=member.display_avatar.url)

      await ctx.send(embed=embed)





  @commands.command(name="uptime", description="Shows the bot's Uptime.")
  @blacklist_check() 
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def uptime(self, ctx):

      pfp = ctx.author.display_avatar.url

      uptime_seconds = int(round(time.time() - start_time))

      uptime_timedelta = datetime.timedelta(seconds=uptime_seconds)

      uptime_duration_string = str(uptime_timedelta)
      view = discord.ui.LayoutView()
      view.add_item(
          discord.ui.Container(
              discord.ui.Section(
                  discord.ui.TextDisplay(f"### Synapse Uptime\n<:Latency:1470724764816638179> **Online Duration:** ``{uptime_duration_string}``"),
                  accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=pfp))
              ),
              accent_color=0x2b2d31
          )
      )

      await ctx.send(view=view)






  @commands.command(name="boostcount",
                    help="Shows boosts count",
                    aliases=["bc"],
                    with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def boosts(self, ctx):
    guild = ctx.guild
    current = guild.premium_subscription_count
    current_level = guild.premium_tier

    thresholds = [2, 7, 14]
    tier_names = ["Level 1", "Level 2", "Level 3"]
    tier_perks = [
        "50 Emoji Slots · 128kbps Audio · Custom Invite BG",
        "100 Emoji Slots · 256kbps Audio · Server Banner · 50MB Upload",
        "250 Emoji Slots · 384kbps Audio · Vanity URL · 100MB Upload",
    ]

    bar_length = 20
    if current_level >= 3:
        filled = bar_length
        progress_pct = 100
        next_text = "Maximum boost level reached"
        target = thresholds[-1]
    else:
        target = thresholds[current_level]
        prev = thresholds[current_level - 1] if current_level > 0 else 0
        segment_progress = current - prev
        segment_total = target - prev
        progress_pct = min(100, int((segment_progress / segment_total) * 100)) if segment_total > 0 else 0
        filled = int((progress_pct / 100) * bar_length)
        needed = target - current
        next_text = f"**{needed}** more boost{'s' if needed != 1 else ''} needed for **{tier_names[current_level]}**"

    bar = "▰" * filled + "▱" * (bar_length - filled)

    tier_display = ""
    for i, (thresh, name, perk) in enumerate(zip(thresholds, tier_names, tier_perks)):
        if i < current_level:
            marker = "<:emoji_1769867605256:1467155817726873650>"
        elif i == current_level and current_level < 3:
            marker = "<:SynapseBoost2:1478620777564864667>"
        else:
            marker = "⠀⠀"
        tier_display += f"{marker} **{name}** — {thresh} boosts\n-# {perk}\n"

    boosters = sorted(guild.premium_subscribers, key=lambda m: m.premium_since or datetime.datetime.min, reverse=True)[:5]
    if boosters:
        recent_lines = "\n".join(
            f"> {m.mention} — <t:{int(m.premium_since.timestamp())}:R>"
            for m in boosters if m.premium_since
        )
        recent_section = f"\n**Recent Boosters**\n{recent_lines}"
    else:
        recent_section = ""

    desc = (
        f"### <:SynapseBoost:1478618644014698526> Server Boosts\n"
        f"`{bar}` **{progress_pct}%**\n\n"
        f"> **Boosts** ─ `{current}` ⠀ **Tier** ─ `Level {current_level}` ⠀ **Boosters** ─ `{len(guild.premium_subscribers)}`\n\n"
        f"<:SynapseBoost2:1478620777564864667> {next_text}\n\n"
        f"{tier_display}"
        f"{recent_section}"
    )

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(desc),
                accessory=discord.ui.Thumbnail(
                    discord.UnfurledMediaItem(url=guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png")
                )
            ),
            accent_color=0x2b2d31
        )
    )
    await ctx.send(view=view)





  @commands.hybrid_group(name="list",
                         invoke_without_command=True,
                         with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def __list_(self, ctx: commands.Context):
    if ctx.invoked_subcommand is not None:
        return
    help_cog = ctx.bot.get_cog("Help")
    return await help_cog.send_group_help_auto(ctx, ctx.command)



  @__list_.command(name="boosters",
                   aliases=["boost", "booster"],
                   help="List of boosters in the Guild",
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_boost(self, ctx):
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{round(mem.premium_since.timestamp())}:R>"
      for no, mem in enumerate(guild.premium_subscribers, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=
      f"List of Boosters in {guild.name} - {len(guild.premium_subscribers)}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="bans", help= "List of all banned members in Guild", aliases=["ban"], with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(view_audit_log=True)
  @commands.bot_has_permissions(view_audit_log=True)
  async def list_ban(self, ctx):
    bans = [member async for member in ctx.guild.bans()]
    if len(bans) == 0:
      return await ctx.reply("There aren't any banned users in this guild.", mention_author=False)
    else:
      mems = ([
      member async for member in ctx.guild.bans()
    ])
      guild = ctx.guild
      entries = [
      f"`#{no}.` {mem}"
      for no, mem in enumerate(mems, start=1)
    ]
      paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Banned Users in {guild.name} - {len(bans)}",
      description="",
      per_page=10),
                          ctx=ctx)
      await paginator.paginate()

  @__list_.command(
    name="inrole",
    aliases=["inside-role"],
    help="List of members that are in the specified role",
    with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_inrole(self, ctx, role: discord.Role):
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(role.members, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"List of Members in {role} - {len(role.members)}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="emojis",
                   aliases=["emoji"],
                   help="List of emojis in the Guild with ids",
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_emojis(self, ctx):
    guild = ctx.guild
    entries = [
      f"`#{no}.` {e} - `{e}`"
      for no, e in enumerate(ctx.guild.emojis, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"List of Emojis in {guild.name} - {len(ctx.guild.emojis)}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="roles",
                   aliases=["role"],
                   help="List of all roles in the server with ids",
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_roles=True)
  async def list_roles(self, ctx):
    guild = ctx.guild
    entries = [
      f"`#{no}.` {e.mention} - `[{e.id}]`"
      for no, e in enumerate(ctx.guild.roles, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"List of Roles in {guild.name} - {len(ctx.guild.roles)}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="bots",
                   aliases=["bot"],
                   help="List of All bots in a server",
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_bots(self, ctx):
    guild = ctx.guild
    people = filter(lambda member: member.bot, ctx.guild.members)
    people = sorted(people, key=lambda member: member.joined_at)
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}]"
      for no, mem in enumerate(people, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"bots in {guild.name} - {len(people)}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="admins",
                   aliases=["admin"],
                   help="List of all Admins of the Guild",
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_admin(self, ctx):
    mems = ([
      mem for mem in ctx.guild.members
      if mem.guild_permissions.administrator
    ])
    mems = sorted(mems, key=lambda mem: not mem.bot)
    admins = len([
      mem for mem in ctx.guild.members
      if mem.guild_permissions.administrator
    ])
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Admins in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="invoice", help="List of all users in a voice channel", aliases=["invc"], with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def listusers(self, ctx):
    if not ctx.author.voice:
      return await ctx.send("You are not connected to a voice channel")
    members = ctx.author.voice.channel.members
    entries = [
      f"`[{n}]` | {member} [{member.mention}]"
      for n, member in enumerate(members, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      description="",
      title=f"Voice List of {ctx.author.voice.channel.name} - {len(members)}",
      color=0x2b2d31),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="moderators", help= "List of All Admins of a server", aliases=["mods"], with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_mod(self, ctx):
    membs = ([
      mem for mem in ctx.guild.members
      if mem.guild_permissions.ban_members
      or mem.guild_permissions.kick_members
    ])
    mems = filter(lambda member: member.bot, ctx.guild.members)
    mems = sorted(membs, key=lambda mem: mem.joined_at)
    admins = len([
      mem for mem in ctx.guild.members
      if mem.guild_permissions.ban_members
      or mem.guild_permissions.kick_members
    ])
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Mods in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="early", aliases=["sup"], help= "List of members that have Early Supporter badge.", with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_early(self, ctx):
    mems = ([
      memb for memb in ctx.guild.members
      if memb.public_flags.early_supporter
    ])
    mems = sorted(mems, key=lambda memb: memb.created_at)
    admins = len([
      memb for memb in ctx.guild.members
      if memb.public_flags.early_supporter
    ])
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id})  [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Early Supporters Id's in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="activedeveloper", help= "List of members that have Active Developer badge.",
                   aliases=["activedev"],
                   with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_activedeveloper(self, ctx):
    mems = ([
      memb for memb in ctx.guild.members
      if memb.public_flags.active_developer
    ])
    mems = sorted(mems, key=lambda memb: memb.created_at)
    admins = len([
      memb for memb in ctx.guild.members
      if memb.public_flags.active_developer
    ])
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Active Developer Id's in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="createdat", help= "List of Account Creation Date of all Users", with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_cpos(self, ctx):
    mems = ([memb for memb in ctx.guild.members])
    mems = sorted(mems, key=lambda memb: memb.created_at)
    admins = len([memb for memb in ctx.guild.members])
    guild = ctx.guild
    entries = [
      f"`[{no}]` | [{mem}](https://discord.com/users/{mem.id}) - <t:{int(mem.created_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Creation every id in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @__list_.command(name="joinedat", help= "List of Guild Joined date of all Users", with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def list_joinpos(self, ctx):
    mems = ([memb for memb in ctx.guild.members])
    mems = sorted(mems, key=lambda memb: memb.joined_at)
    admins = len([memb for memb in ctx.guild.members])
    guild = ctx.guild
    entries = [
      f"`#{no}.` [{mem}](https://discord.com/users/{mem.id}) Joined At - <t:{int(mem.joined_at.timestamp())}:D>"
      for no, mem in enumerate(mems, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      title=f"Join Position of every user in {guild.name} - {admins}",
      description="",
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()




  @commands.command(name="joined-at",
                    help="Shows when a user joined",
                    usage="joined-at [user]",
                    with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def joined_at(self, ctx):
    joined = ctx.author.joined_at.strftime("%a, %d %b %Y %I:%M %p")
    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"### Joined At\n**`{joined}`**"),
            accent_color=0x2b2d31
        )
    )
    await ctx.send(view=view)

  @commands.command(name="github", usage="github [search]")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def github(self, ctx, *, search_query):
    json = requests.get(
      f"https://api.github.com/search/repositories?q={search_query}").json()

    if json["total_count"] == 0:
      await ctx.send(f"No matching repositories found with the name: {search_query}")
    else:
      view = discord.ui.LayoutView()
      view.add_item(
          discord.ui.Container(
              discord.ui.TextDisplay(
                  f"### GitHub Search\n"
                  f"Found result for '{search_query}':\n"
                  f"{json['items'][0]['html_url']}"
              ),
              accent_color=0x2b2d31
          )
      )
      await ctx.send(view=view)

  @commands.hybrid_command(name="vcinfo",
                           description="View information about a voice channel.",
                           help="View information about a voice channel.", 
                           usage="<VoiceChannel>",
                           with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def vcinfo(self, ctx, channel: discord.VoiceChannel = None):
    if channel is None:
      await ctx.reply(f"{cross} Please provide a valid voice channel.")
      return
    desc = (
        f"### Voice Channel Info for: {channel.name}\n"
        f"**<:SynapseInfo:1478618076961439806> General Information**\n"
        f"> **ID:** `{channel.id}`\n"
        f"> **Members:** `{len(channel.members)}`\n"
        f"> **Bitrate:** `{channel.bitrate/1000} kbps`\n"
        f"> **Created At:** `{channel.created_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"> **Category:** `{channel.category.name if channel.category else 'None'}`\n"
        f"> **Region:** `{channel.rtc_region}`\n"
    )

    if channel.user_limit:
        desc += f"> **User Limit:** `{channel.user_limit}`\n"

    overwrites_str = ""
    if channel.overwrites:
      overwrites = []
      for role, permissions in channel.overwrites.items():
        overwrites.append(f"> **{role}**: {permissions}")
      overwrites_str = "\n".join(overwrites)

    view = discord.ui.LayoutView()
    items = [discord.ui.TextDisplay(desc)]

    if overwrites_str:
        items.extend([
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"**<:SynapseOverwrites:1478624613947932804> Overwrites**\n{overwrites_str}")
        ])

    join_btn = discord.ui.Button(label="Join", style=discord.ButtonStyle.green, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}")
    inv_btn = discord.ui.Button(label="Invite", style=discord.ButtonStyle.link, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/invite")

    items.extend([
        discord.ui.Separator(),
        discord.ui.ActionRow(join_btn, inv_btn)
    ])

    view.add_item(
        discord.ui.Container(
            *items,
            accent_color=0x2b2d31
        )
    )

    await ctx.send(view=view)


  @commands.hybrid_command(name="channelinfo",
     aliases=['cinfo', 'ci'],
     description='Get information about a channel.',
     help='Get information about a channel.',
     usage="<Channel>",
     with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def channelinfo(self, ctx, channel: discord.TextChannel = None):
    if channel is None:
      channel = ctx.channel

    desc = (
        f"### Channel Info - {channel.name}\n"
        f"**<:SynapseInfo:1478618076961439806> Details**\n"
        f"> **ID:** `{channel.id}`\n"
        f"> **Created At:** `{channel.created_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"> **Category:** `{channel.category.name if channel.category else 'None'}`\n"
        f"> **Topic:** `{channel.topic if channel.topic else 'None'}`\n"
        f"> **Slowmode:** `{channel.slowmode_delay} seconds`\n" if channel.slowmode_delay else f"> **Slowmode:** `None`\n"
        f"> **NSFW:** `{channel.is_nsfw()}`"
    )

    overwrites_view = discord.ui.LayoutView()
    redirect_btn = discord.ui.Button(label="Redirect Channel", style=discord.ButtonStyle.green, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}")

    show_ovr_btn = discord.ui.Button(label='Show Overwrites', style=discord.ButtonStyle.primary)

    async def show_overwrites_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("Uh oh! That message doesn't belong to you. You must run this command to interact with it.", ephemeral=True)
            return

        overwrites = []
        for target, perms in channel.overwrites.items():
            permissions = {
                "View Channel": perms.view_channel,
                "Send Messages": perms.send_messages,
                "Read Message History": perms.read_message_history,
                "Manage Messages": perms.manage_messages,
                "Embed Links": perms.embed_links,
                "Attach Files": perms.attach_files,
                "Manage Channels": perms.manage_channels,
                "Manage Permissions": perms.manage_permissions,
                "Manage Webhooks": perms.manage_webhooks,
                "Create Instant Invite": perms.create_instant_invite,
                "Add Reactions": perms.add_reactions,
                "Mention Everyone": perms.mention_everyone,
                "Kick Members": perms.kick_members,
                "Ban Members": perms.ban_members,
                "Moderate Members": perms.moderate_members,
                "Send TTS Messages": perms.send_tts_messages,
                "Use External Emojis": perms.external_emojis,
                "Use External Stickers": perms.external_stickers,
                "View Audit Log": perms.view_audit_log,
                "Voice Mute Members": perms.mute_members,
                "Voice Deafen Members": perms.deafen_members,
                "Administrator": perms.administrator
            }

            overwrites.append(f"**For {target.name}**\n" +
                              "\n".join(f"  * **{perm}:** {'<:emoji_1769867605256:1467155817726873650>' if value else '<:emoji_1769867589372:1467155751456735326>' if value is False else '<:SynapseInfo:1478618076961439806>'}" for perm, value in permissions.items()))

        new_ephemeral = discord.ui.LayoutView(timeout=180)
        desc_ovr = "\n".join(overwrites) if overwrites else "No overwrites for this channel."

        items = []
        if len(desc_ovr) > 2000:
            parts = [desc_ovr[i:i+2000] for i in range(0, len(desc_ovr), 2000)]
            for part in parts[:3]:
                items.append(discord.ui.TextDisplay(part))
        else:
            items.append(discord.ui.TextDisplay(f"### Overwrites for {channel.name}\n{desc_ovr}"))

        new_ephemeral.add_item(discord.ui.Container(*items, accent_color=discord.Color.blurple().value))
        await interaction.response.send_message(view=new_ephemeral, ephemeral=True)

    show_ovr_btn.callback = show_overwrites_callback

    overwrites_view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(desc),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url="https://cdn.discordapp.com/emojis/1205345282158501899.png"))
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"*Requested By {ctx.author.display_name}*"),
            discord.ui.Separator(),
            discord.ui.ActionRow(show_ovr_btn, redirect_btn),
            accent_color=0x2b2d31
        )
    )

    await ctx.send(view=overwrites_view)


  @commands.command(name="ping", aliases=['latency'],
                      help="Checks the bot latency.",
                      with_app_command=True)
  @ignore_check()
  @blacklist_check()
  @commands.cooldown(1, 2, commands.BucketType.user)
  async def ping(self, ctx):
    s_id = ctx.guild.shard_id
    sh = self.bot.get_shard(s_id)
    start_time = time.perf_counter()
    end_time = time.perf_counter()
    response_time = round((end_time - start_time) * 10000000, 3)
    latency = self.bot.latency * 1000
    shard_id = ctx.guild.shard_id if ctx.guild else 0
    shard_latency = round(self.bot.latencies[shard_id][1] * 1000, 3)

    users = sum(g.member_count for g in self.bot.guilds
                if g.member_count != None)
    db_latency = None
    try:
      async with aiosqlite.connect("afk_data.db") as db:
        start_time = time.perf_counter()
        await db.execute("SELECT 1")
        end_time = time.perf_counter()
        db_latency = (end_time - start_time) * 1000
        db_latency = round(db_latency, 2)
    except Exception as e:
      print(f"Error measuring database latency: {e}")
      db_latency = "N/A"

    desc = (
        f"### Synapse Latency\n"
        f"**- Server Latency Details**\n"
        f"```API Latency: {latency:.3f}ms\n"
        f"Database Latency: {db_latency}ms\n"
        f"Response Time: {response_time:.3f}ms```\n\n"
        f"**- Shard Details**\n"
        f"```Latency: {shard_latency:.3f}ms\n"
        f"Status: Online\n"
        f"Ratelimited: No```"
    )

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(desc),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=ctx.author.display_avatar.url))
            ),
            accent_color=self.color
        )
    )

    await ctx.reply(view=view)


  @commands.command(name="permissions", aliases= ["perms"],
                           help="Check and list the key permissions of a specific user",
                           usage="perms <user>",
                           with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def keyperms(self, ctx, member: discord.Member):
    key_permissions = []

    if member.guild_permissions.create_instant_invite:
      key_permissions.append("Create Instant Invite")
    if member.guild_permissions.kick_members:
      key_permissions.append("Kick Members")
    if member.guild_permissions.ban_members:
      key_permissions.append("Ban Members")
    if member.guild_permissions.administrator:
      key_permissions.append("Administrator")
    if member.guild_permissions.manage_channels:
      key_permissions.append("Manage Channels")
    if member.guild_permissions.manage_messages:
      key_permissions.append("Manage Messages")
    if member.guild_permissions.mention_everyone:
      key_permissions.append("Mention Everyone")
    if member.guild_permissions.manage_nicknames:
      key_permissions.append("Manage Nicknames")
    if member.guild_permissions.manage_roles:
      key_permissions.append("Manage Roles")
    if member.guild_permissions.manage_webhooks:
      key_permissions.append("Manage Webhooks")
    if member.guild_permissions.manage_emojis:
      key_permissions.append("Manage Emojis")
    if member.guild_permissions.manage_guild:
      key_permissions.append("Manage Server")
    if member.guild_permissions.manage_permissions:
      key_permissions.append("Manage Permissions")
    if member.guild_permissions.manage_threads:
      key_permissions.append("Manage Threads")
    if member.guild_permissions.moderate_members:
      key_permissions.append("Moderate Members")
    if member.guild_permissions.move_members:
      key_permissions.append("Move Members")
    if member.guild_permissions.mute_members:
      key_permissions.append("Mute Members (VC)")
    if member.guild_permissions.deafen_members:
      key_permissions.append("Deafen Members")
    if member.guild_permissions.priority_speaker:
      key_permissions.append("Priority Speaker")
    if member.guild_permissions.stream:
      key_permissions.append("Stream")




    permissions_list = ", ".join(key_permissions) if key_permissions else "None"

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                f"### Here are the Key Permissions of {member.display_name}\n"
                f"**Key Permissions**\n"
                f"> {permissions_list}"
            ),
            accent_color=0x2b2d31
        )
    )

    await ctx.reply(view=view)






  @commands.hybrid_command(name="report",
                           aliases=["bug"],
                           usage='Report <bug>',
                           description='Report a bug to the Development team.',
                           help='Report a bug to the Development team.',
                           with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 30, commands.BucketType.channel)
  async def report(self, ctx, *, bug):
    channel = self.bot.get_channel(1460229146927173674)
    report_desc = (
        f"### Bug Reported\n"
        f"**Bug:** {bug}\n\n"
        f"**<:SynapseInfo:1478618076961439806> Details**\n"
        f"> **Reported By:** `{ctx.author.name}`\n"
        f"> **Server:** `{ctx.guild.name}`\n"
        f"> **Channel:** `{ctx.channel.name}`"
    )

    report_view = discord.ui.LayoutView()
    report_view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(report_desc),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url="https://cdn.discordapp.com/emoji"))
            ),
            accent_color=0x2b2d31
        )
    )
    await channel.send(view=report_view)
    confirm_view = discord.ui.LayoutView()
    confirm_view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("### Bug Reported\nThank you for reporting the bug. We will look into it."),
            accent_color=0x2b2d31
        )
    )
    await ctx.reply(view=confirm_view)

async def setup(bot):
    await bot.add_cog(Extra(bot))