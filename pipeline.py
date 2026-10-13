import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = Any  # type: ignore
from utils.graph_runtime import END, StateGraph

from core.account_manager import MultiAccountContextManager, AccountHealth
from core.stealth_engine import StealthEngine
from core.rate_limiter import VelocityRateLimiter
from core.config import settings
from ingestion.stream_interceptor import StreamInterceptor
from ingestion.jev_classifier import JevValidationEngine, JevClassificationResult
from ingestion.infinite_scroll_engine import AdaptiveScrollController, ScrollHealthStatus
from agents.dom_extractor import DOMExtractor
from state.graph_state import TrendIngestionState

logger = logging.getLogger("FlywheelIngestionPipeline")


class MarketingFlywheelIngestionPipeline:
    """
    LangGraph StateGraph Ingestion & Filtration Engine.
    Coordinates multi-account isolation, dynamic stream capture, adaptive
    infinite scrolling, velocity rate limiting, and sub-100ms Jev AI viral validation.
    """

    def __init__(self, account_manager: Optional[MultiAccountContextManager] = None):
        self.account_manager = account_manager or MultiAccountContextManager()
        self.rate_limiter = VelocityRateLimiter(max_actions_per_minute=18)
        self.jev_engine = JevValidationEngine(min_virality_score=0.60, max_slop_score=0.45)
        self.graph = self._compile_graph()


    def _compile_graph(self) -> Any:
        workflow = StateGraph(TrendIngestionState)

        workflow.add_node("initialize_session", self._node_initialize_session)
        workflow.add_node("scrape_and_capture_streams", self._node_scrape_and_capture_streams)
        workflow.add_node("jev_validation_gate", self._node_jev_validation_gate)
        workflow.add_node("audit_and_checkpoint", self._node_audit_and_checkpoint)

        workflow.set_entry_point("initialize_session")

        workflow.add_conditional_edges(
            "initialize_session",
            lambda s: "audit_and_checkpoint" if s["status"] == "error" else "scrape_and_capture_streams",
        )
        workflow.add_conditional_edges(
            "scrape_and_capture_streams",
            lambda s: "audit_and_checkpoint" if s["status"] in {"error", "degraded"} else "jev_validation_gate",
        )
        workflow.add_edge("jev_validation_gate", "audit_and_checkpoint")
        workflow.add_edge("audit_and_checkpoint", END)

        return workflow.compile()

    # -----------------------------------------------------------------
    # LangGraph Nodes
    # -----------------------------------------------------------------

    def _node_initialize_session(self, state: TrendIngestionState) -> Dict[str, Any]:
        """Resolves active isolated account and validates proxy/storage readiness."""
        platform = state["platform"]
        account_id = state.get("account_id")

        profile = None
        if account_id:
            profile = self.account_manager.accounts.get(account_id)
        if not profile:
            profile = self.account_manager.get_active_account(platform)

        if not profile:
            # Auto-register an account sandbox if none configured yet
            profile = self.account_manager.register_account(
                account_id=f"{platform}_agent_auto",
                platform=platform,
            )

        return {
            "account_id": profile.account_id,
            "status": "scraping",
            "raw_scraped_items": [],
            "validated_viral_trends": [],
            "rejected_items": [],
            "media_assets": {},
            "scroll_cycles": 0,
            "depth_reached_px": 0,
            "error_message": None,
        }

    async def _node_scrape_and_capture_streams(self, state: TrendIngestionState) -> Dict[str, Any]:
        """
        Launches isolated persistent Chromium context, intercepts live media,
        navigates feed, and executes adaptive scroll loop.
        """
        account_id = state["account_id"]
        platform = state["platform"]
        target = state["target_query_or_handle"].strip().lstrip("@")
        target_count = state["target_count"]

        interceptor = StreamInterceptor()
        scroll_engine = AdaptiveScrollController(max_stagnant_scrolls=4)
        raw_items: List[Dict[str, Any]] = []
        status = "filtering"
        error_msg = None

        target_url = f"https://x.com/{target}" if platform == "x" else f"https://www.instagram.com/{target}/"

        async with async_playwright() as p:
            try:
                context = await self.account_manager.launch_isolated_context(
                    playwright_instance=p,
                    account_id=account_id,
                    headless=settings.HEADLESS,
                )
                await StealthEngine.apply_full_stealth(context)
                page = await context.new_page()

                # Attach network stream interceptor
                interceptor.attach_network_interceptor(page, post_id=f"{target}_feed")

                logger.info("Navigating to target profile: %s", target_url)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT_MS)
                await asyncio.sleep(2.0)

                # Adaptive extraction loop
                while len(raw_items) < target_count:
                    # 1. Extract currently rendered DOM elements
                    if platform == "x":
                        tweets = await DOMExtractor.extract_visible_tweets(page)
                        for tw in tweets:
                            item_dict = tw.model_dump()
                            raw_items.append(item_dict)
                    else:
                        posts = await DOMExtractor.extract_visible_instagram_posts(page, target)
                        for post in posts:
                            item_dict = post.model_dump()
                            raw_items.append(item_dict)

                    # Deduplicate in scroll engine
                    scroll_engine.record_viewport_content(raw_items)

                    if len(raw_items) >= target_count:
                        break

                    # 2. Velocity Governor: Acquire rate-limiting token before scrolling
                    await self.rate_limiter.acquire()

                    # 3. Execute depth-adjusted adaptive scroll step
                    health = await scroll_engine.execute_adaptive_scroll_step(page)

                    if health == ScrollHealthStatus.RATE_LIMITED:
                        logger.warning("Account rate-limited. Triggering exponential backoff & cooldown.")
                        self.account_manager.mark_account_degraded(account_id, AccountHealth.COOLDOWN)
                        await self.rate_limiter.trigger_backoff("Platform rate-limit banner hit")
                        status = "degraded"
                        break

                    elif health == ScrollHealthStatus.FEED_EXHAUSTED:
                        logger.info("Reached end of timeline feed.")
                        break
                    elif health == ScrollHealthStatus.LOGIN_INTERRUPT:
                        logger.warning("Session expired or login gate hit.")
                        self.account_manager.mark_account_degraded(account_id, AccountHealth.SESSION_EXPIRED)
                        status = "degraded"
                        break

                interceptor.detach_network_interceptor()
                await context.close()

            except Exception as e:
                logger.error("Scraping execution error: %s", e)
                status = "error"
                error_msg = str(e)

        # Deduplicate final items list by ID
        unique_map: Dict[str, Dict[str, Any]] = {}
        for it in raw_items:
            key = it.get("tweet_id") or it.get("shortcode") or str(it.get("tweet_text", "")[:40])
            if key and key not in unique_map:
                unique_map[key] = it

        media_assets_dict = {k: str(v) for k, v in interceptor.captured_files.items()}

        return {
            "raw_scraped_items": list(unique_map.values()),
            "media_assets": media_assets_dict,
            "scroll_cycles": scroll_engine.scroll_cycle,
            "depth_reached_px": scroll_engine.current_depth_px,
            "status": status,
            "error_message": error_msg,
        }

    def _node_jev_validation_gate(self, state: TrendIngestionState) -> Dict[str, Any]:
        """
        High-Velocity Validation Engine (Jev AI).
        Executes sub-100ms matrix evaluation across extracted records.
        """
        raw_items = state["raw_scraped_items"]
        validated: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        logger.info("Passing %d extracted records through Jev AI validation matrix...", len(raw_items))

        for item in raw_items:
            item_id = str(item.get("tweet_id") or item.get("shortcode") or "item")
            text = str(item.get("tweet_text") or item.get("caption") or "")
            likes = int(item.get("likes_count") or 0)
            retweets_or_shares = int(item.get("retweets_count") or 0)
            views = item.get("views_count")
            views_int = int(views) if views else None

            classification: JevClassificationResult = self.jev_engine.classify_item(
                item_id=item_id,
                text=text,
                likes=likes,
                shares_or_retweets=retweets_or_shares,
                views=views_int,
            )

            item["jev_metrics"] = classification.model_dump()

            if classification.is_approved:
                validated.append(item)
            else:
                item["rejection_reason"] = classification.rejection_reason
                rejected.append(item)

        logger.info(
            "Jev validation complete: %d Approved Viral Trends, %d Rejected (Brand Unsafe / Low Velocity / AI Slop).",
            len(validated),
            len(rejected),
        )

        return {
            "validated_viral_trends": validated,
            "rejected_items": rejected,
            "status": "completed",
        }

    def _node_audit_and_checkpoint(self, state: TrendIngestionState) -> Dict[str, Any]:
        """Audit logging and telemetry checkpoint before handing off to the Create Loop."""
        logger.info(
            "Flywheel Ingestion Loop Finished. Target: %s | Approved Trends: %d | Intercepted Media: %d",
            state["target_query_or_handle"],
            len(state["validated_viral_trends"]),
            len(state["media_assets"]),
        )
        return state

    async def execute_listen_loop(
        self,
        platform: Literal["x", "instagram"],
        target_handle: str,
        target_count: int = 15,
        account_id: Optional[str] = None,
    ) -> TrendIngestionState:
        """Entrypoint for the 'Listen' Loop."""
        initial_state: TrendIngestionState = {
            "account_id": account_id or "",
            "platform": platform,
            "target_query_or_handle": target_handle,
            "target_count": target_count,
            "raw_scraped_items": [],
            "validated_viral_trends": [],
            "rejected_items": [],
            "media_assets": {},
            "scroll_cycles": 0,
            "depth_reached_px": 0,
            "status": "init",
            "error_message": None,
        }

        final_state = await self.graph.ainvoke(initial_state)
        return final_state
