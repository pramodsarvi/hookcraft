import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class ScraperSettings(BaseSettings):
        """Configuration management via environment variables or .env file."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        # Qwen Vision-Language Model Endpoint (vLLM / Ollama / OpenAI-compatible)
        QWEN_API_BASE: str = "http://localhost:8000/v1"
        QWEN_API_KEY: str = "EMPTY"
        QWEN_MODEL_NAME: str = "Qwen/Qwen2.5-VL-72B-Instruct"
        QWEN_TEMPERATURE: float = 0.1

        # Browser Execution
        HEADLESS: bool = False
        BROWSER_TIMEOUT_MS: int = 30000
        USER_AGENT: str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        )

        # Proxy Configuration (Smartproxy, IPRoyal, Webshare, Custom)
        PROXY_PROVIDER: str = "custom"
        PROXY_HOST: Optional[str] = None
        PROXY_PORT: int = 8080
        PROXY_USERNAME: Optional[str] = None
        PROXY_PASSWORD: Optional[str] = None
        PROXY_COUNTRY: str = "us"
        PROXY_SESSION_DURATION_MINS: int = 30
        PROXY_SERVER: Optional[str] = None

        # Storage paths
        SESSIONS_DIR: Path = Path("./sessions")

        def get_session_file(self, platform_name: str) -> Path:
            self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            return self.SESSIONS_DIR / f"{platform_name}_storage_state.json"

except ImportError:
    from pydantic import BaseModel, Field

    class ScraperSettings(BaseModel):  # type: ignore[no-redef]
        """Fallback configuration class when pydantic-settings is not installed."""

        QWEN_API_BASE: str = Field(default_factory=lambda: os.getenv("QWEN_API_BASE", "http://localhost:8000/v1"))
        QWEN_API_KEY: str = Field(default_factory=lambda: os.getenv("QWEN_API_KEY", "EMPTY"))
        QWEN_MODEL_NAME: str = Field(default_factory=lambda: os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen2.5-VL-72B-Instruct"))
        QWEN_TEMPERATURE: float = Field(default_factory=lambda: float(os.getenv("QWEN_TEMPERATURE", "0.1")))

        HEADLESS: bool = Field(default_factory=lambda: os.getenv("HEADLESS", "false").lower() == "true")
        BROWSER_TIMEOUT_MS: int = Field(default_factory=lambda: int(os.getenv("BROWSER_TIMEOUT_MS", "30000")))
        USER_AGENT: str = Field(
            default_factory=lambda: os.getenv(
                "USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            )
        )

        PROXY_PROVIDER: str = Field(default_factory=lambda: os.getenv("PROXY_PROVIDER", "custom"))
        PROXY_HOST: Optional[str] = Field(default_factory=lambda: os.getenv("PROXY_HOST"))
        PROXY_PORT: int = Field(default_factory=lambda: int(os.getenv("PROXY_PORT", "8080")))
        PROXY_USERNAME: Optional[str] = Field(default_factory=lambda: os.getenv("PROXY_USERNAME"))
        PROXY_PASSWORD: Optional[str] = Field(default_factory=lambda: os.getenv("PROXY_PASSWORD"))
        PROXY_COUNTRY: str = Field(default_factory=lambda: os.getenv("PROXY_COUNTRY", "us"))
        PROXY_SESSION_DURATION_MINS: int = Field(default_factory=lambda: int(os.getenv("PROXY_SESSION_DURATION_MINS", "30")))
        PROXY_SERVER: Optional[str] = Field(default_factory=lambda: os.getenv("PROXY_SERVER"))
        SESSIONS_DIR: Path = Field(default_factory=lambda: Path(os.getenv("SESSIONS_DIR", "./sessions")))

        def get_session_file(self, platform_name: str) -> Path:
            self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            return self.SESSIONS_DIR / f"{platform_name}_storage_state.json"




settings = ScraperSettings()
