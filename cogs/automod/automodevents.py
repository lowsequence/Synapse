import discord
import aiosqlite
import re
import os
from discord.ext import commands
from datetime import timedelta, datetime
from utils.automod_utils import Embeds

class AutoModEvents(commands.Cog):
    """Handles all AutoMod events and detection logic"""
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "database/automod.db"
        self.jail_db = "database/jail.db"
        self.spam_cache = {}
        self.link_regex = re.compile(r"https?://[^\s]+")
        self.invite_regex = re.compile(r"(discord\.gg/|discord\.com/invite/)[a-zA-Z0-9]+")
        # Matches Unicode emojis and Discord custom emojis
        self.emoji_regex = re.compile(
            r"("
            r"<a?:[a-zA-Z0-9_]+:[0-9]+>"
            r"|[\U0001F600-\U0001F64F]"
            r"|[\U0001F300-\U0001F5FF]"
            r"|[\U0001F680-\U0001F6FF]"
            r"|[\U0001F1E0-\U0001F1FF]"
            r"|[\U00002702-\U000027B0]"
            r"|[\U000024C2-\U0001F251]"
            r"|[\U0001f926-\U0001f937]"
            r"|[\U00010000-\U0010ffff]"
            r"|[\u2640-\u2642]"
            r"|[\u2600-\u2B55]"
            r"|[\u200d]"
            r"|[\u23cf]"
            r"|[\u23e9]"
            r"|[\u231a]"
            r"|[\ufe0f]"
            r"|[\u3030]"
            r")"
        )

    async def get_db_row(self, table, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"SELECT * FROM {table} WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    async def is_whitelisted(self, message):
        guild_id = message.guild.id
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT target_id, type FROM whitelist WHERE guild_id = ?", (guild_id,))
            rows = await cursor.fetchall()
            for r_id, r_type in rows:
                if r_type == "user" and message.author.id == r_id: return True
                if r_type == "channel" and message.channel.id == r_id: return True
                if r_type == "role":
                    if any(role.id == r_id for role in message.author.roles): return True
        return False

    async def log_violation(self, guild, user, module, content, channel):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT webhook_url FROM logging WHERE guild_id = ?", (guild.id,))
            row = await cursor.fetchone()
            if not row: return

            try:
                case_id = f"#{int(datetime.now().timestamp())}"
                webhook = discord.SyncWebhook.from_url(row[0])
                embed = discord.Embed(
                    description=(
                        f"## <:synapse_automod:1471871079256424550> AutoMod Violation Logged\n"
                        f"<:syanapse_bar:1471870923241029753> **User:** {user.mention} (`{user.id}`)\n"
                        f"<:syanapse_bar:1471870923241029753> **Module:** `{module}`\n"
                        f"<:syanapse_bar:1471870923241029753> **Channel:** {channel.mention}\n"
                        f"<:syanapse_bar:1471870923241029753> **Case:** `{case_id}`\n"
                        f"\n"
                        f"### <:Synapse_search:1471871156783943812> Detected Message\n"
                        f"> {content[:500] if content else '*No content (attachments only)*'}\n"

                    ),                                                                                                             


                    color=Embeds.COLOR,
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Violation Case {case_id} • Synapse AutoMod", icon_url=self.bot.user.display_avatar.url)
                webhook.send(embed=embed, username="Synapse AutoMod")
            except: pass

    async def execute_punishment(self, message, module, punishment, timeout_sec):
        user = message.author
        guild = message.guild

        try:
            if punishment == "timeout" and timeout_sec > 0:
                await user.timeout(timedelta(seconds=timeout_sec), reason=f"AutoMod: {module}")
            elif punishment == "kick":
                await user.kick(reason=f"AutoMod: {module}")
            elif punishment == "ban":
                await user.ban(reason=f"AutoMod: {module}")
            elif punishment == "jail":
                if os.path.exists(self.jail_db):
                    async with aiosqlite.connect(self.jail_db) as db:
                        cursor = await db.execute("SELECT role_id FROM jail_config WHERE guild_id = ?", (guild.id,))
                        row = await cursor.fetchone()
                        if row and row[0]:
                            jail_role = guild.get_role(row[0])
                            if jail_role:
                                await user.edit(roles=[jail_role], reason=f"AutoMod: {module}")




            pretty = (
                    "timed out" if punishment == "timeout"
                    else "kicked" if punishment == "kick"
                    else "banned" if punishment == "ban"
                    else "jailed" if punishment == "jail"
                    else "warned" if punishment == "none"
                    else punishment
                )
            embed = discord.Embed(
                description=(
                    f"<:eye_automod:1471870318388707564> {user.mention} has been **{pretty}** due to a violation detected under the **{module}** module.\n"
                    f"<:WickAutoMod:1471870274659160156> Please ensure compliance with server rules to avoid future actions.\n"
                ),
                color=Embeds.COLOR,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_author(name="AutoMod System", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Synapse AutoMod • Enforcement", icon_url=message.guild.icon.url if message.guild.icon else user.display_avatar.url)
            await message.channel.send(content=user.mention, embed=embed, delete_after=8)

            await self.log_violation(guild, user, module, message.content, message.channel)

        except Exception as e: print(f"Punishment Error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        # Moderator bypass removed globally to allow per-module control or total enforcement
        # if message.author.guild_permissions.manage_messages: return 
        if await self.is_whitelisted(message): return

        content = message.content
        guild_id = message.guild.id

        r = await self.get_db_row("config_anticaps", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            if len(content) >= r[5]:
                caps = sum(1 for c in content if c.isupper())
                total = sum(1 for c in content if c.isalpha())
                if total > 0 and (caps / total) * 100 >= r[6]:
                    try: await message.delete()
                    except: pass
                    return await self.execute_punishment(message, "Anti-Caps", r[3], r[4])

        r = await self.get_db_row("config_antiinvite", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            invites = self.invite_regex.findall(content)
            if invites:
                async with aiosqlite.connect(self.db_path) as db:
                    c = await db.execute("SELECT code FROM allowed_invites WHERE guild_id = ?", (guild_id,))
                    allowed = [row[0] for row in await c.fetchall()]
                for inv in invites:
                    code = inv.split("/")[-1]
                    if code not in allowed:
                        try: await message.delete()
                        except: pass
                        return await self.execute_punishment(message, "Anti-Invite", r[3], r[4])

        r = await self.get_db_row("config_antilink", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            links = self.link_regex.findall(content)
            if links:
                async with aiosqlite.connect(self.db_path) as db:
                    c = await db.execute("SELECT pattern FROM allowed_links WHERE guild_id = ?", (guild_id,))
                    allowed = [row[0] for row in await c.fetchall()]
                for link in links:
                    if not any(p in link for p in allowed):
                        try: await message.delete()
                        except: pass
                        return await self.execute_punishment(message, "Anti-Link", r[3], r[4])

        r = await self.get_db_row("config_antinsfw", guild_id)
        if r and r[1] and not message.channel.nsfw and not message.author.guild_permissions.manage_messages:
            is_nsfw = False
            if message.attachments:
                for a in message.attachments:
                    if a.content_type and "image" in a.content_type and a.is_spoiler(): is_nsfw = True
            if is_nsfw:
                try: await message.delete()
                except: pass
                return await self.execute_punishment(message, "Anti-NSFW", r[3], r[4])

        r = await self.get_db_row("config_antiswear", guild_id)
        if r and r[1]:
            # NOTE: Swear filter applies to EVERYONE (including moderators) if enabled.
            async with aiosqlite.connect(self.db_path) as db:
                c = await db.execute("SELECT word FROM swear_words WHERE guild_id = ?", (guild_id,))
                words = [row[0] for row in await c.fetchall()]
            
            if words:
                content_lower = content.lower()
                # MASTER REGEX: Combine all words into a single optimized pattern for speed
                # We use word boundaries only if the word is fully alphanumeric to prevent false positives
                patterns = []
                for w in words:
                    w_escaped = re.escape(w.lower())
                    if w.isalnum():
                        patterns.append(rf"\b{w_escaped}\b")
                    else:
                        patterns.append(w_escaped)
                
                master_pattern = re.compile("|".join(patterns), flags=re.IGNORECASE | re.UNICODE)
                if master_pattern.search(content_lower):
                    try: await message.delete()
                    except: pass
                    return await self.execute_punishment(message, "Anti-Swear", r[3], r[4])

        r = await self.get_db_row("config_antispam", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            key = (message.author.id, guild_id)
            now = datetime.now().timestamp()
            if key not in self.spam_cache: self.spam_cache[key] = []
            self.spam_cache[key].append(now)
            self.spam_cache[key] = [t for t in self.spam_cache[key] if now - t < 5]
            if len(self.spam_cache[key]) >= r[5]:
                self.spam_cache[key] = []
                try: await message.delete()
                except: pass
                return await self.execute_punishment(message, "Anti-Spam", r[3], r[4])

        r = await self.get_db_row("config_antiemoji", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            emoji_count = len(self.emoji_regex.findall(content))
            if emoji_count > r[5]:
                try: await message.delete()
                except: pass
                return await self.execute_punishment(message, "Anti-Emoji Spam", r[3], r[4])

        r = await self.get_db_row("config_antimassline", guild_id)
        if r and r[1] and not message.author.guild_permissions.manage_messages:
            line_count = len(content.splitlines())
            if line_count > r[5]:
                try: await message.delete()
                except: pass
                return await self.execute_punishment(message, "Anti-Mass Line", r[3], r[4])

async def setup(bot):
    await bot.add_cog(AutoModEvents(bot))
