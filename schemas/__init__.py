from .base import BaseScrapedItem, SocialPlatform
from .x_twitter import XUserProfile, XTweet, XScrapedFeed
from .instagram import InstagramProfile, InstagramPost, InstagramComment, InstagramScrapedFeed

__all__ = [
    "BaseScrapedItem",
    "SocialPlatform",
    "XUserProfile",
    "XTweet",
    "XScrapedFeed",
    "InstagramProfile",
    "InstagramPost",
    "InstagramComment",
    "InstagramScrapedFeed",
]
