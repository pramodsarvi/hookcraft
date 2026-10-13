import asyncio
import math
import random
from typing import Any, List, Optional, Tuple

try:
    from playwright.async_api import BrowserContext, Locator, Page
    from playwright_stealth import stealth_async
except ImportError:
    BrowserContext = Any  # type: ignore
    Locator = Any  # type: ignore
    Page = Any  # type: ignore
    stealth_async = None  # type: ignore



class StealthEngine:
    """
    Advanced Anti-Bot Evasion Engine.
    Provides mathematical Bézier mouse kinematics, human typing cadences,
    eased scroll dynamics, and fingerprint masking.
    """

    @staticmethod
    async def apply_full_stealth(context: BrowserContext) -> None:
        """Applies playwright-stealth and deep runtime evasion scripts."""
        await stealth_async(context)

        # Remove automated webdriver properties and patch browser signatures
        await context.add_init_script("""
            // Wipe navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Emulate legitimate Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: () => {},
                csi: () => {},
                app: {}
            };

            // Emulate standard permissions query
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    origQuery(parameters)
            );

            // AudioContext and WebGL unmasking
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) return 'Intel Inc.';
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.apply(this, arguments);
            };

            // Canvas Fingerprint Micro-Noise (Defeats Canvas Hash Device Clustering)
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imgData = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                    // Subtle 1-bit noise on lowest order byte
                    if (imgData.data.length > 0) {
                        imgData.data[0] = imgData.data[0] ^ 1;
                        ctx.putImageData(imgData, 0, 0);
                    }
                }
                return origToDataURL.apply(this, arguments);
            };
        """)


    @staticmethod
    def _compute_cubic_bezier_points(
        p0: Tuple[float, float],
        p3: Tuple[float, float],
        steps: int = 25,
    ) -> List[Tuple[float, float]]:
        """
        Computes 2D points along a cubic Bézier curve with randomized control points
        to simulate natural human arm/wrist motor trajectories.
        Formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
        """
        x0, y0 = p0
        x3, y3 = p3
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        # Calculate randomized intermediate control points with perpendicular deviation
        dev_factor = random.uniform(0.15, 0.35) * (1 if random.random() > 0.5 else -1)
        p1 = (
            x0 + dx * 0.3 + dy * dev_factor + random.uniform(-10, 10),
            y0 + dy * 0.3 - dx * dev_factor + random.uniform(-10, 10),
        )
        p2 = (
            x0 + dx * 0.7 - dy * (dev_factor * 0.5) + random.uniform(-10, 10),
            y0 + dy * 0.7 + dx * (dev_factor * 0.5) + random.uniform(-10, 10),
        )

        points = []
        for i in range(steps + 1):
            t = i / steps
            # Add subtle physiological micro-tremor (+/- 0.5px)
            tremor_x = random.uniform(-0.5, 0.5) if (0 < i < steps) else 0
            tremor_y = random.uniform(-0.5, 0.5) if (0 < i < steps) else 0

            bx = (
                (1 - t) ** 3 * x0
                + 3 * (1 - t) ** 2 * t * p1[0]
                + 3 * (1 - t) * t ** 2 * p2[0]
                + t ** 3 * x3
                + tremor_x
            )
            by = (
                (1 - t) ** 3 * y0
                + 3 * (1 - t) ** 2 * t * p1[1]
                + 3 * (1 - t) * t ** 2 * p2[1]
                + t ** 3 * y3
                + tremor_y
            )
            points.append((bx, by))

        return points

    @classmethod
    async def human_mouse_move(
        cls,
        page: Page,
        target_x: float,
        target_y: float,
        current_pos: Optional[Tuple[float, float]] = None,
    ) -> None:
        """
        Dispatches smooth, non-linear mouse cursor movement using Bézier trajectories
        with velocity profiling (fast acceleration in mid-stroke, deceleration near target).
        """
        start = current_pos or (random.uniform(100, 300), random.uniform(100, 300))
        target = (target_x, target_y)
        steps = random.randint(20, 35)

        points = cls._compute_cubic_bezier_points(start, target, steps=steps)

        for i, (x, y) in enumerate(points):
            await page.mouse.move(x, y)
            # Bell-shaped velocity distribution: faster in middle, slower at endpoints
            progress = i / steps
            delay = 0.005 + 0.015 * math.sin(progress * math.pi)
            await asyncio.sleep(delay)

    @classmethod
    async def human_click(cls, page: Page, selector_or_locator: Any) -> None:
        """Moves to an element via a Bézier path, pauses briefly, and triggers a click."""
        if isinstance(selector_or_locator, str):
            loc = page.locator(selector_or_locator).first
        else:
            loc = selector_or_locator

        box = await loc.bounding_box()
        if not box:
            await loc.click()
            return

        # Target slightly off-center (humans rarely click exact center)
        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

        await cls.human_mouse_move(page, target_x, target_y)
        await asyncio.sleep(random.uniform(0.08, 0.22))
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.04, 0.11))
        await page.mouse.up()

    @staticmethod
    async def human_type(
        locator: Locator,
        text: str,
        typo_probability: float = 0.04,
    ) -> None:
        """
        Simulates realistic human typing cadences with log-normal delays,
        thinking pauses between words, and realistic typo & backspace recovery.
        """
        keyboard_neighbors = {
            "a": "s", "s": "d", "e": "r", "o": "p", "t": "y",
            "n": "m", "i": "o", "l": "k", "h": "j",
        }

        for char in text:
            # Check for simulated typo
            if random.random() < typo_probability and char.lower() in keyboard_neighbors:
                mistake_char = keyboard_neighbors[char.lower()]
                await locator.press_sequentially(mistake_char, delay=random.uniform(40, 100))
                # Realization pause
                await asyncio.sleep(random.uniform(0.18, 0.38))
                # Backspace
                await locator.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.16))

            # Normal keystroke delay (log-normal distribution)
            key_delay = random.lognormvariate(math.log(75), 0.35)
            key_delay = max(35, min(key_delay, 220))

            await locator.press_sequentially(char, delay=key_delay)

            # Natural cadence: longer pause at space or punctuation
            if char in {" ", ".", ",", "!", "?"}:
                await asyncio.sleep(random.uniform(0.15, 0.40))

    @staticmethod
    async def human_scroll(
        page: Page,
        target_distance: int = 700,
        direction: int = 1,
        steps: int = 9,
    ) -> None:
        """Smoothly scrolls the viewport using eased cosine momentum."""
        total_dist = target_distance * direction
        step_distances = []

        for i in range(steps):
            factor = (1 - math.cos((i + 1) * math.pi / steps)) / 2 - (1 - math.cos(i * math.pi / steps)) / 2
            step_distances.append(total_dist * factor * random.uniform(0.9, 1.1))

        for delta in step_distances:
            await page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.04, 0.11))

        await asyncio.sleep(random.uniform(0.35, 0.75))
