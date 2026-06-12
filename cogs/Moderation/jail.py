import discord
import aiosqlite
from discord.ext import commands
import os
from utils.automod_utils import Embeds
from utils.Tools import ignore_check, blacklist_check

JAIL_FOOTER = "Synapse - Jail System"

class JE:
    """Thin wrapper that forwards to Embeds with jail-specific footer."""
    @staticmethod
    def success(text): return Embeds.success(text, footer=JAIL_FOOTER)
    @staticmethod
    def error(text): return Embeds.error(text, footer=JAIL_FOOTER)
    @staticmethod
    def info(title, text): return Embeds.info(title, text, footer=JAIL_FOOTER)
    @staticmethod
    def config(title, fields): return Embeds.config(title, fields, footer=JAIL_FOOTER)


class Jail(commands.Cog):
    """Jail System for managing violators"""
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "database/jail.db"
        self.color = 0x2b2d31
        os.makedirs("database", exist_ok=True)

    def get_db(self):
        return aiosqlite.connect(self.db_path)

    async def cog_load(self):
        async with self.get_db() as db:
            await db.execute("CREATE TABLE IF NOT EXISTS jail_config (guild_id INTEGER PRIMARY KEY, role_id INTEGER, channel_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS jailed_users (guild_id INTEGER, user_id INTEGER, role_ids TEXT)")
            await db.commit()

    async def get_config(self, guild_id):
        async with self.get_db() as db:
            cursor = await db.execute("SELECT role_id, channel_id FROM jail_config WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    @commands.group(name="jail", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def jail_group(self, ctx, member: discord.Member = None):
        """Main jail command. Use 'jail @user' to jail someone."""
        if ctx.invoked_subcommand:
            return

        if not member:
            return await ctx.send(embed=JE.error("Please specify a member to jail."))

        config = await self.get_config(ctx.guild.id)
        if not config or not config[0]:
            return await ctx.send(embed=JE.error("Jail role is not configured for this server. Use `jail setup`."))

        jail_role = ctx.guild.get_role(config[0])
        if not jail_role:
             return await ctx.send(embed=JE.error("Jail role not found. Please run `jail setup` again."))

        if jail_role in member.roles:
            return await ctx.send(embed=JE.error("This user is already jailed."))

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(embed=JE.error("This user has a higher or equal role than me."))

        if member.id == ctx.author.id:
            return await ctx.send(embed=JE.error("You cannot jail yourself."))

        roles_to_remove = [r.id for r in member.roles if r != ctx.guild.default_role and not r.managed]
        role_ids_str = ",".join(map(str, roles_to_remove))

        async with self.get_db() as db:
            await db.execute("INSERT INTO jailed_users (guild_id, user_id, role_ids) VALUES (?, ?, ?)", (ctx.guild.id, member.id, role_ids_str))
            await db.commit()

        try:
            await member.edit(roles=[jail_role], reason="Jailed by AutoMod/Admin")
            await ctx.send(embed=JE.success(f"Successfully jailed {member.mention}."))
        except Exception as e:
            await ctx.send(embed=JE.error(f"Failed to jail member: {e}"))

    @commands.command(name="unjail")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def unjail(self, ctx, member: discord.Member):
        """Unjail a member and restore their roles"""
        config = await self.get_config(ctx.guild.id)
        if not config or not config[0]:
            return await ctx.send(embed=JE.error("Jail role is not configured."))

        jail_role = ctx.guild.get_role(config[0])
        async with self.get_db() as db:
            cursor = await db.execute("SELECT role_ids FROM jailed_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            row = await cursor.fetchone()

            if not row and (not jail_role or jail_role not in member.roles):
                return await ctx.send(embed=JE.error("This user is not jailed."))

            await db.execute("DELETE FROM jailed_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()

        roles_to_add = []
        if row and row[0]:
            role_ids = map(int, row[0].split(","))
            for rid in role_ids:
                r = ctx.guild.get_role(rid)
                if r: roles_to_add.append(r)

        try:
            await member.edit(roles=roles_to_add, reason="Unjailed by Admin")
            await ctx.send(embed=JE.success(f"Successfully unjailed {member.mention}."))
        except Exception as e:
            await ctx.send(embed=JE.error(f"Failed to unjail member: {e}"))

    @jail_group.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def jail_setup(self, ctx):
        """Setup the jail role and channel"""

        config = await self.get_config(ctx.guild.id)
        if config and config[0]:
            return await ctx.send(
                embed=JE.error(
                    "Jail is already setup for this server."
                )
            )

        embed = discord.Embed(description="<a:Loadixd:1469568214169288890> Setting Up Jail System.....", color=0x2b2d31)
        setupmsg = await ctx.send(embed=embed)

        role = await ctx.guild.create_role(
            name="Jailed",
            reason="AutoMod Jail Setup"
        )

        await role.edit(
            permissions=discord.Permissions.none()
        )

        for channel in ctx.guild.channels:
            try:
                await channel.set_permissions(
                    role,
                    view_channel=False,
                    send_messages=False,
                    add_reactions=False,
                    connect=False,
                    speak=False
                )
            except discord.Forbidden:
                pass

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        channel = await ctx.guild.create_text_channel(
            name="jail",
            overwrites=overwrites,
            reason="AutoMod Jail Setup"
        )

        async with self.get_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO jail_config (guild_id, role_id, channel_id) "
                "VALUES (?, ?, ?)",
                (
                    ctx.guild.id,
                    role.id,
                    channel.id
                )
            )
            await db.commit()

        await setupmsg.edit(
            embed=JE.success(
                f"Jail system setup complete. The jail role is: {role.mention} and channel is {channel.mention}"


            )
        )

    @jail_group.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def jail_reset(self, ctx):
        """Reset the jail system settings"""

        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.send(
                embed=JE.error("Jail system is not configured.")
            )

        role_id, channel_id = config

        if role_id:
            role = ctx.guild.get_role(role_id)
            if role:
                try:
                    await role.delete(
                        reason="Jail system reset"
                    )
                except discord.Forbidden:
                    pass

        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete(
                        reason="Jail system reset"
                    )
                except discord.Forbidden:
                    pass

        async with self.get_db() as db:
            await db.execute(
                "DELETE FROM jail_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            await db.execute(
                "DELETE FROM jailed_users WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            await db.commit()

        await ctx.send(
            embed=JE.success(
                "Jail system has been fully reset and cleaned up."

            )
        )

    @jail_group.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def jail_config(self, ctx):
        """View jail configuration"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.send(embed=JE.error("Jail is not configured."))

        await ctx.send(embed=JE.config("Jail", {
            "Role": f"<@&{config[0]}>" if config[0] else "None",
            "Channel": f"<#{config[1]}>" if config[1] else "None"
        }))

async def setup(bot):
    await bot.add_cog(Jail(bot))

