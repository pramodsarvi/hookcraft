import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
    from playwright_stealth import stealth_async
except ImportError:
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    async_playwright = Any  # type: ignore
    stealth_async = None  # type: ignore


from .config import settings

logger = logging.getLogger("ScraperSessionManager")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =====================================================================
# Custom Exceptions for Granular Error Handling
# =====================================================================

class ScraperException(Exception):
    """Base exception for scraping pipeline."""
    pass


class LoginWallDetectedException(ScraperException):
    """Raised when redirected to a login wall or non-dismissible login modal."""
    pass


class CaptchaEncounteredException(ScraperException):
    """Raised when an Arkose FunCaptcha, reCAPTCHA, or Cloudflare challenge is triggered."""
    pass


class RateLimitOrTemporaryBlockException(ScraperException):
    """Raised when X or Instagram issues a temporary IP or rate block (e.g. 429, 'Wait a few minutes')."""
    pass


class SessionExpiredException(ScraperException):
    """Raised when stored cookies/localStorage are invalid or revoked."""
    pass


# =====================================================================
# Session Manager
# =====================================================================

class SessionManager:
    """
    Manages browser sessions, storage states (cookies + localStorage),
    interactive authenticated checkpoints, and anti-bot/gate diagnostics
    for X (Twitter) and Instagram.
    """

    PLATFORM_URLS = {
        "x": {
            "login": "https://x.com/i/flow/login",
            "home": "https://x.com/home",
            "domain": "x.com",
            "auth_cookie": "auth_token",
        },
        "instagram": {
            "login": "https://www.instagram.com/accounts/login/",
            "home": "https://www.instagram.com/",
            "domain": "instagram.com",
            "auth_cookie": "sessionid",
        },
    }

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_storage_state_path(self, platform: str) -> Path:
        """Returns the storage_state.json file path for the platform."""
        normalized = platform.lower().strip()
        if "twitter" in normalized or normalized == "x":
            key = "x"
        elif "instagram" in normalized or normalized == "ig":
            key = "instagram"
        else:
            key = normalized
        return self.sessions_dir / f"{key}_storage_state.json"

    def has_saved_session(self, platform: str) -> bool:
        """Checks if a valid, non-empty storage state file exists."""
        path = self.get_storage_state_path(platform)
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cookies = data.get("cookies", [])
                return len(cookies) > 0
        except Exception:
            return False

    async def interactive_login(
        self,
        platform: str,
        timeout_seconds: int = 300,
        proxy: Optional[Dict[str, str]] = None,
    ) -> Path:
        """
        Launches a headed Chromium browser window for manual authentication.
        Once the user finishes logging in (including SMS/email 2FA), cookies and
        localStorage are persisted to local JSON for subsequent headless reuse.
        """
        normalized_platform = "x" if "x" in platform.lower() or "twitter" in platform.lower() else "instagram"
        plat_cfg = self.PLATFORM_URLS[normalized_platform]
        session_file = self.get_storage_state_path(normalized_platform)

        logger.info(
            "Starting interactive login for %s. Browser window will open. "
            "Complete login and 2FA manually in the window.",
            normalized_platform.upper(),
        )

        async with async_playwright() as p:
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,900",
            ]

            browser: Browser = await p.chromium.launch(
                headless=False,
                args=browser_args,
                proxy=proxy,
            )

            context: BrowserContext = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=settings.USER_AGENT,
                locale="en-US",
                timezone_id="America/New_York",
            )
            await stealth_async(context)

            page: Page = await context.new_page()
            await page.goto(plat_cfg["login"], wait_until="networkidle")

            logger.info("Awaiting successful authentication (looking for auth cookie: '%s')...", plat_cfg["auth_cookie"])
            auth_success = False
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                cookies = await context.cookies()
                has_auth_cookie = any(
                    c["name"] == plat_cfg["auth_cookie"] and plat_cfg["domain"] in c["domain"]
                    for c in cookies
                )

                # Check if current URL transitioned away from login page
                current_url = page.url
                is_on_logged_in_page = (
                    "x.com/home" in current_url
                    or ("instagram.com" in current_url and "accounts/login" not in current_url and len(cookies) > 5)
                )

                if has_auth_cookie or is_on_logged_in_page:
                    logger.info("Authentication cookie identified. Allowing 5 seconds for localStorage hydration...")
                    await page.wait_for_timeout(5000)
                    auth_success = True
                    break

                await asyncio.sleep(2)

            if not auth_success:
                await browser.close()
                raise TimeoutError(f"Interactive login timed out after {timeout_seconds} seconds.")

            # Persist full state (Cookies + LocalStorage) to disk
            await context.storage_state(path=str(session_file))
            logger.info("Session successfully saved to: %s", session_file.resolve())

            await browser.close()
            return session_file

    async def inspect_and_handle_barriers(self, page: Page, platform: str) -> None:
        """
        Analyzes the current page DOM, URL, and responses for anti-bot barriers:
        - CAPTCHAs (Arkose Labs FunCaptcha, Cloudflare, reCAPTCHA)
        - Session invalidation / Forced redirects to login
        - Rate limiting / Temporary blocks / Account checkpoints
        """
        current_url = page.url.lower()
        normalized_platform = "x" if "x" in platform.lower() or "twitter" in platform.lower() else "instagram"

        # 1. Global / Common Bot & Cloudflare Detections
        is_cloudflare = await page.locator("text='Just a moment...'").count() > 0 or \
                        await page.locator("text='Enable JavaScript and cookies to continue'").count() > 0 or \
                        await page.locator("#challenge-running, #cf-challenge-body").count() > 0

        if is_cloudflare:
            raise CaptchaEncounteredException(f"Cloudflare bot protection wall encountered on {current_url}.")

        # 2. X (Twitter) Specific Barrier Checks
        if normalized_platform == "x":
            # Arkose Labs FunCaptcha iframe
            has_arkose = await page.locator("iframe[src*='arkoselabs'], iframe[src*='arkose']").count() > 0
            if has_arkose:
                raise CaptchaEncounteredException("X Arkose Labs FunCaptcha verification triggered. Agent cannot proceed autonomously without solver.")

            # Forced login redirect or modal
            if "/i/flow/login" in current_url or "/login" in current_url:
                raise LoginWallDetectedException("Redirected to X login flow. Session expired or rejected.")

            # Account challenge or suspension
            if "/account/access" in current_url:
                raise RateLimitOrTemporaryBlockException("X account requires challenge verification (phone/email check).")

            # Check for Rate Limit message
            rate_limit_elem = await page.locator("text='Rate limit exceeded'").count() > 0 or \
                              await page.locator("text='Something went wrong. Try reloading.'").count() > 0
            if rate_limit_elem:
                logger.warning("X rate limit indicator detected on page.")

        # 3. Instagram Specific Barrier Checks
        elif normalized_platform == "instagram":
            # Checkpoint / Challenge / Suspended
            if "/challenge/" in current_url or "/checkpoint/" in current_url or "/accounts/suspended/" in current_url:
                raise CaptchaEncounteredException(f"Instagram security checkpoint or challenge triggered at {current_url}.")

            # Forced login redirect
            if "/accounts/login" in current_url:
                raise LoginWallDetectedException("Redirected to Instagram login wall. Session expired or rejected.")

            # Modal blocking interaction
            login_modal = await page.locator("div[role='dialog']").filter(
                has_text="Log In"
            ).count() > 0
            if login_modal:
                raise LoginWallDetectedException("Instagram blocking dialog ('Log in to continue') detected.")

            # Temporary action block
            action_blocked = await page.locator("text='Action Blocked'").count() > 0 or \
                             await page.locator("text='Please wait a few minutes before you try again'").count() > 0
            if action_blocked:
                raise RateLimitOrTemporaryBlockException("Instagram temporary action block active.")

    async def validate_session_liveness(self, platform: str) -> bool:
        """
        Executes a lightweight, non-invasive check to determine if the stored session
        is still valid without triggering anti-scraping flags.
        """
        if not self.has_saved_session(platform):
            return False

        normalized_platform = "x" if "x" in platform.lower() or "twitter" in platform.lower() else "instagram"
        plat_cfg = self.PLATFORM_URLS[normalized_platform]
        session_file = self.get_storage_state_path(normalized_platform)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                storage_state=str(session_file),
                user_agent=settings.USER_AGENT,
            )
            await stealth_async(context)
            page = await context.new_page()

            try:
                # Direct navigation to authenticated feed
                response = await page.goto(
                    plat_cfg["home"],
                    wait_until="domcontentloaded",
                    timeout=settings.BROWSER_TIMEOUT_MS,
                )
                if response and response.status >= 400:
                    logger.warning("Session probe returned status code %d", response.status)
                    await browser.close()
                    return False

                # Short wait for any immediate redirect to kick in
                await page.wait_for_timeout(3000)
                await self.inspect_and_handle_barriers(page, normalized_platform)
                logger.info("Session probe passed for %s.", normalized_platform.upper())
                await browser.close()
                return True

            except (LoginWallDetectedException, SessionExpiredException):
                logger.warning("Session for %s is expired or invalidated.", normalized_platform)
                await browser.close()
                return False
            except Exception as e:
                logger.error("Session verification encountered error: %s", str(e))
                await browser.close()
                return False
