import json
import logging
from pathlib import Path
from typing import Any, Optional

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = Any  # type: ignore

try:
    from browser_use import Browser, BrowserConfig
    from browser_use.browser.context import BrowserContextConfig
except ImportError:
    Browser = Any  # type: ignore
    BrowserConfig = Any  # type: ignore
    BrowserContextConfig = Any  # type: ignore


from .config import settings
from .session_manager import SessionManager

logger = logging.getLogger("BrowserFactory")


def get_qwen_vlm(
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Any:
    """
    Initializes a LangChain ChatOpenAI client pointed at an OpenAI-compatible
    endpoint serving Qwen2.5-VL or Qwen2.5-Coder (e.g. vLLM or Ollama).
    """
    if ChatOpenAI is not Any:
        return ChatOpenAI(
            model=model_name or settings.QWEN_MODEL_NAME,
            base_url=api_base or settings.QWEN_API_BASE,
            api_key=api_key or settings.QWEN_API_KEY,
            temperature=temperature if temperature is not None else settings.QWEN_TEMPERATURE,
        )

    # Lightweight fallback object when langchain-openai is not yet installed
    class MockQwenClient:
        def __init__(self, model: str, base_url: str):
            self.model = model
            self.base_url = base_url

        def invoke(self, *args, **kwargs):
            return "Generated response"

    return MockQwenClient(
        model=model_name or settings.QWEN_MODEL_NAME,
        base_url=api_base or settings.QWEN_API_BASE,
    )



def create_authenticated_browser_context(
    platform: str,
    session_manager: Optional[SessionManager] = None,
    headless: Optional[bool] = None,
) -> BrowserContextConfig:
    """
    Prepares a BrowserContextConfig pre-loaded with persisted storage state
    (cookies and localStorage) for X or Instagram.
    """
    sm = session_manager or SessionManager()
    session_path = sm.get_storage_state_path(platform)

    context_kwargs = {
        "user_agent": settings.USER_AGENT,
        "browser_window_size": {"width": 1280, "height": 900},
        "highlight_elements": True,
        "viewport_expansion": 500,
    }

    if session_path.exists():
        logger.info("Found existing session storage at: %s. Injecting into context.", session_path)
        # browser-use supports storage_state or cookies_file
        # We can pass storage_state or load cookies directly
        context_kwargs["cookies_file"] = str(session_path)
    else:
        logger.warning(
            "No saved session found at %s. Launching unauthenticated (may hit login walls).",
            session_path,
        )

    return BrowserContextConfig(**context_kwargs)


def create_browser_instance(headless: Optional[bool] = None) -> Browser:
    """
    Creates and configures a Browser instance with stealth-compliant
    Chromium parameters.
    """
    is_headless = headless if headless is not None else settings.HEADLESS

    chrome_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
    ]

    config = BrowserConfig(
        headless=is_headless,
        extra_chromium_args=chrome_args,
    )
    return Browser(config=config)
