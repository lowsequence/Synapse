from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord.ext import commands

from utils.acore import (
    E_WARN,
    should_process,
    punish,
    send_log,
    make_log_embed,
    get_config,
    is_antinuke_admin,
    is_whitelisted,
    get_audit_executor,
)

NEW_MEMBER_WINDOW_MINUTES = 5

DANGEROUS_PERMS = (
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
)


class QuickRoleEvents(commands.Cog):
    """Anti Quick Role event handler."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild

        cfg = await get_config(guild.id)
        if not cfg or not cfg.get("quickrole") or not cfg.get("enabled"):
            return

        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        dangerous: List[discord.Role] = [
            r for r in added_roles
            if any(getattr(r.permissions, p, False) for p in DANGEROUS_PERMS)
        ]
        if not dangerous:
            return

        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.member_role_update, after.id, fallback_seconds=5)

        if executor:
            if executor.bot or executor.id == guild.owner_id:
                return
            if await is_antinuke_admin(self.bot, guild.id, executor.id):
                return
            if await is_whitelisted(guild.id, executor, "anti_role_update"):
                return

        is_new_member = False
        if after.joined_at:
            joined_utc = after.joined_at.replace(tzinfo=None) if after.joined_at.tzinfo else after.joined_at
            if isinstance(joined_utc, datetime) and joined_utc.tzinfo is not None:
                joined_utc = joined_utc.astimezone(timezone.utc).replace(tzinfo=None)
            is_new_member = (datetime.utcnow() - joined_utc) < timedelta(minutes=NEW_MEMBER_WINDOW_MINUTES)

        should_act = is_new_member

        if not should_act:
            return

        punish_result = "N/A"
        if executor and executor.id != guild.owner_id and not executor.bot:
            punish_result = await punish(
                self.bot, guild, executor,
                f"Anti Quick Role — rapidly assigning dangerous roles",
                cfg["punishment"], cfg.get("quarantine_role_id"),
            )

        stripped = []
        for role in dangerous:
            try:
                await after.remove_roles(role, reason="[Antinuke] Anti Quick Role — dangerous role stripped")
                stripped.append(role)
            except Exception:
                pass

        perm_list = ", ".join(
            p.replace("_", " ").title()
            for r in dangerous
            for p in DANGEROUS_PERMS if getattr(r.permissions, p, False)
        )

        embed = make_log_embed(
            "Anti-Quick-Role Triggered",
            f"{E_WARN} **Dangerous role(s) stripped from {'new member' if is_new_member else 'member'}.**",
            color=0xFF8800,
            fields=[
                ("Target Member", f"{after.mention} (`{after.id}`)", True),
                ("Is New Member", f"{'Yes (joined < 5min ago)' if is_new_member else 'No'}", True),
                ("Roles Stripped", " ".join(r.mention for r in stripped) or "None", True),
                ("Dangerous Perms", perm_list or "Unknown", True),
                ("Executor", f"{executor.mention} (`{executor.id}`)" if executor else "Unknown", True),
                ("Executor Action", punish_result, True),
            ],
        )
        await send_log(self.bot, guild.id, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuickRoleEvents(bot))
