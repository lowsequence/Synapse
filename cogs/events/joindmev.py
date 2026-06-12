import discord
from discord.ext import commands
import asyncio
import time

from utils.joindm_helpers import (
    parse_variables,
    JoinDMDatabase
)


def validate_url(url: str) -> str | None:
    """Return the URL only if it's a valid HTTP URL."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None


class JoinDMEvent(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JoinDMDatabase()

        self.cooldown = {}
        self.COOLDOWN_SECONDS = 1
        self.GUILD_RATE_LIMIT = {}
        self.GUILD_RATE_TIME = 1.1

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        if member.bot:
            return

        data = await self.db.fetch(member.guild.id)
        if not data or not data.get("enabled", False):
            return

        now = time.time()
        if now - self.cooldown.get(member.id, 0) < self.COOLDOWN_SECONDS:
            return

        self.cooldown[member.id] = now

        if now - self.GUILD_RATE_LIMIT.get(member.guild.id, 0) < self.GUILD_RATE_TIME:
            return

        self.GUILD_RATE_LIMIT[member.guild.id] = now

        if data["mode"] == "message":
            raw = data.get("message", "")
            if raw:
                final = parse_variables(member, raw)
                try:
                    await member.send(final)
                except:
                    pass
            return

        embed = discord.Embed(
            title=parse_variables(member, data.get("embed_title", "") or ""),
            description=parse_variables(member, data.get("embed_description", "") or ""),
            color=data.get("embed_color") or 0x2F3136
        )

        if data.get("embed_author"):
            author_name = parse_variables(member, data["embed_author"])

            raw_icon = data.get("embed_author_icon", "") or ""
            parsed_icon = parse_variables(member, raw_icon)
            icon = validate_url(parsed_icon)

            if icon:
                embed.set_author(name=author_name, icon_url=icon)
            else:
                embed.set_author(name=author_name)

        if data.get("embed_footer"):
            foot_text = parse_variables(member, data["embed_footer"])

            raw_ficon = data.get("embed_footer_icon", "") or ""
            parsed_ficon = parse_variables(member, raw_ficon)
            footer_icon = validate_url(parsed_ficon)

            if footer_icon:
                embed.set_footer(text=foot_text, icon_url=footer_icon)
            else:
                embed.set_footer(text=foot_text)

        if data.get("embed_thumbnail"):
            raw_thumb = data["embed_thumbnail"]
            parsed = parse_variables(member, raw_thumb)
            url = validate_url(parsed)
            if url:
                embed.set_thumbnail(url=url)

        if data.get("embed_image"):
            raw_img = data["embed_image"]
            parsed = parse_variables(member, raw_img)
            url = validate_url(parsed)
            if url:
                embed.set_image(url=url)

        for field in data.get("embed_fields", []):
            name = parse_variables(member, field.get("name", ""))
            value = parse_variables(member, field.get("value", ""))
            inline = field.get("inline", False)

            if name.strip() and value.strip():
                embed.add_field(name=name, value=value, inline=inline)

        try:
            await member.send(embed=embed)
        except:
            pass


async def setup(bot):
    await bot.add_cog(JoinDMEvent(bot))