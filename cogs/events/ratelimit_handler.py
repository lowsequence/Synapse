import discord
import asyncio
import logging
import time
from collections import defaultdict, deque
from discord.ext import commands
from core import Synapse, Cog

log = logging.getLogger(__name__)


HOT_THRESHOLD = 3
WINDOW_SECONDS = 10

PAUSE_DURATION = 5



class RateLimitHandler(Cog):
    """
    Listens for Discord HTTP 429 rate-limit events dispatched by discord.py
    and provides smart per-route back-off + console telemetry.

    discord.py fires  ``on_http_ratelimit``  whenever it receives a 429 and
    automatically waits for the retry-after; this cog simply watches,
    logs, and adds an extra grace period when a route keeps getting hit.
    """

    def __init__(self, client: Synapse) -> None:
        self.client = client
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._paused: dict[str, float] = {}


    def _record_hit(self, route: str) -> int:
        """Record a hit for *route*, prune old entries, return recent hit count."""
        now = time.monotonic()
        hits = self._hits[route]
        hits.append(now)
        
        # O(1) removal from left
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
            
        return len(hits)

    def _is_hot(self, route: str) -> bool:
        return len(self._hits[route]) >= HOT_THRESHOLD

    async def _pause_route(self, route: str, extra: float) -> None:
        """Optionally sleep an extra grace period for a hot route."""
        if route in self._paused:
            return
        self._paused[route] = time.monotonic()
        log.warning(
            "[RateLimit] Route '%s' is hot (%d hits/%ds) — sleeping %.2fs extra.",
            route, len(self._hits[route]), WINDOW_SECONDS, extra,
        )
        await asyncio.sleep(extra)
        self._paused.pop(route, None)
        log.info("[RateLimit] Route '%s' resumed after grace period.", route)


    @commands.Cog.listener()
    async def on_http_ratelimit(
        self,
        sleep_for: float,
        route: str,
        is_global: bool,
    ) -> None:
        """Fired by discord.py whenever a 429 is encountered."""

        if is_global:
            log.critical(
                "[RateLimit] GLOBAL rate-limit hit! Discord is pausing ALL requests for %.2fs.",
                sleep_for,
            )
        else:
            hit_count = self._record_hit(route)
            log.warning(
                "[RateLimit] Route '%s' hit (retry-after=%.2fs, recent hits=%d/%ds).",
                route, sleep_for, hit_count, WINDOW_SECONDS,
            )

            if self._is_hot(route):
                asyncio.create_task(
                    self._pause_route(route, PAUSE_DURATION),
                    name=f"ratelimit_pause_{route}",
                )

    @commands.Cog.listener()
    async def on_shard_connect(self, shard_id: int) -> None:
        log.info("[RateLimit] Shard %d connected — monitoring rate-limits.", shard_id)


    def stats(self) -> dict[str, int]:
        """Return the current hit-count per route (inside the sliding window)."""
        now = time.monotonic()
        res = {}
        for route, hits in self._hits.items():
            # Quick cleanup before reporting
            while hits and now - hits[0] > WINDOW_SECONDS:
                hits.popleft()
            if hits:
                res[route] = len(hits)
        return res


async def setup(client: Synapse) -> None:
    await client.add_cog(RateLimitHandler(client))
