from datetime import datetime
import re
from typing import List, Optional
from pydantic import Field, field_validator

from .base import BaseScrapedItem, SocialPlatform
from utils.parsers import clean_text_content, parse_compact_number


class InstagramComment(BaseScrapedItem):
    """Sub-model for an individual comment under an Instagram post."""

    platform: SocialPlatform = Field(default=SocialPlatform.INSTAGRAM)
    author_handle: str = Field(
        ...,
        description="Handle of the user who posted the comment.",
    )
    comment_text: str = Field(
        ...,
        description="Text content of the comment.",
    )
    likes_count: int = Field(
        default=0,
        description="Number of likes on this comment.",
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Timestamp string (e.g., '3d', '1w', '2026-10-12').",
    )

    @field_validator("author_handle", mode="before")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        return v.strip().lstrip("@") if v else "unknown"

    @field_validator("comment_text", mode="before")
    @classmethod
    def clean_comment(cls, v: str) -> str:
        return clean_text_content(v) or ""

    @field_validator("likes_count", mode="before")
    @classmethod
    def parse_likes(cls, v: object) -> int:
        res = parse_compact_number(v)
        return res if res is not None else 0


class InstagramProfile(BaseScrapedItem):
    """Structured entity representing an Instagram public profile."""

    platform: SocialPlatform = Field(default=SocialPlatform.INSTAGRAM)
    handle: str = Field(
        ...,
        description="Instagram handle without '@'.",
        examples=["natgeo", "cristiano"],
    )
    full_name: Optional[str] = Field(
        default=None,
        description="Public full name or brand name displayed on profile.",
    )
    bio: Optional[str] = Field(
        default=None,
        description="User biography text, including line breaks.",
    )
    bio_link: Optional[str] = Field(
        default=None,
        description="External clickable link in profile bio.",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the profile has the blue verified badge.",
    )
    is_private: bool = Field(
        default=False,
        description="Whether the profile is marked as private/restricted.",
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
        description="Total lifetime posts.",
    )
    profile_pic_url: Optional[str] = Field(
        default=None,
        description="Direct image CDN URL for avatar.",
    )

    @field_validator("handle", mode="before")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        if not v:
            raise ValueError("Instagram handle cannot be empty.")
        return v.strip().lstrip("@")

    @field_validator("bio", mode="before")
    @classmethod
    def clean_bio(cls, v: Optional[str]) -> Optional[str]:
        return clean_text_content(v)

    @field_validator("followers_count", "following_count", "posts_count", mode="before")
    @classmethod
    def parse_counts(cls, v: object) -> Optional[int]:
        return parse_compact_number(v)


class InstagramPost(BaseScrapedItem):
    """Structured entity representing an individual Instagram Post or Reel."""

    platform: SocialPlatform = Field(default=SocialPlatform.INSTAGRAM)
    shortcode: Optional[str] = Field(
        default=None,
        description="Instagram post shortcode (e.g. 'DBfG39sA7bC' from /p/DBfG39sA7bC/).",
    )
    post_url: Optional[str] = Field(
        default=None,
        description="Canonical URL to the post.",
    )
    author_handle: str = Field(
        ...,
        description="Handle of the post author.",
    )
    caption: Optional[str] = Field(
        default=None,
        description="Caption text accompanying the post.",
    )
    post_type: str = Field(
        default="image",
        description="Detected media type: 'image', 'video', 'carousel', or 'reel'.",
    )
    media_urls: List[str] = Field(
        default_factory=list,
        description="Direct URLs of post images or video thumbnail posters.",
    )
    likes_count: int = Field(
        default=0,
        description="Number of likes.",
    )
    comments_count: int = Field(
        default=0,
        description="Total comment count.",
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Publication date/time string.",
    )
    alt_text: Optional[str] = Field(
        default=None,
        description="Accessibility alt text or VLM vision description of the post image.",
    )
    is_pinned: bool = Field(
        default=False,
        description="Whether this post is pinned to top of profile grid.",
    )
    top_comments: List[InstagramComment] = Field(
        default_factory=list,
        description="Sample or top highlighted comments.",
    )

    @field_validator("author_handle", mode="before")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        return v.strip().lstrip("@") if v else "unknown"

    @field_validator("caption", mode="before")
    @classmethod
    def clean_caption_text(cls, v: Optional[str]) -> Optional[str]:
        return clean_text_content(v)

    @field_validator("likes_count", "comments_count", mode="before")
    @classmethod
    def parse_metrics(cls, v: object) -> int:
        res = parse_compact_number(v)
        return res if res is not None else 0


class InstagramScrapedFeed(BaseScrapedItem):
    """Aggregate model for Instagram profile grid or feed scrape results."""

    platform: SocialPlatform = Field(default=SocialPlatform.INSTAGRAM)
    target_handle: str = Field(
        ...,
        description="Instagram handle targeted in scrape.",
    )
    profile: Optional[InstagramProfile] = Field(
        default=None,
        description="Profile metadata.",
    )
    posts: List[InstagramPost] = Field(
        default_factory=list,
        description="Collection of scraped Instagram posts.",
    )
    total_posts_captured: int = Field(
        default=0,
        description="Total distinct posts parsed in this session.",
    )
