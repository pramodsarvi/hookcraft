import asyncio
import logging
import random
import time
from typing import Optional

logger = logging.getLogger("VelocityRateLimiter")


class VelocityRateLimiter:
    """
    Token-Bucket Rate Limiter with Stochastic Jitter and Exponential Backoff.
    Prevents account lockouts by enforcing human consumption velocity caps:
    - Maximum actions/scrolls per minute per account.
    - Gaussian micro-jitter to prevent mechanical rhythm detection.
    - Automated exponential backoff when rate-limit banners are detected.
    """

    def __init__(
        self,
        max_actions_per_minute: int = 18,
        base_backoff_seconds: int = 300,  # 5 minutes
        max_backoff_seconds: int = 3600,   # 60 minutes
    ):
        self.capacity = max_actions_per_minute
        self.tokens = float(max_actions_per_minute)
        self.fill_rate = max_actions_per_minute / 60.0  # tokens added per second
        self.last_update = time.monotonic()
        self.base_backoff = base_backoff_seconds
        self.max_backoff = max_backoff_seconds
        self.consecutive_rate_limits = 0
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquires a token before executing a scroll or page action.
        If tokens are depleted, asynchronously pauses execution until replenished.
        """
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            # Replenish tokens based on elapsed time
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.fill_rate)

            if self.tokens < 1.0:
                sleep_needed = (1.0 - self.tokens) / self.fill_rate
                # Add human jitter (+/- 20%)
                jitter = sleep_needed * random.uniform(0.9, 1.3)
                logger.debug("Velocity cap reached. Throttling for %.2f seconds...", jitter)
                await asyncio.sleep(jitter)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

        # Natural human pause between consecutive actions (1.8s - 3.8s)
        human_pause = random.uniform(1.8, 3.8)
        await asyncio.sleep(human_pause)

    async def trigger_backoff(self, reason: str = "Rate Limit 429 Detected") -> float:
        """
        Called when a platform rate-limit banner is detected.
        Applies exponential backoff with full jitter to allow platform cooldown.
        """
        async with self.lock:
            self.consecutive_rate_limits += 1
            # Exponential formula: base * 2^(n-1) capped at max_backoff
            exp_factor = 2 ** min(self.consecutive_rate_limits - 1, 5)
            backoff = min(self.max_backoff, self.base_backoff * exp_factor)
            # Full jitter: random uniform between 50% and 100% of backoff
            actual_sleep = random.uniform(backoff * 0.5, backoff)

            logger.warning(
                "🚨 RATE LIMIT DETECTED (%s). Entering exponential backoff for %.1f minutes (attempt #%d)...",
                reason,
                actual_sleep / 60.0,
                self.consecutive_rate_limits,
            )

        await asyncio.sleep(actual_sleep)
        return actual_sleep

    def reset_backoff(self) -> None:
        """Resets backoff counter upon consecutive healthy scrape cycles."""
        self.consecutive_rate_limits = 0
