import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from playwright.async_api import BrowserContext, Page, async_playwright
except ImportError:
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    async_playwright = Any  # type: ignore

from core.account_manager import MultiAccountContextManager
from core.stealth_engine import StealthEngine
from core.config import settings
from generation.schemas import AdCopyVariation, TargetPlatform

logger = logging.getLogger("AdsManagerPublisher")


class AdDeploymentResult(BaseModel):
    """Execution status of an ad campaign deployment."""

    ad_id: str
    campaign_name: str
    target_platform: TargetPlatform
    status: str = Field(..., description="'active', 'staged_draft', 'failed', 'simulated'")
    ad_set_id: Optional[str] = None
    creative_url: Optional[str] = None
    error_message: Optional[str] = None


class HeadlessAdsManagerPublisher:
    """
    Automated Headless Account Publisher.
    Navigates Meta Ads Manager or X Ads interface, uploads media assets,
    injects generated text copy, and launches or stages draft campaigns.
    """

    PLATFORM_URLS = {
        TargetPlatform.META_REELS: "https://adsmanager.facebook.com/adsmanager/manage/campaigns",
        TargetPlatform.INSTAGRAM: "https://adsmanager.facebook.com/adsmanager/manage/campaigns",
        TargetPlatform.X: "https://ads.x.com/campaigns",
    }

    def __init__(self, account_manager: Optional[MultiAccountContextManager] = None):
        self.account_manager = account_manager or MultiAccountContextManager()

    async def deploy_ad_creative(
        self,
        account_id: str,
        ad_variation: AdCopyVariation,
        media_path: Optional[Path] = None,
        simulate_launch: bool = True,
    ) -> AdDeploymentResult:
        """
        Executes end-to-end ad staging and deployment:
        1. Launches isolated persistent browser context for the designated ad account.
        2. Navigates to the platform ads dashboard.
        3. Fills in primary text, headline, CTA, and uploads media asset.
        4. Triggers review/publish.
        """
        platform = ad_variation.target_platform
        logger.info(
            "Initiating ad launch workflow for [%s] on %s (Mode: %s)...",
            ad_variation.ad_id,
            platform.value,
            "SIMULATION" if simulate_launch else "LIVE_BROWSER",
        )

        if simulate_launch:
            # High-velocity headless simulation mode for integration testing
            await asyncio.sleep(1.2)
            mock_ad_set_id = f"act_{platform.value[:2]}_{ad_variation.ad_id}_9921"
            logger.info("[SIMULATION] Ad creative [%s] successfully staged: %s", ad_variation.ad_id, mock_ad_set_id)
            return AdDeploymentResult(
                ad_id=ad_variation.ad_id,
                campaign_name=f"Flywheel_{ad_variation.persona_id}_{platform.value}",
                target_platform=platform,
                status="staged_draft",
                ad_set_id=mock_ad_set_id,
                creative_url=f"https://ads.internal/{mock_ad_set_id}",
            )

        # Live browser automation path
        async with async_playwright() as p:
            try:
                context = await self.account_manager.launch_isolated_context(
                    playwright_instance=p,
                    account_id=account_id,
                    headless=settings.HEADLESS,
                )
                await StealthEngine.apply_full_stealth(context)
                page: Page = await context.new_page()

                ads_url = self.PLATFORM_URLS.get(platform, "https://adsmanager.facebook.com")
                await page.goto(ads_url, wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT_MS)
                await asyncio.sleep(3.0)

                # 1. Locate Create Campaign button
                create_btn = page.locator("button, div[role='button']").filter(has_text="Create")
                if await create_btn.count() > 0:
                    await StealthEngine.human_click(page, create_btn.first)
                    await asyncio.sleep(2.0)

                # 2. Fill Primary Text & Headline via human typing cadences
                text_input = page.locator("textarea[placeholder*='text'], div[role='textbox']").first
                if await text_input.count() > 0:
                    await StealthEngine.human_click(page, text_input)
                    await StealthEngine.human_type(text_input, ad_variation.primary_text)

                headline_input = page.locator("input[placeholder*='Headline']").first
                if await headline_input.count() > 0:
                    await StealthEngine.human_click(page, headline_input)
                    await StealthEngine.human_type(headline_input, ad_variation.headline)

                # 3. Handle File Upload if media asset provided
                if media_path and media_path.exists():
                    file_input = page.locator("input[type='file']").first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(str(media_path.resolve()))
                        logger.info("Uploaded creative asset: %s", media_path.name)
                        await asyncio.sleep(4.0)

                # 4. Stage Draft or Publish
                publish_btn = page.locator("button").filter(has_text="Publish").first
                draft_btn = page.locator("button").filter(has_text="Close and save to draft").first

                if await draft_btn.count() > 0:
                    await StealthEngine.human_click(page, draft_btn)
                elif await publish_btn.count() > 0:
                    await StealthEngine.human_click(page, publish_btn)

                await asyncio.sleep(2.0)
                await context.close()

                return AdDeploymentResult(
                    ad_id=ad_variation.ad_id,
                    campaign_name=f"Flywheel_{ad_variation.persona_id}_{platform.value}",
                    target_platform=platform,
                    status="active",
                    ad_set_id=f"live_{ad_variation.ad_id}",
                )

            except Exception as e:
                logger.error("Live ad deployment encountered error: %s", e)
                return AdDeploymentResult(
                    ad_id=ad_variation.ad_id,
                    campaign_name=f"Flywheel_{ad_variation.persona_id}_{platform.value}",
                    target_platform=platform,
                    status="failed",
                    error_message=str(e),
                )
