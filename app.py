import os
from core.Synapse import Synapse
from utils.config import whCL, TOKEN
from discord.ext.commands import Context
from discord.ext import commands
import discord
import jishaku, cogs
from discord import app_commands
from lavalink import Client
import lavalink
import wavelink
from utils.database import init_db
import time
import aiohttp
import aiosqlite
import asyncio
try:
    import traceback
    from utils.Tools import *
    from discord import Webhook
except ModuleNotFoundError:
    os.system("pip install git+https://github.com/darknight156/jishaku")
    os.system("pip install git+https://github.com/Rapptz/discord-ext-menus")


os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"
os.environ["JISHAKU_OWNER_IDS"] = "1420658724992974971"

token = TOKEN



client = Synapse(help_command=None)

tree = client.tree




@client.command()
async def guildinfo(ctx, guild_id: int):
    guild = client.get_guild(guild_id)
    if not guild:
        await ctx.send("Guild not found!")
        return
    invite_links = await guild.invites()
    if invite_links:
        invite = invite_links[0]
        await ctx.send(f"Guild Invite Link: {invite.url}")
    else:
        await ctx.send("No active invite links found for this guild!")

@client.command()
async def find_guild(ctx, channel_id: int):
    channel = client.get_channel(channel_id)
    if channel:
        guild = channel.guild
        await ctx.send(f"Channel belongs to guild: {guild.name} (ID: {guild.id})")
    else:
        await ctx.send("Channel not found or not in cache!")

@client.event
async def on_ready():   
    print("Loaded & Online!")
    print(f"Logged in as: {client.user}")
    print(f"Connected to: {len(client.guilds)} guilds")
    print(f"Connected to: {len(client.users)} users")
    print("discord.py version:", discord.__version__)
    print("wavelink version:", wavelink.__version__)

@client.event
async def on_command(ctx):
    try:
        webhook_url = ""
        if not ctx.command:
            return

        server_name = ctx.guild.name if ctx.guild else "DMs"
        server_id = ctx.guild.id if ctx.guild else "N/A"
        channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "N/A"
        channel_id = ctx.channel.id
        user_name = ctx.author.name
        user_id = ctx.author.id
        command_name = ctx.command.qualified_name
        message_content = ctx.message.content

        embed = discord.Embed(
            title="Command Used \U0001f4e1",
            color=0x2b2d31,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{user_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
        embed.add_field(name="Command", value=f"`{command_name}`", inline=True)
        embed.add_field(name="Message", value=f"`{message_content}`", inline=False)
        embed.add_field(name="User", value=f"{user_name} (`{user_id}`)", inline=False)
        embed.add_field(name="Server", value=f"{server_name} (`{server_id}`)", inline=False)
        embed.add_field(name="Channel", value=f"{channel_name} (`{channel_id}`)", inline=False)

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, session=session)
            await webhook.send(embed=embed)
    except Exception as e:
        print(f"Command logger error: {e}")


async def load():
    for root, _, files in os.walk("cogs"):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                module_path = os.path.join(root, filename[:-3]).replace(os.sep, ".")
                await client.load_extension(module_path)    




async def main():
    os.makedirs("database", exist_ok=True)
    init_db()
    async with client:
        os.system("clear")
        await client.load_extension("jishaku")
        
        @client.check
        async def restrict_jishaku(ctx):
            if ctx.command and ctx.command.cog_name == "Jishaku":
                return ctx.author.id in [1368989570816802886, 190487452949938176, 1113016552623722497, 1482994688305791088]
            return True
            
        @client.check
        async def restrict_dms(ctx):
            if ctx.guild is None and ctx.command:
                if ctx.command.cog_name == "Jishaku":
                    return True
                if ctx.command.cog_name not in ["Emotes", "Entertainment"]:
                    return False
            return True

        @client.tree.interaction_check
        async def restrict_app_dms(interaction: discord.Interaction):
            if interaction.guild is None and interaction.command:
                cog = getattr(interaction.command, 'binding', None)
                cog_name = getattr(cog, "qualified_name", getattr(cog, "__cog_name__", type(cog).__name__)) if cog else None
                if cog_name not in ["Emotes", "Entertainment"]:
                    await interaction.response.send_message("This command cannot be used in DMs.", ephemeral=True)
                    return False
            return True

        await load()

        for cmd in client.tree.walk_commands():
            cog = getattr(cmd, 'binding', None)
            cog_name = getattr(cog, "qualified_name", getattr(cog, "__cog_name__", type(cog).__name__)) if cog else None
            if cog_name not in ["Emotes", "Entertainment"]:
                try:
                    cmd.allowed_contexts = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
                except Exception:
                    pass

        await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
