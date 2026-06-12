from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Set

import discord
from discord.ext import commands

from utils.acore import (
    E_WARN,
    should_process,
    punish,
    send_log,
    make_log_embed,
    get_config,
    is_event_enabled,
    get_audit_executor,
)


class GuildEvents(commands.Cog):
    """Antinuke guild-level event handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        guild = after
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.guild_update)

        guild_changed = (
            before.name != after.name or
            before.description != after.description or
            str(before.icon) != str(after.icon)
        )
        if not guild_changed:
            return

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_guild")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized guild settings change",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        if cfg.get("autorecovery") and before.name != after.name:
            try:
                await after.edit(name=before.name, reason="[Antinuke] Autorecovery — guild name restored")
            except Exception:
                pass
        changes = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if before.description != after.description:
            changes.append("Description changed")
        if str(before.icon) != str(after.icon):
            changes.append("Icon changed")

        embed = make_log_embed(
            "Anti-Guild Triggered",
            f"{E_WARN} **Unauthorized guild settings change detected.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)" if executor else "Unknown", True),
                ("Action", result, True),
                ("Changes", "\n".join(changes), False),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guild = entry.guild

        if entry.action == discord.AuditLogAction.integration_create:
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_integration")
            if proceed:
                result = await punish(
                    self.bot, guild, executor,
                    "Unauthorized integration added",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Integration Triggered",
                    f"{E_WARN} **Unauthorized integration/OAuth bot added.**",
                    color=0xFF4400,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                        ("Integration", f"`{getattr(entry.target, 'name', 'Unknown')}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.webhook_create:
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_webhook_create")
            if proceed:
                result = await punish(
                    self.bot, guild, executor,
                    "Unauthorized webhook creation",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )

                if cfg.get("autorecovery"):
                    try:
                        wh_id = entry.target.id if entry.target else None
                        if wh_id:
                            wh = await self.bot.fetch_webhook(wh_id)
                            await wh.delete(reason="[Antinuke] Autorecovery")
                    except Exception:
                        pass
                embed = make_log_embed(
                    "Anti-Webhook Create Triggered",
                    f"{E_WARN} **Unauthorized webhook creation detected.**",
                    color=0xFF4444,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.webhook_update:
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_webhook_update")
            if proceed:
                result = await punish(
                    self.bot, guild, executor,
                    "Unauthorized webhook update",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Webhook Update Triggered",
                    f"{E_WARN} **Unauthorized webhook update detected.**",
                    color=0xFF8800,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action == discord.AuditLogAction.webhook_delete:
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_webhook_delete")
            if proceed:
                result = await punish(
                    self.bot, guild, executor,
                    "Unauthorized webhook deletion",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Webhook Delete Triggered",
                    f"{E_WARN} **Unauthorized webhook deletion detected.**",
                    color=0xFF0000,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action in (discord.AuditLogAction.sticker_create, discord.AuditLogAction.emoji_create):
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_emotes_create")
            if proceed:
                kind = "sticker" if entry.action == discord.AuditLogAction.sticker_create else "emoji"
                name = getattr(entry.target, "name", "Unknown") if entry.target else "Unknown"
                result = await punish(
                    self.bot, guild, executor,
                    f"Unauthorized {kind} creation ({name})",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Emotes Create Triggered",
                    f"{E_WARN} **Mass {kind} creation detected.**",
                    color=0xFF4444,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                        ("Type", kind.capitalize(), True),
                        (f"{kind.capitalize()} Name", f"`{name}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action in (discord.AuditLogAction.sticker_delete, discord.AuditLogAction.emoji_delete):
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_emotes_delete")
            if proceed:
                kind = "sticker" if entry.action == discord.AuditLogAction.sticker_delete else "emoji"
                name = getattr(entry.target, "name", "Unknown") if entry.target else "Unknown"
                result = await punish(
                    self.bot, guild, executor,
                    f"Unauthorized {kind} deletion ({name})",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Emotes Delete Triggered",
                    f"{E_WARN} **Mass {kind} deletion detected.**",
                    color=0xFF0000,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                        ("Type", kind.capitalize(), True),
                        (f"{kind.capitalize()} Name", f"`{name}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)

        elif entry.action in (discord.AuditLogAction.sticker_update, discord.AuditLogAction.emoji_update):
            executor = guild.get_member(entry.user_id)
            cfg, proceed = await should_process(self.bot, guild, executor, "anti_emotes_update")
            if proceed:
                kind = "sticker" if entry.action == discord.AuditLogAction.sticker_update else "emoji"
                name = getattr(entry.target, "name", "Unknown") if entry.target else "Unknown"
                result = await punish(
                    self.bot, guild, executor,
                    f"Unauthorized {kind} update ({name})",
                    cfg["punishment"], cfg.get("quarantine_role_id"),
                )
                embed = make_log_embed(
                    "Anti-Emotes Update Triggered",
                    f"{E_WARN} **Mass {kind} update detected.**",
                    color=0xFF8800,
                    fields=[
                        ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                        ("Action", result, True),
                        ("Type", kind.capitalize(), True),
                        (f"{kind.capitalize()} Name", f"`{name}`", True),
                    ],
                )
                await send_log(self.bot, guild.id, embed)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return
        guild = member.guild
        await asyncio.sleep(0.05)

        executor = await get_audit_executor(guild, discord.AuditLogAction.bot_add, member.id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_bot_add")
        if not proceed:
            return

        try:
            await guild.kick(member, reason="[Antinuke] Unauthorized bot added")
        except Exception:
            pass

        result = await punish(
            self.bot, guild, executor,
            f"Unauthorized bot added ({member})",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Bot Add Triggered",
            f"{E_WARN} **Unauthorized bot addition detected and stopped.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Bot Added", f"{member.mention} (`{member.id}`)", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not (message.mention_everyone):
            return

        guild = message.guild
        executor = message.author
        if not isinstance(executor, discord.Member):
            return

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_everyone")
        if not proceed:
            return

        try:
            await message.delete()
        except Exception:
            pass

        result = await punish(
            self.bot, guild, executor,
            "@everyone/@here mention by unauthorized user",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Everyone Triggered",
            f"{E_WARN} **Unauthorized @everyone/@here mention detected.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Channel", message.channel.mention, True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener()
    async def on_message_admin_mention(self, message: discord.Message):
        """Handled inside on_message below to avoid listener duplication."""
        pass

    @commands.Cog.listener()
    async def on_message_admin_role_check(self, message: discord.Message):
        """Duplicate — handled inside on_message."""
        pass

    async def _check_admin_mention(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        admin_roles = [
            r for r in message.role_mentions
            if r.permissions.administrator or r.permissions.mention_everyone
        ]
        if not admin_roles:
            return

        guild = message.guild
        executor = message.author
        if not isinstance(executor, discord.Member):
            return

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_admin_mention")
        if not proceed:
            return

        try:
            await message.delete()
        except Exception:
            pass

        result = await punish(
            self.bot, guild, executor,
            f"Mentioned admin role(s) without permission",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Admin Mention Triggered",
            f"{E_WARN} **Admin role mention by unauthorized user detected.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Roles Mentioned", " ".join(r.mention for r in admin_roles[:5]), True),
                ("Channel", message.channel.mention, True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener("on_message")
    async def on_message_admin_filter(self, message: discord.Message):
        await self._check_admin_mention(message)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild
        if not guild: return

        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        dangerous_perms = ["administrator", "ban_members", "kick_members", "manage_guild", "manage_channels", "manage_roles", "manage_webhooks", "mention_everyone"]

        dangerous_added = []
        for r in added_roles:
            p = r.permissions
            if any(getattr(p, perm, False) for perm in dangerous_perms):
                dangerous_added.append(r)

        if not dangerous_added:
            return

        cfg = await get_config(guild.id)
        if not cfg or not cfg["enabled"]:
            return

        managed_dangerous = [r for r in dangerous_added if r.managed]

        if managed_dangerous:
            if await is_whitelisted(guild.id, after, "anti_linked_role") or \
               await is_whitelisted(guild.id, after, "anti_member_update"):
                pass
            else:
                try:
                    await guild.ban(after, reason=f"[Antinuke] Anti-Link Role: Managed role(s) with dangerous perms assigned")
                    result = "Banned"
                except Exception as e:
                    result = f"Failed ({e})"

                embed = make_log_embed(
                    "Anti-Link Role Protection",
                    f"{E_WARN} **Member gained a managed role with dangerous permissions.**",
                    color=0xFF0000,
                    fields=[
                        ("Target Member", f"{after.mention} (`{after.id}`)", True),
                        ("Action", result, True),
                        ("Managed Role(s)", ", ".join(f"`{r.name}`" for r in managed_dangerous), True),
                        ("Note", "Bot cannot edit managed roles; member was banned.", False),
                    ],
                )
                await send_log(self.bot, guild.id, embed, cfg)
                return

        await asyncio.sleep(0.05)
        executor = await get_audit_executor(guild, discord.AuditLogAction.member_role_update, after.id)

        cfg, proceed = await should_process(self.bot, guild, executor, "anti_member_update")
        if not proceed:
            return

        result = await punish(
            self.bot, guild, executor,
            "Unauthorized dangerous role assignment",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        if cfg.get("autorecovery"):
            normal_dangerous = [r for r in dangerous_added if not r.managed]
            if normal_dangerous:
                try:
                    await after.remove_roles(*normal_dangerous, reason="[Antinuke] Autorecovery — dangerous role assigned")
                except Exception:
                    pass

        embed = make_log_embed(
            "Anti-Member Update Triggered",
            f"{E_WARN} **Dangerous roles assigned to members.**",
            color=0xFF8800,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)" if executor else "Unknown", True),
                ("Action", result, True),
                ("Target Member", f"{after.mention} (`{after.id}`)", True),
                ("Dangerous Roles", " ".join(r.mention for r in dangerous_added[:5]), True),
                ("Auto-Recovery", f"{'<:emoji_1769867605256:1467155817726873650> Roles removed' if cfg.get('autorecovery') else '<:emoji_1769867589372:1467155751456735326> Disabled'}", True),
            ],
        )
        await send_log(self.bot, guild.id, embed, cfg)


    @commands.Cog.listener("on_audit_log_entry_create")
    async def on_linked_role_detect(self, entry: discord.AuditLogEntry):
        if entry.action not in (
            discord.AuditLogAction.role_create,
            discord.AuditLogAction.role_update,
        ):
            return

        guild = entry.guild
        executor = guild.get_member(entry.user_id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_linked_role")
        if not proceed:
            return


        raw = getattr(entry, "_data", {})
        is_linked = any(
            change.get("key") == "application_role_connection"
            for change in raw.get("changes", [])
        )
        if not is_linked:
            return

        role_name = getattr(entry.target, "name", "Unknown") if entry.target else "Unknown"

        result = await punish(
            self.bot, guild, executor,
            f"Created/modified a Linked Role ({role_name})",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Linked-Role Triggered",
            f"{E_WARN} **Linked Role creation/modification detected.**",
            color=0xFF4444,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Role", f"`{role_name}`", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)

    @commands.Cog.listener("on_audit_log_entry_create")
    async def on_invite_role_detect(self, entry: discord.AuditLogEntry):
        if entry.action not in (
            discord.AuditLogAction.invite_create,
            discord.AuditLogAction.invite_update,
        ):
            return

        guild = entry.guild
        executor = guild.get_member(entry.user_id)
        cfg, proceed = await should_process(self.bot, guild, executor, "anti_invite_role")
        if not proceed:
            return

        raw = getattr(entry, "_data", {})
        has_role = any(
            change.get("key") == "role_ids"
            for change in raw.get("changes", [])
        )
        if not has_role and hasattr(entry.target, "role"):
            has_role = entry.target.role is not None

        if not has_role:
            return

        invite_code = raw.get("target_id", "unknown")

        result = await punish(
            self.bot, guild, executor,
            f"Created/modified a role-linked invite (code: {invite_code})",
            cfg["punishment"], cfg.get("quarantine_role_id"),
        )

        embed = make_log_embed(
            "Anti-Invite-Role Triggered",
            f"{E_WARN} **Role-linked invite detected.**",
            color=0xFF4400,
            fields=[
                ("Punished User", f"{executor.mention} (`{executor.id}`)", True),
                ("Action", result, True),
                ("Invite Code", f"`{invite_code}`", True),
                ("Punishment Mode", f"`{cfg['punishment'].capitalize()}`", True),
            ],
        )
        await send_log(self.bot, guild.id, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildEvents(bot))
