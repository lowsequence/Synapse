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
)


async def _get_meta_executor(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: Optional[int] = None,
) -> Optional[discord.Member]:
    cutoff = datetime.utcnow() - timedelta(seconds=15)
    try:
        async for entry in guild.audit_logs(limit=50, action=action):
            if entry.created_at.replace(tzinfo=None) < cutoff:
                break
            if target_id and getattr(entry.target, "id", None) != target_id:
                continue
            return guild.get_member(entry.user_id)
    except Exception:
        pass
    return None


class AntibetrayEvents(commands.Cog):
    """Cog to handle meta-nuke events for the Antibetray system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        """Monitor webhook changes (Creation/Deletion)."""
        guild = channel.guild
        # We check both create and delete log actions
        executor = await _get_meta_executor(guild, discord.AuditLogAction.webhook_create)
        if not executor:
            executor = await _get_meta_executor(guild, discord.AuditLogAction.webhook_delete)
        
        if not executor:
            return

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_webhook")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized Webhook modification",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Webhook Triggered",
            f"{E_WARN} **Webhook modification detected and stopped.**",
            color=0xFF00FF,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Channel", channel.mention, True),
                ("System", "**Antibetray Protection**", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild):
        """Monitor integration changes (Bots, Apps)."""
        executor = await _get_meta_executor(guild, discord.AuditLogAction.integration_create)
        if not executor:
            executor = await _get_meta_executor(guild, discord.AuditLogAction.integration_delete)
            
        if not executor:
            return

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_integration")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized Integration modification",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Integration Triggered",
            f"{E_WARN} **Server integration change detected and stopped.**",
            color=0x00FFFF,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("System", "**Antibetray Protection**", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntibetrayEvents(bot))
