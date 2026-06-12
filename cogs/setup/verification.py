import discord
from discord.ext import commands
import aiosqlite
import random
import asyncio

from utils.Tools import blacklist_check, ignore_check

DB_PATH = "database/verification.db"
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS verify_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                channel_id INTEGER,
                role_id INTEGER,
                log_channel_id INTEGER,
                mode TEXT NOT NULL DEFAULT 'button',
                message TEXT DEFAULT 'Click the button below to verify yourself!',
                panel_message_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS verified_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                verified_at REAL NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()


async def get_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT enabled, channel_id, role_id, log_channel_id, mode, message, panel_message_id FROM verify_config WHERE guild_id = ?", (guild_id,)) as cur:
            return await cur.fetchone()


async def ensure_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO verify_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()


class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", emoji="<:icons_verify:1495402797883985963>", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify_btn(self, interaction: discord.Interaction, btn: discord.ui.Button):
        cfg = await get_config(interaction.guild.id)
        if not cfg or not cfg[0]:
            return await interaction.response.send_message("Verification is not enabled.", ephemeral=True)

        role = interaction.guild.get_role(cfg[2])
        if not role:
            return await interaction.response.send_message("Verification role not found. Contact an admin.", ephemeral=True)

        if role in interaction.user.roles:
            return await interaction.response.send_message("You are already verified!", ephemeral=True)

        mode = cfg[4]

        if mode == "button":
            try:
                await interaction.user.add_roles(role)
            except Exception:
                return await interaction.response.send_message("Failed to assign role.", ephemeral=True)

            import time
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO verified_users (guild_id, user_id, verified_at) VALUES (?, ?, ?)", (interaction.guild.id, interaction.user.id, time.time()))
                await db.commit()

            await interaction.response.send_message("<:emoji_1769867605256:1467155817726873650> You have been verified!", ephemeral=True)

            if cfg[3]:
                log_ch = interaction.guild.get_channel(cfg[3])
                if log_ch:
                    embed = discord.Embed(description=f"<:icons_verify:1495402797883985963> {interaction.user.mention} has been verified.", color=0x57f287)
                    await log_ch.send(embed=embed)

        elif mode == "math":
            a, b = random.randint(1, 20), random.randint(1, 20)
            answer = a + b
            await interaction.response.send_message(f"<:reminder:1495402276981051432> Solve to verify: **{a} + {b} = ?**\nType the answer below within 30 seconds.", ephemeral=True)

            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

            try:
                msg = await interaction.client.wait_for("message", check=check, timeout=30)
                try:
                    await msg.delete()
                except Exception:
                    pass
                if int(msg.content.strip()) == answer:
                    await interaction.user.add_roles(role)
                    import time
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("INSERT OR REPLACE INTO verified_users (guild_id, user_id, verified_at) VALUES (?, ?, ?)", (interaction.guild.id, interaction.user.id, time.time()))
                        await db.commit()
                    await interaction.followup.send("<:emoji_1769867605256:1467155817726873650> Correct! You have been verified.", ephemeral=True)
                else:
                    await interaction.followup.send("<:emoji_1769867589372:1467155751456735326> Wrong answer. Try again.", ephemeral=True)
            except asyncio.TimeoutError:
                await interaction.followup.send("<:reminder:1495402276981051432> Timed out. Try again.", ephemeral=True)


class VerificationCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        client.add_view(VerifyButton())

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def verify(self, ctx):
        """Verification system commands."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help verify` for a list of subcommands.")

    @verify.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_setup(self, ctx, channel: discord.TextChannel, role: discord.Role):
        """Set up the verification system."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET channel_id = ?, role_id = ?, enabled = 1 WHERE guild_id = ?", (channel.id, role.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification set up in {channel.mention} with role {role.mention}. Use `verify sendpanel` to send the panel.")

    @verify.command(name="mode")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_mode(self, ctx, mode: str):
        """Set verification mode: button or math."""
        mode = mode.lower()
        if mode not in ("button", "math"):
            return await ctx.reply(f"{E_ERR} Mode must be `button` or `math`.")
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET mode = ? WHERE guild_id = ?", (mode, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification mode set to **{mode}**.")

    @verify.command(name="message")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_message(self, ctx, *, text: str):
        """Set the verification panel message."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET message = ? WHERE guild_id = ?", (text, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification panel message updated.")

    @verify.command(name="logchannel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_logchannel(self, ctx, channel: discord.TextChannel):
        """Set the verification log channel."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET log_channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification logs will be sent to {channel.mention}.")

    @verify.command(name="sendpanel")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_sendpanel(self, ctx):
        """Send the verification panel."""
        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg[1]:
            return await ctx.reply(f"{E_ERR} Run `verify setup` first.")

        channel = ctx.guild.get_channel(cfg[1])
        if not channel:
            return await ctx.reply(f"{E_ERR} Verification channel not found.")

        embed = discord.Embed(
            title="<:icons_verify:1495402797883985963> Verification",
            description=cfg[5] or "Click the button below to verify yourself!",
            color=0x57f287,
        )
        embed.set_footer(text=f"{ctx.guild.name} • Verification System")
        msg = await channel.send(embed=embed, view=VerifyButton())

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET panel_message_id = ? WHERE guild_id = ?", (msg.id, ctx.guild.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification panel sent to {channel.mention}.")

    @verify.command(name="enable")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_enable(self, ctx):
        """Enable the verification system."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification **enabled**.")

    @verify.command(name="disable")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_disable(self, ctx):
        """Disable the verification system."""
        await ensure_config(ctx.guild.id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE verify_config SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification **disabled**.")

    @verify.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def verify_config(self, ctx):
        """View verification config."""
        cfg = await get_config(ctx.guild.id)
        if not cfg:
            return await ctx.reply(f"{E_ERR} Verification not configured.")

        ch = ctx.guild.get_channel(cfg[1]) if cfg[1] else None
        role = ctx.guild.get_role(cfg[2]) if cfg[2] else None
        log_ch = ctx.guild.get_channel(cfg[3]) if cfg[3] else None

        embed = discord.Embed(title="<:icons_verify:1495402797883985963> Verification Config", color=EMBED_COLOR)
        embed.add_field(name="Status", value="Enabled" if cfg[0] else "Disabled")
        embed.add_field(name="Channel", value=ch.mention if ch else "Not set")
        embed.add_field(name="Role", value=role.mention if role else "Not set")
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        embed.add_field(name="Mode", value=cfg[4].title())
        await ctx.reply(embed=embed, mention_author=False)

    @verify.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verify_reset(self, ctx):
        """Reset all verification settings."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM verify_config WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM verified_users WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(f"{E_OK} Verification system fully reset.")

    @verify.command(name="stats")
    @blacklist_check()
    @ignore_check()
    async def verify_stats(self, ctx):
        """View verification stats."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM verified_users WHERE guild_id = ?", (ctx.guild.id,)) as cur:
                count = (await cur.fetchone())[0]
        embed = discord.Embed(title="<:icons_verify:1495402797883985963> Verification Stats", color=EMBED_COLOR)
        embed.add_field(name="Total Verified", value=str(count))
        embed.add_field(name="Server Members", value=str(ctx.guild.member_count))
        await ctx.reply(embed=embed, mention_author=False)

    @verify.command(name="user")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    async def verify_user(self, ctx, member: discord.Member):
        """Manually verify a user."""
        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg[2]:
            return await ctx.reply(f"{E_ERR} Verification not configured.")
        role = ctx.guild.get_role(cfg[2])
        if not role:
            return await ctx.reply(f"{E_ERR} Verification role not found.")
        await member.add_roles(role)
        import time
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO verified_users (guild_id, user_id, verified_at) VALUES (?, ?, ?)", (ctx.guild.id, member.id, time.time()))
            await db.commit()
        await ctx.reply(f"{E_OK} {member.mention} has been manually verified.")

    @verify.command(name="unverify")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    async def verify_unverify(self, ctx, member: discord.Member):
        """Remove verification from a user."""
        cfg = await get_config(ctx.guild.id)
        if not cfg or not cfg[2]:
            return await ctx.reply(f"{E_ERR} Verification not configured.")
        role = ctx.guild.get_role(cfg[2])
        if role and role in member.roles:
            await member.remove_roles(role)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM verified_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()
        await ctx.reply(f"{E_OK} {member.mention} has been unverified.")


async def setup(client):
    await init_db()
    await client.add_cog(VerificationCog(client))
