import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from generation.schemas import AdCopyVariation

logger = logging.getLogger("MetaMarketingAPI")


class MetaAPISettings(BaseModel):
    access_token: str = Field(default_factory=lambda: os.getenv("META_ACCESS_TOKEN", ""))
    ad_account_id: str = Field(default_factory=lambda: os.getenv("META_AD_ACCOUNT_ID", ""))
    api_version: str = "v21.0"

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    @property
    def account_endpoint(self) -> str:
        clean_act = self.ad_account_id.replace("act_", "")
        return f"{self.base_url}/act_{clean_act}"


class MetaMarketingAPIClient:
    """
    Direct Programmatic Meta Graph Marketing API Client.
    Used by InstaAgent-style production systems to launch, pause, and scale
    ad sets directly through Meta's ad infrastructure without browser selector dependencies.
    """

    def __init__(self, settings: Optional[MetaAPISettings] = None):
        self.settings = settings or MetaAPISettings()
        self.is_configured = bool(self.settings.access_token and self.settings.ad_account_id)
        if not self.is_configured:
            logger.info("Meta Marketing API credentials not fully set; operating in hybrid fallback mode.")

    async def create_campaign(self, name: str, objective: str = "OUTCOME_TRAFFIC") -> Optional[str]:
        """Creates a top-level Meta campaign."""
        if not self.is_configured:
            return f"sim_campaign_{hash(name) % 100000}"

        url = f"{self.settings.account_endpoint}/campaigns"
        params = {
            "name": name,
            "objective": objective,
            "status": "PAUSED",
            "special_ad_categories": "NONE",
            "access_token": self.settings.access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=params)
            data = resp.json()
            if "id" in data:
                logger.info("Created Meta Campaign ID: %s", data["id"])
                return data["id"]
            logger.error("Meta Campaign creation failed: %s", data)
            return None

    async def pause_ad(self, ad_id: str) -> bool:
        """Kills/Pauses an underperforming ad creative."""
        if not self.is_configured or ad_id.startswith("sim_") or ad_id.startswith("act_"):
            logger.info("[API SIMULATION] Successfully paused ad [%s]", ad_id)
            return True

        url = f"{self.settings.base_url}/{ad_id}"
        params = {"status": "PAUSED", "access_token": self.settings.access_token}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=params)
            return resp.status_code == 200

    async def update_adset_budget(self, adset_id: str, new_daily_budget_cents: int) -> bool:
        """Scales the budget for a winning ad set."""
        if not self.is_configured or adset_id.startswith("sim_") or adset_id.startswith("act_"):
            logger.info("[API SIMULATION] Scaled ad set [%s] budget to %d cents", adset_id, new_daily_budget_cents)
            return True

        url = f"{self.settings.base_url}/{adset_id}"
        params = {
            "daily_budget": str(new_daily_budget_cents),
            "access_token": self.settings.access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=params)
            return resp.status_code == 200

    async def fetch_ad_insights(self, ad_id: str) -> Optional[Dict[str, Any]]:
        """Polls real conversion metrics: impressions, clicks, spend, CTR."""
        if not self.is_configured or ad_id.startswith("sim_") or ad_id.startswith("act_"):
            return None

        url = f"{self.settings.base_url}/{ad_id}/insights"
        params = {
            "fields": "impressions,clicks,spend,ctr,cpc,video_p25_watched_actions",
            "access_token": self.settings.access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]
            return None
