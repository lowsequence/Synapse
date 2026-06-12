from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiosqlite
import discord
from discord.ext import commands


_fast_audit_cache: Dict[Tuple[int, int, Optional[int]], Tuple[int, float]] = {}

def push_audit_executor(guild_id: int, action_value: int, target_id: Optional[int], executor_id: int):
    """Pushes an executor to the high-speed memory cache."""
    _fast_audit_cache[(guild_id, action_value, target_id)] = (executor_id, time.monotonic() + 15.0)

async def get_audit_executor(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: Optional[int] = None,
    fallback_seconds: int = 15,
) -> Optional[discord.Member]:
    """Exceedingly fast executor fetcher using gateway cache + HTTP fallback."""
    now = time.monotonic()
    
    # 1. Try exact target match
    cache_key = (guild.id, action.value, target_id)
    if cache_key in _fast_audit_cache:
        exec_id, expiry = _fast_audit_cache[cache_key]
        if expiry > now:
            return guild.get_member(exec_id)
            
    # 2. Match without explicit target if we just need the generic executor
    if target_id is None:
        for key, val in _fast_audit_cache.items():
            if key[0] == guild.id and key[1] == action.value and val[1] > now:
                return guild.get_member(val[0])
                
    # 3. Fallback to HTTP API if cache misses
    cutoff = datetime.utcnow() - timedelta(seconds=fallback_seconds)
    try:
        async for entry in guild.audit_logs(limit=30, action=action):
            if entry.created_at.replace(tzinfo=None) < cutoff:
                break
            if target_id and getattr(entry.target, "id", None) != target_id:
                continue
            executor = guild.get_member(entry.user_id)
            if executor:
                push_audit_executor(guild.id, action.value, target_id, executor.id)
                return executor
    except Exception:
        pass
    return None
# ------------------------

DB_PATH       = "database/antinuke.db"
ANTIBETRAY_DB = "database/antibetray.db"
PREMIUM_DB    = "database/premium_codes.db"
COLOR         = 0x2b2d31


E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
E_SHIELD= "<:SynapseShield:1477236015830663324>"
E_WARN  = "<:Lund:1464624797374873611>"
E_NOTE  = "<:SynapseNote:1477236015830663324>"
FOOTER  = "Synapse — Antinuke System"

WL_WINDOW = 60
DEFAULT_LIMIT = 50

_wl_tracker: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(deque)))
_antibetray_tracker: dict = defaultdict(lambda: defaultdict(deque))


async def is_guild_premium(guild_id: int) -> bool:
    """Checks if the guild has an active premium subscription."""
    import os
    if not os.path.exists(PREMIUM_DB):
        return False
    try:
        async with aiosqlite.connect(PREMIUM_DB) as db:
            async with db.execute(
                "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return False
        expires_at = datetime.fromisoformat(row[0])
        if expires_at < datetime.utcnow():
            return False
        return True
    except Exception:
        return False


def record_wl_action(guild_id: int, user_id: int, event: str, window_sec: int = 10) -> int:
    """Record a whitelisted user's action. Returns count within window_sec."""
    now = datetime.utcnow()
    window = now - timedelta(seconds=window_sec)
    tracker = _wl_tracker[guild_id][user_id][event]
    
    # O(1) removal from left
    while tracker and tracker[0] < window:
        tracker.popleft()
        
    tracker.append(now)
    return len(tracker)


def record_antibetray_action(guild_id: int, user_id: int, window_sec: int = 60) -> int:
    """Record a global nuke action for Antibetray. Returns count within window_sec."""
    now = datetime.utcnow()
    window = now - timedelta(seconds=window_sec)
    tracker = _antibetray_tracker[guild_id][user_id]

    while tracker and tracker[0] < window:
        tracker.popleft()

    tracker.append(now)
    return len(tracker)


def clear_wl_tracker(guild_id: int, user_id: int) -> None:
    """Reset all limit counts for a user after punishment."""
    if guild_id in _wl_tracker and user_id in _wl_tracker[guild_id]:
        del _wl_tracker[guild_id][user_id]


_config_cache: Dict[int, Tuple[dict, float]] = {}
_event_cache:  Dict[Tuple[int, str], Tuple[bool, float]] = {}
_admin_cache:  Dict[Tuple[int, int], Tuple[bool, float]] = {}
_limit_cache:  Dict[Tuple[int, str], Tuple[int, float]] = {}
_whitelist_cache: Dict[Tuple[int, int, str], Tuple[bool, float]] = {}

_ab_config_cache: Dict[int, Tuple[dict, float]] = {}
_ab_limit_cache:  Dict[Tuple[int, str], Tuple[int, float]] = {}

CACHE_TTL = 5


def _now() -> float:
    return time.monotonic()


def invalidate_guild_cache(guild_id: int) -> None:
    """Call after config changes to bust cache immediately."""
    _config_cache.pop(guild_id, None)
    _ab_config_cache.pop(guild_id, None)

    to_del = [k for k in _event_cache if k[0] == guild_id]
    for k in to_del: del _event_cache[k]
    
    to_del = [k for k in _admin_cache if k[0] == guild_id]
    for k in to_del: del _admin_cache[k]
    
    to_del = [k for k in _limit_cache if k[0] == guild_id]
    for k in to_del: del _limit_cache[k]
    
    to_del = [k for k in _whitelist_cache if k[0] == guild_id]
    for k in to_del: del _whitelist_cache[k]

    to_del = [k for k in _ab_limit_cache if k[0] == guild_id]
    for k in to_del: del _ab_limit_cache[k]


async def get_config(guild_id: int) -> Optional[dict]:
    now = _now()
    cached = _config_cache.get(guild_id)
    if cached and cached[1] > now:
        return cached[0]

    async with aiosqlite.connect(DB_PATH) as db:
        # Ensure legacy columns exist (Migration fix)
        for col in ["night_mode", "cynical_mode", "quickrole"]:
            try:
                await db.execute(f"ALTER TABLE antinuke_config ADD COLUMN {col} INTEGER DEFAULT 0")
                await db.commit()
            except Exception:
                pass

        async with db.execute(
            "SELECT guild_id,enabled,punishment,log_channel_id,wall_role_id,"
            "quarantine_role_id,autorecovery,panic_mode,night_mode,cynical_mode,quickrole,setup_at "
            "FROM antinuke_config WHERE guild_id=?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        _config_cache[guild_id] = (None, now + CACHE_TTL)
        return None
    keys = [
        "guild_id", "enabled", "punishment", "log_channel_id", "wall_role_id",
        "quarantine_role_id", "autorecovery", "panic_mode", "night_mode", "cynical_mode", "quickrole", "setup_at",
    ]
    cfg = dict(zip(keys, row))
    _config_cache[guild_id] = (cfg, now + CACHE_TTL)
    return cfg


async def get_antibetray_config(guild_id: int) -> Optional[dict]:
    """Fetch Antibetray config from the new dedicated database."""
    now = _now()
    cached = _ab_config_cache.get(guild_id)
    if cached and cached[1] > now:
        return cached[0]

    import os
    if not os.path.exists(ANTIBETRAY_DB):
        return None

    async with aiosqlite.connect(ANTIBETRAY_DB) as db:
        async with db.execute(
            "SELECT enabled, window, threshold FROM config WHERE guild_id=?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"enabled": 0, "window": 60, "threshold": 3}
    
    cfg = {"enabled": row[0], "window": row[1], "threshold": row[2]}
    _ab_config_cache[guild_id] = (cfg, now + CACHE_TTL)
    return cfg


async def get_antibetray_limit(guild_id: int, event: str) -> Optional[int]:
    """Fetch Antibetray-specific limit for an event."""
    now = _now()
    key = (guild_id, event)
    cached = _ab_limit_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    import os
    if not os.path.exists(ANTIBETRAY_DB):
        return None

    async with aiosqlite.connect(ANTIBETRAY_DB) as db:
        async with db.execute(
            "SELECT max_actions FROM limits WHERE guild_id=? AND event=?",
            (guild_id, event),
        ) as cur:
            row = await cur.fetchone()
    
    limit = row[0] if row else None
    _ab_limit_cache[key] = (limit, now + CACHE_TTL)
    return limit


async def is_event_enabled(guild_id: int, event: str) -> bool:
    now = _now()
    key = (guild_id, event)
    cached = _event_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT enabled FROM antinuke_events WHERE guild_id=? AND event=?",
            (guild_id, event),
        ) as cur:
            row = await cur.fetchone()
    result = True if row is None else bool(row[0])
    _event_cache[key] = (result, now + CACHE_TTL)
    return result


async def get_limit(guild_id: int, event: str) -> int:
    """Get the configured action limit for an event. Returns DEFAULT_LIMIT if not set."""
    now = _now()
    key = (guild_id, event)
    cached = _limit_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT max_actions FROM antinuke_limits WHERE guild_id=? AND event=?",
            (guild_id, event),
        ) as cur:
            row = await cur.fetchone()
    limit = row[0] if row else DEFAULT_LIMIT
    _limit_cache[key] = (limit, now + CACHE_TTL)
    return limit


async def is_whitelisted(guild_id: int, member: discord.Member, event: str) -> bool:
    """
    Returns True if the member (or any of their roles) is whitelisted for this event.
    Uses a TTL cache to avoid redundant database lookups.
    """
    now = _now()
    key = (guild_id, member.id, event)
    cached = _whitelist_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT events FROM antinuke_whitelist_users WHERE guild_id=? AND user_id=?",
            (guild_id, member.id),
        ) as cur:
            row = await cur.fetchone()
        if row:
            evts = json.loads(row[0])
            if event in evts:
                _whitelist_cache[key] = (True, now + CACHE_TTL)
                return True

        role_ids = [r.id for r in member.roles]
        if role_ids:
            placeholders = ",".join("?" * len(role_ids))
            async with db.execute(
                f"SELECT events FROM antinuke_whitelist_roles WHERE guild_id=? AND role_id IN ({placeholders})",
                (guild_id, *role_ids),
            ) as cur:
                rows = await cur.fetchall()
        else:
            rows = []

    result = False
    for (ev_json,) in rows:
        evts = json.loads(ev_json)
        if event in evts:
            result = True
            break

    _whitelist_cache[key] = (result, now + CACHE_TTL)
    return result


async def is_antinuke_admin(bot: commands.Bot, guild_id: int, user_id: int) -> bool:
    now = _now()
    key = (guild_id, user_id)
    cached = _admin_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    guild = bot.get_guild(guild_id)
    if guild and guild.owner_id == user_id:
        _admin_cache[key] = (True, now + CACHE_TTL)
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM antinuke_admins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ) as cur:
            result = await cur.fetchone() is not None
    _admin_cache[key] = (result, now + CACHE_TTL)
    return result


async def record_violation(guild_id: int, user_id: int, event: str, count: int, punished: str = "N/A") -> None:
    """Insert a whitelist limit violation into the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO antinuke_violations (guild_id, user_id, event, count, punished, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, user_id, event, count, punished, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def send_log(bot: commands.Bot, guild_id: int, embed: discord.Embed, cfg: Optional[dict] = None) -> None:
    if cfg is None:
        cfg = await get_config(guild_id)
    if not cfg or not cfg.get("log_channel_id"):
        return
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    ch = guild.get_channel(cfg["log_channel_id"])
    if ch:
        try:
            await ch.send(embed=embed)
        except Exception:
            pass


def make_log_embed(
    title: str,
    description: str,
    color: int = 0xFF4444,
    fields: Optional[List[Tuple[str, str, bool]]] = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{E_SHIELD} {title}",
        description=description,
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=FOOTER)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed


async def punish(
    bot: commands.Bot,
    guild: discord.Guild,
    member: discord.Member,
    reason: str,
    punishment: str,
    quarantine_role_id: Optional[int] = None,
) -> str:
    """
    Execute punishment on the offending member.
    Returns a string describing what was done.
    """
    clear_wl_tracker(guild.id, member.id)

    if punishment == "ban":
        try:
            await guild.ban(member, reason=f"[Antinuke] {reason}", delete_message_seconds=0)
            return "Banned"
        except discord.Forbidden:
            return "Failed (Missing permissions to ban)"
        except Exception as e:
            return f"Failed ({e})"

    elif punishment == "kick":
        try:
            await guild.kick(member, reason=f"[Antinuke] {reason}")
            return "Kicked"
        except discord.Forbidden:
            return "Failed (Missing permissions to kick)"
        except Exception as e:
            return f"Failed ({e})"

    elif punishment == "quarantine":
        qr = guild.get_role(quarantine_role_id) if quarantine_role_id else None
        if not qr:
            try:
                await guild.kick(member, reason=f"[Antinuke] {reason} (quarantine role not found)")
                return "Kicked (quarantine role not found)"
            except Exception:
                return "Failed (quarantine role not found)"
        try:
            roles_to_remove = [r for r in member.roles if r != guild.default_role and r != qr]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"[Antinuke] {reason}")
            await member.add_roles(qr, reason=f"[Antinuke] {reason}")
            return "Quarantined"
        except discord.Forbidden:
            return "Failed (Missing permissions to quarantine)"
        except Exception as e:
            return f"Failed ({e})"

    return "Unknown punishment mode"


async def should_process(
    bot: commands.Bot,
    guild: discord.Guild,
    executor: Optional[discord.Member],
    event: str,
) -> Tuple[Optional[dict], bool]:
    """
    Common guard used at the top of every event handler.
    Returns (cfg, proceed).
    proceed=False means skip (not set up, disabled, bot, owner, admin, or whitelisted-under-limit).
    proceed=True means punish (unwhitelisted, or whitelisted-over-limit).
    """
    cfg = await get_config(guild.id)
    if not cfg or not cfg["enabled"]:
        return None, False

    if not await is_event_enabled(guild.id, event):
        return cfg, False

    if executor is None:
        return cfg, False

    if executor.id == bot.user.id or executor.id == guild.owner_id:
        return cfg, False

    if await is_whitelisted(guild.id, executor, event):
        # STANDALONE Antibetray Check
        ab_cfg = await get_antibetray_config(guild.id)
        if ab_cfg and ab_cfg.get("enabled") == 1:
            if await is_guild_premium(guild.id):
                window_sec = ab_cfg.get("window", 60)
                
                # Global Threshold (Mass Actions across ALL events)
                ab_count = record_antibetray_action(guild.id, executor.id, window_sec=window_sec)
                ab_threshold = ab_cfg.get("threshold", 3)
                
                if ab_count >= ab_threshold:
                    await record_violation(guild.id, executor.id, "Antibetray_Global", ab_count, punished="Antibetray (Global Threshold)")
                    return cfg, True
                
                # Per-Event Specific Limit (Dynamic)
                ab_limit = await get_antibetray_limit(guild.id, event)
                if ab_limit is not None:
                    strict_count = record_wl_action(guild.id, executor.id, event, window_sec=window_sec)
                    if strict_count >= ab_limit:
                        await record_violation(guild.id, executor.id, event, strict_count, punished="Antibetray (Per-Event Window)")
                        return cfg, True
                
                # If no AB limit set, fall back to checking strict window with normal limit
                else:
                    norm_limit = await get_limit(guild.id, event)
                    strict_count = record_wl_action(guild.id, executor.id, event, window_sec=window_sec)
                    if strict_count >= norm_limit:
                        await record_violation(guild.id, executor.id, event, strict_count, punished="Antibetray (Fallback Window)")
                        return cfg, True
                
                return cfg, False

        # Normal Whitelist Check (Legacy 10s Window)
        limit = await get_limit(guild.id, event)
        count = record_wl_action(guild.id, executor.id, event, window_sec=10)
        if count < limit:
            return cfg, False
        await record_violation(guild.id, executor.id, event, count)
        return cfg, True

    return cfg, True


async def get_mainroles(guild_id: int) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role_id FROM antinuke_mainroles WHERE guild_id=?", (guild_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]
