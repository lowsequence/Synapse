import discord
from discord.ext import commands
import aiosqlite
import asyncio
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

DB_PATH     = "database/tagroles.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


class TagRoleEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.cooldown = set()
        bot.loop.create_task(self.load_cache())

    async def load_cache(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id, role_id, log_channel_id, mode, enabled FROM tag_roles"
            ) as cursor:
                rows = await cursor.fetchall()

        for guild_id, role_id, channel_id, mode, enabled in rows:
            if enabled:
                self.cache[guild_id] = {
                    "role_id": role_id,
                    "channel_id": channel_id,
                    "mode": mode,
                }

    @staticmethod
    def has_tag(member: discord.Member, tag: str) -> bool:
        name = (member.nick or member.name).lower()
        return tag in name

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick == after.nick and before.name == after.name:
            return

        cfg = self.cache.get(after.guild.id)
        if not cfg:
            return

        if getattr(after.guild, "clan", None) is None or getattr(after.guild.clan, "tag", None) is None:
            return

        guild_tag = after.guild.clan.tag.lower()

        role    = after.guild.get_role(cfg["role_id"])
        channel = after.guild.get_channel(cfg["channel_id"])
        if not role or not channel:
            return

        before_has = self.has_tag(before, guild_tag)
        after_has  = self.has_tag(after,  guild_tag)

        if after.id in self.cooldown:
            return

        if after_has and not before_has and role not in after.roles:
            self.cooldown.add(after.id)
            try:
                await after.add_roles(role, reason="Clan tag detected in name")
                await self.send_add(after, role, guild_tag, channel, cfg["mode"])
            except Exception:
                pass
            await asyncio.sleep(4)
            self.cooldown.discard(after.id)

        elif not after_has and before_has and role in after.roles:
            self.cooldown.add(after.id)
            try:
                await after.remove_roles(role, reason="Clan tag removed from name")
                await self.send_remove(after, role, guild_tag, channel, cfg["mode"])
            except Exception:
                pass
            await asyncio.sleep(4)
            self.cooldown.discard(after.id)

    async def generate_tag_image(self, member: discord.Member, main_text: str, tag: str, is_remove: bool = False):
        WIDTH, HEIGHT = 950, 320

        avatar_bytes = await member.display_avatar.read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

        bg = avatar.resize((WIDTH, HEIGHT))
        bg = bg.filter(ImageFilter.GaussianBlur(24))
        bg = ImageEnhance.Brightness(bg).enhance(0.32)

        draw = ImageDraw.Draw(bg)

        name_font  = ImageFont.truetype("assets/fonts/Inter-SemiBold.ttf", 28)
        title_font = ImageFont.truetype("assets/fonts/Inter-Bold.ttf", 46)
        sub_font   = ImageFont.truetype("assets/fonts/Inter-Regular.ttf", 22)

        AVATAR_SIZE = 190
        avatar_fg   = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
        mask  = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
        avatar_fg.putalpha(mask)

        AVATAR_X = 55
        AVATAR_Y = (HEIGHT - AVATAR_SIZE) // 2
        bg.paste(avatar_fg, (AVATAR_X, AVATAR_Y), avatar_fg)

        TEXT_X = 280

        draw.text((TEXT_X, 90), member.display_name, font=name_font, fill=(220, 220, 220))

        draw.text((TEXT_X, 130), main_text.upper(), font=title_font, fill=(255, 215, 0))

        subtitle = (
            f"Tag [{tag}] was removed from your name"
            if is_remove
            else f"Thanks for repping [{tag}] in your name"
        )
        draw.text((TEXT_X, 190), subtitle, font=sub_font, fill=(190, 190, 190))

        buffer = io.BytesIO()
        bg.save(buffer, "PNG")
        buffer.seek(0)
        return buffer

    async def send_add(self, member: discord.Member, role: discord.Role, tag: str, channel: discord.TextChannel, mode: str):
        if mode == "message":
            await channel.send(
                f"{member.mention} has been awarded the **{role.name}** role "
                f"for repping `{tag}` in their name!"
            )

        elif mode == "embed":
            embed = discord.Embed(
                description=(
                    f"Thanks for repping **{tag}** in your name! 🤍\n\n"
                    f"> 🏷️ **Tag:** `{tag}`\n"
                    f"> 🏆 **Role Earned:** {role.mention}\n"
                    f"> 📱 **Detected In:** Username / Nickname"
                ),
                color=EMBED_COLOR,
            )
            embed.set_author(name="Tag Detected — Role Added", icon_url=member.display_avatar.url)
            embed.set_footer(text="Keep the tag in your name to maintain the role!")
            await channel.send(content=member.mention, embed=embed)

        elif mode == "image":
            img = await self.generate_tag_image(member, "Tag Role Added", tag, is_remove=False)
            await channel.send(content=member.mention, file=discord.File(img, "tag_add.png"))

    async def send_remove(self, member: discord.Member, role: discord.Role, tag: str, channel: discord.TextChannel, mode: str):
        if mode == "message":
            await channel.send(
                f"{member.mention} lost the **{role.name}** role "
                f"for removing `{tag}` from their name."
            )

        elif mode == "embed":
            embed = discord.Embed(
                description=(
                    f"Tag **{tag}** was removed from your name.\n\n"
                    f"> 🏷️ **Tag:** `{tag}`\n"
                    f"> 🏆 **Role Lost:** {role.mention}\n"
                    f"> 💔 **Reason:** Tag not found in name"
                ),
                color=EMBED_COLOR,
            )
            embed.set_author(name="Tag Removed — Role Revoked", icon_url=member.display_avatar.url)
            embed.set_footer(text="Add the tag back to your name to regain the role!")
            await channel.send(content=member.mention, embed=embed)

        elif mode == "image":
            img = await self.generate_tag_image(member, "Tag Role Removed", tag, is_remove=True)
            await channel.send(content=member.mention, file=discord.File(img, "tag_remove.png"))


async def setup(bot):
    await bot.add_cog(TagRoleEvent(bot))
