from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

from utils.acore import (
    COLOR,
    E_WARN,
    FOOTER,
    should_process,
    punish,
    send_log,
    make_log_embed,
    push_audit_executor,
)

class AntinukeBanEvents(commands.Cog):
    """Antinuke ban/kick/unban/prune event handlers using Gateway Audit Logs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guild = entry.guild
        executor_member = guild.get_member(entry.user_id) if entry.user_id else None
        
        # Globally push all audit logs to our ultra-fast memory cache for other modules
        target_id = getattr(entry.target, "id", None) if entry.target else None
        if entry.user_id:
            push_audit_executor(guild.id, entry.action.value, target_id, entry.user_id)

        if not executor_member:
            return

        if entry.action == discord.AuditLogAction.ban:
            cfg, proceed = await should_process(self.bot, guild, executor_member, "anti_ban")
            if proceed:
                result = await punish(
                    self.bot, guild, executor_member,
                    "Banned member",
                    cfg["punishment"],
                    cfg.get("quarantine_role_id"),
                )

                if cfg.get("autorecovery") and entry.target:
                    try:
                        await guild.unban(entry.target, reason="[Antinuke] Autorecovery — victim of mass ban")
                    except Exception:
                        pass

                embed = make_log_embed(
                    "Anti-Ban Triggered",
                    f"{E_WARN} **Mass banning detected and stopped.**",
                    color=0xFF4444,
                    fields=[
                        ("Punished User", f"{executor_member.mention} (`{executor_member.id}`)", True),
                        ("Action", result, True),
                        ("Victim", f"`{getattr(entry.target, 'id', 'Unknown')}`", True),
                        ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                        ("Auto-Recovery", f"{'<:emoji_1769867605256:1467155817726873650> Victim unbanned' if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.kick:
            cfg, proceed = await should_process(self.bot, guild, executor_member, "anti_kick")
            if proceed:
                result = await punish(
                    self.bot, guild, executor_member,
                    "Kicked member",
                    cfg["punishment"],
                    cfg.get("quarantine_role_id"),
                )

                embed = make_log_embed(
                    "Anti-Kick Triggered",
                    f"{E_WARN} **Mass kicking detected and stopped.**",
                    color=0xFF6600,
                    fields=[
                        ("Punished User", f"{executor_member.mention} (`{executor_member.id}`)", True),
                        ("Action", result, True),
                        ("Victim", f"`{getattr(entry.target, 'id', 'Unknown')}`", True),
                        ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.unban:
            cfg, proceed = await should_process(self.bot, guild, executor_member, "anti_unban")
            if proceed:
                result = await punish(
                    self.bot, guild, executor_member,
                    "Unbanned member without permission",
                    cfg["punishment"],
                    cfg.get("quarantine_role_id"),
                )

                embed = make_log_embed(
                    "Anti-Unban Triggered",
                    f"{E_WARN} **Mass unbanning detected and stopped.**",
                    color=0xFF8800,
                    fields=[
                        ("Punished User", f"{executor_member.mention} (`{executor_member.id}`)", True),
                        ("Action", result, True),
                        ("User Unbanned", f"`{getattr(entry.target, 'id', 'Unknown')}`", True),
                        ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.member_prune:
            cfg, proceed = await should_process(self.bot, guild, executor_member, "anti_prune")
            if proceed:
                prune_count = getattr(entry.extra, "members_removed", "?")
                result = await punish(
                    self.bot, guild, executor_member,
                    f"Unauthorized member prune ({prune_count} members pruned)",
                    cfg["punishment"],
                    cfg.get("quarantine_role_id"),
                )
                
                embed = make_log_embed(
                    "Anti-Prune Triggered",
                    f"{E_WARN} **Unauthorized member prune detected and stopped.**",
                    color=0xFF2200,
                    fields=[
                        ("Punished User", f"{executor_member.mention} (`{executor_member.id}`)", True),
                        ("Action", result, True),
                        ("Members Pruned", f"`{prune_count}`", True),
                        ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntinukeBanEvents(bot))
