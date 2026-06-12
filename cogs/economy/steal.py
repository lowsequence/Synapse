import discord
from discord.ext import commands
from discord.ui import View, Button
import requests
from io import BytesIO
import re
import traceback,sys
import io
from utils.logging import logger
from utils.Tools import *

class Steal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="steal",
        help="Can Be Used To Steal Emoji/Multiple Emojis From A Server"
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(rate=3,per=10,type=commands.BucketType.user)
    async def steal_command(self,ctx:commands.Context,*emojis:discord.PartialEmoji):
        try:
            if not ctx.author.guild_permissions.manage_emojis:
                return await ctx.send(embed=discord.Embed(description="You lack `Manage Emojis` Permission To Run This Command."),delete_after=10)

            if not emojis:
                replied_message = ctx.message.reference
                if not replied_message:
                    return await ctx.send(embed=discord.Embed(description="Please Provide Some Custom Emojis To Steal or Reply To A Message With Custom Stickers"),delete_after=10)

                reply_message = await ctx.channel.fetch_message(replied_message.message_id)
                if not reply_message:
                    return await ctx.send(embed=discord.Embed(description="Please Provide Some Custom Emojis To Steal or Reply To A Message With Custom Stickers"),delete_after=10)

                stickers = reply_message.stickers

                if not stickers:
                    raw_emojis = re.findall(r'<a?:\w+:\d+>',reply_message.content)
                    stickers = []
                    for raw_emoji in raw_emojis:
                        try:
                            emoji = await commands.PartialEmojiConverter().convert(ctx,raw_emoji)
                            if emoji:
                                stickers.append(emoji)
                        except Exception as e:
                            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
                            logger.warning(f"Failed To Convert Emoji {raw_emoji} Error: {e}")
                    if not stickers:
                        return await ctx.send(embed=discord.Embed(description="Please Provide Some Custom Emojis To Steal or Reply To A Message With Custom Stickers"),delete_after=10)




                view_timeout_time = 60
                cancled = False
                added=False
                added_title=None

                async def get_embed():
                    sticker = stickers[current_page_index]
                    embed = discord.Embed(
                        title="Add as Emoji or Sticker" if not added else added_title,

                    )
                    embed.set_image(url=sticker.url)
                    embed.set_footer(
                        text=f"{current_page_index+1}/{len(stickers)} Stickers",
                        icon_url=ctx.bot.user.display_avatar.url
                    )
                    return embed

                current_page_index = 0
                async def get_view(disabled=False):
                    view = discord.ui.View(timeout=60)

                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.grey,
                        label="Previous",
                        row=1,
                        disabled=current_page_index <= 0
                    )
                    previous_button.callback = lambda i: previous_button_callback(i)
                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.red,
                        emoji="<:Trash:1462771196885074002>",
                        row=1
                    )
                    stop_button.callback = lambda i: stop_button_callback(i)
                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.grey,
                        label="Next",
                        row=1,
                        disabled=current_page_index >= len(stickers)-1
                    )
                    next_button.callback = lambda i: next_button_callback(i)


                    add_as_emoji_button = discord.ui.Button(
                        label="Add as Emoji",
                        style=discord.ButtonStyle.green,
                        row=0
                    )
                    add_as_emoji_button.callback = lambda i: add_as_emoji_button_callback(i)
                    add_as_sticker_button = discord.ui.Button(
                        label="Add as Sticker",
                        style=discord.ButtonStyle.green,
                        row=0
                    )
                    add_as_sticker_button.callback = lambda i: add_as_sticker_button_callback(i)

                    if not added:
                        view.add_item(add_as_emoji_button)
                        view.add_item(add_as_sticker_button)
                    if len(stickers) > 1:
                        view.add_item(previous_button)
                        view.add_item(next_button)
                    if disabled:
                        for item in view.children:
                            item.disabled = True
                    return view

                async def previous_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal current_page_index
                    current_page_index -= 1
                    await interaction.response.edit_message(embed=await get_embed(),view=await get_view())

                async def stop_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal cancled
                    cancled = True
                    await interaction.response.edit_message(
                        view=await get_view(True)
                    )

                async def next_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal current_page_index
                    current_page_index += 1
                    await interaction.response.edit_message(embed=await get_embed(),view=await get_view())

                async def add_as_emoji_button_callback(interaction:discord.Interaction):
                    try:
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)

                        await interaction.response.edit_message(
                            embed=discord.Embed(title=None,description="Adding as Emoji"),
                            view=None
                        )

                        added_emojis = []
                        failed_emojis = []

                        for sticker in stickers:
                            try:
                                added_emoji = await ctx.guild.create_custom_emoji(name=sticker.name.strip("_"),image=await sticker.read(),reason=f"Emoji Added By {ctx.author.name}")
                                added_emojis.append(added_emoji)
                            except Exception as e:
                                failed_emojis.append(sticker)
                                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
                                logger.warning(f"Falied To Add Emoji {sticker.name} To The Server {ctx.guild.name} By {ctx.author.name} Error: {e}")

                        nonlocal added,added_title
                        added = True
                        added_title = f"Emojis Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60
                        )
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

                async def add_as_sticker_button_callback(interaction:discord.Interaction):
                    try:
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)

                        await interaction.response.edit_message(
                            embed=discord.Embed(title=None,description="Adding as Sticker"),
                            view=None
                        )

                        added_stickers = []
                        failed_stickers = []

                        for sticker in stickers:
                            try:
                                image_bytes = await sticker.read()

                                image_file = discord.File(io.BytesIO(image_bytes), filename=f"{sticker.name}.{'png'}")

                                added_sticker = await ctx.guild.create_sticker(
                                    name=sticker.name,
                                    emoji="🤖",
                                    description=f"Sticker Added By {ctx.author.name}",
                                    reason=f"Sticker Added By {ctx.author.name}",
                                    file=image_file
                                )
                                added_stickers.append(added_sticker)
                            except Exception as e:
                                failed_stickers.append(sticker)
                                logger.warning(f"Falied To Add Sticker {sticker.name} To The Server {ctx.guild.name} By {ctx.author.name} Error: {e}")

                        nonlocal added,added_title
                        added = True
                        added_title = f"{self.bot.emoji.SUCCESS} - Stickers Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60
                        )
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

                message = await ctx.send(embed=await get_embed(),view=await get_view())

                while not cancled:
                    view_timeout_time -= 1
                    if view_timeout_time <= 0:
                        await message.edit(view=await get_view(True))
                        break
                    await asyncio.sleep(1)

            else:
                for emoji in emojis:
                    if not emoji.is_custom_emoji():
                        return await ctx.send(embed=discord.Embed(description="Please Provide Some Custom Emojis To Steal"),delete_after=10)

                view_timeout_time = 60
                cancled = False
                added=False
                added_title=None

                async def get_embed():
                    emoji = emojis[current_page_index]
                    embed = discord.Embed(
                        title="Add as Emoji or Sticker" if not added else added_title,
                    )
                    embed.set_image(url=emoji.url)
                    embed.set_footer(
                        text=f"{current_page_index+1}/{len(emojis)} Emojis",
                        icon_url=ctx.bot.user.display_avatar.url
                    )
                    return embed

                current_page_index = 0


                async def get_view(disabled=False):
                    view = discord.ui.View(timeout=65)

                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.grey,
                        label="Previous",
                        row=1,
                        disabled=current_page_index <= 0
                    )
                    previous_button.callback = lambda i: previous_button_callback(i)
                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.red,
                        emoji="<:Trash:1462771196885074002>",
                        row=1
                    )
                    stop_button.callback = lambda i: stop_button_callback(i)
                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.grey,
                        label="Next",
                        row=1,
                        disabled=current_page_index >= len(emojis)-1
                    )
                    next_button.callback = lambda i: next_button_callback(i)


                    add_as_emoji_button = discord.ui.Button(
                        label="Add as Emoji",
                        style=discord.ButtonStyle.green,
                        row=0
                    )
                    add_as_emoji_button.callback = lambda i: add_as_emoji_button_callback(i)
                    add_as_sticker_button = discord.ui.Button(
                        label="Add as Sticker",
                        style=discord.ButtonStyle.green,
                        row=0
                    )
                    add_as_sticker_button.callback = lambda i: add_as_sticker_button_callback(i)

                    if not added:
                        view.add_item(add_as_emoji_button)
                        view.add_item(add_as_sticker_button)
                    if len(emojis) > 1:
                        view.add_item(previous_button)
                        view.add_item(next_button)
                    if disabled:
                        for item in view.children:
                            item.disabled = True
                    return view

                async def previous_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal current_page_index
                    current_page_index -= 1
                    await interaction.response.edit_message(embed=await get_embed(),view=await get_view())

                async def stop_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal cancled
                    cancled = True
                    await interaction.response.edit_message(
                        view=await get_view(True)
                    )

                async def next_button_callback(interaction:discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)
                    nonlocal current_page_index
                    current_page_index += 1
                    await interaction.response.edit_message(embed=await get_embed(),view=await get_view())



                async def add_as_emoji_button_callback(interaction:discord.Interaction):
                    try:
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)


                        await interaction.response.edit_message(
                            embed=discord.Embed(title=None,description="Adding as Emoji"),
                            view=None
                        )

                        added_emojis = []
                        failed_emojis = []

                        for emoji in emojis:
                            try:
                                added_emoji = await ctx.guild.create_custom_emoji(name=emoji.name,image=await emoji.read(),reason=f"Emoji Added By {ctx.author.name}")
                                added_emojis.append(added_emoji)
                            except Exception as e:
                                failed_emojis.append(emoji)
                                logger.warning(f"Falied To Add Emoji {emoji.name} To The Server {ctx.guild.name} By {ctx.author.name} Error: {e}")

                        nonlocal added,added_title
                        added = True
                        added_title = f"<:emoji_1769867605256:1467155817726873650> - Emojis Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60
                        )
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

                async def add_as_sticker_button_callback(interaction:discord.Interaction):
                    try:
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(embed=discord.Embed(description="You Can't Interact With This Button"),ephemeral=True,delete_after=10)


                        await interaction.response.edit_message(
                            embed=discord.Embed(title=None,description="Adding as Sticker"),
                            view=None
                        )

                        added_stickers = []
                        failed_stickers = []

                        for emoji in emojis:
                            try:
                                image_bytes = await emoji.read()

                                image_file = discord.File(io.BytesIO(image_bytes), filename=f"{emoji.name}.{'gif' if emoji.animated else 'png'}")

                                added_sticker = await ctx.guild.create_sticker(
                                    name=emoji.name,
                                    emoji="🤖",
                                    description=f"Sticker Added By {ctx.author.name}",
                                    reason=f"Sticker Added By {ctx.author.name}",
                                    file=image_file
                                )
                                added_stickers.append(added_sticker)
                            except Exception as e:
                                failed_stickers.append(emoji)
                                logger.warning(f"Falied To Add Sticker {emoji.name} To The Server {ctx.guild.name} By {ctx.author.name} Error: {e}")

                        nonlocal added,added_title
                        added = True
                        added_title = f"<:emoji_1769867605256:1467155817726873650> - Stickers Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60
                        )
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

                message = await ctx.send(embed=await get_embed(),view=await get_view())
                while not cancled:
                    view_timeout_time -= 1
                    if view_timeout_time <= 0:
                        await message.edit(view=await get_view(True))
                        break
                    await asyncio.sleep(1)

        except Exception as e:
            await(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

async def setup(client):
    await client.add_cog(Steal(client))
