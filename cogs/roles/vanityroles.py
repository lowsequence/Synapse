import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/vanityroles.db"
EMBED_COLOR = 0x2b2d31

class VanityRolesCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def vanityroles(self, ctx):
        """Main Vanityroles Command Group"""
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        return await help_cog.send_group_help_auto(ctx, ctx.command)


    @vanityroles.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def setup(self, ctx, vanity: str, role: discord.Role, channel: discord.TextChannel):
        """Setup the vanityrole system"""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT enabled FROM vanity_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                embed = discord.Embed(
                    title="Vanityroles Setup Failed",
                    description="Vanityroles is already configured. Use `vanityroles reset` first.",
                    color=EMBED_COLOR
                )
                return await ctx.send(embed=embed)

            await db.execute(
                "INSERT INTO vanity_roles (guild_id, vanity, role_id, log_channel_id, mode, enabled, current_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, vanity.strip(), role.id, channel.id, "message", 1, None)
            )
            await db.commit()

        cog = self.bot.get_cog("VanityRolesEvent")
        if cog:
            cog.cache[ctx.guild.id] = {
                "vanity": vanity.strip().lower(),
                "role_id": role.id,
                "channel_id": channel.id,
                "mode": "message"
            }

        embed = discord.Embed(
            title="Vanityroles Setup Complete",
            description=f"<:emoji_1769867605256:1467155817726873650> Vanity `{vanity}` → {role.mention} in {channel.mention}",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @vanityroles.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def reset(self, ctx):
        """Reset the vanityroles configuration"""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT enabled FROM vanity_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                embed = discord.Embed(
                    title="Vanityroles Reset Failed",
                    description="<:emoji_1769867589372:1467155751456735326> Vanityroles is not configured.",
                    color=EMBED_COLOR
                )
                return await ctx.send(embed=embed)

            await db.execute("DELETE FROM vanity_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        cog = self.bot.get_cog("VanityRolesEvent")
        if cog and ctx.guild.id in cog.cache:
            del cog.cache[ctx.guild.id]

        embed = discord.Embed(
            title="Vanityroles Reset",
            description="<:emoji_1769867605256:1467155817726873650> Vanityroles configuration has been reset.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @vanityroles.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def config(self, ctx):
        """Shows the configuration of vanityroles"""
        cog = self.bot.get_cog("VanityRolesEvent")
        cfg = cog.cache.get(ctx.guild.id) if cog else None

        if not cfg:
            embed = discord.Embed(
                title="Vanityroles Config",
                description="<:emoji_1769867589372:1467155751456735326> Vanityroles is not enabled.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        role = ctx.guild.get_role(cfg["role_id"])
        channel = ctx.guild.get_channel(cfg["channel_id"])

        embed = discord.Embed(title="Vanityroles Configuration", color=EMBED_COLOR)
        embed.add_field(name="Vanity", value=cfg["vanity"], inline=False)
        embed.add_field(name="Role", value=role.mention if role else "Not found", inline=False)
        embed.add_field(name="Channel", value=channel.mention if channel else "Not found", inline=False)
        embed.add_field(name="Mode", value=cfg["mode"], inline=False)
        await ctx.send(embed=embed)

    @vanityroles.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def toggle(self, ctx, option: str):
        """Toggle vanityroles (disable/enable)"""
        option = option.lower()
        if option not in ["enable", "disable"]:
            embed = discord.Embed(
                title="Vanityroles Toggle Failed",
                description="<:emoji_1769867589372:1467155751456735326> Option must be `enable` or `disable`.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT enabled FROM vanity_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                embed = discord.Embed(
                    title="Vanityroles Toggle Failed",
                    description="<:emoji_1769867589372:1467155751456735326> Vanityroles is not configured.",
                    color=EMBED_COLOR
                )
                return await ctx.send(embed=embed)

            enabled = 1 if option == "enable" else 0
            await db.execute("UPDATE vanity_roles SET enabled = ? WHERE guild_id = ?", (enabled, ctx.guild.id))
            await db.commit()

        cog = self.bot.get_cog("VanityRolesEvent")
        if cog:
            if enabled:
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT vanity, role_id, log_channel_id, mode FROM vanity_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            vanity, role_id, channel_id, mode = row
                            cog.cache[ctx.guild.id] = {
                                "vanity": vanity.lower(),
                                "role_id": role_id,
                                "channel_id": channel_id,
                                "mode": mode
                            }
            else:
                if ctx.guild.id in cog.cache:
                    del cog.cache[ctx.guild.id]

        embed = discord.Embed(
            title="Vanityroles Toggled",
            description=f"<:emoji_1769867605256:1467155817726873650> Vanityroles has been {option}d.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @vanityroles.command()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def mode(self, ctx, mode_type: str):
        """Change the vanityroles mode from embed, message and image"""
        mode_type = mode_type.lower()
        if mode_type not in ["message", "embed", "image"]:
            embed = discord.Embed(
                title="Vanityroles Mode Failed",
                description="<:emoji_1769867589372:1467155751456735326> Mode must be `message`, `embed`, or `image`.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE vanity_roles SET mode = ? WHERE guild_id = ?", (mode_type, ctx.guild.id))
            await db.commit()

        cog = self.bot.get_cog("VanityRolesEvent")
        if cog and ctx.guild.id in cog.cache:
            cog.cache[ctx.guild.id]["mode"] = mode_type

        embed = discord.Embed(
            title="Vanityroles Mode Updated",
            description=f"<:emoji_1769867605256:1467155817726873650> Mode set to `{mode_type}`.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(VanityRolesCommands(bot))
