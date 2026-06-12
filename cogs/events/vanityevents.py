import discord
from discord.ext import commands
import aiosqlite
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import io
import asyncio

DB_PATH = "database/vanityroles.db"
EMBED_COLOR = 0x2b2d31


class VanityRolesEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.cooldown = set()
        bot.loop.create_task(self.load_cache())

    async def load_cache(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT guild_id, vanity, role_id, log_channel_id, mode, enabled
                FROM vanity_roles
            """) as cursor:
                rows = await cursor.fetchall()

        for guild_id, vanity, role_id, channel_id, mode, enabled in rows:
            if enabled:
                self.cache[guild_id] = {
                    "vanity": str(vanity).strip().lower(),
                    "role_id": role_id,
                    "channel_id": channel_id,
                    "mode": mode
                }

    def has_vanity(self, member: discord.Member, vanity: str) -> bool:
        vanity = str(vanity).strip().lower()
        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                if activity.name and vanity in activity.name.lower():
                    return True
        return False

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.activities == after.activities:
            return

        cfg = self.cache.get(after.guild.id)
        if not cfg:
            return

        role = after.guild.get_role(cfg["role_id"])
        channel = after.guild.get_channel(cfg["channel_id"])
        if not role or not channel:
            return

        before_has = self.has_vanity(before, cfg["vanity"])
        after_has = self.has_vanity(after, cfg["vanity"])

        if after.id in self.cooldown:
            return

        if after_has and not before_has and role not in after.roles:
            self.cooldown.add(after.id)
            try:
                await after.add_roles(role, reason="Vanity detected in custom status")
                await self.send_add(after, role, cfg["vanity"], channel, cfg["mode"])
            except Exception:
                pass
            await asyncio.sleep(4)
            self.cooldown.discard(after.id)

        elif not after_has and before_has and role in after.roles:
            self.cooldown.add(after.id)
            try:
                await after.remove_roles(role, reason="Vanity removed from custom status")
                await self.send_remove(after, role, cfg["vanity"], channel, cfg["mode"])
            except Exception:
                pass
            await asyncio.sleep(4)
            self.cooldown.discard(after.id)

    async def generate_baatchit_image(self, member, main_text, vanity, is_remove=False):
        WIDTH, HEIGHT = 950, 320

        avatar_bytes = await member.display_avatar.read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

        bg = avatar.resize((WIDTH, HEIGHT))
        bg = bg.filter(ImageFilter.GaussianBlur(24))
        bg = ImageEnhance.Brightness(bg).enhance(0.32)

        draw = ImageDraw.Draw(bg)

        name_font = ImageFont.truetype("assets/fonts/Inter-SemiBold.ttf", 28)
        title_font = ImageFont.truetype("assets/fonts/Inter-Bold.ttf", 46)
        sub_font = ImageFont.truetype("assets/fonts/Inter-Regular.ttf", 22)

        AVATAR_SIZE = 190
        avatar_fg = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))

        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
        avatar_fg.putalpha(mask)

        AVATAR_X = 55
        AVATAR_Y = (HEIGHT - AVATAR_SIZE) // 2
        bg.paste(avatar_fg, (AVATAR_X, AVATAR_Y), avatar_fg)

        TEXT_X = 280

        draw.text(
            (TEXT_X, 90),
            member.display_name,
            font=name_font,
            fill=(220, 220, 220)
        )

        draw.text(
            (TEXT_X, 130),
            main_text.upper(),
            font=title_font,
            fill=(255, 215, 0)
        )

        subtitle = (
            f"Vanity {vanity} was removed from your status"
            if is_remove
            else f"Thanks for representing {vanity} in your status"
        )

        draw.text(
            (TEXT_X, 190),
            subtitle,
            font=sub_font,
            fill=(190, 190, 190)
        )

        buffer = io.BytesIO()
        bg.save(buffer, "PNG")
        buffer.seek(0)
        return buffer

    async def send_add(self, member, role, vanity, channel, mode):
        if mode == "message":
            await channel.send(
                f"{member.mention} has been awarded the **{role.name}** role "
                f"for proudly repping our vanity `{vanity}` in their status!"
            )

        elif mode == "embed":
            embed = discord.Embed(
                title="Vanity Added",
                description=f"Thanks for representing **{vanity}** in your status! 🤍",
                color=EMBED_COLOR
            )
            embed.add_field(name="🎯 Vanity Text", value=vanity, inline=False)
            embed.add_field(name="🏆 Role Earned", value=role.mention, inline=False)
            embed.add_field(name="📱 Detected In", value="Custom Status", inline=False)
            embed.set_footer(text="Keep the vanity text in your status to maintain the role!")
            await channel.send(content=member.mention, embed=embed)

        elif mode == "image":
            img = await self.generate_baatchit_image(
                member,
                "Vanityroles Added",
                vanity,
                is_remove=False
            )
            await channel.send(
                content=member.mention,
                file=discord.File(img, "vanity_add.png")
            )

    async def send_remove(self, member, role, vanity, channel, mode):
        if mode == "message":
            await channel.send(
                f"{member.mention} lost the **{role.name}** role "
                f"for removing `{vanity}` from their status."
            )

        elif mode == "embed":
            embed = discord.Embed(
                title="Vanity Removed",
                description=f"Vanity text **{vanity}** was removed from your status.",
                color=EMBED_COLOR
            )
            embed.add_field(name="🎯 Vanity Text", value=vanity, inline=False)
            embed.add_field(name="🏆 Role Lost", value=role.mention, inline=False)
            embed.add_field(name="💔 Reason", value="Vanity text not found in status", inline=False)
            embed.set_footer(text="Add the vanity text back to regain the role!")
            await channel.send(content=member.mention, embed=embed)

        elif mode == "image":
            img = await self.generate_baatchit_image(
                member,
                "Vanityroles Removed",
                vanity,
                is_remove=True
            )
            await channel.send(
                content=member.mention,
                file=discord.File(img, "vanity_remove.png")
            )


async def setup(bot):
    await bot.add_cog(VanityRolesEvent(bot))