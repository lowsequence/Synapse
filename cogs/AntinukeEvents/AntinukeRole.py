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
    get_audit_executor,
)

DANGEROUS_PERMS = (
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "mention_everyone",
)


class RoleEvents(commands.Cog):
    """Antinuke role event handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.role_create, role.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_role_create")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized role creation",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        if cfg.get("autorecovery"):
            try:
                await role.delete(reason="[Antinuke] Autorecovery — mass role creation")
            except Exception:
                pass

        embed = make_log_embed(
            "Anti-Role Create Triggered",
            f"{E_WARN} **Mass role creation detected and stopped.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Role", f"`{role.name}` (`{role.id}`)", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                ("Auto-Recovery", f"{'<:emoji_1769867605256:1467155817726873650> Role deleted' if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.role_delete, role.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_role_delete")
        if not proceed:
            return

        snap = {
            "name":        role.name,
            "permissions": role.permissions,
            "color":       role.color,
            "hoist":       role.hoist,
            "mentionable": role.mentionable,
            "position":    role.position,
        }

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized role deletion",
            cfg["punishment"],
            cfg.get("quarantine_role_id"),
        )

        recovered = None
        if cfg.get("autorecovery"):
            try:
                recovered = await guild.create_role(
                    name=snap["name"],
                    permissions=snap["permissions"],
                    color=snap["color"],
                    hoist=snap["hoist"],
                    mentionable=snap["mentionable"],
                    reason="[Antinuke] Deep Restore — role deletion",
                )
                if snap["position"] > 0:
                    try:
                        await recovered.edit(position=snap["position"])
                    except Exception:
                        pass
            except Exception:
                pass

        embed = make_log_embed(
            "Anti-Role Delete Triggered",
            f"{E_WARN} **Mass role deletion detected and stopped.**",
            color=0xFF0000,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Role", f"`{snap['name']}`", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                ("Deep Restore", f"{'<:emoji_1769867605256:1467155817726873650> Recreated: ' + (recovered.mention if recovered else 'failed') if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = after.guild
        await asyncio.sleep(0.05)

        added_perms = []
        for perm in DANGEROUS_PERMS:
            before_val = getattr(before.permissions, perm, False)
            after_val  = getattr(after.permissions, perm, False)
            if not before_val and after_val:
                added_perms.append(perm.replace("_", " ").title())

        became_mentionable = not before.mentionable and after.mentionable

        if not added_perms and not became_mentionable:
            return

        executor = await get_audit_executor(guild, discord.AuditLogAction.role_update, after.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_role_update")
        if not proceed:
            return

        if added_perms or became_mentionable:
            result = await punish(
                self.bot, guild, executor,
                f"Dangerous role update ({', '.join(added_perms) or 'perms/mentionable changed'})",
                cfg["punishment"],
                cfg.get("quarantine_role_id"),
            )

            if cfg.get("autorecovery"):
                try:
                    await after.edit(
                        permissions=before.permissions,
                        mentionable=before.mentionable,
                        reason="[Antinuke] Autorecovery — dangerous permission added",
                    )
                except Exception:
                    pass

            changes_str = ""
            if added_perms:
                changes_str += f"Perms Added: {', '.join(f'`{p}`' for p in added_perms)}\n"
            if became_mentionable:
                changes_str += "Role made **mentionable**\n"

            embed = make_log_embed(
                "Anti-Role Update Triggered",
                f"{E_WARN} **Dangerous role update detected and stopped.**",
                color=0xFF8800,
                fields=[
                    ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                    ("Action", result, True),
                    ("Role", f"{after.mention} (`{after.id}`)", True),
                    ("Dangerous Changes", changes_str or "Mass updates", False),
                    ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
                    ("Auto-Recovery", f"{'<:emoji_1769867605256:1467155817726873650> Reverted' if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
                ],
            )
            await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_update_admin_mention(self, before: discord.Role, after: discord.Role):
        """Duplicate listener alias — handled in on_guild_role_update above."""
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RoleEvents(bot))
