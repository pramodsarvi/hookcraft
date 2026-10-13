import asyncio
import math
import random
from typing import Dict, Optional, Tuple
from playwright.async_api import BrowserContext, Page
from playwright_stealth import stealth_async
from core.config import settings
from core.proxy_providers import ProxyProviderManager


class StealthManager:
    """
    Manages browser anti-fingerprinting, human-like motor kinematics (scrolling/delays),
    and residential proxy routing to evade bot-detection heuristics on X and Instagram.
    """

    @staticmethod
    def get_proxy_dict(account_id: str = "default_worker") -> Optional[Dict[str, str]]:
        """Constructs Playwright-compatible proxy dictionary via ProxyProviderManager."""
        mgr = ProxyProviderManager()
        return mgr.get_playwright_proxy_dict(account_id)


    @staticmethod
    async def apply_stealth_evasions(context: BrowserContext) -> None:
        """
        Applies playwright-stealth and injects client evasions to patch
        navigator properties, WebGL signatures, and automation flags.
        """
        # 1. Apply standard playwright-stealth overrides
        await stealth_async(context)

        # 2. Inject deep evasions via init script before any document loads
        await context.add_init_script("""
            // Mask automation flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Emulate Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Fix navigator plugins & languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Patch permissions query for notifications
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

    @staticmethod
    async def human_delay(min_sec: float = 1.0, max_sec: float = 2.5) -> None:
        """
        Pauses execution using a randomized delay that approximates
        human attention latency.
        """
        # Gaussian distribution centered between min and max
        mid = (min_sec + max_sec) / 2.0
        sigma = (max_sec - min_sec) / 4.0
        delay = random.gauss(mid, sigma)
        delay = max(min_sec, min(max_sec, delay))
        await asyncio.sleep(delay)

    @staticmethod
    async def human_scroll(
        page: Page,
        target_distance: int = 600,
        direction: int = 1,
        steps: int = 8,
    ) -> None:
        """
        Performs naturalistic scrolling with acceleration, deceleration,
        and micro-jitter instead of instantaneous window.scrollBy calls.
        
        Args:
            page: Playwright Page instance
            target_distance: Total vertical pixels to traverse
            direction: 1 for down, -1 for up
            steps: Number of intermediate scroll ticks
        """
        distance_remaining = target_distance * direction

        # Distribute the distance using an ease-in-out cosine curve
        step_distances = []
        for i in range(steps):
            factor = (1 - math.cos((i + 1) * math.pi / steps)) / 2 - (1 - math.cos(i * math.pi / steps)) / 2
            jitter = random.uniform(0.9, 1.1)
            step_distances.append(distance_remaining * factor * jitter)

        for delta in step_distances:
            await page.mouse.wheel(0, delta)
            # Short variable pause between wheel ticks (40ms - 120ms)
            await asyncio.sleep(random.uniform(0.04, 0.12))

        # Micro pause after completing a scroll motion
        await asyncio.sleep(random.uniform(0.3, 0.7))

    @staticmethod
    async def human_mouse_wander(page: Page) -> None:
        """Simulates subtle human mouse wander across the viewport."""
        viewport = page.viewport_size or {"width": 1280, "height": 900}
        target_x = random.randint(100, viewport["width"] - 100)
        target_y = random.randint(100, viewport["height"] - 100)
        await page.mouse.move(target_x, target_y, steps=random.randint(5, 12))
