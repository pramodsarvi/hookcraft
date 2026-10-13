import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore

from core.stealth_engine import StealthEngine


logger = logging.getLogger("InfiniteScrollEngine")


class ScrollHealthStatus:
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    LAYOUT_BREAK = "layout_break"
    FEED_EXHAUSTED = "feed_exhausted"
    LOGIN_INTERRUPT = "login_interrupt"


class AdaptiveScrollController:
    """
    Adaptive Infinite-Scroll State Engine.
    Controls scrolling distance and hydration pauses based on page depth,
    detects layout breaks and rate limits, and maintains viewport history
    to prevent infinite-loop crashes.
    """

    RATE_LIMIT_MARKERS = [
        "rate limit exceeded",
        "something went wrong. try reloading",
        "please wait a few minutes before you try again",
        "action blocked",
        "try again later",
        "you're temporarily blocked",
    ]

    LOGIN_MARKERS = [
        "log in to continue",
        "don't miss what's happening",
        "sign in to x",
    ]

    def __init__(self, max_stagnant_scrolls: int = 4, max_depth_pixels: int = 50_000):
        self.max_stagnant_scrolls = max_stagnant_scrolls
        self.max_depth_pixels = max_depth_pixels
        self.current_depth_px: int = 0
        self.scroll_cycle: int = 0
        self.stagnant_cycles: int = 0
        self.viewport_history_hashes: Set[str] = set()

    def record_viewport_content(self, items: List[Dict[str, Any]]) -> int:
        """
        Hashes items in viewport to detect if new content has rendered.
        Returns the number of genuinely new items discovered.
        """
        new_items_count = 0
        for item in items:
            raw_repr = f"{item.get('tweet_id') or item.get('shortcode') or item.get('text', '')}"
            item_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()
            if item_hash not in self.viewport_history_hashes:
                self.viewport_history_hashes.add(item_hash)
                new_items_count += 1

        if new_items_count == 0:
            self.stagnant_cycles += 1
            logger.debug("Viewport content stagnant (cycle %d/%d)", self.stagnant_cycles, self.max_stagnant_scrolls)
        else:
            self.stagnant_cycles = 0

        return new_items_count

    async def inspect_page_health(self, page: Page) -> str:
        """Detects rate limits, login interrupts, and layout breaks."""
        # 1. Inspect DOM text for rate-limit notifications
        page_text = (await page.evaluate("() => document.body.innerText || ''")).lower()

        for marker in self.RATE_LIMIT_MARKERS:
            if marker in page_text:
                logger.error("Rate-limit banner detected: '%s'", marker)
                return ScrollHealthStatus.RATE_LIMITED

        for marker in self.LOGIN_MARKERS:
            if marker in page_text:
                logger.warning("Login interruption modal detected: '%s'", marker)
                return ScrollHealthStatus.LOGIN_INTERRUPT

        # 2. Check for layout break / blank infinite space
        dom_metrics = await page.evaluate("""
            () => ({
                scrollHeight: document.body.scrollHeight,
                innerHeight: window.innerHeight,
                scrollY: window.scrollY
            })
        """)
        if dom_metrics["scrollHeight"] == 0 or (self.current_depth_px > 5000 and dom_metrics["scrollY"] == 0):
            logger.error("DOM layout collapsed (scrollHeight: 0 or viewport reset).")
            return ScrollHealthStatus.LAYOUT_BREAK

        # 3. Check for stagnation termination
        if self.stagnant_cycles >= self.max_stagnant_scrolls or self.current_depth_px >= self.max_depth_pixels:
            return ScrollHealthStatus.FEED_EXHAUSTED

        return ScrollHealthStatus.HEALTHY

    def compute_adaptive_scroll_params(self) -> Tuple[int, float]:
        """
        Dynamically calculates scroll distance and settle delay based on depth.
        At deeper depths, React DOM unmounting incurs higher garbage-collection pauses.
        """
        if self.current_depth_px < 3000:
            # Fast, nimble scrolling at top of feed
            distance = 650
            settle_delay = 1.3
        elif self.current_depth_px < 15000:
            # Standard mid-feed cadence
            distance = 800
            settle_delay = 1.8
        else:
            # Deep feed: larger travel, longer wait for heavy virtualization reconciliation
            distance = 1000
            settle_delay = 2.6

        return distance, settle_delay

    async def execute_adaptive_scroll_step(self, page: Page) -> str:
        """
        Executes a single humanized scroll step with depth-adapted distance,
        motor kinematics, and health inspection.
        """
        self.scroll_cycle += 1
        distance, settle_delay = self.compute_adaptive_scroll_params()

        # Execute Bézier/eased human scroll
        await StealthEngine.human_scroll(page, target_distance=distance, steps=8)
        self.current_depth_px += distance

        # Allow lazy media and React windowing to hydrate
        await asyncio.sleep(settle_delay)

        # Diagnose health
        health = await self.inspect_page_health(page)
        return health
