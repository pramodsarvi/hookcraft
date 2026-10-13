from datetime import datetime
import re
from typing import List, Optional
from pydantic import Field, field_validator

from .base import BaseScrapedItem, SocialPlatform
from utils.parsers import clean_text_content, parse_compact_number


class XUserProfile(BaseScrapedItem):
    """Structured entity representing an X (Twitter) user profile."""

    platform: SocialPlatform = Field(default=SocialPlatform.X)
    handle: str = Field(
        ...,
        description="Twitter handle/username without '@' symbol.",
        examples=["elonmusk", "ylecun"],
    )
    display_name: str = Field(
        ...,
        description="Public display name shown on profile.",
    )
    bio: Optional[str] = Field(
        default=None,
        description="User profile biography.",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the account has a verified badge.",
    )
    location: Optional[str] = Field(
        default=None,
        description="User-stated profile location.",
    )
    website: Optional[str] = Field(
        default=None,
        description="External URL attached to profile.",
    )
    joined_date: Optional[str] = Field(
        default=None,
        description="Date joined X (e.g., 'Joined June 2009').",
    )
    followers_count: Optional[int] = Field(
        default=None,
        description="Number of followers.",
    )
    following_count: Optional[int] = Field(
        default=None,
        description="Number of accounts followed.",
    )
    posts_count: Optional[int] = Field(
        default=None,
        description="Total lifetime posts/tweets.",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="URL to user's profile picture.",
    )
    banner_url: Optional[str] = Field(
        default=None,
        description="URL to profile header banner image.",
    )

    @field_validator("handle", mode="before")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        if not v:
            raise ValueError("Handle cannot be empty.")
        clean = v.strip().lstrip("@")
        if not re.match(r"^[A-Za-z0-9_]{1,15}$", clean):
            # Fallback relaxed check if handle contains unusual chars
            return clean.split()[0]
        return clean

    @field_validator("bio", mode="before")
    @classmethod
    def clean_bio_text(cls, v: Optional[str]) -> Optional[str]:
        return clean_text_content(v)

    @field_validator("followers_count", "following_count", "posts_count", mode="before")
    @classmethod
    def parse_counts(cls, v: object) -> Optional[int]:
        return parse_compact_number(v)


class XTweet(BaseScrapedItem):
    """Structured entity representing an individual Tweet / Post on X."""

    platform: SocialPlatform = Field(default=SocialPlatform.X)
    tweet_id: Optional[str] = Field(
        default=None,
        description="Unique tweet status snowflake ID if extractable from URL or DOM.",
    )
    author_handle: str = Field(
        ...,
        description="Handle of the tweet author.",
    )
    author_display_name: Optional[str] = Field(
        default=None,
        description="Display name of the tweet author.",
    )
    tweet_text: str = Field(
        ...,
        description="Main text body of the tweet.",
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 string or human readable timestamp (e.g. '2026-10-13T10:00:00Z', '2h').",
    )
    likes_count: int = Field(
        default=0,
        description="Number of likes/favorites.",
    )
    retweets_count: int = Field(
        default=0,
        description="Number of retweets/reposts.",
    )
    replies_count: int = Field(
        default=0,
        description="Number of replies.",
    )
    quotes_count: int = Field(
        default=0,
        description="Number of quote tweets.",
    )
    views_count: Optional[int] = Field(
        default=None,
        description="Number of views/impressions if available.",
    )
    media_urls: List[str] = Field(
        default_factory=list,
        description="List of attached media URLs (images, videos, cards).",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="List of hashtags mentioned in tweet body.",
    )
    mentions: List[str] = Field(
        default_factory=list,
        description="List of @ handles mentioned in tweet body.",
    )
    is_retweet: bool = Field(
        default=False,
        description="Flag indicating if this tweet is a repost/retweet from another account.",
    )
    is_reply: bool = Field(
        default=False,
        description="Flag indicating if this tweet is replying to another conversation.",
    )
    tweet_url: Optional[str] = Field(
        default=None,
        description="Direct permalink to this tweet.",
    )

    @field_validator("author_handle", mode="before")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        if not v:
            return "unknown"
        return v.strip().lstrip("@")

    @field_validator("tweet_text", mode="before")
    @classmethod
    def clean_tweet_text(cls, v: str) -> str:
        return clean_text_content(v) or ""

    @field_validator(
        "likes_count", "retweets_count", "replies_count", "quotes_count", "views_count",
        mode="before"
    )
    @classmethod
    def parse_metric_counts(cls, v: object) -> int:
        res = parse_compact_number(v)
        return res if res is not None else 0


class XScrapedFeed(BaseScrapedItem):
    """Aggregate model for batch feed scrape outcomes from X."""

    platform: SocialPlatform = Field(default=SocialPlatform.X)
    target_query_or_user: str = Field(
        ...,
        description="Original query, hashtag, or handle scraped.",
    )
    profile: Optional[XUserProfile] = Field(
        default=None,
        description="Profile metadata if scraping a user timeline.",
    )
    tweets: List[XTweet] = Field(
        default_factory=list,
        description="Collection of unique scraped tweets.",
    )
    total_tweets_captured: int = Field(
        default=0,
        description="Total distinct tweets parsed in this session.",
    )
