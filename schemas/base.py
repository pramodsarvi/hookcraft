from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SocialPlatform(str, Enum):
    X = "x_twitter"
    INSTAGRAM = "instagram"


class BaseScrapedItem(BaseModel):
    """Base model for all scraped social media data entities."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow",
    )

    platform: SocialPlatform = Field(
        ...,
        description="Target social platform.",
    )
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp indicating when the record was extracted.",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Direct URL from which the entity was extracted.",
    )
    raw_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw unstructured attributes or OCR vision data captured during extraction.",
        exclude=True,
    )
