import os
import asyncio
import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check


DB_PATH     = os.path.join("database", "voice.db")
EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


async def _init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS vcroles (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                role_id    INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );
            """
        )
        await db.commit()



def _embed(desc: str, color: int = EMBED_COLOR) -> discord.Embed:
    e = discord.Embed(description=desc, color=color)
    e.set_footer(text="Synapse - Voice System")
    return e

def _ok(desc: str) -> discord.Embed:
    return _embed(f"{E_OK} {desc}")

def _err(desc: str) -> discord.Embed:
    return _embed(f"{E_ERR} {desc}")



class Voice(commands.Cog):
    """Voice-channel management and VCRole auto-assign system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild_id = member.guild.id

        if after.channel and (before.channel != after.channel):
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT role_id FROM vcroles WHERE guild_id=? AND channel_id=?",
                    (guild_id, after.channel.id),
                ) as cur:
                    row = await cur.fetchone()
            if row:
                role = member.guild.get_role(row[0])
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="VCRole — joined VC")
                    except discord.Forbidden:
                        pass

        if before.channel and (before.channel != after.channel if after.channel else True):
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT role_id FROM vcroles WHERE guild_id=? AND channel_id=?",
                    (guild_id, before.channel.id),
                ) as cur:
                    row = await cur.fetchone()
            if row:
                role = member.guild.get_role(row[0])
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="VCRole — left VC")
                    except discord.Forbidden:
                        pass


    @staticmethod
    def _vc(ctx: commands.Context) -> discord.VoiceChannel | None:
        return ctx.author.voice.channel if ctx.author.voice else None


    @commands.group(
        name="voice",
        invoke_without_command=True,
        help="Voice channel management commands.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def voice(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @voice.command(
        name="ban",
        help="Disconnect a member and block them from rejoining the VC.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_ban(self, ctx: commands.Context, member: discord.Member) -> None:
        """Disconnect and deny Connect for a member in the author's VC."""
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        if not member.voice or member.voice.channel != vc:
            return await ctx.send(embed=_err(f"{member.mention} is not in your voice channel."))

        try:
            overwrite = vc.overwrites_for(member)
            overwrite.connect = False
            await vc.set_permissions(member, overwrite=overwrite, reason=f"Voice ban by {ctx.author}")
            await member.move_to(None, reason=f"Voice ban by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been **voice banned** from {vc.mention}."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="kick",
        help="Disconnect a member from their voice channel.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_kick(self, ctx: commands.Context, member: discord.Member) -> None:
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in a voice channel."))
        try:
            channel_name = member.voice.channel.mention
            await member.move_to(None, reason=f"Voice kick by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been disconnected from {channel_name}."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="kickall",
        help="Disconnect everyone from your current voice channel.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_kickall(self, ctx: commands.Context) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        members = [m for m in vc.members if m != ctx.author]
        if not members:
            return await ctx.send(embed=_err("No one else is in your voice channel."))
        count = 0
        for m in members:
            try:
                await m.move_to(None, reason=f"Voice kickall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Disconnected **{count}** member(s) from {vc.mention}."))


    @voice.command(
        name="mute",
        help="Server-mute a member in voice.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_mute(self, ctx: commands.Context, member: discord.Member) -> None:
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in a voice channel."))
        if member.voice.mute:
            return await ctx.send(embed=_err(f"{member.mention} is already server-muted."))
        try:
            await member.edit(mute=True, reason=f"Voice mute by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been **server muted**."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="muteall",
        help="Server-mute everyone in your voice channel.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_muteall(self, ctx: commands.Context) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        members = [m for m in vc.members if m != ctx.author and not m.voice.mute]
        if not members:
            return await ctx.send(embed=_err("No unmuted members in your voice channel."))
        count = 0
        for m in members:
            try:
                await m.edit(mute=True, reason=f"Voice muteall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Muted **{count}** member(s) in {vc.mention}."))


    @voice.command(
        name="unmute",
        help="Server-unmute a member in voice.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_unmute(self, ctx: commands.Context, member: discord.Member) -> None:
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in a voice channel."))
        if not member.voice.mute:
            return await ctx.send(embed=_err(f"{member.mention} is not muted."))
        try:
            await member.edit(mute=False, reason=f"Voice unmute by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been **unmuted**."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="unmuteall",
        help="Unmute everyone in your voice channel.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_unmuteall(self, ctx: commands.Context) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        members = [m for m in vc.members if m.voice.mute]
        if not members:
            return await ctx.send(embed=_err("No muted members in your voice channel."))
        count = 0
        for m in members:
            try:
                await m.edit(mute=False, reason=f"Voice unmuteall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Unmuted **{count}** member(s) in {vc.mention}."))


    @voice.command(
        name="deafen",
        help="Server-deafen a member.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_deafen(self, ctx: commands.Context, member: discord.Member) -> None:
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in a voice channel."))
        if member.voice.deaf:
            return await ctx.send(embed=_err(f"{member.mention} is already deafened."))
        try:
            await member.edit(deafen=True, reason=f"Voice deafen by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been **deafened**."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="deafenall",
        help="Server-deafen everyone in your voice channel.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_deafenall(self, ctx: commands.Context) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        members = [m for m in vc.members if m != ctx.author and not m.voice.deaf]
        if not members:
            return await ctx.send(embed=_err("No undeafened members in your voice channel."))
        count = 0
        for m in members:
            try:
                await m.edit(deafen=True, reason=f"Voice deafenall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Deafened **{count}** member(s) in {vc.mention}."))


    @voice.command(
        name="undeafen",
        help="Server-undeafen a member.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_undeafen(self, ctx: commands.Context, member: discord.Member) -> None:
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in a voice channel."))
        if not member.voice.deaf:
            return await ctx.send(embed=_err(f"{member.mention} is not deafened."))
        try:
            await member.edit(deafen=False, reason=f"Voice undeafen by {ctx.author}")
            await ctx.send(embed=_ok(f"{member.mention} has been **undeafened**."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to do that."))


    @voice.command(
        name="undeafenall",
        help="Undeafen everyone in your voice channel.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_undeafenall(self, ctx: commands.Context) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        members = [m for m in vc.members if m.voice.deaf]
        if not members:
            return await ctx.send(embed=_err("No deafened members in your voice channel."))
        count = 0
        for m in members:
            try:
                await m.edit(deafen=False, reason=f"Voice undeafenall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Undeafened **{count}** member(s) in {vc.mention}."))


    @voice.command(
        name="pull",
        help="Pull a member into your voice channel.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_pull(self, ctx: commands.Context, member: discord.Member) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        if not member.voice:
            return await ctx.send(embed=_err(f"{member.mention} is not in any voice channel."))
        if member.voice.channel == vc:
            return await ctx.send(embed=_err(f"{member.mention} is already in your channel."))
        try:
            await member.move_to(vc, reason=f"Voice pull by {ctx.author}")
            await ctx.send(embed=_ok(f"Pulled {member.mention} into {vc.mention}."))
        except discord.Forbidden:
            await ctx.send(embed=_err("I don't have permission to move that member."))


    @voice.command(
        name="moveall",
        help="Move everyone from one VC to another.",
        usage="<#to_channel>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_moveall(self, ctx: commands.Context, to_channel: discord.VoiceChannel) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        if vc == to_channel:
            return await ctx.send(embed=_err("Source and destination are the same channel."))
        members = vc.members
        if not members:
            return await ctx.send(embed=_err("No members to move."))
        count = 0
        for m in members:
            try:
                await m.move_to(to_channel, reason=f"Voice moveall by {ctx.author}")
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(embed=_ok(f"Moved **{count}** member(s) to {to_channel.mention}."))


    @voice.command(
        name="invite",
        help="DM a member with an invite link to your current VC.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def voice_invite(self, ctx: commands.Context, member: discord.Member) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        try:
            invite = await vc.create_invite(max_uses=1, max_age=300, reason=f"VC invite by {ctx.author}")
            dm_embed = _embed(
                f"**{ctx.author.display_name}** invited you to join **{vc.name}** "
                f"in **{ctx.guild.name}**!\n\n[Click to join]({invite.url})"
            )
            dm_embed.set_author(name="Voice Channel Invite", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            await member.send(embed=dm_embed)
            await ctx.send(embed=_ok(f"Sent a VC invite to {member.mention}."))
        except discord.Forbidden:
            await ctx.send(embed=_err(f"Could not DM {member.mention}. They may have DMs disabled."))


    @voice.command(
        name="request",
        help="Request a member to join your voice channel.",
        usage="<@member>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def voice_request(self, ctx: commands.Context, member: discord.Member) -> None:
        vc = self._vc(ctx)
        if not vc:
            return await ctx.send(embed=_err("You must be in a voice channel."))
        try:
            dm_embed = _embed(
                f"**{ctx.author.display_name}** is requesting you to join "
                f"**{vc.name}** in **{ctx.guild.name}**."
            )
            dm_embed.set_author(name="Voice Channel Request", icon_url=ctx.author.display_avatar.url)
            await member.send(embed=dm_embed)
            await ctx.send(embed=_ok(f"Sent a join request to {member.mention}."))
        except discord.Forbidden:
            await ctx.send(embed=_err(f"Could not DM {member.mention}. They may have DMs disabled."))


    @commands.group(
        name="vcrole",
        invoke_without_command=True,
        help="Auto-assign a role when a member joins a specific VC.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    async def vcrole(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)


    @vcrole.command(
        name="set",
        help="Assign a role to auto-give when someone joins a VC.",
        usage="<voice_channel> <@role>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vcrole_set(
        self, ctx: commands.Context,
        channel: discord.VoiceChannel,
        role: discord.Role,
    ) -> None:
        """Set a VCRole mapping for a voice channel."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vcroles (guild_id, channel_id, role_id) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, channel_id) DO UPDATE SET role_id = excluded.role_id",
                (ctx.guild.id, channel.id, role.id),
            )
            await db.commit()
        await ctx.send(
            embed=_ok(
                f"Members joining {channel.mention} will now receive {role.mention}.\n"
                f"> Role is removed when they leave the channel."
            )
        )

    @vcrole.command(
        name="show",
        aliases=["list"],
        help="Show all VCRole mappings for this server.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vcrole_show(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT channel_id, role_id FROM vcroles WHERE guild_id=? ORDER BY channel_id",
                (ctx.guild.id,),
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.send(embed=_embed("No VCRole mappings configured."))

        lines = []
        for ch_id, role_id in rows:
            channel = ctx.guild.get_channel(ch_id)
            role    = ctx.guild.get_role(role_id)
            ch_name = channel.mention if channel else f"`{ch_id}` (deleted)"
            r_name  = role.mention if role else f"`{role_id}` (deleted)"
            lines.append(f"> {ch_name} → {r_name}")

        embed = discord.Embed(
            description=f"**VCRole Mappings [{len(rows)}]**\n" + "\n".join(lines),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Synapse - Voice System")
        await ctx.send(embed=embed)


    @vcrole.command(
        name="config",
        aliases=["reset", "remove"],
        help="Remove a VCRole mapping, or reset all mappings.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vcrole_config(self, ctx: commands.Context, channel: discord.VoiceChannel = None) -> None:
        """Remove a single mapping, or reset all if no channel given."""
        if channel:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT 1 FROM vcroles WHERE guild_id=? AND channel_id=?",
                    (ctx.guild.id, channel.id),
                ) as cur:
                    exists = await cur.fetchone()
            if not exists:
                return await ctx.send(embed=_err(f"No VCRole mapping found for {channel.mention}."))
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "DELETE FROM vcroles WHERE guild_id=? AND channel_id=?",
                    (ctx.guild.id, channel.id),
                )
                await db.commit()
            await ctx.send(embed=_ok(f"Removed VCRole mapping for {channel.mention}."))
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                res = await db.execute(
                    "DELETE FROM vcroles WHERE guild_id=?", (ctx.guild.id,)
                )
                await db.commit()
            await ctx.send(embed=_ok("All VCRole mappings have been reset."))




async def setup(bot: commands.Bot) -> None:
    await _init_db()
    await bot.add_cog(Voice(bot))
