import discord
from discord.ext import commands
import aiosqlite
import json
import os
import io
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageOps
import aiohttp

DB_PATH = os.path.join("database", "welcomer.db")
FONT_PATH = os.path.join("assets", "fonts", "Inter-Bold.ttf")

def get_ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"

class VariableReplacer:
    def __init__(self, member: discord.Member):
        self.member = member
        self.guild = member.guild
        self.user = member

    def replace(self, text: str) -> str:
        if not text: return text

        text = text.replace("{user}", str(self.user))
        text = text.replace("{user_id}", str(self.user.id))
        text = text.replace("{user_name}", self.user.name)
        text = text.replace("{user_tag}", str(self.user))
        text = text.replace("{user_discriminator}", getattr(self.user, 'discriminator', '0'))
        text = text.replace("{user_mention}", self.user.mention)
        text = text.replace("{user_avatar}", self.user.avatar.url if self.user.avatar else self.user.default_avatar.url)
        text = text.replace("{user_avatar_png}", (self.user.avatar.with_format('png').url if self.user.avatar else self.user.default_avatar.url))

        text = text.replace("{server}", self.guild.name)
        text = text.replace("{server_id}", str(self.guild.id))
        text = text.replace("{server_membercount}", str(self.guild.member_count))
        text = text.replace("{server_icon}", self.guild.icon.url if self.guild.icon else "")
        text = text.replace("{server_icon_png}", self.guild.icon.with_format('png').url if self.guild.icon else "")
        text = text.replace("{server_banner}", self.guild.banner.url if self.guild.banner else "")
        text = text.replace("{server_banner_png}", self.guild.banner.with_format('png').url if self.guild.banner else "")

        owner = self.guild.owner
        text = text.replace("{guild_owner}", str(owner) if owner else "Unknown")
        text = text.replace("{guild_owner_id}", str(owner.id) if owner else "0")
        text = text.replace("{guild_owner_mention}", owner.mention if owner else "")

        text = text.replace("{joined_at}", self.member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if self.member.joined_at else "")
        text = text.replace("{created_at}", self.member.created_at.strftime("%Y-%m-%d %H:%M:%S"))

        text = text.replace("{boost_count}", str(self.guild.premium_subscription_count))
        text = text.replace("{boost_tier}", str(self.guild.premium_tier))

        text = text.replace("{member_position}", str(self.guild.member_count))
        text = text.replace("{member_count_ordinal}", get_ordinal(self.guild.member_count))

        return text

class GreetEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def fetch_image(self, url: str) -> Image.Image:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
        except:
            pass
        img = Image.new("RGBA", (256, 256), (44, 47, 51, 255))
        return img

    async def generate_card(self, member: discord.Member, config: dict) -> discord.File:
        replacer = VariableReplacer(member)
        card_type = config.get("card_type", 1)

        try:
            font_title = ImageFont.truetype(FONT_PATH, 55)
            font_subtitle = ImageFont.truetype(FONT_PATH, 35)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()

        avatar_url = member.avatar.with_format('png').with_size(1024).url if member.avatar else member.default_avatar.url
        avatar = await self.fetch_image(str(avatar_url))

        from PIL import ImageFilter
        w, h = avatar.size
        if w / h > (1000 / 350):
            new_w = int(h * (1000 / 350))
            left = (w - new_w) / 2
            bg = avatar.crop((left, 0, left + new_w, h)).resize((1000, 350), Image.Resampling.LANCZOS)
        else:
            new_h = int(w * (350 / 1000))
            top = (h - new_h) / 2
            bg = avatar.crop((0, top, w, top + new_h)).resize((1000, 350), Image.Resampling.LANCZOS)

        base = bg.filter(ImageFilter.GaussianBlur(15))
        dark_overlay = Image.new("RGBA", (1000, 350), (0, 0, 0, 160))
        base.paste(dark_overlay, (0, 0), dark_overlay)
        draw = ImageDraw.Draw(base)

        avatar_small = avatar.resize((200, 200), Image.Resampling.LANCZOS)
        mask = Image.new("L", (200, 200), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 200, 200), fill=255)
        avatar_round = Image.composite(avatar_small, Image.new("RGBA", avatar_small.size, (0, 0, 0, 0)), mask)

        top_text_raw = config.get("card_text", config.get("message", "Welcome"))
        top_text = replacer.replace(top_text_raw)
        mid_text = replacer.replace("{user_name}")
        pill_text = replacer.replace("MEMBER #{server_membercount}")

        import re
        def resolve_mention(match):
            uid = int(match.group(1))
            m = member.guild.get_member(uid)
            return f"@{m.name}" if m else "@User"

        top_text = re.sub(r'<@!?(\d+)>', resolve_mention, top_text)
        mid_text = re.sub(r'<@!?(\d+)>', resolve_mention, mid_text)

        overlay = Image.new("RGBA", (1000, 350), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        box_rect = [(40, 20), (960, 330)]
        glass_fill = (10, 10, 15, 120)
        glass_outline = (180, 180, 200, 50)

        if card_type == 1:
            ava_pos, text_x, align, ava_size = (80, 75), 330, "left", 200
            overlay_draw.rounded_rectangle(box_rect, radius=25, fill=glass_fill, outline=glass_outline, width=2)

        elif card_type == 2:
            ava_pos, text_x, align, ava_size = (720, 75), 670, "right", 200
            overlay_draw.rounded_rectangle(box_rect, radius=25, fill=glass_fill, outline=glass_outline, width=2)

        elif card_type == 3:
            ava_pos, text_x, align, ava_size = (420, 30), 500, "center", 160
            overlay_draw.rounded_rectangle(box_rect, radius=25, fill=glass_fill, outline=glass_outline, width=2)

        elif card_type == 4:
            ava_pos, text_x, align, ava_size = (80, 75), 920, "right", 200
            overlay_draw.rounded_rectangle(box_rect, radius=25, fill=glass_fill, outline=glass_outline, width=2)

        else:
            ava_pos, text_x, align, ava_size = (80, 75), 330, "left", 200
            overlay_draw.rounded_rectangle(box_rect, radius=25, fill=glass_fill, outline=glass_outline, width=2)

        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        def get_fitted_font(text: str, max_width: int, max_font_size: int, font_path: str = FONT_PATH) -> ImageFont.FreeTypeFont:
            size = max_font_size
            while size > 15:
                try: font = ImageFont.truetype(font_path, size)
                except: return ImageFont.load_default()
                if draw.textlength(text, font=font) <= max_width: return font
                size -= 2
            try: return ImageFont.truetype(font_path, 15)
            except: return ImageFont.load_default()

        avatar_small = avatar.resize((ava_size, ava_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (ava_size, ava_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, ava_size, ava_size), fill=255)
        avatar_round = Image.composite(avatar_small, Image.new("RGBA", avatar_small.size, (0, 0, 0, 0)), mask)

        ax, ay = ava_pos
        tx = text_x

        base.paste(avatar_round, (ax, ay), avatar_round)
        draw.ellipse((ax-3, ay-3, ax+ava_size+3, ay+ava_size+3), outline=(220, 220, 230, 255), width=6)

        font_top = get_fitted_font(top_text, 600, 35)
        font_mid = get_fitted_font(mid_text, 600, 65)
        font_pill = get_fitted_font(pill_text, 200, 25)

        w_top = draw.textlength(top_text, font=font_top)
        w_mid = draw.textlength(mid_text, font=font_mid)
        w_pill = draw.textlength(pill_text, font=font_pill)

        pill_fill = (45, 45, 60, 200)
        pill_outline = (90, 90, 120, 255)
        pill_text_color = (180, 180, 210, 255)

        if align == "left":
            y_top, y_mid, y_line, y_pill = 100, 145, 235, 250
            draw.text((tx, y_top), top_text, font=font_top, fill=(180, 180, 180, 255))
            draw.text((tx, y_mid), mid_text, font=font_mid, fill=(255, 255, 255, 255))
            draw.line([(tx, y_line), (tx + max(w_top, w_mid, 200), y_line)], fill=(100, 100, 110, 255), width=2)

            pill_pad = 15
            pill_rect = [(tx, y_pill), (tx + w_pill + pill_pad*2, y_pill + 35)]
            draw.rounded_rectangle(pill_rect, radius=17, fill=pill_fill, outline=pill_outline, width=1)
            draw.text((tx + pill_pad, y_pill + 4), pill_text, font=font_pill, fill=pill_text_color)

        elif align == "right":
            y_top, y_mid, y_line, y_pill = 100, 145, 235, 250
            draw.text((tx - w_top, y_top), top_text, font=font_top, fill=(180, 180, 180, 255))
            draw.text((tx - w_mid, y_mid), mid_text, font=font_mid, fill=(255, 255, 255, 255))
            draw.line([(tx - max(w_top, w_mid, 200), y_line), (tx, y_line)], fill=(100, 100, 110, 255), width=2)

            pill_pad = 15
            pill_w = w_pill + pill_pad*2
            pill_rect = [(tx - pill_w, y_pill), (tx, y_pill + 35)]
            draw.rounded_rectangle(pill_rect, radius=17, fill=pill_fill, outline=pill_outline, width=1)
            draw.text((tx - pill_w + pill_pad, y_pill + 4), pill_text, font=font_pill, fill=pill_text_color)

        elif align == "center":
            y_top, y_mid, y_line, y_pill = 195, 230, 305, 315
            y_pill = 310
            draw.text((tx - w_top/2, y_top), top_text, font=font_top, fill=(180, 180, 180, 255))
            draw.text((tx - w_mid/2, y_mid), mid_text, font=font_mid, fill=(255, 255, 255, 255))

            line_w = max(w_top, w_mid, 200)
            draw.line([(tx - line_w/2, y_line), (tx + line_w/2, y_line)], fill=(100, 100, 110, 255), width=2)

            pill_pad = 15
            pill_w = w_pill + pill_pad*2
            y_line = 295
            y_pill = 305
            pill_rect = [(tx - pill_w/2, y_pill), (tx + pill_w/2, y_pill + 35)]
            draw.rounded_rectangle(pill_rect, radius=17, fill=pill_fill, outline=pill_outline, width=1)
            draw.text((tx - w_pill/2 + pill_pad, y_pill + 4), pill_text, font=font_pill, fill=pill_text_color)

        out = io.BytesIO()
        base.save(out, format="PNG")
        out.seek(0)
        return discord.File(out, filename=f"welcome_{member.id}.png")

    async def execute_greet(self, member: discord.Member, name: str, mock_channel_id: int = None):
        guild = member.guild
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT config_json, mode, enable_autodelete, autodelete_time FROM welcomer_setups WHERE guild_id = ? AND name = ?", (guild.id, name)) as c:
                row = await c.fetchone()
                if not row: return
            config_str, mode, enable_ad, ad_time = row

            async with db.execute("SELECT channel_id FROM welcomer_channels WHERE guild_id = ? AND setup_name = ?", (guild.id, name)) as c:
                channel_rows = await c.fetchall()

        config = json.loads(config_str)
        replacer = VariableReplacer(member)
        del_kwargs = {"delete_after": ad_time} if enable_ad and ad_time > 0 else {}

        channel_ids = [r[0] for r in channel_rows]
        if mock_channel_id:
            channel_ids = [mock_channel_id]

        for cid in channel_ids:
            channel = guild.get_channel(cid)
            if not channel: continue

            try:
                if mode == "message":
                    msg = replacer.replace(config.get("message", ""))
                    await channel.send(content=msg, **del_kwargs)
                elif mode == "embed":
                    msg = replacer.replace(config.get("message", ""))
                    embed = discord.Embed(
                        title=replacer.replace(config.get("title")),
                        description=replacer.replace(config.get("description")),
                        color=config.get("color", 0x2b2d31)
                    )
                    if config.get("author_name"):
                        embed.set_author(name=replacer.replace(config.get("author_name")), icon_url=replacer.replace(config.get("author_icon", "")))
                    if config.get("footer_text"):
                        embed.set_footer(text=replacer.replace(config.get("footer_text")), icon_url=replacer.replace(config.get("footer_icon", "")))
                    if config.get("image"):
                        embed.set_image(url=replacer.replace(config.get("image")))
                    if config.get("thumbnail"):
                        embed.set_thumbnail(url=replacer.replace(config.get("thumbnail")))
                    for field in config.get("fields", []):
                        embed.add_field(name=replacer.replace(field.get("name", "")), value=replacer.replace(field.get("value", "")), inline=field.get("inline", False))

                    await channel.send(content=msg if msg else None, embed=embed, **del_kwargs)
                elif mode == "image":
                    msg = replacer.replace(config.get("content", ""))
                    file = await self.generate_card(member, config)
                    await channel.send(content=msg if msg else None, file=file, **del_kwargs)
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Error executing greet for {name}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM welcomer_setups WHERE guild_id = ? AND is_enabled = 1", (member.guild.id,)) as c:
                setups = await c.fetchall()
        for (name,) in setups:
            await self.execute_greet(member, name)

    @commands.Cog.listener()
    async def on_member_join_test_mock(self, member: discord.Member, setup_name: str, channel_id: int):
        await self.execute_greet(member, setup_name, mock_channel_id=channel_id)

async def setup(bot):
    await bot.add_cog(GreetEvents(bot))
