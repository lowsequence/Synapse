import os
import io
import asyncio
import aiosqlite
import aiohttp
import discord
from discord import ui
from discord.ext import commands
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

DB_PATH = os.path.join("database", "ytverify.db")

COLOR_YT = 0x2b2d31
COLOR_PASS = 0x43b581
COLOR_FAIL = 0xf04747
FOOTER = "Synapse · YouTube Verifier"
E_OK   = "<:emoji_1769867605256:1467155817726873650>"
E_ERR  = "<:SynapseExcl:1477234549552320634>"

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"- {desc}", color=COLOR_YT)

def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"- {desc}", color=COLOR_YT)


class YTVerifyPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Verify Subscription", emoji="<:SynapsYoutube:1466044611599302686>", style=discord.ButtonStyle.secondary, custom_id="ytverify_panel_btn")
    async def verify_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=_err("Please **upload your screenshot** directly in this channel within 60 seconds. \nThe bot will automatically scan and delete it."),
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and m.attachments

        try:
            msg = await interaction.client.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            return await interaction.followup.send(embed=_err("Verification timed out. Click the button again when you are ready."), ephemeral=True)

        attachment = msg.attachments[0]
        if not attachment.content_type or not attachment.content_type.startswith("image/"):
            try: await msg.delete() 
            except: pass
            return await interaction.followup.send(embed=_err("Invalid file type. Please upload an image screenshot."), ephemeral=True)

        if pytesseract is None:
            return await interaction.followup.send(embed=_err("Error: Optical Character Recognition (`pytesseract`) is not installed on the server."), ephemeral=True)

        processing_msg = await msg.reply(embed=_ok("Scanning your image, please wait... <a:Loading:1477234549552320634>"))

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ytverify_configs WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                config = await cursor.fetchone()

        if not config:
            return await processing_msg.edit(embed=_err("Verifier is not configured correctly on this server."))

        target_yt_channel = config["target_yt_channel"].lower()
        reward_role_id = config["reward_role_id"]
        log_channel_id = config["log_channel_id"]
        try:
            auto_delete = config["auto_delete"]
        except (KeyError, IndexError):
            auto_delete = 0

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        return await processing_msg.edit(embed=_err("Failed to download your image."))
                    data = await resp.read()

            image = Image.open(io.BytesIO(data))

            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, pytesseract.image_to_string, image)
            text_lower = text.lower()

            is_subscribed = "subscribed" in text_lower or "abonné" in text_lower
            has_channel_name = target_yt_channel in text_lower

            if is_subscribed and has_channel_name:
                role = interaction.guild.get_role(reward_role_id)
                if role:
                    try:
                        await interaction.user.add_roles(role, reason="Automated YouTube Verification via OCR")
                        await processing_msg.edit(embed=_ok(f"**Verification Passed!** You have been granted the {role.mention} role."))
                    except Exception as e:
                        await processing_msg.edit(embed=_err(f"Passed verification, but I could not assign the role: `{e}`"))
                else:
                    await processing_msg.edit(embed=_err("**Verification Passed!** But the reward role no longer exists."))

                log_ch = interaction.guild.get_channel(log_channel_id)
                if log_ch:
                    e = discord.Embed(
                        description=f"- **User:** {interaction.user.mention}\n- **Status:** {E_OK} Verification Passed\n- **Target Channel:** `{config['target_yt_channel']}`",
                        color=COLOR_PASS
                    )
                    e.set_author(name=f"{interaction.user} Verified", icon_url=interaction.user.display_avatar.url)
                    e.set_image(url=attachment.url)
                    await log_ch.send(embed=e)

            else:
                fail_reasons = []
                if not is_subscribed: fail_reasons.append("Could not find the word **'Subscribed'**.")
                if not has_channel_name: fail_reasons.append(f"Could not find the channel name **'{config['target_yt_channel']}'**.")

                await processing_msg.edit(embed=_err(f"**Verification Failed!**\n\n" + "\n".join(f"- {r}" for r in fail_reasons) + "\n\nMake sure your screenshot clearly shows BOTH components and is not blurry."))

                log_ch = interaction.guild.get_channel(log_channel_id)
                if log_ch:
                    e = discord.Embed(
                        description=f"- **User:** {interaction.user.mention}\n- **Status:** {E_ERR} Verification Failed\n- **Missing:** {', '.join(fail_reasons)}",
                        color=COLOR_FAIL
                    )
                    e.set_author(name=f"{interaction.user} Failed Verification", icon_url=interaction.user.display_avatar.url)
                    e.set_image(url=attachment.url)
                    await log_ch.send(embed=e)

            if auto_delete > 0:
                try: await msg.delete(delay=auto_delete)
                except: pass
                try: await processing_msg.delete(delay=auto_delete)
                except: pass

        except Exception as e:
            await processing_msg.edit(embed=_err(f"An error occurred during image processing: `{e}`"))
            if auto_delete > 0:
                try: await msg.delete(delay=auto_delete)
                except: pass
                try: await processing_msg.delete(delay=auto_delete)
                except: pass


class YTVerifyUI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(YTVerifyPanelView())

    @property
    def YTVerifyPanelView(self):
        """Allows access to the view class for other Cogs (e.g YTVerifyCommands)"""
        return YTVerifyPanelView

async def setup(bot):
    await bot.add_cog(YTVerifyUI(bot))
