from discord.ext import commands
from core import Synapse, Cog
import discord
import logging
from discord.ui import View, Button, Select

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)

client = Synapse()

class Guild(Cog):
    def __init__(self, client: Synapse):
        self.client = client

    @client.event
    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_add(self, guild):
        try:

            rope = [inv for inv in await guild.invites() if inv.max_age == 0 and inv.max_uses == 0]
            ch = 1480765446478106626
            me = self.client.get_channel(ch)
            if me is None:
                logging.error(f"Channel with ID {ch} not found.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)

            embed.set_author(name="Guild Joined")
            embed.set_footer(text=f"Added in {guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner:** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            embed.add_field(
                name="**__Members__**",
                value=f"""Members : {len(guild.members)}\nHumans : {len(list(filter(lambda m: not m.bot, guild.members)))}\nBots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )  
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)  

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            await me.send(f"{rope[0]}" if rope else "No Pre-Made Invite Found", embed=embed)

            try:
                from utils.Tools import getConfig
                data = await getConfig(guild.id)
                prefix = data.get("prefix", ".") if data else "."
            except Exception:
                prefix = "."

            channel_to_send = None
            if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                channel_to_send = guild.system_channel
            else:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        channel_to_send = channel
                        break

            if channel_to_send:
                server_embed = discord.Embed(
                    title=f"Thanks for adding {self.client.user.name}!",
                    description=(
                        f"I'm an advanced multi-purpose bot designed to keep your server safe and active.\n\n"
                        f"<:rightarrow:1469267754409529394> **My Prefix:** `{prefix}`\n"
                        f"<:rightarrow:1469267754409529394> **Help Command:** `{prefix}help` or mention me `@{self.client.user.name}`\n\n"
                        f"Type `{prefix}help` to explore all my features and configuration options!"
                    ),
                    color=0x2b2d31,
                    timestamp=discord.utils.utcnow()
                )
                if self.client.user.display_avatar:
                    server_embed.set_thumbnail(url=self.client.user.display_avatar.url)
                if guild.icon:
                    server_embed.set_footer(text=f"Joined {guild.name}", icon_url=guild.icon.url)
                else:
                    server_embed.set_footer(text=f"Joined {guild.name}")

                from utils.config import serverLink
                view = View()
                if serverLink:
                    view.add_item(Button(label="Support Server", url=serverLink))
                view.add_item(Button(label="Invite Me", url=f"https://discord.com/api/oauth2/authorize?client_id={self.client.user.id}&permissions=8&scope=bot%20applications.commands"))

                try:
                    await channel_to_send.send(embed=server_embed, view=view)
                except discord.Forbidden:
                    pass

            adder = None
            try:
                if guild.me.guild_permissions.view_audit_log:
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                        if entry.target.id == self.client.user.id:
                            adder = entry.user
                            break
            except Exception:
                pass

            if not adder:
                adder = guild.owner

            if adder:
                user_embed = discord.Embed(
                    title="Thanks for inviting me!",
                    description=(
                        f"Hi {adder.mention}! Thank you so much for inviting **{self.client.user.name}** to **{guild.name}**.\n\n"
                        f"Here is some quick information to get you started:\n\n"
                        f"<:emoji_1769867605256:1467155817726873650> - **Default Prefix:** `{prefix}` (You can also mention me!)\n"
                        f"<:emoji_1769867605256:1467155817726873650> - **View Commands:** Type `{prefix}help` in the server.\n\n"
                        f"Take some time to configure my settings to better suit your community. If you need any help, please don't hesitate to reach out."
                    ),
                    color=0x2b2d31,
                    timestamp=discord.utils.utcnow()
                )
                if guild.icon:
                    user_embed.set_thumbnail(url=guild.icon.url)
                user_embed.set_footer(text=f"{self.client.user.name}", icon_url=self.client.user.display_avatar.url if self.client.user.display_avatar else None)

                from utils.config import serverLink
                view = View()
                if serverLink:
                    view.add_item(Button(label="Support Server", url=serverLink))
                view.add_item(Button(label="Invite Me", url=f"https://discord.com/api/oauth2/authorize?client_id={self.client.user.id}&permissions=8&scope=bot%20applications.commands"))

                try:
                    await adder.send(embed=user_embed, view=view)
                except discord.Forbidden:
                    pass

        except Exception as e:
            logging.error(f"Error in on_guild_join: {e}")

    @client.event
    @commands.Cog.listener(name="on_guild_remove")
    async def on_guild_remove(self, guild):
        try:
            ch = 1336379386244632648
            idk = self.client.get_channel(ch)
            if idk is None:
                logging.error(f"Channel with ID {ch} not found.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)

            embed.set_author(name="Guild Removed")
            embed.set_footer(text=f"{guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )


            embed.add_field(
                name="**__Members__**",
                value=f"""
Members : {len(guild.members)}
Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}
Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )   
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            await idk.send(embed=embed)
        except Exception as e:
            logging.error(f"Error in on_guild_remove: {e}")

async def setup(client):
    await client.add_cog(Guild(client))