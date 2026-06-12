from __future__ import annotations
import os, re, asyncio
import io, aiohttp
import discord, aiosqlite
from discord.ext import commands
from discord import ui
from PIL import Image, ImageDraw, ImageFont
from utils.Tools import blacklist_check, ignore_check


DB_PATH = os.path.join("database", "voicemaster.db")
COLOR   = 0x2b2d31
E_OK    = "<:emoji_1769867605256:1467155817726873650>"
E_ERR   = "<:SynapseExcl:1477234549552320634>"

EM_LOCK     = "<:lock:1479821447063932959>"
EM_UNLOCK   = "<:unlock:1479821419356618762>"
EM_HIDE     = "<:hide:1479821528903319645>"
EM_UNHIDE   = "<:transfer:1479822112016437329>"
EM_LIMIT    = "<:limit:1479821557898543104>"
EM_INVITE   = "<:invite:1479821612881547264>"
EM_BAN      = "<:ban:1479821582368116969>"
EM_PERMIT   = "<:permit:1479821798206869627>"
EM_RENAME   = "<:rename:1479821764782718996>"
EM_BITRATE  = "<:bitrate:1479821868570644531>"
EM_REGION   = "<:region:1479821829190193303>"
EM_TEMPLATE = "<:template:1479825007281569922>"
EM_CHAT     = "<:chat:1479821895779090683>"
EM_WAITING  = "<:waiting:1479821931749314640>"
EM_CLAIM    = "<:vmclaim:1479821347306733651>"
EM_TRANSFER = "<:transfer:1479822112016437329>"


def _ok(t: str) -> discord.Embed:
    return discord.Embed(description=f"{E_OK} {t}", color=0x4dff94)

def _err(t: str) -> discord.Embed:
    return discord.Embed(description=f"{E_ERR} {t}", color=0x2b2d31)

async def _parse_member(guild: discord.Guild, text: str):
    text = text.strip()
    m = re.match(r"<@!?(\d+)>", text)
    if m:
        return guild.get_member(int(m.group(1)))
    try:
        return guild.get_member(int(text))
    except ValueError:
        pass
    return discord.utils.find(
        lambda mb: mb.name.lower() == text.lower(), guild.members
    )


async def _init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS vm_config (
                guild_id         INTEGER PRIMARY KEY,
                category_id      INTEGER,
                generator_id     INTEGER,
                interface_id     INTEGER,
                interface_msg_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS vm_defaults (
                guild_id   INTEGER PRIMARY KEY,
                user_limit INTEGER DEFAULT 0,
                bitrate    INTEGER DEFAULT 64000,
                region     TEXT
            );
            CREATE TABLE IF NOT EXISTS vm_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                owner_id   INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );
            CREATE TABLE IF NOT EXISTS vm_templates (
                guild_id      INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                name_template TEXT,
                user_limit    INTEGER DEFAULT 0,
                bitrate       INTEGER DEFAULT 64000,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()



class RenameModal(ui.Modal, title="Rename Voice Channel"):
    name_input = ui.TextInput(label="New Channel Name", placeholder="My Channel", max_length=100)

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.vc.edit(name=self.name_input.value)
            await interaction.response.send_message(
                embed=_ok(f"Channel renamed to **{self.name_input.value}**."), ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(embed=_err("Missing permissions."), ephemeral=True)


class LimitModal(ui.Modal, title="Set User Limit"):
    limit = ui.TextInput(label="User Limit (0 = unlimited)", placeholder="0", max_length=3)

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.limit.value)
            if not 0 <= val <= 99:
                return await interaction.response.send_message(
                    embed=_err("Must be between 0 and 99."), ephemeral=True
                )
            await self.vc.edit(user_limit=val)
            txt = f"User limit set to **{val}**." if val else "User limit **removed**."
            await interaction.response.send_message(embed=_ok(txt), ephemeral=True)
        except ValueError:
            await interaction.response.send_message(embed=_err("Enter a valid number."), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=_err("Missing permissions."), ephemeral=True)


class BitrateModal(ui.Modal, title="Set Bitrate"):
    bitrate = ui.TextInput(label="Bitrate in kbps (8–384)", placeholder="64", max_length=3)

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.bitrate.value) * 1000
            if not 8000 <= val <= 384000:
                return await interaction.response.send_message(
                    embed=_err("Must be between 8 and 384."), ephemeral=True
                )
            val = min(val, interaction.guild.bitrate_limit)
            await self.vc.edit(bitrate=val)
            await interaction.response.send_message(
                embed=_ok(f"Bitrate set to **{val // 1000} kbps**."), ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(embed=_err("Enter a valid number."), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=_err("Missing permissions."), ephemeral=True)


class RegionModal(ui.Modal, title="Set Voice Region"):
    region = ui.TextInput(
        label="Region (auto, us-east, europe …)",
        placeholder="auto",
        max_length=20,
    )

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        val = self.region.value.strip().lower()
        rtc = None if val in ("auto", "automatic", "none", "") else val
        try:
            await self.vc.edit(rtc_region=rtc)
            await interaction.response.send_message(
                embed=_ok(f"Region set to **{rtc or 'Automatic'}**."), ephemeral=True
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=_err("Invalid region. Try: `auto`, `us-east`, `us-west`, `europe`, `brazil`, `singapore`, `japan`, `india`, `sydney`."),
                ephemeral=True,
            )


class UserActionModal(ui.Modal):
    user_input = ui.TextInput(
        label="User (ID or @mention)", placeholder="123456789012345678", max_length=50
    )

    def __init__(self, vc: discord.VoiceChannel, action: str):
        self.vc = vc
        self.action = action
        titles = {
            "invite": "Invite User",
            "ban": "Ban User",
            "permit": "Permit User",
            "transfer": "Transfer Ownership",
        }
        super().__init__(title=titles.get(action, "User Action"))

    async def on_submit(self, interaction: discord.Interaction):
        member = await _parse_member(interaction.guild, self.user_input.value)
        if not member:
            return await interaction.response.send_message(
                embed=_err("User not found. Use their ID or @mention."), ephemeral=True
            )

        if self.action == "invite":
            ow = self.vc.overwrites_for(member)
            ow.connect = True
            await self.vc.set_permissions(member, overwrite=ow)
            await interaction.response.send_message(
                embed=_ok(f"{member.mention} has been **invited**."), ephemeral=True
            )

        elif self.action == "ban":
            ow = self.vc.overwrites_for(member)
            ow.connect = False
            await self.vc.set_permissions(member, overwrite=ow)
            if member.voice and member.voice.channel == self.vc:
                try:
                    await member.move_to(None, reason="VoiceMaster ban")
                except discord.Forbidden:
                    pass
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO vm_channels (guild_id, channel_id, owner_id) "
                    "SELECT ?, ?, owner_id FROM vm_channels WHERE guild_id = ? AND channel_id = ?",
                    (interaction.guild.id, self.vc.id, interaction.guild.id, self.vc.id),
                )
                await db.commit()
            await interaction.response.send_message(
                embed=_ok(f"{member.mention} has been **banned** from your channel."), ephemeral=True
            )

        elif self.action == "permit":
            ow = self.vc.overwrites_for(member)
            ow.connect = True
            ow.speak = True
            await self.vc.set_permissions(member, overwrite=ow)
            await interaction.response.send_message(
                embed=_ok(f"{member.mention} has been **permitted**."), ephemeral=True
            )

        elif self.action == "transfer":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE vm_channels SET owner_id = ? WHERE guild_id = ? AND channel_id = ?",
                    (member.id, interaction.guild.id, self.vc.id),
                )
                await db.commit()
            await interaction.response.send_message(
                embed=_ok(f"Ownership transferred to {member.mention}."), ephemeral=True
            )



class VoiceMasterView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _get_vc(self, interaction: discord.Interaction, owner_only: bool = True):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                embed=_err("You must be in a voice channel."), ephemeral=True
            )
            return None, None

        vc = interaction.user.voice.channel
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT owner_id FROM vm_channels WHERE guild_id = ? AND channel_id = ?",
                (interaction.guild.id, vc.id),
            )
            row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(
                embed=_err("This is not a VoiceMaster channel."), ephemeral=True
            )
            return None, None

        owner_id = row[0]
        if owner_only and interaction.user.id != owner_id:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    embed=_err("Only the channel owner can do this."), ephemeral=True
                )
                return None, None

        return vc, owner_id

    @ui.button(emoji=EM_LOCK, style=discord.ButtonStyle.secondary, custom_id="vm_lock", row=0)
    async def lock_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        ow.connect = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(embed=_ok("Channel **locked**."), ephemeral=True)

    @ui.button(emoji=EM_UNLOCK, style=discord.ButtonStyle.secondary, custom_id="vm_unlock", row=0)
    async def unlock_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        ow.connect = None
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(embed=_ok("Channel **unlocked**."), ephemeral=True)

    @ui.button(emoji=EM_HIDE, style=discord.ButtonStyle.secondary, custom_id="vm_hide", row=0)
    async def hide_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        ow.view_channel = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(embed=_ok("Channel **hidden**."), ephemeral=True)

    @ui.button(emoji=EM_UNHIDE, style=discord.ButtonStyle.secondary, custom_id="vm_unhide", row=0)
    async def unhide_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        ow.view_channel = None
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(embed=_ok("Channel **unhidden**."), ephemeral=True)

    @ui.button(emoji=EM_LIMIT, style=discord.ButtonStyle.secondary, custom_id="vm_limit", row=1)
    async def limit_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(LimitModal(vc))

    @ui.button(emoji=EM_INVITE, style=discord.ButtonStyle.secondary, custom_id="vm_invite", row=1)
    async def invite_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(UserActionModal(vc, "invite"))

    @ui.button(emoji=EM_BAN, style=discord.ButtonStyle.secondary, custom_id="vm_ban", row=1)
    async def ban_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(UserActionModal(vc, "ban"))

    @ui.button(emoji=EM_PERMIT, style=discord.ButtonStyle.secondary, custom_id="vm_permit", row=1)
    async def permit_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(UserActionModal(vc, "permit"))

    @ui.button(emoji=EM_RENAME, style=discord.ButtonStyle.secondary, custom_id="vm_rename", row=2)
    async def rename_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(RenameModal(vc))

    @ui.button(emoji=EM_BITRATE, style=discord.ButtonStyle.secondary, custom_id="vm_bitrate", row=2)
    async def bitrate_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(BitrateModal(vc))

    @ui.button(emoji=EM_REGION, style=discord.ButtonStyle.secondary, custom_id="vm_region", row=2)
    async def region_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(RegionModal(vc))

    @ui.button(emoji=EM_TEMPLATE, style=discord.ButtonStyle.secondary, custom_id="vm_template", row=2)
    async def template_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vm_templates (guild_id, user_id, name_template, user_limit, bitrate) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET "
                "name_template=excluded.name_template, user_limit=excluded.user_limit, bitrate=excluded.bitrate",
                (interaction.guild.id, interaction.user.id, vc.name, vc.user_limit, vc.bitrate),
            )
            await db.commit()
        await interaction.response.send_message(
            embed=_ok("Current channel settings saved as your **template**."), ephemeral=True
        )

    @ui.button(emoji=EM_CHAT, style=discord.ButtonStyle.secondary, custom_id="vm_chat", row=3)
    async def chat_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        current = ow.send_messages
        ow.send_messages = False if current is not False else None
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        state = "disabled" if ow.send_messages is False else "enabled"
        await interaction.response.send_message(
            embed=_ok(f"Text chat **{state}** for everyone."), ephemeral=True
        )

    @ui.button(emoji=EM_WAITING, style=discord.ButtonStyle.secondary, custom_id="vm_waiting", row=3)
    async def waiting_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        ow = vc.overwrites_for(interaction.guild.default_role)
        current = ow.speak
        ow.speak = False if current is not False else None
        await vc.set_permissions(interaction.guild.default_role, overwrite=ow)
        state = "enabled" if ow.speak is False else "disabled"
        await interaction.response.send_message(
            embed=_ok(f"Waiting room **{state}**."), ephemeral=True
        )

    @ui.button(emoji=EM_CLAIM, style=discord.ButtonStyle.secondary, custom_id="vm_claim", row=3)
    async def claim_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, owner_id = await self._get_vc(interaction, owner_only=False)
        if not vc:
            return
        owner_in_vc = any(m.id == owner_id for m in vc.members)
        if owner_in_vc:
            return await interaction.response.send_message(
                embed=_err("The channel owner is still in the channel."), ephemeral=True
            )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE vm_channels SET owner_id = ? WHERE guild_id = ? AND channel_id = ?",
                (interaction.user.id, interaction.guild.id, vc.id),
            )
            await db.commit()
        await interaction.response.send_message(
            embed=_ok("You have **claimed** this channel."), ephemeral=True
        )

    @ui.button(emoji=EM_TRANSFER, style=discord.ButtonStyle.secondary, custom_id="vm_transfer", row=3)
    async def transfer_btn(self, interaction: discord.Interaction, button: ui.Button):
        vc, _ = await self._get_vc(interaction)
        if not vc:
            return
        await interaction.response.send_modal(UserActionModal(vc, "transfer"))



class VoiceMaster(commands.Cog):
    """Join-To-Create voice channel system with persistent interface."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.loop.create_task(_init_db())
        self._vm_banner_bytes = None

    async def get_vm_image(self) -> io.BytesIO:
        if self._vm_banner_bytes:
            return io.BytesIO(self._vm_banner_bytes)

        buttons_info = [
            (EM_LOCK, "Lock"), (EM_UNLOCK, "Unlock"), (EM_HIDE, "Hide"), (EM_UNHIDE, "Unhide"),
            (EM_LIMIT, "Limit"), (EM_INVITE, "invite"), (EM_BAN, "Ban"), (EM_PERMIT, "Permit"),
            (EM_RENAME, "Rename"), (EM_BITRATE, "Bitrate"), (EM_REGION, "Region"), (EM_TEMPLATE, "Template"),
            (EM_CHAT, "Chat"), (EM_WAITING, "Waiting"), (EM_CLAIM, "Claim"), (EM_TRANSFER, "Transfer")
        ]

        async with aiohttp.ClientSession() as session:
            emoji_images = []
            for em_str, _ in buttons_info:
                try:
                    em_id = em_str.split(':')[-1][:-1]
                    url = f"https://cdn.discordapp.com/emojis/{em_id}.png"
                    async with session.get(url) as r:
                        if r.status == 200:
                            data = await r.read()
                            img = Image.open(io.BytesIO(data)).convert("RGBA")
                            img = img.resize((46, 46), Image.LANCZOS)
                            emoji_images.append(img)
                        else:
                            emoji_images.append(None)
                except Exception:
                    emoji_images.append(None)

            try:
                font = ImageFont.truetype("assets/fonts/Poppins-SemiBold.ttf", 30)
            except Exception:
                font = ImageFont.load_default()

        cols, rows = 4, 4
        btn_w, btn_h = 290, 80
        gap_x, gap_y = 16, 16

        width = cols * btn_w + (cols - 1) * gap_x
        height = rows * btn_h + (rows - 1) * gap_y

        out_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(out_img)

        for i in range(16):
            col = i % cols
            row = i // cols
            x = col * (btn_w + gap_x)
            y = row * (btn_h + gap_y)

            draw.rounded_rectangle([x, y, x + btn_w, y + btn_h], radius=12, fill="#2b2d31")
            
            em_img = emoji_images[i]
            if em_img:
                out_img.paste(em_img, (x + 22, y + 17), em_img)
            
            text = buttons_info[i][1]
            draw.text((x + 82, y + 40), text, font=font, fill="#ffffff", anchor="lm")

        buf = io.BytesIO()
        out_img.save(buf, format="PNG")
        self._vm_banner_bytes = buf.getvalue()

        return io.BytesIO(self._vm_banner_bytes)

    async def _send_help(self, ctx: commands.Context):
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        guild = member.guild

        if after.channel:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(
                    "SELECT category_id, generator_id FROM vm_config WHERE guild_id = ?",
                    (guild.id,),
                )
                cfg = await cur.fetchone()

            if cfg and after.channel.id == cfg[1]:
                category = guild.get_channel(cfg[0])
                if not category:
                    return

                async with aiosqlite.connect(DB_PATH) as db:
                    cur = await db.execute(
                        "SELECT channel_id FROM vm_channels WHERE guild_id = ? AND owner_id = ?",
                        (guild.id, member.id),
                    )
                    existing = await cur.fetchone()

                if existing:
                    ch = guild.get_channel(existing[0])
                    if ch:
                        try:
                            await member.move_to(ch)
                        except discord.Forbidden:
                            pass
                        return

                name = f"{member.display_name}'s Channel"
                ulimit, bitrate = 0, 64000

                async with aiosqlite.connect(DB_PATH) as db:
                    cur = await db.execute(
                        "SELECT name_template, user_limit, bitrate FROM vm_templates "
                        "WHERE guild_id = ? AND user_id = ?",
                        (guild.id, member.id),
                    )
                    tmpl = await cur.fetchone()

                    if tmpl:
                        name = tmpl[0] or name
                        ulimit = tmpl[1] or 0
                        bitrate = tmpl[2] or 64000
                    else:
                        cur = await db.execute(
                            "SELECT user_limit, bitrate FROM vm_defaults WHERE guild_id = ?",
                            (guild.id,),
                        )
                        defs = await cur.fetchone()
                        if defs:
                            ulimit = defs[0] or 0
                            bitrate = defs[1] or 64000

                bitrate = min(bitrate, guild.bitrate_limit)

                try:
                    new_vc = await guild.create_voice_channel(
                        name=name,
                        category=category,
                        user_limit=ulimit,
                        bitrate=bitrate,
                        reason="VoiceMaster — join-to-create",
                    )
                    await new_vc.set_permissions(
                        member,
                        connect=True,
                        speak=True,
                        manage_channels=True,
                        move_members=True,
                    )
                    await member.move_to(new_vc)

                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "INSERT OR REPLACE INTO vm_channels (guild_id, channel_id, owner_id) VALUES (?, ?, ?)",
                            (guild.id, new_vc.id, member.id),
                        )
                        await db.commit()
                except discord.Forbidden:
                    pass

        if before.channel and before.channel != after.channel:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(
                    "SELECT 1 FROM vm_channels WHERE guild_id = ? AND channel_id = ?",
                    (guild.id, before.channel.id),
                )
                is_temp = await cur.fetchone()

            if is_temp and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="VoiceMaster — empty temp VC cleanup")
                except discord.Forbidden:
                    pass
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "DELETE FROM vm_channels WHERE guild_id = ? AND channel_id = ?",
                        (guild.id, before.channel.id),
                    )
                    await db.commit()


    @commands.group(
        name="voicemaster",
        aliases=["vm"],
        invoke_without_command=True,
        help="VoiceMaster join-to-create system.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def voicemaster(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @voicemaster.command(name="setup", help="Create VoiceMaster category, generator, and interface.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_setup(self, ctx: commands.Context):
        guild = ctx.guild

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM vm_config WHERE guild_id = ?", (guild.id,)
            )
            if await cur.fetchone():
                return await ctx.reply(
                    embed=_err("VoiceMaster is already set up. Use `voicemaster reset` first."),
                    mention_author=False,
                )

        status = await ctx.reply(embed=discord.Embed(description="<a:Loadixd:1469568214169288890> Setting up VoiceMaster...", color=COLOR))

        try:
            category = await guild.create_category("Synapse Voice", reason="VoiceMaster setup")

            generator = await guild.create_voice_channel(
                "Join to Create", category=category, reason="VoiceMaster setup"
            )

            interface = await guild.create_text_channel(
                "interface", category=category, reason="VoiceMaster setup"
            )

            await interface.set_permissions(
                guild.default_role, send_messages=False, add_reactions=False
            )
            await interface.set_permissions(
                guild.me, send_messages=True, embed_links=True, attach_files=True
            )

            bot_avatar = self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url
            desc = (
                "### 🎙️ **VoiceMaster Hub**\n"
                "Customize and manage your temporary voice channel dynamically! Click on the corresponding option on the interface image below to execute the action in real-time.\n\n"
                "> **Dashboard Information**\n"
                "• **Auto-Creation**: Channels are created instantly when joining **Join to Create**.\n"
                "• **Auto-Cleanup**: Channels are deleted automatically when all members leave.\n"
                "• **Full Customization**: Manage visibility, slots, names, and regional settings with ease."
            )
            embed = discord.Embed(description=desc, color=COLOR)
            embed.set_author(name="Synapse Interface", icon_url=bot_avatar)
            
            img_buf = await self.get_vm_image()
            file = discord.File(fp=img_buf, filename="vm_interface.png")
            embed.set_image(url="attachment://vm_interface.png")
            
            embed.set_footer(text="Synapse — VoiceMaster Control Center", icon_url=bot_avatar)
            view = VoiceMasterView()
            msg = await interface.send(embed=embed, file=file, view=view)

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO vm_config (guild_id, category_id, generator_id, interface_id, interface_msg_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (guild.id, category.id, generator.id, interface.id, msg.id),
                )
                await db.execute(
                    "INSERT OR IGNORE INTO vm_defaults (guild_id) VALUES (?)",
                    (guild.id,),
                )
                await db.commit()

            await status.edit(
                embed=_ok(
                    f"VoiceMaster setup complete!\n\n"
                    f"> **Category:** {category.name}\n"
                    f"> **Generator:** {generator.mention}\n"
                    f"> **Interface:** {interface.mention}"
                )
            )
        except discord.Forbidden:
            await status.edit(embed=_err("I don't have permission to create channels."))
        except Exception as e:
            await status.edit(embed=_err(f"Setup failed: `{e}`"))

    @voicemaster.command(name="reset", help="Delete VoiceMaster setup and clean up channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_reset(self, ctx: commands.Context):
        guild = ctx.guild

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT category_id, generator_id, interface_id FROM vm_config WHERE guild_id = ?",
                (guild.id,),
            )
            cfg = await cur.fetchone()

        if not cfg:
            return await ctx.reply(
                embed=_err("VoiceMaster is not set up in this server."),
                mention_author=False,
            )

        for ch_id in cfg:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.delete(reason="VoiceMaster reset")
                except discord.Forbidden:
                    pass

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT channel_id FROM vm_channels WHERE guild_id = ?", (guild.id,)
            )
            temp_chs = await cur.fetchall()

        for (ch_id,) in temp_chs:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.delete(reason="VoiceMaster reset")
                except discord.Forbidden:
                    pass

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM vm_config WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM vm_channels WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM vm_defaults WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM vm_templates WHERE guild_id = ?", (guild.id,))
            await db.commit()

        await ctx.reply(embed=_ok("VoiceMaster has been **reset**. All channels and data removed."))

    @voicemaster.command(name="config", help="Show current VoiceMaster configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_config(self, ctx: commands.Context):
        guild = ctx.guild

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT category_id, generator_id, interface_id FROM vm_config WHERE guild_id = ?",
                (guild.id,),
            )
            cfg = await cur.fetchone()
            cur = await db.execute(
                "SELECT user_limit, bitrate, region FROM vm_defaults WHERE guild_id = ?",
                (guild.id,),
            )
            defs = await cur.fetchone()
            cur = await db.execute(
                "SELECT COUNT(*) FROM vm_channels WHERE guild_id = ?", (guild.id,)
            )
            active = (await cur.fetchone())[0]

        if not cfg:
            return await ctx.reply(
                embed=_err("VoiceMaster is not set up. Use `voicemaster setup`."),
                mention_author=False,
            )

        cat = guild.get_channel(cfg[0])
        gen = guild.get_channel(cfg[1])
        iface = guild.get_channel(cfg[2])

        desc = (
            f"**Category:** {cat.name if cat else 'Deleted'}\n"
            f"**Generator:** {gen.mention if gen else 'Deleted'}\n"
            f"**Interface:** {iface.mention if iface else 'Deleted'}\n"
            f"**Active Channels:** {active}\n"
        )

        if defs:
            limit_txt = str(defs[0]) if defs[0] else "Unlimited"
            bitrate_txt = f"{(defs[1] or 64000) // 1000} kbps"
            region_txt = defs[2] or "Automatic"
            desc += (
                f"\n**Default User Limit:** {limit_txt}\n"
                f"**Default Bitrate:** {bitrate_txt}\n"
                f"**Default Region:** {region_txt}"
            )

        embed = discord.Embed(title="VoiceMaster Configuration", description=desc, color=COLOR)
        embed.set_footer(text="Synapse - VoiceMaster")
        await ctx.reply(embed=embed, mention_author=False)

    @voicemaster.group(
        name="default",
        invoke_without_command=True,
        help="Configure default settings for new temp voice channels.",
    )
    @blacklist_check()
    @ignore_check()
    async def vm_default(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        await self._send_help(ctx)

    @vm_default.command(name="limit", help="Set the default user limit for new channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_default_limit(self, ctx: commands.Context, limit: int):
        if not 0 <= limit <= 99:
            return await ctx.reply(embed=_err("Limit must be between 0 and 99."), mention_author=False)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vm_defaults (guild_id, user_limit) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET user_limit = ?",
                (ctx.guild.id, limit, limit),
            )
            await db.commit()
        txt = f"Default user limit set to **{limit}**." if limit else "Default user limit **removed**."
        await ctx.reply(embed=_ok(txt))

    @vm_default.command(name="bitrate", help="Set the default bitrate (kbps) for new channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_default_bitrate(self, ctx: commands.Context, kbps: int):
        val = kbps * 1000
        if not 8000 <= val <= 384000:
            return await ctx.reply(embed=_err("Bitrate must be between 8 and 384 kbps."), mention_author=False)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vm_defaults (guild_id, bitrate) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET bitrate = ?",
                (ctx.guild.id, val, val),
            )
            await db.commit()
        await ctx.reply(embed=_ok(f"Default bitrate set to **{kbps} kbps**."))

    @vm_default.command(name="region", help="Set the default voice region for new channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_default_region(self, ctx: commands.Context, *, region: str):
        val = region.strip().lower()
        rtc = None if val in ("auto", "automatic", "none") else val
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vm_defaults (guild_id, region) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET region = ?",
                (ctx.guild.id, rtc, rtc),
            )
            await db.commit()
        await ctx.reply(embed=_ok(f"Default region set to **{rtc or 'Automatic'}**."))

    @voicemaster.command(name="category", help="Set the category for VoiceMaster temporary channels.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def vm_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """Set the category where new temporary voice channels will be created."""
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM vm_config WHERE guild_id = ?", (ctx.guild.id,)
            )
            if not await cur.fetchone():
                return await ctx.reply(
                    embed=_err("VoiceMaster is not set up in this server. Use `voicemaster setup` first."),
                    mention_author=False,
                )
            
            await db.execute(
                "UPDATE vm_config SET category_id = ? WHERE guild_id = ?",
                (category.id, ctx.guild.id),
            )
            await db.commit()

        await ctx.reply(
            embed=_ok(f"VoiceMaster temporary voice channels will now be created in the category **{category.name}**."),
            mention_author=False,
        )



async def setup(bot: commands.Bot):
    await _init_db()
    bot.add_view(VoiceMasterView())
    await bot.add_cog(VoiceMaster(bot))
