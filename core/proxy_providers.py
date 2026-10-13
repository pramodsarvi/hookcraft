import asyncio
import logging
import os
import random
import string
from enum import Enum
from typing import Any, Dict, Optional, Tuple
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("ProxyProviderManager")


class ProxyProviderType(str, Enum):
    IPROYAL = "iproyal"
    SMARTPROXY = "smartproxy"
    WEBSHARE = "webshare"
    CUSTOM = "custom"


class ProxyConfig(BaseModel):
    """
    Standardized proxy configuration supporting IPRoyal, Smartproxy, Webshare,
    sticky session pinning, and geo-targeting.
    """

    provider: ProxyProviderType = Field(default=ProxyProviderType.CUSTOM)
    host: str = Field(default="")
    port: int = Field(default=8080)
    username: str = Field(default="")
    password: str = Field(default="")
    country: str = Field(default="us", description="Two-letter ISO country code (e.g. 'us', 'gb', 'de').")
    session_duration_minutes: int = Field(default=30, description="Sticky IP duration before rotating.")


class ProxyProviderManager:
    """
    Automated Proxy Gateway & Session Pinning Generator.
    Tailored for residential proxies from IPRoyal, Smartproxy, and Webshare.
    """

    # Provider gateway default backbones
    PROVIDER_GATEWAYS = {
        ProxyProviderType.SMARTPROXY: {
            "host": "gate.smartproxy.com",
            "port": 7000,
        },
        ProxyProviderType.IPROYAL: {
            "host": "geo.iproyal.com",
            "port": 12321,
        },
        ProxyProviderType.WEBSHARE: {
            "host": "p.webshare.io",
            "port": 80,
        },
    }

    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or self._load_from_env()

    @classmethod
    def _load_from_env(cls) -> ProxyConfig:
        """Parses proxy settings from environment variables."""
        provider_str = os.getenv("PROXY_PROVIDER", "custom").lower().strip()
        provider_type = ProxyProviderType.CUSTOM
        for p in ProxyProviderType:
            if p.value == provider_str:
                provider_type = p
                break

        host = os.getenv("PROXY_HOST", "")
        port = int(os.getenv("PROXY_PORT", "8080"))

        # Fallback to provider default gateways if host not explicitly provided
        if not host and provider_type in cls.PROVIDER_GATEWAYS:
            host = cls.PROVIDER_GATEWAYS[provider_type]["host"]
            port = cls.PROVIDER_GATEWAYS[provider_type]["port"]

        return ProxyConfig(
            provider=provider_type,
            host=host,
            port=port,
            username=os.getenv("PROXY_USERNAME", ""),
            password=os.getenv("PROXY_PASSWORD", ""),
            country=os.getenv("PROXY_COUNTRY", "us").lower(),
            session_duration_minutes=int(os.getenv("PROXY_SESSION_DURATION_MINS", "30")),
        )

    def generate_account_proxy_url(self, account_id: str) -> Optional[str]:
        """
        Builds a dedicated residential proxy URL with sticky session parameters
        pinned to the specific account ID.
        """
        if not self.config.username or not self.config.host:
            # Check for legacy single-string PROXY_SERVER
            legacy_url = os.getenv("PROXY_SERVER")
            return legacy_url if legacy_url else None

        # Clean session token derived from account_id (e.g. 'session_x_bot_01')
        clean_sess = account_id.replace("-", "").replace("_", "")[:12]
        country = self.config.country.lower()

        # Format provider-specific username strings for session pinning
        if self.config.provider == ProxyProviderType.SMARTPROXY:
            # Smartproxy syntax: user-<username>-country-<country>-session-<session_id>-sessionduration-<mins>
            auth_user = f"user-{self.config.username}-country-{country}-session-{clean_sess}-sessionduration-{self.config.session_duration_minutes}"
            proxy_url = f"http://{auth_user}:{self.config.password}@{self.config.host}:{self.config.port}"

        elif self.config.provider == ProxyProviderType.IPROYAL:
            # IPRoyal syntax: <username>_country-<country>_session-<session_id>_lifetime-{mins}m
            auth_user = f"{self.config.username}_country-{country}_session-{clean_sess}_lifetime-{self.config.session_duration_minutes}m"
            proxy_url = f"http://{auth_user}:{self.config.password}@{self.config.host}:{self.config.port}"

        elif self.config.provider == ProxyProviderType.WEBSHARE:
            # Webshare residential syntax: <username>-country-<country>-session-<session_id>
            auth_user = f"{self.config.username}-country-{country}-session-{clean_sess}"
            proxy_url = f"http://{auth_user}:{self.config.password}@{self.config.host}:{self.config.port}"

        else:
            # Standard custom proxy
            if self.config.username and self.config.password:
                proxy_url = f"http://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}"
            else:
                proxy_url = f"http://{self.config.host}:{self.config.port}"

        return proxy_url

    def get_playwright_proxy_dict(self, account_id: str) -> Optional[Dict[str, str]]:
        """Constructs Playwright-compatible proxy dictionary."""
        proxy_url = self.generate_account_proxy_url(account_id)
        if not proxy_url:
            return None
        return {"server": proxy_url}

    async def test_proxy_connection(self, account_id: str = "probe_test") -> Dict[str, Any]:
        """
        Validates the proxy connection by querying public IP and geo telemetry.
        Returns live IP, detected country, and latency in milliseconds.
        """
        proxy_url = self.generate_account_proxy_url(account_id)
        if not proxy_url:
            return {
                "success": False,
                "error": "No proxy configured in settings or environment.",
            }

        logger.info("Testing connection through %s gateway...", self.config.provider.value.upper())
        start_time = asyncio.get_event_loop().time()

        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=12.0) as client:
                resp = await client.get("https://httpbin.org/ip")
                elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    origin_ip = data.get("origin", "Unknown")
                    logger.info("✅ Proxy online! Egress IP: %s (Latency: %.1fms)", origin_ip, elapsed_ms)
                    return {
                        "success": True,
                        "provider": self.config.provider.value,
                        "origin_ip": origin_ip,
                        "latency_ms": elapsed_ms,
                        "proxy_url_masked": proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text[:100],
                    }

        except Exception as e:
            logger.error("❌ Proxy health check failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }
