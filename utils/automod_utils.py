import discord
from discord.ext import commands
from datetime import datetime
import os

class Embeds:
    COLOR = 0x2b2d31
    FOOTER = "Synapse - AutoMod System"

    @staticmethod
    def success(text: str, footer: str = None) -> discord.Embed:
        embed = discord.Embed(
            description=f"> <:emoji_1769867605256:1467155817726873650> **Success:** {text}",
            color=Embeds.COLOR,
            timestamp=datetime.now()
        )
        embed.set_footer(text=footer or Embeds.FOOTER)
        return embed

    @staticmethod
    def error(text: str, footer: str = None) -> discord.Embed:
        embed = discord.Embed(
            description=f"> <:Lund:1464624797374873611> **Error:** {text}",
            color=Embeds.COLOR,
            timestamp=datetime.now()
        )
        embed.set_footer(text=footer or Embeds.FOOTER)
        return embed

    @staticmethod
    def info(title: str, text: str, footer: str = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"<:Synapse_search:1471871156783943812> {title}",
            description=f"{text}",
            color=Embeds.COLOR,
            timestamp=datetime.now()
        )
        embed.set_footer(text=footer or Embeds.FOOTER)
        return embed

    @staticmethod
    def config(title: str, fields: dict, footer: str = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"<:synapse_automod:1471871079256424550> {title} Configuration",
            color=Embeds.COLOR,
            timestamp=datetime.now()
        )
        desc = ""
        for key, value in fields.items():
            status = "Enabled" if value is True else "Disabled" if value is False else f"`{value}`"
            desc += f"- **{key}:** {status}\n"
        embed.description = desc
        embed.set_footer(text=footer or Embeds.FOOTER)
        return embed
