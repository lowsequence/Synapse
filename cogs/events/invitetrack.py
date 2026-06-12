import discord
from discord.ext import commands
import aiosqlite
import os
import datetime

DB_PATH = os.path.join("database", "invites.db")

class InviteTrackEvents(commands.Cog):
    """Core Event Listener for advanced premium invite tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.invites = {}

    async def cog_load(self):
        await self._init_db()
        await self._update_all_invites()

    async def _init_db(self):
        """Initializes the completely new invites.db"""
        os.makedirs("database", exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_counts (
                    guild_id INTEGER,
                    user_id INTEGER,
                    total_invites INTEGER DEFAULT 0,
                    regular_invites INTEGER DEFAULT 0,
                    fake_invites INTEGER DEFAULT 0,
                    left_invites INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_config (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    alt_threshold INTEGER DEFAULT 3
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_roles (
                    guild_id INTEGER,
                    invites_required INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, invites_required)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS join_leaves (
                    guild_id INTEGER,
                    member_id INTEGER,
                    inviter_id INTEGER,
                    PRIMARY KEY (guild_id, member_id)
                )
            """)
            await db.commit()

    async def _update_all_invites(self):
        """Initial cache generation on bot load"""
        for guild in self.bot.guilds:
            try:
                guild_invites = await guild.invites()
                self.invites[guild.id] = {invite.code: invite.uses for invite in guild_invites}
                if guild.vanity_url_code:
                    try:
                        vanity = await guild.vanity_invite()
                        self.invites[guild.id][guild.vanity_url_code] = vanity.uses
                    except discord.Forbidden:
                        pass
            except discord.Forbidden:
                pass

    def _find_inviter(self, guild, new_invites):
        """Helper to deduce which invite was used by comparing new vs old cache"""
        old_invites = self.invites.get(guild.id, {})
        for new_invite in new_invites:
            code = new_invite.code
            uses = new_invite.uses
            old_uses = old_invites.get(code, 0)
            if uses > old_uses:
                return new_invite.inviter
        return None

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild.id not in self.invites:
            self.invites[invite.guild.id] = {}
        self.invites[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invites and invite.code in self.invites[invite.guild.id]:
            del self.invites[invite.guild.id][invite.code]

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            guild_invites = await guild.invites()
            self.invites[guild.id] = {invite.code: invite.uses for invite in guild_invites}
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if guild.id in self.invites:
            del self.invites[guild.id]

    async def _check_invite_roles(self, guild, inviter, regular_invites):
        """Validates if the inviter reached a milestone and applies the role"""
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT invites_required, role_id FROM invite_roles WHERE guild_id = ? ORDER BY invites_required ASC", (guild.id,))
            rows = await cur.fetchall()

        for req, role_id in rows:
            if regular_invites >= req:
                role = guild.get_role(role_id)
                if role and role not in inviter.roles:
                    try:
                        await inviter.add_roles(role, reason=f"Reached {req} invites.")
                    except discord.Forbidden:
                        pass
            else:
                role = guild.get_role(role_id)
                if role and role in inviter.roles:
                    try:
                        await inviter.remove_roles(role, reason=f"Dropped below {req} invites.")
                    except discord.Forbidden:
                        pass


    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if guild.me.bot and member.bot:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled, alt_threshold FROM invite_config WHERE guild_id = ?", (guild.id,))
            config = await cur.fetchone()

        if not config or config[0] == 0:
            return

        alt_threshold_days = config[1]

        try:
            new_invites = await guild.invites()
            if guild.vanity_url_code:
                 try:
                     vanity = await guild.vanity_invite()
                     if vanity: new_invites.append(vanity)
                 except:
                     pass

            inviter = self._find_inviter(guild, new_invites)

            self.invites[guild.id] = {invite.code: invite.uses for invite in new_invites}

        except discord.Forbidden:
            return

        if not inviter:
            return

        is_fake = False
        now = discord.utils.utcnow()
        account_age = (now - member.created_at).days
        if account_age < alt_threshold_days:
            is_fake = True

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO invite_counts (guild_id, user_id, total_invites, regular_invites, fake_invites, left_invites)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET 
                    total_invites = total_invites + ?,
                    regular_invites = regular_invites + ?,
                    fake_invites = fake_invites + ?
            """, (
                guild.id, inviter.id, 
                1, 0 if is_fake else 1, 1 if is_fake else 0, 0,
                1, 0 if is_fake else 1, 1 if is_fake else 0
            ))

            await db.execute("INSERT OR REPLACE INTO join_leaves (guild_id, member_id, inviter_id) VALUES (?, ?, ?)", (guild.id, member.id, inviter.id))
            await db.commit()

            cur = await db.execute("SELECT regular_invites FROM invite_counts WHERE guild_id = ? AND user_id = ?", (guild.id, inviter.id))
            row = await cur.fetchone()
            if row:
                await self._check_invite_roles(guild, inviter, row[0])

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM invite_config WHERE guild_id = ?", (guild.id,))
            config = await cur.fetchone()

            if not config or config[0] == 0:
                return

            cur = await db.execute("SELECT inviter_id FROM join_leaves WHERE guild_id = ? AND member_id = ?", (guild.id, member.id))
            row = await cur.fetchone()

            if not row:
                return

            inviter_id = row[0]

            await db.execute("""
                UPDATE invite_counts SET 
                    left_invites = left_invites + 1,
                    regular_invites = MAX(0, regular_invites - 1)
                WHERE guild_id = ? AND user_id = ?
            """, (guild.id, inviter_id))

            await db.execute("DELETE FROM join_leaves WHERE guild_id = ? AND member_id = ?", (guild.id, member.id))
            await db.commit()

            cur = await db.execute("SELECT regular_invites FROM invite_counts WHERE guild_id = ? AND user_id = ?", (guild.id, inviter_id))
            count_row = await cur.fetchone()

            inviter_obj = guild.get_member(inviter_id)
            if inviter_obj and count_row:
                await self._check_invite_roles(guild, inviter_obj, count_row[0])


async def setup(bot):
    await bot.add_cog(InviteTrackEvents(bot))
