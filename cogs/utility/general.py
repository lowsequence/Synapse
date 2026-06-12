import asyncio
import discord
from discord.ext import commands, tasks
from discord.utils import get
import datetime
import random
import requests
import aiohttp
import re
from discord.ext.commands.errors import BadArgument
from discord.ext.commands import Cog
from discord.colour import Color
import hashlib
from utils.Tools import *
from traceback import format_exception
import discord
from discord.ext import commands
import datetime
from discord import ButtonStyle
from discord.ui import Button, View
import psutil
import time
from datetime import datetime, timezone, timedelta
import sqlite3
from typing import *
import string

lawda = [
  '8', '3821', '23', '21', '313', '43', '29', '76', '11', '9',
  '44', '470', '318' , '26', '69'
]



class AvatarView(discord.ui.View):
  def __init__(self, user, member, author_id, banner_url, timeout=70):
    super().__init__(timeout=timeout)
    self.user = user
    self.member = member
    self.author_id = author_id
    self.banner_url = banner_url

    if getattr(self.user, "avatar", None):
      if self.user.avatar.is_animated():
        self.add_item(discord.ui.Button(label='GIF', url=self.user.avatar.with_format('gif').url, style=discord.ButtonStyle.link, row=0))
      self.add_item(discord.ui.Button(label='PNG', url=self.user.avatar.with_format('png').url, style=discord.ButtonStyle.link, row=0))
      self.add_item(discord.ui.Button(label='JPEG', url=self.user.avatar.with_format('jpg').url, style=discord.ButtonStyle.link, row=0))
      self.add_item(discord.ui.Button(label='WEBP', url=self.user.avatar.with_format('webp').url, style=discord.ButtonStyle.link, row=0))

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user.id != self.author_id:
      await interaction.response.send_message(
        "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
        ephemeral=True
      )
      return False
    return True

  @discord.ui.button(label='Server Avatar', style=discord.ButtonStyle.success, custom_id='server_avatar_button', row=1)
  async def server_avatar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
    if not getattr(self.member, "guild_avatar", None):
      await interaction.response.send_message(
        "This user doesn't have a different guild avatar.",
        ephemeral=True
      )
    else:
      embed = interaction.message.embeds[0]
      embed.set_image(url=self.member.guild_avatar.url)
      await interaction.response.edit_message(embed=embed)

  @discord.ui.button(label='User Banner', style=discord.ButtonStyle.success, custom_id='banner_button', row=1)
  async def banner_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
    if not self.banner_url:
      await interaction.response.send_message(
        "This user doesn't have a banner.",
        ephemeral=True
      )
    else:
      embed = interaction.message.embeds[0]
      embed.set_image(url=self.banner_url)
      await interaction.response.edit_message(embed=embed)





class General(commands.Cog):

  def __init__(self, client, *args, **kwargs):
    self.client = client

    self.aiohttp = aiohttp.ClientSession()
    self._URL_REGEX = r'(?P<url><[^: >]+:\/[^ >]+>|(?:https?|steam):\/\/[^\s<]+[^<.,:;\"\'\]\s])'
    self.color = 0x000000


  @commands.hybrid_command(
    usage="Avatar <member>",
    name='avatar',
    aliases=['av'],
    help="Get User avater/Guild avatar & Banner of a user."
  )
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def _user(self, ctx, member: Optional[Union[discord.Member, discord.User]] = None):
    try:
      if member is None:
        member = ctx.author
      user = await self.client.fetch_user(member.id)

      banner_url = user.banner.url if user.banner else None

      avatar_url = user.avatar.url if getattr(user, "avatar", None) else user.default_avatar.url
      description = f"**Avatar & Banner Options:**"

      if getattr(user, "avatar", None):
        description += f"\n[`PNG`]({user.avatar.with_format('png').url}) | [`JPG`]({user.avatar.with_format('jpg').url}) | [`WEBP`]({user.avatar.with_format('webp').url})"
        if user.avatar.is_animated():
          description += f" | [`GIF`]({user.avatar.with_format('gif').url})"
      else:
        description += f"\n[`DEF`]({user.default_avatar.url})"

      if banner_url:
        description += f" | [`Banner`]({banner_url})"

      embed = discord.Embed(title=f"{member.display_name}'s Avatar", description=description, color=self.color)
      embed.set_image(url=avatar_url)
      embed.set_thumbnail(url=member.display_avatar.url)

      view = AvatarView(user, member, ctx.author.id, banner_url)

      await ctx.send(embed=embed, view=view)
    except Exception as e:
      print(f"Error: {e}")

  @commands.hybrid_command(
    name="servericon",
    help="Get the server icon",
    usage="Servericon"
  )
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def servericon(self, ctx: commands.Context):
    server = ctx.guild
    if server.icon is None:
      await ctx.reply("This server does not have an icon.")
      return

    webp = server.icon.replace(format='webp')
    jpg = server.icon.replace(format='jpg')
    png = server.icon.replace(format='png')

    description = f"**Icon Downloads:**\n[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
    if server.icon.is_animated():
      gif = server.icon.replace(format='gif')
      description += f" | [`GIF`]({gif})"

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"### {server.name}'s Icon\n{description}")
            ),
            discord.ui.MediaGallery(discord.UnfurledMediaItem(url=server.icon.url)),
            accent_color=self.color
        )
    )
    view.add_item(discord.ui.ActionRow(discord.ui.Button(label="Download Icon", url=server.icon.url, style=discord.ButtonStyle.link)))

    await ctx.send(view=view)



  @commands.hybrid_command(name="membercount",
                           help="Get total member count of the server",
                           usage="membercount",
                           aliases=["mc"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 2, commands.BucketType.user)
  async def membercount(self, ctx: commands.Context):
        total_members = len(ctx.guild.members)
        total_humans = len([member for member in ctx.guild.members if not member.bot])
        total_bots = len([member for member in ctx.guild.members if member.bot])

        online = len([member for member in ctx.guild.members if member.status == discord.Status.online])
        offline = len([member for member in ctx.guild.members if member.status == discord.Status.offline])
        idle = len([member for member in ctx.guild.members if member.status == discord.Status.idle])
        dnd = len([member for member in ctx.guild.members if member.status == discord.Status.do_not_disturb])



        view = discord.ui.LayoutView()
        metrics = (
            f"**Member Statistics**\n"
            f"> <:SynapseTotal:1478619843845685349>Total Members: `{total_members}`\n"
            f"> <:SynapseHuman:1478619793816027176> Total Humans: `{total_humans}`\n"
            f"> <:SynapseBot:1478619736559452293> Total Bots: `{total_bots}`\n\n"
            f"**Status Counts**\n"
            f"<:syon:1460238701060952096> Online: `{online}`  | <:syof:1460238775581151425> Offline: `{offline}`\n"
            f"<:synapseidle:1460238735223291980> Idle: `{idle}`  |  <:synapsednd:1460238675840471061> Dnd: `{dnd}`"
        )

        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(metrics),
                accent_color=0x2b2d31
            )
        )

        await ctx.send(view=view)

  @commands.hybrid_command(name="poll", usage="<message>")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def poll(self, ctx: commands.Context, *, message):
    author = ctx.author
    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"### Poll raised by {author.display_name}!\n> {message}"),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=author.avatar.url if author.avatar else author.default_avatar.url))
            ),
            accent_color=self.color
        )
    )
    msg = await ctx.send(view=view)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")


  @commands.command(name="hack",
    help="hack someone's discord account",
    usage="Hack <member>")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def hack(self, ctx: commands.Context, member: discord.Member):
    stringi = member.name
    min_length = 2
    max_length = 12
    length = random.randint(min_length, max_length)
    stringg = member.name
    remaining_length = length - len(stringg)
    all_chars = string.ascii_letters + string.digits + string.punctuation
    random_chars = random.choices(all_chars, k=remaining_length)

    password = stringg + ''.join(random_chars)

    lund = await ctx.send(f"Processing to Hack {member.mention}...")
    await asyncio.sleep(2)
    random_pass = random.choice(lawda)

    random_pass2 = ''.join(random.choices(string.ascii_letters + string.digits, k=3))

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                f"### Hacked {member.display_name}!\n\n"
                f"**User:** {member.mention}\n"
                f"**E-Mail:** {''.join(letter for letter in stringi if letter.isalnum())}{random_pass}@gmail.com\n"
                f"**Account Password:** {member.name}@{random_pass2}\n\n"
                f"*Hacked By: {ctx.author.display_name}*"
            ),
            accent_color=0x000000
        )
    )
    await ctx.send(view=view)
    await lund.delete()


  @commands.command(name="token", usage="<member>")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 2, commands.BucketType.user)
  async def token(self, ctx: commands.Context, user: discord.Member = None):
    list = [
      "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",
      "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "_"
      'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n',
      'ñ', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0',
      '1', '2', '3', '4', '5', '6', '7', '8', '9'
    ]
    token = random.choices(list, k=59)
    if user is None:
      user = ctx.author
      await ctx.send(user.mention + "'s token: " + ''.join(token))
    else:
      await ctx.send(user.mention + "'s token: " + "".join(token))

  @commands.command(name="users", help="checks total users of Synapse.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def users(self, ctx: commands.Context):
    users = sum(g.member_count for g in self.bot.guilds
                if g.member_count != None)
    guilds = len(self.client.guilds)

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"### Total Users of Synapse\nWatching over **{users}** users across **{guilds}** servers!"),
            accent_color=self.color
        )
    )
    await ctx.send(view=view)


  @commands.command(name="wizz", usage="")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def wizz(self, ctx: commands.Context):
    message6 = await ctx.send(
      f"`Wizzing {ctx.guild.name}, will take 22 seconds to complete`")
    message7 = await ctx.send(f"Changing all guild settings...")
    message5 = await ctx.send(f"Deleting **{len(ctx.guild.roles)}** Roles...")
    await asyncio.sleep(1)
    message4 = await ctx.send(
      f"Deleting **{len(ctx.guild.channels)}** Channels...")
    await asyncio.sleep(1)
    message3 = await ctx.send(f"Deleting Webhooks...")
    message2 = await ctx.send(f"Deleting emojis")
    await asyncio.sleep(1)
    message1 = await ctx.send(f"Installing Ban Wave..")
    await asyncio.sleep(1)
    await message6.delete()
    await message7.delete()
    await message5.delete()
    await message4.delete()
    await message3.delete()
    await message2.delete()
    await message1.delete()

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                f"### {self.client.user.name}\n"
                f"**Successfully Wizzed {ctx.guild.name}**\n\n"
                f"*Wizzed By {ctx.author.display_name}*"
            ),
            accent_color=0x2b2d31
        )
    )
    await ctx.send(view=view)


  @commands.hybrid_command(
    name="urban",
    description="Searches for specified phrase on urbandictionary",
    help="Get meaning of specified phrase",
    usage="Urban <phrase>")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def urban(self, ctx: commands.Context, *, phrase):
    async with self.aiohttp.get(
        "http://api.urbandictionary.com/v0/define?term={}".format(
          phrase)) as urb:
      urban = await urb.json()
      try:
        result = random.choice(urban['list'])
        def_text = result['definition'].replace('[', '').replace(']', '')
        ex_text = result['example'].replace('[', '').replace(']', '')
        author = result['author'].replace('[', '').replace(']', '')
        date = result['written_on'].replace('[', '').replace(']', '')

        view = discord.ui.LayoutView()
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"### Meaning of \"{phrase}\"\n"
                    f"**Definition:**\n{def_text}\n\n"
                    f"**Example:**\n{ex_text}\n\n"
                    f"**Author:** {author}\n"
                    f"**Written On:** {date}"
                ),
                accent_color=self.color
            )
        )
        temp = await ctx.reply(view=view, mention_author=True)
        await asyncio.sleep(45)
        await temp.delete()
        await ctx.message.delete()
      except:
        pass

  @commands.command(name="rickroll",
                           help="Detects if provided url is a rick-roll",
                           usage="Rickroll <url>")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def rickroll(self, ctx: commands.Context, *, url: str):
    if not re.match(self._URL_REGEX, url):
      raise BadArgument("Invalid URL")

    phrases = [
      "rickroll", "rick roll", "rick astley", "never gonna give you up"
    ]
    source = str(await (await self.aiohttp.get(
      url, allow_redirects=True)).content.read()).lower()
    rickRoll = bool((re.findall('|'.join(phrases), source,
                                re.MULTILINE | re.IGNORECASE)))

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                f"### Rick Roll Detection\n"
                f"Rick Roll **{'was found' if rickRoll else 'was not found'}** in the provided webpage."
            ),
            accent_color=0xff0000 if rickRoll else 0x00ff00
        )
    )

    await ctx.reply(view=view, mention_author=True)

  @commands.command(name="hash",
                           help="Hashes provided text with provided algorithm")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def hash(self, ctx: commands.Context, algorithm: str, *, message):
    algos: dict[str, str] = {
      "md5": hashlib.md5(bytes(message.encode("utf-8"))).hexdigest(),
      "sha1": hashlib.sha1(bytes(message.encode("utf-8"))).hexdigest(),
      "sha224": hashlib.sha224(bytes(message.encode("utf-8"))).hexdigest(),
      "sha3_224": hashlib.sha3_224(bytes(message.encode("utf-8"))).hexdigest(),
      "sha256": hashlib.sha256(bytes(message.encode("utf-8"))).hexdigest(),
      "sha3_256": hashlib.sha3_256(bytes(message.encode("utf-8"))).hexdigest(),
      "sha384": hashlib.sha384(bytes(message.encode("utf-8"))).hexdigest(),
      "sha3_384": hashlib.sha3_384(bytes(message.encode("utf-8"))).hexdigest(),
      "sha512": hashlib.sha512(bytes(message.encode("utf-8"))).hexdigest(),
      "sha3_512": hashlib.sha3_512(bytes(message.encode("utf-8"))).hexdigest(),
      "blake2b": hashlib.blake2b(bytes(message.encode("utf-8"))).hexdigest(),
      "blake2s": hashlib.blake2s(bytes(message.encode("utf-8"))).hexdigest()
    }

    desc = f"### Hashed \"{message}\"\n\n"
    if algorithm.lower() not in list(algos.keys()):
      for algo in list(algos.keys()):
        hashValue = algos[algo]
        desc += f"**{algo}**\n```\n{hashValue}```\n"
    else:
      desc += f"**{algorithm}**\n```\n{algos[algorithm.lower()]}```\n"

    view = discord.ui.LayoutView()
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(desc),
            accent_color=0x000000
        )
    )
    await ctx.reply(view=view, mention_author=True)


  @commands.command(name="invite",
                           aliases=['invite-bot'],
                           description="Get Support & Bot invite link!")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def invite(self, ctx: commands.Context):
    embed = discord.Embed(
        title="Synapse Invite & Support",
        description=(
            "- Hello! I'm **Synapse**, your comprehensive server security solution with advanced protection features.\n\n"
            "- Need help or want to add me to your server? Use the buttons below!"
        ),
        color=0x2b2d31
    )
    embed.set_footer(text="Synapse — The Ultimate Security Solution")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label='Add Synapse',
        style=discord.ButtonStyle.link,
        url='https://discord.com/oauth2/authorize?client_id=1482361945653903422&permissions=8&scope=bot%20applications.commands'
    ))
    view.add_item(discord.ui.Button(
        label='Support Server',
        style=discord.ButtonStyle.link,
        url='https://dsc.gg/astrex-dev'
    ))

    await ctx.send(embed=embed, view=view)



async def setup(client):
    await client.add_cog(General(client))
