import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional, Union
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph

from core.config import settings
from core.session_manager import (
    SessionManager,
    CaptchaEncounteredException,
    LoginWallDetectedException,
    RateLimitOrTemporaryBlockException,
)
from core.stealth import StealthManager
from core.browser_factory import get_qwen_vlm
from agents.dom_extractor import DOMExtractor, ExtractionBuffer
from agents.prompts import (
    QWEN_VISION_SYSTEM_PROMPT,
    get_x_scraping_prompt,
    get_instagram_scraping_prompt,
)
from schemas.x_twitter import XTweet, XScrapedFeed
from schemas.instagram import InstagramPost, InstagramScrapedFeed

logger = logging.getLogger("SocialScraperAgent")


# =====================================================================
# LangGraph Workflow State
# =====================================================================

class ScraperState(TypedDict):
    platform: Literal["x", "instagram"]
    target_handle: str
    target_count: int
    current_url: str
    items: List[Dict[str, Any]]
    scroll_cycles: int
    stagnant_cycles: int
    is_finished: bool
    status: str
    error: Optional[str]


# =====================================================================
# Hybrid High-Performance Scraper Engine
# =====================================================================

class SocialScraperPipeline:
    """
    Production-grade scraping pipeline orchestrating Playwright stealth,
    session injection, infinite scroll motor emulation, and Pydantic validation.
    """

    def __init__(self):
        self.session_manager = SessionManager()
        self.workflow = self._build_langgraph_workflow()

    def _build_langgraph_workflow(self) -> Any:
        """Constructs the LangGraph state orchestration graph."""
        graph = StateGraph(ScraperState)

        # Register execution steps
        graph.add_node("validate_prerequisites", self._node_validate_prerequisites)
        graph.add_node("execute_scraping", self._node_execute_scraping)
        graph.add_node("finalize_dataset", self._node_finalize_dataset)

        graph.set_entry_point("validate_prerequisites")

        graph.add_conditional_edges(
            "validate_prerequisites",
            lambda s: "finalize_dataset" if s["status"] == "error" else "execute_scraping",
        )
        graph.add_edge("execute_scraping", "finalize_dataset")
        graph.add_edge("finalize_dataset", END)

        return graph.compile()

    def _node_validate_prerequisites(self, state: ScraperState) -> Dict[str, Any]:
        """Validates that session storage exists and targets are clean."""
        platform = state["platform"]
        clean_handle = state["target_handle"].strip().lstrip("@")

        if not self.session_manager.has_saved_session(platform):
            logger.warning(
                "No saved session state found for %s. Pipeline will attempt "
                "unauthenticated scrape, but may encounter login walls.",
                platform,
            )

        target_url = (
            f"https://x.com/{clean_handle}"
            if platform == "x"
            else f"https://www.instagram.com/{clean_handle}/"
        )

        return {
            "target_handle": clean_handle,
            "current_url": target_url,
            "status": "ready",
            "items": [],
            "scroll_cycles": 0,
            "stagnant_cycles": 0,
            "is_finished": False,
        }

    async def _node_execute_scraping(self, state: ScraperState) -> Dict[str, Any]:
        """
        Executes stealth browser lifecycle, navigates to target, and runs
        the humanized infinite-scroll extraction loop.
        """
        platform = state["platform"]
        target_handle = state["target_handle"]
        target_count = state["target_count"]
        session_file = self.session_manager.get_storage_state_path(platform)
        proxy_cfg = StealthManager.get_proxy_dict()

        buffer = ExtractionBuffer(target_count=target_count, max_stagnant_scrolls=4)
        error_msg = None
        status = "success"

        async with async_playwright() as p:
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,900",
            ]

            browser: Browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                args=browser_args,
                proxy=proxy_cfg,
            )

            context_kwargs: Dict[str, Any] = {
                "viewport": {"width": 1280, "height": 900},
                "user_agent": settings.USER_AGENT,
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }
            if session_file.exists():
                context_kwargs["storage_state"] = str(session_file)

            context: BrowserContext = await browser.new_context(**context_kwargs)
            await StealthManager.apply_stealth_evasions(context)
            page: Page = await context.new_page()

            try:
                logger.info("Navigating to %s...", state["current_url"])
                await page.goto(
                    state["current_url"],
                    wait_until="domcontentloaded",
                    timeout=settings.BROWSER_TIMEOUT_MS,
                )

                # Initial settle & barrier diagnostic
                await StealthManager.human_delay(1.5, 3.0)
                await self.session_manager.inspect_and_handle_barriers(page, platform)

                # Dismiss transient popups if present
                await self._dismiss_transient_dialogs(page, platform)

                # Infinite scroll extraction loop
                scroll_count = 0
                while not buffer.is_finished and scroll_count < 25:
                    scroll_count += 1
                    logger.info(
                        "[%s] Extraction loop #%d (Collected: %d/%d)...",
                        platform.upper(),
                        scroll_count,
                        len(buffer.items),
                        target_count,
                    )

                    # Extract currently visible items using semantic selectors
                    if platform == "x":
                        visible_tweets = await DOMExtractor.extract_visible_tweets(page)
                        new_added = buffer.add_items(visible_tweets, id_key="tweet_id")
                    else:
                        visible_posts = await DOMExtractor.extract_visible_instagram_posts(page, target_handle)
                        new_added = buffer.add_items(visible_posts, id_key="shortcode")

                    logger.debug("Discovered %d new unique posts in this viewport.", new_added)

                    if buffer.is_finished:
                        break

                    # Human-like motor kinematics: mouse movement & eased scroll
                    await StealthManager.human_mouse_wander(page)
                    await StealthManager.human_scroll(
                        page=page,
                        target_distance=random.randint(650, 950),
                        direction=1,
                        steps=random.randint(7, 12),
                    )

                    # Lazy loading network wait with variable jitter
                    await StealthManager.human_delay(min_sec=1.5, max_sec=2.8)

                    # Periodically re-check barriers
                    await self.session_manager.inspect_and_handle_barriers(page, platform)

            except (CaptchaEncounteredException, LoginWallDetectedException, RateLimitOrTemporaryBlockException) as e:
                logger.error("Scraping halted due to barrier: %s", e)
                status = "blocked"
                error_msg = str(e)
            except Exception as e:
                logger.error("Scraping encountered unexpected error: %s", e)
                status = "error"
                error_msg = str(e)
            finally:
                await browser.close()

        # Serialize buffer items to dictionaries for state
        serialized_items = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in buffer.items
        ]

        return {
            "items": serialized_items,
            "scroll_cycles": buffer.stagnant_scroll_count,
            "is_finished": True,
            "status": status,
            "error": error_msg,
        }

    def _node_finalize_dataset(self, state: ScraperState) -> Dict[str, Any]:
        """Logs completion statistics."""
        logger.info(
            "Workflow finalized for %s. Total records: %d. Status: %s.",
            state["target_handle"],
            len(state["items"]),
            state["status"],
        )
        return state

    async def _dismiss_transient_dialogs(self, page: Page, platform: str) -> None:
        """Softly closes dismissible cookie or promotional dialogs."""
        try:
            if platform == "x":
                # Look for 'Refuse non-essential cookies' or close icon
                cookie_close = page.locator("div[role='button']").filter(has_text="Refuse non-essential cookies")
                if await cookie_close.count() > 0:
                    await cookie_close.first.click()
            else:
                # Instagram 'Decline optional cookies' or 'Not Now'
                not_now = page.locator("button").filter(has_text="Not Now")
                if await not_now.count() > 0:
                    await not_now.first.click()
        except Exception:
            pass

    async def run(
        self,
        platform: Literal["x", "instagram"],
        target_handle: str,
        target_count: int = 10,
    ) -> Union[XScrapedFeed, InstagramScrapedFeed]:
        """
        Executes the full LangGraph scraping workflow and outputs a strict
        Pydantic dataset container.
        """
        initial_state: ScraperState = {
            "platform": platform,
            "target_handle": target_handle,
            "target_count": target_count,
            "current_url": "",
            "items": [],
            "scroll_cycles": 0,
            "stagnant_cycles": 0,
            "is_finished": False,
            "status": "init",
            "error": None,
        }

        final_state = await self.workflow.ainvoke(initial_state)

        # Validate and return strict Pydantic feed models
        if platform == "x":
            tweets = [XTweet(**item) for item in final_state["items"]]
            return XScrapedFeed(
                target_query_or_user=target_handle,
                tweets=tweets,
                total_tweets_captured=len(tweets),
            )
        else:
            posts = [InstagramPost(**item) for item in final_state["items"]]
            return InstagramScrapedFeed(
                target_handle=target_handle,
                posts=posts,
                total_posts_captured=len(posts),
            )


# =====================================================================
# Autonomous browser-use Agent Mode (Vision-Grounded)
# =====================================================================

async def run_autonomous_vision_agent(
    platform: Literal["x", "instagram"],
    target_handle: str,
    max_items: int = 10,
) -> Any:
    """
    Executes an autonomous vision-grounded agent loop via browser-use
    powered by Qwen2.5-VL.
    """
    from browser_use import Agent
    from core.browser_factory import create_browser_instance, create_authenticated_browser_context

    vlm = get_qwen_vlm()
    browser = create_browser_instance(headless=settings.HEADLESS)
    context_config = create_authenticated_browser_context(platform)

    prompt = (
        get_x_scraping_prompt(target_handle, max_items)
        if platform == "x"
        else get_instagram_scraping_prompt(target_handle, max_items)
    )

    agent = Agent(
        task=prompt,
        llm=vlm,
        browser=browser,
        browser_context=context_config,
        system_prompt=QWEN_VISION_SYSTEM_PROMPT,
        max_actions_per_step=3,
    )

    logger.info("Launching autonomous browser-use agent with Qwen2.5-VL...")
    history = await agent.run(max_steps=20)
    return history
