import logging
from typing import Any, Dict, List, Optional, Set
try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore
from schemas.x_twitter import XTweet
from schemas.instagram import InstagramPost

logger = logging.getLogger("DOMExtractor")


class ExtractionBuffer:
    """
    Maintains a deduplicated collection of scraped items to counter
    DOM element recycling (virtualized list unmounting) during infinite scroll.
    """

    def __init__(self, target_count: int = 20, max_stagnant_scrolls: int = 5):
        self.target_count = target_count
        self.max_stagnant_scrolls = max_stagnant_scrolls
        self.seen_identifiers: Set[str] = set()
        self.items: List[Any] = []
        self.stagnant_scroll_count = 0

    def add_items(self, new_items: List[Any], id_key: str) -> int:
        """Adds unique items to buffer. Returns count of newly discovered items."""
        added = 0
        for item in new_items:
            ident = getattr(item, id_key, None) or item.source_url or str(hash(str(item)))
            if ident and ident not in self.seen_identifiers:
                self.seen_identifiers.add(ident)
                self.items.append(item)
                added += 1

        if added == 0:
            self.stagnant_scroll_count += 1
        else:
            self.stagnant_scroll_count = 0

        return added

    @property
    def is_finished(self) -> bool:
        """Determines if target item threshold reached or feed is exhausted."""
        if len(self.items) >= self.target_count:
            return True
        if self.stagnant_scroll_count >= self.max_stagnant_scrolls:
            logger.info("Infinite scroll feed exhausted: no new posts after %d attempts.", self.max_stagnant_scrolls)
            return True
        return False


class DOMExtractor:
    """
    Resilient DOM extractor that uses accessibility attributes, semantic HTML tags,
    and relative structural trees instead of randomized or hashed CSS class names.
    """

    @staticmethod
    async def extract_visible_tweets(page: Page) -> List[XTweet]:
        """
        Extracts currently rendered tweets from the DOM using stable
        data-testid and aria accessibility attributes.
        """
        # Execute robust JavaScript extraction inside the browser page
        raw_tweets: List[Dict[str, Any]] = await page.evaluate("""
            () => {
                const results = [];
                // Locate tweets via stable accessibility selector data-testid="tweet"
                const tweetNodes = document.querySelectorAll('article[data-testid="tweet"]');

                tweetNodes.forEach(node => {
                    try {
                        // 1. Author and handle
                        const userBlock = node.querySelector('div[data-testid="User-Name"]');
                        let authorName = '';
                        let handle = '';
                        if (userBlock) {
                            const links = userBlock.querySelectorAll('a');
                            if (links.length > 0) {
                                authorName = links[0].innerText.split('\\n')[0].trim();
                            }
                            const handleMatch = userBlock.innerText.match(/@([A-Za-z0-9_]+)/);
                            if (handleMatch) {
                                handle = handleMatch[1];
                            }
                        }

                        // 2. Tweet Text (data-testid="tweetText")
                        const textNode = node.querySelector('div[data-testid="tweetText"]');
                        const tweetText = textNode ? textNode.innerText.trim() : '';

                        // 3. Timestamp & Permalinks
                        const timeElem = node.querySelector('time');
                        const timestamp = timeElem ? timeElem.getAttribute('datetime') : null;
                        let tweetUrl = null;
                        let tweetId = null;
                        if (timeElem) {
                            const permalink = timeElem.closest('a');
                            if (permalink) {
                                tweetUrl = permalink.href;
                                const idMatch = tweetUrl.match(/status\\/(\\d+)/);
                                if (idMatch) tweetId = idMatch[1];
                            }
                        }

                        // 4. Metrics via aria-label or role="group"
                        const group = node.querySelector('div[role="group"]');
                        let replies = '0', retweets = '0', likes = '0', views = null;

                        if (group) {
                            // Extract numbers from reply/retweet/like testid wrappers
                            const replyElem = group.querySelector('div[data-testid="reply"]');
                            const retweetElem = group.querySelector('div[data-testid="retweet"], div[data-testid="unretweet"]');
                            const likeElem = group.querySelector('div[data-testid="like"], div[data-testid="unlike"]');
                            const viewElem = group.querySelector('a[href*="/analytics"]');

                            if (replyElem) replies = replyElem.innerText || '0';
                            if (retweetElem) retweets = retweetElem.innerText || '0';
                            if (likeElem) likes = likeElem.innerText || '0';
                            if (viewElem) views = viewElem.innerText || null;
                        }

                        // 5. Media URLs
                        const mediaUrls = [];
                        const images = node.querySelectorAll('div[data-testid="tweetPhoto"] img');
                        images.forEach(img => {
                            if (img.src && !img.src.includes('profile_images')) {
                                mediaUrls.push(img.src);
                            }
                        });

                        // 6. Repost / reply flags
                        const isRetweet = node.innerText.includes('Reposted') || node.innerText.includes('Retweeted');

                        if (handle || tweetText) {
                            results.push({
                                tweet_id: tweetId,
                                author_handle: handle,
                                author_display_name: authorName,
                                tweet_text: tweetText,
                                timestamp: timestamp,
                                likes_count: likes,
                                retweets_count: retweets,
                                replies_count: replies,
                                views_count: views,
                                media_urls: mediaUrls,
                                tweet_url: tweetUrl,
                                is_retweet: isRetweet,
                            });
                        }
                    } catch (e) {
                        // Skip corrupted DOM nodes silently
                    }
                });

                return results;
            }
        """)

        tweets = []
        for raw in raw_tweets:
            try:
                tweet = XTweet(**raw)
                tweets.append(tweet)
            except Exception as e:
                logger.debug("Failed validating raw tweet item: %s", e)
        return tweets

    @staticmethod
    async def extract_visible_instagram_posts(page: Page, target_handle: str) -> List[InstagramPost]:
        """
        Extracts visible Instagram posts from profile grid or feed using
        semantic link tags (href containing /p/ or /reel/) and accessibility alt texts.
        """
        raw_posts: List[Dict[str, Any]] = await page.evaluate("""
            (handle) => {
                const results = [];
                // Instagram profile post grid links always contain /p/ or /reel/
                const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');

                links.forEach(a => {
                    try {
                        const href = a.href;
                        const match = href.match(/\\/(p|reel)\\/([A-Za-z0-9_-]+)/);
                        if (!match) return;

                        const postType = match[1] === 'reel' ? 'reel' : 'image';
                        const shortcode = match[2];

                        // Find nested image for accessibility alt text and image source
                        const img = a.querySelector('img');
                        let altText = null;
                        let imgSrc = null;
                        if (img) {
                            altText = img.getAttribute('alt') || null;
                            imgSrc = img.src || null;
                        }

                        results.push({
                            shortcode: shortcode,
                            post_url: href,
                            author_handle: handle,
                            caption: altText,
                            post_type: postType,
                            media_urls: imgSrc ? [imgSrc] : [],
                            alt_text: altText,
                            likes_count: 0,
                            comments_count: 0,
                        });
                    } catch (e) {}
                });

                return results;
            }
        """, target_handle)

        posts = []
        for raw in raw_posts:
            try:
                post = InstagramPost(**raw)
                posts.append(post)
            except Exception as e:
                logger.debug("Failed validating raw instagram post: %s", e)
        return posts
