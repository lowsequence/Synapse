from __future__ import annotations
from discord.ext import commands
from utils.config import BotName
from utils.Tools import *
from discord import *
import os
from utils.config import OWNER_IDS, No_Prefix
import json, discord
from typing import *
import sqlite3
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw, ImageChops
import typing
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
import time, datetime
from typing import Optional




class StaffManageView(discord.ui.LayoutView):
    def __init__(self, cog: "Owner", author_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id

        add_btn = discord.ui.Button(label="Add Staff", style=discord.ButtonStyle.success, custom_id="sm_add")
        remove_btn = discord.ui.Button(label="Remove Staff", style=discord.ButtonStyle.danger, custom_id="sm_remove")
        list_btn = discord.ui.Button(label="List Staff", style=discord.ButtonStyle.primary, custom_id="sm_list")

        add_btn.callback = self.add_callback
        remove_btn.callback = self.remove_callback
        list_btn.callback = self.list_callback

        header = discord.ui.TextDisplay("# <:Icon_Star:1477547731420581979> Staff Management\nUse the buttons below to manage bot staff.")

        container = discord.ui.Container(
            header,
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(add_btn, remove_btn, list_btn),
            accent_color=0x2f3136
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
            return False
        return True

    async def add_callback(self, interaction: discord.Interaction):
        class AddStaffModal(discord.ui.Modal, title="Add Staff Member"):
            user_id = discord.ui.TextInput(label="User ID", placeholder="Enter the user's Discord ID...", min_length=17, max_length=20)

            def __init__(self, view_obj):
                super().__init__()
                self.view_obj = view_obj

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    uid = int(self.user_id.value)
                except ValueError:
                    return await modal_interaction.response.send_message("Invalid ID format.", ephemeral=True)

                if uid in self.view_obj.cog.staff:
                    return await modal_interaction.response.send_message("This user is already staff.", ephemeral=True)

                try:
                    user = await modal_interaction.client.fetch_user(uid)
                except discord.NotFound:
                    return await modal_interaction.response.send_message("User not found.", ephemeral=True)

                self.view_obj.cog.staff.add(uid)
                async with aiosqlite.connect(self.view_obj.cog.db_path) as db:
                    await db.execute('INSERT OR IGNORE INTO staff (id) VALUES (?)', (uid,))
                    await db.commit()
                np_cog = modal_interaction.client.get_cog('NoPrefix')
                if np_cog:
                    np_cog.staff.add(uid)
                await modal_interaction.response.send_message(f"Added **{user}** to the staff list.", ephemeral=True)

        await interaction.response.send_modal(AddStaffModal(self))

    async def remove_callback(self, interaction: discord.Interaction):
        class RemoveStaffModal(discord.ui.Modal, title="Remove Staff Member"):
            user_id = discord.ui.TextInput(label="User ID", placeholder="Enter the user's Discord ID...", min_length=17, max_length=20)

            def __init__(self, view_obj):
                super().__init__()
                self.view_obj = view_obj

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    uid = int(self.user_id.value)
                except ValueError:
                    return await modal_interaction.response.send_message("Invalid ID format.", ephemeral=True)

                if uid not in self.view_obj.cog.staff:
                    return await modal_interaction.response.send_message("This user is not in the staff list.", ephemeral=True)

                self.view_obj.cog.staff.remove(uid)
                async with aiosqlite.connect(self.view_obj.cog.db_path) as db:
                    await db.execute('DELETE FROM staff WHERE id = ?', (uid,))
                    await db.commit()
                np_cog = modal_interaction.client.get_cog('NoPrefix')
                if np_cog:
                    np_cog.staff.discard(uid)
                await modal_interaction.response.send_message(f"Removed ID **{uid}** from the staff list.", ephemeral=True)

        await interaction.response.send_modal(RemoveStaffModal(self))

    async def list_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.cog.staff:
            return await interaction.followup.send("The staff list is currently empty.", ephemeral=True)

        member_list = []
        for staff_id in self.cog.staff:
            try:
                member = await interaction.client.fetch_user(staff_id)
                member_list.append(f"• **{member}** (`{staff_id}`)")
            except discord.NotFound:
                member_list.append(f"• Unknown User (`{staff_id}`)")

        desc = "\n".join(member_list)

        view = discord.ui.LayoutView(timeout=60)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"**Current Staff Members ({len(self.cog.staff)})**\n\n{desc}"),
                accent_color=0x2f3136
            )
        )
        await interaction.followup.send(view=view, ephemeral=True)

class Owner(commands.Cog):

  def __init__(self, client):
    self.client = client
    self.staff = set()
    self.np_cache = []
    self.db_path = 'database/np.db'
    self.color = 0x2f3136

  async def setup_database(self):
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute('''
          CREATE TABLE IF NOT EXISTS staff (
              id INTEGER PRIMARY KEY
          )
        ''')
        await db.commit()

  async def load_staff(self):
      await self.client.wait_until_ready()
      async with aiosqlite.connect(self.db_path) as db:
          async with db.execute('SELECT id FROM staff') as cursor:
              self.staff = {row[0] for row in await cursor.fetchall()}

  async def cog_load(self):
      await self.setup_database()
      self.client.loop.create_task(self.load_staff())


  @commands.command(name="mstaff", help="Open the Staff Management menu.")
  @commands.is_owner()
  async def staff_menu(self, ctx):
      view = StaffManageView(self, ctx.author.id)
      await ctx.send(view=view)


  @commands.command(name="slist")
  @commands.is_owner()
  async def _slist(self, ctx):
    vg = ["Void's Hub"]
    hasanop = ([hasan for hasan in self.client.guilds])
    hasanop = sorted(hasanop,
                     key=lambda hasan: hasan.member_count,
                     reverse=True)
    entries = [
      f"`[{i}]` | [{f'{BotName}’s Hub' if g.name in vg else g.name}](https://discord.com/channels/{g.id}) - {g.member_count} (ID: `{g.id}`)"
      for i, g in enumerate(hasanop, start=1)
    ]
    paginator = Paginator(source=DescriptionEmbedPaginator(
      entries=entries,
      description="",
      title=f"Server List of {self.client.user.name} - {len(self.client.guilds)}",
      color=self.color,
      per_page=10),
                          ctx=ctx)
    await paginator.paginate()

  @commands.command(name="synapse.restart", help="Restarts the client.")
  @commands.is_owner()
  async def _restart(self, ctx):
    embed = discord.Embed(
        description=f"| Restarting {self.client.user.name} .",
        color=discord.Colour(self.color))
    embed.set_author(name=ctx.author,icon_url=ctx.author.display_avatar.url)
    restart_program()
    await ctx.reply(embed=embed, mention_author=False)




  DEVELOPER_ID = 1368989570816802886

  @commands.group(name="owners", invoke_without_command=True)
  async def owners_group(self, ctx):
      """Manage bot owners — add, remove, or list."""
      if ctx.author.id != self.DEVELOPER_ID:
          return
      if ctx.invoked_subcommand is None:
          await ctx.invoke(self.owners_list)

  @owners_group.command(name="list")
  async def owners_list(self, ctx):
      """List all bot owners."""
      if ctx.author.id != self.DEVELOPER_ID:
          return
      with open("info.json") as f:
          data = json.load(f)
      owner_ids = data.get("OWNER_IDS", [])
      if not owner_ids:
          embed = discord.Embed(description="<:emoji_1769867589372:1467155751456735326> | The owner list is empty.", color=0xff4646)
          return await ctx.send(embed=embed)

      npl = [await self.client.fetch_user(uid) for uid in owner_ids]
      npl = sorted(npl, key=lambda u: u.created_at)
      entries = [
          f"`[{no}]` | [{mem}](https://discord.com/users/{mem.id}) (ID: {mem.id})"
          for no, mem in enumerate(npl, start=1)
      ]
      paginator = Paginator(source=DescriptionEmbedPaginator(
          entries=entries,
          title=f"Owner list of {self.client.user.name} — {len(owner_ids)}",
          description="",
          per_page=10,
          color=self.color),
                            ctx=ctx)
      await paginator.paginate()

  @owners_group.command(name="add")
  async def owners_add(self, ctx, user: discord.User):
      """Add a user to the bot owner list."""
      if ctx.author.id != self.DEVELOPER_ID:
          return
      with open("info.json", "r") as f:
          data = json.load(f)

      owner_ids = data.get("OWNER_IDS", [])
      if user.id in owner_ids:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | **{user}** is already a bot owner.", color=0xff4646)
          return await ctx.send(embed=embed)

      owner_ids.append(user.id)
      data["OWNER_IDS"] = owner_ids

      with open("info.json", "w") as f:
          json.dump(data, f, indent=4)

      self.client.owner_ids.add(user.id)

      embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | Added **{user}** (`{user.id}`) to the bot owner list.", color=0x4dff94)
      await ctx.send(embed=embed)

  @owners_group.command(name="remove")
  async def owners_remove(self, ctx, user: discord.User):
      """Remove a user from the bot owner list."""
      if ctx.author.id != self.DEVELOPER_ID:
          return
      if user.id == ctx.author.id:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | You cannot remove yourself from the owner list.", color=0xff4646)
          return await ctx.send(embed=embed)

      with open("info.json", "r") as f:
          data = json.load(f)

      owner_ids = data.get("OWNER_IDS", [])
      if user.id not in owner_ids:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | **{user}** is not in the bot owner list.", color=0xff4646)
          return await ctx.send(embed=embed)

      owner_ids.remove(user.id)
      data["OWNER_IDS"] = owner_ids

      with open("info.json", "w") as f:
          json.dump(data, f, indent=4)

      self.client.owner_ids.discard(user.id)

      embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | Removed **{user}** (`{user.id}`) from the bot owner list.", color=0x4dff94)
      await ctx.send(embed=embed)



  @commands.command()
  @commands.is_owner()
  async def dm(self, ctx, user: discord.User, *, message: str):
    """ DM the user of your choice """
    try:
      await user.send(message)
      await ctx.send(
        f"✅ | Successfully Sent a DM to **{user}**"
      )
    except discord.Forbidden:
      await ctx.send("This user might DMs blocked or it's a bot account")

  @commands.group()
  async def change(self, ctx):
    if ctx.invoked_subcommand is None:
      await ctx.send_help(str(ctx.command))

  @change.command(name="nickname")
  @commands.is_owner()
  async def change_nickname(self, ctx, *, name: str = None):
    """ Change nickname. """
    try:
      await ctx.guild.me.edit(nick=name)
      if name:
        await ctx.send(
          f"✅ | Successfully changed nickname to **{name}**"
        )
      else:
        await ctx.send(
          "✅ | Successfully removed nickname")
    except Exception as err:
      await ctx.send(err)



  @commands.command(name="sleave")
  @commands.is_owner()
  async def l(self, ctx, *, guild_id: int):
        g = self.client.get_guild(guild_id)
        if g is None:
            return await ctx.send(f"Guild with ID `{guild_id}` not found or the bot is not a member.")
        await g.leave()
        await ctx.send(f"Successfully left guild: `{g.name}` (ID: {g.id})")


  @commands.command(name="getinvite", help="Generate an invite link for a specific server.")
  @commands.is_owner()
  async def get_invite(self, ctx, guild_id: int):
      guild = self.client.get_guild(guild_id)
      if guild is None:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | Guild with ID `{guild_id}` not found or the bot is not a member.", color=0xff4646)
          return await ctx.send(embed=embed)

      for channel in guild.text_channels:
          if channel.permissions_for(guild.me).create_instant_invite:
              try:
                  invite = await channel.create_invite(max_age=86400, max_uses=1, unique=True, reason="Owner requested invite via getinvite command")
                  embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | Created invite for **{guild.name}**: {invite.url}", color=0x4dff94)
                  return await ctx.send(embed=embed)
              except discord.HTTPException:
                  continue

      embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | Could not create an invite for **{guild.name}**. I might lack permissions in all text channels.", color=0xff4646)
      await ctx.send(embed=embed)


  @commands.command(name="brahmastra", aliases=["globalban", "gban"], help="Bans a user across all servers the bot is in.")
  @commands.is_owner()
  async def brahmastra(self, ctx, user: discord.User, *, reason: str = "No reason provided."):
      banned_guilds = []
      failed_guilds = []

      msg = await ctx.send(f"Initiating Brahmastra on **{user}**...")

      for guild in self.client.guilds:
          try:
              await guild.ban(user, reason=f"Global Ban by Owner: {reason}")
              banned_guilds.append(guild.name)
          except discord.Forbidden:
              failed_guilds.append(guild.name)
          except discord.HTTPException:
              failed_guilds.append(guild.name)

      embed = discord.Embed(title="⚖️ Brahmastra (Global Ban) Completed", color=0x4dff94)
      embed.description = f"<:emoji_1769867605256:1467155817726873650> | Successfully executed global ban on **{user}** (`{user.id}`)."
      embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
      embed.add_field(name="Success", value=f"Banned from {len(banned_guilds)} servers.", inline=True)
      if failed_guilds:
         embed.add_field(name="Failed", value=f"Failed in {len(failed_guilds)} servers.", inline=True)

      await msg.edit(content=None, embed=embed)



  @commands.command(name="eval", help="Evaluates python code.")
  @commands.is_owner()
  async def _eval(self, ctx, *, code: str):
      code = code.strip('` ')
      if code.startswith('py'):
          code = code[2:].strip()

      env = {
          'ctx': ctx,
          'bot': self.client,
          'client': self.client,
          'channel': ctx.channel,
          'author': ctx.author,
          'guild': ctx.guild,
          'message': ctx.message,
          'discord': discord,
          'os': os,
          'json': json,
          'time': time,
          'datetime': datetime,
          'self': self
      }

      env.update(globals())

      stdout = io.StringIO()

      to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'

      try:
          exec(to_compile, env)
      except Exception as e:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | **Compilation Error:**\n```py\n{e.__class__.__name__}: {e}\n```", color=0xff4646)
          return await ctx.send(embed=embed)

      func = env['func']

      try:
          with contextlib.redirect_stdout(stdout):
              ret = await func()
      except Exception as e:
          value = stdout.getvalue()
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | **Execution Error:**\n```py\n{value}{traceback.format_exc()}\n```", color=0xff4646)
          return await ctx.send(embed=embed)
      else:
          value = stdout.getvalue()

          if ret is None:
              if value:
                  try:
                      embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **Execution Success:**\n```py\n{value}\n```", color=0x4dff94)
                      await ctx.send(embed=embed)
                  except discord.HTTPException:
                      await ctx.send(f"Result too long. Value length: {len(value)}")
              else:
                  embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **Execution Success:**\nNo output.", color=0x4dff94)
                  await ctx.send(embed=embed)
          else:
              try:
                  embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **Execution Success:**\n```py\n{value}{ret}\n```", color=0x4dff94)
                  await ctx.send(embed=embed)
              except discord.HTTPException:
                   await ctx.send(f"Result too long. Value length: {len(str(value) + str(ret))}")

  @commands.command(name="sql", help="Executes an SQL query against the database.")
  @commands.is_owner()
  async def _sql(self, ctx, *, query: str):
      query = query.strip('` ')
      if query.startswith('sql'):
          query = query[3:].strip()

      db_file = self.db_path

      try:
          res = None
          async with aiosqlite.connect(db_file) as db:
              async with db.execute(query) as cursor:
                  if query.lower().startswith('select') or query.lower().startswith('pragma'):
                      res = await cursor.fetchall()
                  else:
                      await db.commit()
                      res = f"Rows affected: {cursor.rowcount}"

          if isinstance(res, list):
              if not res:
                  embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **SQL Success:**\nNo rows returned.", color=0x4dff94)
              else:
                   formatted_res = ""
                   for row in res:
                       formatted_res += f"{row}\n"

                   if len(formatted_res) > 2000:
                       embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **SQL Success:**\nOutput too long to display cleanly. Found {len(res)} rows.", color=0x4dff94)
                   else:
                       embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **SQL Success:**\n```sql\n{formatted_res}\n```", color=0x4dff94)
          else:
               embed = discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> | **SQL Success:**\n{res}", color=0x4dff94)

          await ctx.send(embed=embed)

      except Exception as e:
          embed = discord.Embed(description=f"<:emoji_1769867589372:1467155751456735326> | **SQL Error:**\n```py\n{e}\n```", color=0xff4646)
          await ctx.send(embed=embed)


async def setup(client):
    await client.add_cog(Owner(client))