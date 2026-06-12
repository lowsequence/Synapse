from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

from utils.acore import (
    E_WARN,
    should_process,
    punish,
    send_log,
    make_log_embed,
    get_config,
    get_audit_executor,
)





class ChannelEvents(commands.Cog):
    """Antinuke channel event handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.channel_create, channel.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_channel_create")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized channel creation",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        if cfg.get("autorecovery"):
            try:
                await channel.delete(reason="[Antinuke] Autorecovery — channel creation")
            except Exception:
                pass

        embed = make_log_embed(
            "Anti-Channel Create Triggered",
            f"{E_WARN} **Mass channel creation detected and stopped.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Channel", f"`#{channel.name}` (`{channel.id}`)", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                ("Auto-Recovery", f"{'<:emoji_1769867605256:1467155817726873650> Channel deleted' if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.channel_delete, channel.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_channel_delete")
        if not proceed:
            return

        snapshot = {
            "name":      channel.name,
            "type":      channel.type,
            "category":  channel.category_id,
            "position":  channel.position,
            "topic":     getattr(channel, "topic", None),
            "nsfw":      getattr(channel, "nsfw", False),
            "slowmode":  getattr(channel, "slowmode_delay", 0),
            "bitrate":   getattr(channel, "bitrate", 64000),
            "user_limit":getattr(channel, "user_limit", 0),
            "overwrites": {
                str(target.id): {
                    "type":  "role" if isinstance(target, discord.Role) else "member",
                    "allow": overwrite.pair()[0].value,
                    "deny":  overwrite.pair()[1].value,
                }
                for target, overwrite in channel.overwrites.items()
            },
        }

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized channel deletion",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        recovered_ch = None
        if cfg.get("autorecovery"):
            try:
                category = guild.get_channel(snapshot["category"]) if snapshot["category"] else None

                overwrites: dict = {}
                for tid, data in snapshot["overwrites"].items():
                    target = (
                        guild.get_role(int(tid))
                        if data["type"] == "role"
                        else guild.get_member(int(tid))
                    )
                    if target:
                        overwrites[target] = discord.PermissionOverwrite.from_pair(
                            discord.Permissions(data["allow"]),
                            discord.Permissions(data["deny"]),
                        )

                ch_type = snapshot["type"]

                if ch_type == discord.ChannelType.text:
                    recovered_ch = await guild.create_text_channel(
                        name=snapshot["name"],
                        topic=snapshot["topic"] or "",
                        nsfw=snapshot["nsfw"],
                        slowmode_delay=snapshot["slowmode"],
                        overwrites=overwrites,
                        reason="[Antinuke] Deep Restore — channel deletion",
                    )

                elif ch_type == discord.ChannelType.voice:
                    recovered_ch = await guild.create_voice_channel(
                        name=snapshot["name"],
                        bitrate=min(snapshot["bitrate"], guild.bitrate_limit),
                        user_limit=snapshot["user_limit"],
                        overwrites=overwrites,
                        reason="[Antinuke] Deep Restore — channel deletion",
                    )

                elif ch_type == discord.ChannelType.stage_voice:
                    recovered_ch = await guild.create_stage_channel(
                        name=snapshot["name"],
                        overwrites=overwrites,
                        reason="[Antinuke] Deep Restore — channel deletion",
                    )

                elif ch_type == discord.ChannelType.category:
                    recovered_ch = await guild.create_category(
                        name=snapshot["name"],
                        overwrites=overwrites,
                        reason="[Antinuke] Deep Restore — channel deletion",
                    )

                else:
                    recovered_ch = await guild.create_text_channel(
                        name=snapshot["name"],
                        overwrites=overwrites,
                        reason="[Antinuke] Deep Restore — channel deletion",
                    )

                if recovered_ch and snapshot["position"]:
                    try:
                        await recovered_ch.edit(position=snapshot["position"])
                    except Exception:
                        pass

            except Exception:
                pass

        embed = make_log_embed(
            "Anti-Channel Delete Triggered",
            f"{E_WARN} **Mass channel deletion detected and stopped.**",
            color=0xFF0000,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Channel", f"`#{snapshot['name']}`", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                ("Deep Restore", f"{'<:emoji_1769867605256:1467155817726873650> Restored: ' + (recovered_ch.mention if recovered_ch else 'failed') if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ):
        guild = after.guild
        await asyncio.sleep(0.05)

        perm_changed = before.overwrites != after.overwrites
        name_changed  = before.name != after.name
        if not (perm_changed or name_changed):
            return

        executor = await get_audit_executor(guild, discord.AuditLogAction.channel_update, after.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_channel_update")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized channel update",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        if cfg.get("autorecovery"):
            try:
                edits: dict = {}
                if name_changed:
                    edits["name"] = before.name
                if perm_changed:
                    edits["overwrites"] = before.overwrites
                if edits:
                    await after.edit(**edits, reason="[Antinuke] Deep Restore — channel update")
            except Exception:
                pass

        changes = []
        if name_changed:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if perm_changed:
            changes.append("Permission overwrites changed")

        embed = make_log_embed(
            "Anti-Channel Update Triggered",
            f"{E_WARN} **Mass channel updates detected and stopped.**",
            color=0xFF6600,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Trigger Count", f"`{count}` updates in 10s", True),
                ("Channel", f"{after.mention} (`{after.id}`)", True),
                ("Changes", "\n".join(changes) or "Unknown", False),
            ],
        )
        await send_log(self.bot, guild.id, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChannelEvents(bot))
