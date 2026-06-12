import discord
from discord.ext import commands
import random
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import aiohttp
import os
from utils.Tools import blacklist_check, ignore_check

class Ship(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bg_path = "assets/ship/background.png"
        self.heart_path = "assets/ship/heart.png"

    async def get_image(self, url):
        """Fetches an image from a URL and returns a PIL Image object."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url)) as response:
                    if response.status == 200:
                        data = await response.read()
                        return Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            return None
        return None

    def prep_avatar_mask(self, img: Image.Image, size: tuple) -> Image.Image:
        """Resizes and crops a square image into a circle with an antialiased alpha mask."""
        img = img.resize(size, Image.Resampling.LANCZOS)
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)

        output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
        output.putalpha(mask)
        return output

    async def generate_ship_card(self, user1: discord.Member, user2: discord.Member, percent: int) -> discord.File:
        """Composites the final image card."""
        if not os.path.exists(self.bg_path) or not os.path.exists(self.heart_path):
             base = Image.new("RGBA", (800, 300), (40, 40, 40, 255))
             heart = Image.new("RGBA", (150, 150), (255, 0, 0, 255))
        else:
             base = Image.open(self.bg_path).convert("RGBA").resize((800, 300), Image.Resampling.LANCZOS)
             heart = Image.open(self.heart_path).convert("RGBA").resize((150, 150), Image.Resampling.LANCZOS)

        overlay = Image.new("RGBA", base.size, (255, 255, 255, 30))
        base = Image.alpha_composite(base, overlay)

        av1_url = user1.display_avatar.url
        av2_url = user2.display_avatar.url

        av1_img = await self.get_image(av1_url)
        av2_img = await self.get_image(av2_url)

        if not av1_img: av1_img = Image.new("RGBA", (200, 200), (100, 100, 100, 255))
        if not av2_img: av2_img = Image.new("RGBA", (200, 200), (100, 100, 100, 255))

        av1_img = self.prep_avatar_mask(av1_img, (200, 200))
        av2_img = self.prep_avatar_mask(av2_img, (200, 200))

        base.paste(av1_img, (50, 50), av1_img)
        base.paste(av2_img, (550, 50), av2_img)

        h_size = 150
        if percent < 30: 
             heart = heart.resize((100, 100), Image.Resampling.LANCZOS)
             h_size = 100
             heart = ImageOps.grayscale(heart).convert("RGBA")

        hx, hy = (400 - (h_size//2), 150 - (h_size//2) - 20)
        base.paste(heart, (hx, hy), heart)

        draw = ImageDraw.Draw(base)
        try:
             font = ImageFont.truetype("Pricedown.otf", 70) 
        except:
             font = ImageFont.load_default()

        text = f"{percent}%"

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        tx, ty = (400 - (tw//2), 230)
        draw.text((tx+2, ty+2), text, font=font, fill=(255, 255, 255, 255)) 
        draw.text((tx, ty), text, font=font, fill=(210, 80, 120, 255))

        draw.rounded_rectangle([(300, 210), (500, 225)], radius=7, fill=(255, 255, 255, 180))

        if percent > 0:
             fill_w = int(200 * (percent/100.0))
             r = 255
             g = int(180 - (100 * percent / 100))
             b = int(200 - (100 * percent / 100))
             draw.rounded_rectangle([(300, 210), (300 + fill_w, 225)], radius=7, fill=(r, g, b, 255))

        buffer = io.BytesIO()
        base.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="ship.png")

    @commands.command(name="ship", help="Discover the compatibility between two users.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def ship(self, ctx, user1: discord.Member = None, user2: discord.Member = None):
        if user1 is None:
            user1 = ctx.author
            members = [m for m in ctx.guild.members if not m.bot and m.id != ctx.author.id]
            user2 = random.choice(members) if members else ctx.author
        elif user2 is None:
            user2 = user1
            user1 = ctx.author

        if user1.id == user2.id:
            msg = "You shipping yourself? 100% Narcissist 💀"
            percent = 100
        else:
            sorted_ids = sorted([user1.id, user2.id])
            rng = random.Random(f"{sorted_ids[0]}:{sorted_ids[1]}")
            percent = rng.randint(0, 100)

            if percent == 100: msg = "True soulmates! Perfect match! 💖"
            elif percent >= 80: msg = "Looking incredibly spicy! 🔥"
            elif percent >= 50: msg = "There's definitely some potential here. 🤔"
            elif percent >= 20: msg = "You might want to stay in the friendzone... 😬"
            else: msg = "Sworn enemies. Run away immediately. 💀"

        async with ctx.typing():
             file = await self.generate_ship_card(user1, user2, percent)

             embed = discord.Embed(
                 title=f"Shipping {user1.display_name} & {user2.display_name}",
                 description=f"**{percent}%** Match! \n{msg}",
                 color=0xFF69B4 if percent >= 50 else 0x2b2d31
             )
             embed.set_image(url="attachment://ship.png")
             await ctx.send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(Ship(bot))
