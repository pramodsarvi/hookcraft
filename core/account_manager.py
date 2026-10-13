import asyncio
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

try:
    from playwright.async_api import BrowserContext, async_playwright
except ImportError:
    BrowserContext = Any  # type: ignore
    async_playwright = Any  # type: ignore

from core.config import settings


logger = logging.getLogger("MultiAccountManager")


class AccountHealth(str, Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    CHECKPOINT_TRIGGERED = "checkpoint"
    SESSION_EXPIRED = "expired"


class AccountProfile(BaseModel):
    """Configuration and isolation boundaries for a single social account."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'x_agent_alpha').")
    platform: str = Field(..., description="'x' or 'instagram'.")
    user_data_dir: Path = Field(..., description="Isolated persistent Chromium directory.")
    proxy_url: Optional[str] = Field(None, description="Dedicated residential proxy (http://user:pass@host:port).")
    storage_state_file: Path = Field(..., description="Path to cookies and localStorage JSON snapshot.")
    health: AccountHealth = Field(default=AccountHealth.ACTIVE)
    consecutive_errors: int = Field(default=0)


class MultiAccountContextManager:
    """
    Manages multi-account isolation. Maps unique social accounts to independent
    Chromium user-data directories, pins residential proxies per account, and
    orchestrates session life-cycles with automated re-authentication triggers.
    """

    def __init__(self, profiles_base_dir: Optional[Path] = None):
        self.base_dir = profiles_base_dir or (Path("./data/account_profiles"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.accounts: Dict[str, AccountProfile] = {}
        self._load_registered_accounts()

    def _load_registered_accounts(self) -> None:
        """Loads or initializes account profiles from accounts registry."""
        registry_file = self.base_dir / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        profile = AccountProfile(
                            account_id=item["account_id"],
                            platform=item["platform"],
                            user_data_dir=Path(item["user_data_dir"]),
                            proxy_url=item.get("proxy_url"),
                            storage_state_file=Path(item["storage_state_file"]),
                            health=AccountHealth(item.get("health", "active")),
                            consecutive_errors=item.get("consecutive_errors", 0),
                        )
                        self.accounts[profile.account_id] = profile
            except Exception as e:
                logger.error("Failed loading account registry: %s", e)

    def save_registry(self) -> None:
        """Persists the updated accounts state to disk."""
        registry_file = self.base_dir / "registry.json"
        payload = [
            {
                "account_id": a.account_id,
                "platform": a.platform,
                "user_data_dir": str(a.user_data_dir.resolve()),
                "proxy_url": a.proxy_url,
                "storage_state_file": str(a.storage_state_file.resolve()),
                "health": a.health.value,
                "consecutive_errors": a.consecutive_errors,
            }
            for a in self.accounts.values()
        ]
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def register_account(
        self,
        account_id: str,
        platform: str,
        proxy_url: Optional[str] = None,
    ) -> AccountProfile:
        """Registers a new account with its own isolated directory structure."""
        account_dir = self.base_dir / account_id
        account_dir.mkdir(parents=True, exist_ok=True)
        storage_file = account_dir / f"{account_id}_storage_state.json"

        profile = AccountProfile(
            account_id=account_id,
            platform=platform.lower(),
            user_data_dir=account_dir / "chromium_profile",
            proxy_url=proxy_url or settings.PROXY_SERVER,
            storage_state_file=storage_file,
            health=AccountHealth.ACTIVE,
        )
        profile.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.accounts[account_id] = profile
        self.save_registry()
        logger.info("Registered isolated account profile: %s [%s]", account_id, platform)
        return profile

    def get_active_account(self, platform: str) -> Optional[AccountProfile]:
        """Retrieves an operational account for the specified platform."""
        target_platform = platform.lower()
        for profile in self.accounts.values():
            if profile.platform == target_platform and profile.health == AccountHealth.ACTIVE:
                return profile
        return None

    def mark_account_degraded(self, account_id: str, status: AccountHealth) -> None:
        """Flags an account if rate-limited or flagged with a checkpoint."""
        if account_id in self.accounts:
            self.accounts[account_id].health = status
            self.accounts[account_id].consecutive_errors += 1
            self.save_registry()
            logger.warning("Account %s marked as %s", account_id, status.value)

    async def launch_isolated_context(
        self,
        playwright_instance: Any,
        account_id: str,
        headless: Optional[bool] = None,
    ) -> BrowserContext:
        """
        Launches an isolated persistent Chromium context tied to the account's
        distinct user_data_dir and residential proxy.
        """
        profile = self.accounts.get(account_id)
        if not profile:
            raise ValueError(f"Account ID '{account_id}' is not registered.")

        is_headless = headless if headless is not None else settings.HEADLESS

        # Parse proxy parameters if specified
        proxy_config = None
        if profile.proxy_url:
            proxy_config = {"server": profile.proxy_url}

        chromium_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            f"--window-size=1280,900",
        ]

        logger.info(
            "Launching isolated persistent context for '%s' using directory: %s",
            account_id,
            profile.user_data_dir,
        )

        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(profile.user_data_dir),
            headless=is_headless,
            args=chromium_args,
            proxy=proxy_config,
            viewport={"width": 1280, "height": 900},
            user_agent=settings.USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
        )

        return context
