import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands

DB_PATH      = "database/antiraid.db"
COLOR        = 0x2b2d31
E_SHIELD = "<:synapseShield:1477548906848981225>"

class ARE:
    URL_SHIELD = "https://cdn.discordapp.com/emojis/1477548906848981225.png"
    @staticmethod
    def error(text: str) -> discord.Embed:
        return discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {text}", color=COLOR)

    @staticmethod
    def log(member: discord.Member, reason: str, action: str) -> discord.Embed:
        embed = discord.Embed(
            description=f"**User:** {member.mention} (`{member.id}`)\n**Action Taken:** `{action.capitalize()}`\n**Trigger:** {reason}",
            color=COLOR,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name="Antiraid Triggered", icon_url=ARE.URL_SHIELD)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Synapse Antiraid System")
        return embed

async def get_config(guild_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM antiraid_config WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            keys = ["guild_id", "enabled", "punishment", "log_channel_id", "alert_role_id", "massjoin_limit", "massjoin_time", "accountage_days"]
            return dict(zip(keys, row))

async def get_enabled_events(guild_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT event_name FROM antiraid_events WHERE guild_id=? AND enabled=1", (guild_id,)) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

class AntiraidEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> [list of join timestamps]
        self.massjoin_cache = {} 
        
        # guild_id -> {creation_timestamp_str: count}
        # to reset it slowly
        self.samecreation_cache = {} 
        self.last_samecreation_clear = time.time()
        
        # guild_id -> timestamp of last ping
        self.alert_cooldown = {}

    async def execute_punishment(self, member: discord.Member, config: dict, reason: str):
        action = config.get("punishment", "ban").lower()
        alert_role_id = config.get("alert_role_id")
        log_channel_id = config.get("log_channel_id")
        guild = member.guild

        # Execute Mod Action
        try:
            if action == "ban":
                await member.ban(reason=f"Synapse Antiraid: {reason}")
            else:
                await member.kick(reason=f"Synapse Antiraid: {reason}")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        # Send Log & Alert Role
        if log_channel_id:
            log_ch = guild.get_channel(log_channel_id)
            if log_ch:
                content = None
                if alert_role_id:
                    role = guild.get_role(alert_role_id)
                    if role:
                        now = time.time()
                        last_ping = self.alert_cooldown.get(guild.id, 0)
                        if now - last_ping > 60: # 60 second cooldown on pings
                            content = f"{role.mention} Raid Detected!"
                            self.alert_cooldown[guild.id] = now
                try:
                    await log_ch.send(content=content, embed=ARE.log(member, reason, action))
                except Exception:
                    pass

    def clean_caches(self):
        now = time.time()
        if now - self.last_samecreation_clear > 120:
            self.samecreation_cache.clear()
            self.last_samecreation_clear = now

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        
        config = await get_config(member.guild.id)
        if not config or not config.get("enabled"):
            return
            
        events = await get_enabled_events(member.guild.id)
        if not events:
            return

        self.clean_caches()

        # 1. Default PFP Check
        if "defaultpfp" in events:
            if member.avatar is None:
                await self.execute_punishment(member, config, "Default Avatar Pattern Detected")
                return

        # 2. Account Age Check
        if "accountage" in events:
            min_days = config.get("accountage_days", 3)
            age = datetime.now(timezone.utc) - member.created_at
            if age.days < min_days:
                await self.execute_punishment(member, config, f"Account Age < {min_days} days")
                return

        # 3. Same Creation Date Check
        if "samecreation" in events:
            guild_id = member.guild.id
            if guild_id not in self.samecreation_cache:
                self.samecreation_cache[guild_id] = {}
            
            # Group by hour of creation
            creation_str = member.created_at.strftime("%Y-%m-%d %H")
            self.samecreation_cache[guild_id][creation_str] = self.samecreation_cache[guild_id].get(creation_str, 0) + 1
            
            # If 3 or more accounts from the exact same hour join closely
            if self.samecreation_cache[guild_id][creation_str] >= 3:
                await self.execute_punishment(member, config, f"Same Creation Date Pattern Detected ({creation_str})")
                return

        # 4. Mass Join Check
        if "massjoin" in events:
            guild_id = member.guild.id
            now = time.time()
            if guild_id not in self.massjoin_cache:
                self.massjoin_cache[guild_id] = []
                
            limit = config.get("massjoin_limit", 5)
            window = config.get("massjoin_time", 10)
            
            # Append current join
            self.massjoin_cache[guild_id].append(now)
            
            # Clear old joins
            self.massjoin_cache[guild_id] = [t for t in self.massjoin_cache[guild_id] if now - t <= window]
            
            if len(self.massjoin_cache[guild_id]) >= limit:
                await self.execute_punishment(member, config, f"Mass Join Detected ({limit} in {window}s)")
                return

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiraidEvents(bot))
