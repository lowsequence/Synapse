import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = "assets/fonts"
BOLD = f"{FONT_DIR}/Inter-Bold.ttf"
SEMI = f"{FONT_DIR}/Inter-SemiBold.ttf"
REG = f"{FONT_DIR}/Inter-Regular.ttf"

BG = (24, 24, 28)
CARD_BG = (32, 33, 37)
ACCENT = (255, 255, 255)
SUBTEXT = (148, 148, 153)
BAR_BG = (55, 56, 60)
BAR_FILL = (255, 255, 255)
DIVIDER = (45, 46, 50)
LEVELUP_ACCENT = (88, 101, 242)


def _round_corner(radius, fill):
    circle = Image.new("L", (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
    return circle


def _rounded_rect(img, xy, fill, radius=20):
    x0, y0, x1, y1 = xy
    w = x1 - x0
    h = y1 - y0
    rect = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rect)
    draw.rectangle((0, 0, w, h), fill=fill)

    corner = _round_corner(radius, 255)
    mask = Image.new("L", (w, h), 255)
    mask.paste(corner.crop((0, 0, radius, radius)), (0, 0))
    mask.paste(corner.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
    mask.paste(corner.crop((0, radius, radius, radius * 2)), (0, h - radius))
    mask.paste(corner.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))

    rect.putalpha(mask)
    img.paste(rect, (x0, y0), rect)


def _circular_avatar(avatar_bytes, size):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(av, (0, 0), mask)
    return output


def _fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


async def fetch_avatar(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(str(url)) as resp:
            return await resp.read()


def render_rank_card(
    username: str,
    discriminator: str,
    avatar_bytes: bytes,
    level: int,
    xp: int,
    needed_xp: int,
    rank: int,
    messages: int,
    status_color: tuple = (148, 148, 153),
):
    W, H = 934, 282
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    _rounded_rect(img, (0, 0, W, H), CARD_BG, radius=24)

    draw = ImageDraw.Draw(img)

    av = _circular_avatar(avatar_bytes, 120)
    img.paste(av, (40, 81), av)

    ring = Image.new("RGBA", (132, 132), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    ring_draw.ellipse((0, 0, 131, 131), outline=(58, 59, 63), width=3)
    img.paste(ring, (34, 75), ring)

    status_dot = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    sd = ImageDraw.Draw(status_dot)
    sd.ellipse((0, 0, 27, 27), fill=CARD_BG)
    sd.ellipse((4, 4, 23, 23), fill=status_color)
    img.paste(status_dot, (134, 175), status_dot)

    name_font = ImageFont.truetype(BOLD, 28)
    disc_font = ImageFont.truetype(REG, 18)
    label_font = ImageFont.truetype(REG, 13)
    value_font = ImageFont.truetype(SEMI, 22)
    bar_font = ImageFont.truetype(SEMI, 13)

    draw.text((190, 40), username, fill=ACCENT, font=name_font)
    nw = draw.textlength(username, font=name_font)
    draw.text((190 + nw + 6, 49), f"#{discriminator}" if discriminator != "0" else "", fill=SUBTEXT, font=disc_font)

    stats_y = 85
    stat_x_start = 190

    for i, (label, value) in enumerate([("RANK", f"#{rank}"), ("LEVEL", str(level)), ("MESSAGES", _fmt(messages))]):
        x = stat_x_start + i * 180
        draw.text((x, stats_y), label, fill=SUBTEXT, font=label_font)
        draw.text((x, stats_y + 18), value, fill=ACCENT, font=value_font)

    bar_y = 170
    bar_x = 190
    bar_w = W - bar_x - 40
    bar_h = 22

    _rounded_rect(img, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), BAR_BG, radius=11)

    progress = min(1.0, xp / needed_xp) if needed_xp > 0 else 0
    fill_w = max(22, int(bar_w * progress))
    _rounded_rect(img, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), BAR_FILL, radius=11)

    xp_text = f"{_fmt(xp)} / {_fmt(needed_xp)} XP"
    tw = draw.textlength(xp_text, font=bar_font)
    draw.text((bar_x + bar_w - tw, bar_y + bar_h + 8), xp_text, fill=SUBTEXT, font=bar_font)

    pct_text = f"{int(progress * 100)}%"
    draw.text((bar_x, bar_y + bar_h + 8), pct_text, fill=ACCENT, font=bar_font)

    draw.line((40, 230, W - 40, 230), fill=DIVIDER, width=1)
    footer_font = ImageFont.truetype(REG, 12)
    draw.text((40, 240), "LEVELING SYSTEM", fill=(80, 80, 85), font=footer_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_leaderboard_card(
    guild_name: str,
    entries: list,
    guild_icon_bytes: bytes = None,
):
    entry_h = 58
    header_h = 90
    padding = 24
    W = 700
    H = header_h + len(entries) * entry_h + padding * 2

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _rounded_rect(img, (0, 0, W, H), CARD_BG, radius=24)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(BOLD, 22)
    sub_font = ImageFont.truetype(REG, 13)
    name_font = ImageFont.truetype(SEMI, 17)
    stat_font = ImageFont.truetype(REG, 14)
    rank_font = ImageFont.truetype(BOLD, 20)

    if guild_icon_bytes:
        icon = _circular_avatar(guild_icon_bytes, 48)
        img.paste(icon, (padding, 20), icon)
        text_x = padding + 60
    else:
        text_x = padding

    draw.text((text_x, 22), "XP LEADERBOARD", fill=ACCENT, font=title_font)
    draw.text((text_x, 48), guild_name, fill=SUBTEXT, font=sub_font)

    draw.line((padding, header_h - 2, W - padding, header_h - 2), fill=DIVIDER, width=1)

    medal_colors = {
        1: (255, 215, 0),
        2: (192, 192, 192),
        3: (205, 127, 50),
    }

    for i, entry in enumerate(entries):
        y = header_h + i * entry_h
        rank_num = i + 1

        if i % 2 == 0:
            _rounded_rect(img, (12, y + 2, W - 12, y + entry_h - 2), (38, 39, 43), radius=8)

        rank_color = medal_colors.get(rank_num, SUBTEXT)
        rank_text = f"#{rank_num}"
        draw.text((padding + 8, y + 17), rank_text, fill=rank_color, font=rank_font)

        if entry.get("avatar"):
            av = _circular_avatar(entry["avatar"], 36)
            img.paste(av, (padding + 65, y + 11), av)
            name_x = padding + 112
        else:
            name_x = padding + 65

        draw.text((name_x, y + 12), entry["name"], fill=ACCENT, font=name_font)
        draw.text((name_x, y + 33), f"Level {entry['level']}  •  {_fmt(entry['xp'])} XP", fill=SUBTEXT, font=stat_font)

        mini_bar_x = W - padding - 160
        mini_bar_w = 140
        mini_bar_h = 6
        mini_bar_y = y + 26

        _rounded_rect(img, (mini_bar_x, mini_bar_y, mini_bar_x + mini_bar_w, mini_bar_y + mini_bar_h), BAR_BG, radius=3)
        prog = min(1.0, entry["xp"] / entry["needed"]) if entry["needed"] > 0 else 0
        fill_w = max(6, int(mini_bar_w * prog))
        _rounded_rect(img, (mini_bar_x, mini_bar_y, mini_bar_x + fill_w, mini_bar_y + mini_bar_h), BAR_FILL, radius=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_levelup_card(
    username: str,
    avatar_bytes: bytes,
    new_level: int,
    role_name: str = None,
):
    W, H = 520, 160
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    _rounded_rect(img, (0, 0, W, H), CARD_BG, radius=20)
    draw = ImageDraw.Draw(img)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rectangle((0, 0, 6, H), fill=(255, 255, 255, 40))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    av = _circular_avatar(avatar_bytes, 80)
    img.paste(av, (30, 40), av)

    ring = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((0, 0, 89, 89), outline=(58, 59, 63), width=2)
    img.paste(ring, (25, 35), ring)

    title_font = ImageFont.truetype(BOLD, 13)
    name_font = ImageFont.truetype(BOLD, 22)
    level_font = ImageFont.truetype(BOLD, 36)
    role_font = ImageFont.truetype(REG, 13)

    draw.text((135, 28), "LEVEL UP!", fill=SUBTEXT, font=title_font)
    draw.text((135, 46), username, fill=ACCENT, font=name_font)

    lvl_text = str(new_level)
    lw = draw.textlength(lvl_text, font=level_font)
    draw.text((W - 40 - lw, 35), lvl_text, fill=ACCENT, font=level_font)

    label_font = ImageFont.truetype(REG, 11)
    lbl = "LEVEL"
    lblw = draw.textlength(lbl, font=label_font)
    draw.text((W - 40 - lw / 2 - lblw / 2, 75), lbl, fill=SUBTEXT, font=label_font)

    if role_name:
        draw.text((135, 80), f"+ Unlocked {role_name}", fill=(88, 101, 242), font=role_font)

    draw.line((135, 110, W - 40, 110), fill=DIVIDER, width=1)
    footer_font = ImageFont.truetype(REG, 11)
    draw.text((135, 118), "Keep chatting to level up more!", fill=(80, 80, 85), font=footer_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
