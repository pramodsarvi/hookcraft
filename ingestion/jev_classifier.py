import logging
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("JevValidationEngine")


class JevClassificationResult(BaseModel):
    """Sub-100ms classification matrix output."""

    item_id: str
    is_approved: bool = Field(..., description="Whether the item passes all marketing thresholds.")
    rejection_reason: Optional[str] = Field(None, description="Reason if rejected.")
    brand_safe: bool = Field(default=True)
    brand_safety_score: float = Field(default=1.0)
    is_viral: bool = Field(default=False)
    virality_score: float = Field(default=0.0)
    is_ai_slop: bool = Field(default=False)
    slop_score: float = Field(default=0.0)
    latency_ms: float = Field(default=0.0)


class JevValidationEngine:
    """
    High-Velocity Validation Engine (Jev AI).
    Routes text, transcripts, and metadata through a prompt-less, sub-100ms
    classification matrix to instantly filter out 'Brand Unsafe', 'Low Engagement',
    or 'AI Slop' content before downstream extraction and creative synthesis.
    """

    # High-risk brand safety lexical matrices
    UNSAFE_PATTERNS = [
        r"\b(scam|rugpull|giveaway\s+dm|crypto\s+airdrop|free\s+tokens)\b",
        r"\b(casino|betting|slots|gambling|18\+|onlyfans|nsfw)\b",
        r"\b(hate|racist|terror|violence|kill|bomb|attack)\b",
    ]

    # Heuristic signature of repetitive "AI Slop" & generic engagement bait
    SLOP_PATTERNS = [
        r"thread\s*🧵",
        r"here\s+are\s+\d+\s+ai\s+tools\s+that\s+will",
        r"bookmark\s+this\s+before\s+it\s+gets\s+deleted",
        r"99%\s+of\s+people\s+don't\s+know\s+this",
        r"ai\s+won't\s+replace\s+you,\s+a\s+person\s+using\s+ai\s+will",
        r"comment\s+['\"][a-z]+['\"]\s+and\s+i'll\s+dm\s+you",
        r"secret\s+websites\s+that\s+feel\s+illegal\s+to\s+know",
    ]

    def __init__(self, min_virality_score: float = 0.65, max_slop_score: float = 0.40):
        self.min_virality_score = min_virality_score
        self.max_slop_score = max_slop_score
        self._init_client()

    def _init_client(self) -> None:
        """
        Initializes TypeSafe Jev AI client (System One non-autoregressive decision model)
        if typesafe-sdk or langchain-typesafe is installed and TYPESAFE_API_KEY is configured.
        """
        try:
            from typesafe_sdk import TypeSafeClient, Noul, Score
            self.client = TypeSafeClient()
            self.Noul = Noul
            self.Score = Score
            self.use_native_jev = True
            logger.info("Native TypeSafe Jev 'System One' Decision Engine loaded.")
        except Exception:
            self.client = None
            self.Noul = None
            self.Score = None
            self.use_native_jev = False
            from .laya_engine import LayaDecisionEngine
            self.laya = LayaDecisionEngine(min_virality_score=self.min_virality_score, max_slop_score=self.max_slop_score)
            logger.info("Using Laya (Open-Source Apache 2.0 System-1 Decision Model, $0.00).")


    def classify_item(
        self,
        item_id: str,
        text: str,
        likes: int,
        shares_or_retweets: int,
        views: Optional[int] = None,
        comments: int = 0,
    ) -> JevClassificationResult:
        """
        Executes sub-100ms matrix evaluation:
        1. If TypeSafe Jev SDK is active: dispatches a non-autoregressive System One request.
        2. Fallback: runs the local zero-overhead non-autoregressive decision matrix.
        """
        start_ns = time.perf_counter_ns()
        clean_text = text.lower().strip()

        # If live TypeSafe Jev client is connected
        if self.use_native_jev and self.client:
            try:
                response = self.client.system_one(
                    state=f"Text: {text} | Engagement: {likes} likes, {shares_or_retweets} reposts, {comments} comments",
                    questions={
                        "is_brand_safe": self.Noul(instructions="Is this content brand-safe, devoid of hate speech, scams, NSFW, or crypto spam?"),
                        "is_ai_slop": self.Noul(instructions="Is this repetitive AI-generated spam, engagement bait, or low-effort template content?"),
                        "virality_score": self.Score(instructions="Score viral momentum and high engagement velocity from 0 to 1."),
                    },
                )
                brand_safe = response.nouls["is_brand_safe"].noul > 0.70
                is_ai_slop = response.nouls["is_ai_slop"].noul > 0.45
                virality_score = float(response.scores["virality_score"].score)
                is_viral = virality_score >= self.min_virality_score
                brand_safety_score = float(response.nouls["is_brand_safe"].noul)
                slop_score = float(response.nouls["is_ai_slop"].noul)

                is_approved = brand_safe and not is_ai_slop and is_viral
                rejection_reason = None
                if not brand_safe: rejection_reason = "Flagged: Brand Unsafe Content (Jev Noul)"
                elif is_ai_slop: rejection_reason = "Flagged: AI Slop / Engagement Bait (Jev Noul)"
                elif not is_viral: rejection_reason = f"Rejected: Low Virality Score ({virality_score:.2f} < {self.min_virality_score})"

                elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                return JevClassificationResult(
                    item_id=item_id, is_approved=is_approved, rejection_reason=rejection_reason,
                    brand_safe=brand_safe, brand_safety_score=brand_safety_score,
                    is_viral=is_viral, virality_score=virality_score,
                    is_ai_slop=is_ai_slop, slop_score=slop_score, latency_ms=elapsed_ms,
                )
            except Exception as e:
                logger.warning("Native Jev API call failed (%s); reverting to local System One matrix.", e)

        # If Laya open-source decision engine is active ($0.00)
        if hasattr(self, "laya") and self.laya:
            laya_res = self.laya.evaluate(
                item_id=item_id, text=text, likes=likes,
                shares=shares_or_retweets, views=views, comments=comments
            )
            return JevClassificationResult(
                item_id=item_id,
                is_approved=laya_res.is_approved,
                rejection_reason=laya_res.rejection_reason,
                brand_safe=laya_res.brand_safe,
                brand_safety_score=laya_res.brand_safety_score,
                is_viral=laya_res.is_viral,
                virality_score=laya_res.virality_score,
                is_ai_slop=laya_res.is_ai_slop,
                slop_score=laya_res.slop_score,
                latency_ms=laya_res.latency_ms,
            )

        # -------------------------------------------------------------
        # Embedded System One Non-Autoregressive Decision Matrix
        # -------------------------------------------------------------
        brand_safe = True
        brand_safety_score = 1.0


        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, clean_text, re.IGNORECASE):
                brand_safe = False
                brand_safety_score = 0.05
                break

        # -------------------------------------------------------------
        # 2. AI Slop Index Evaluation
        # -------------------------------------------------------------
        slop_score = 0.0
        matches = sum(1 for p in self.SLOP_PATTERNS if re.search(p, clean_text, re.IGNORECASE))
        if matches > 0:
            slop_score = min(1.0, 0.4 + matches * 0.3)
        # Check emoji density (typical slop has excessive arrows/fingers/robots)
        emoji_count = len(re.findall(r"[\U00010000-\U0010ffff]", text))
        if emoji_count > 8:
            slop_score = min(1.0, slop_score + 0.35)

        is_ai_slop = slop_score > self.max_slop_score

        # -------------------------------------------------------------
        # 3. Virality & Velocity Score
        # -------------------------------------------------------------
        # Engagement velocity weighting: Shares/RTs weighted 3x, Comments 2x, Likes 1x
        virality_score = 0.0
        if views and views > 0:
            # Conversion engagement rate relative to impressions
            engagement_ratio = (likes + (shares_or_retweets * 3) + (comments * 2)) / views
            virality_score = min(1.0, engagement_ratio * 25.0)
        else:
            # Absolute metric scale
            if likes > 5000 or shares_or_retweets > 500:
                virality_score = 0.90
            elif likes > 1000 or shares_or_retweets > 100:
                virality_score = 0.75
            elif likes > 200:
                virality_score = 0.50
            else:
                virality_score = 0.20

        is_viral = virality_score >= self.min_virality_score

        # -------------------------------------------------------------
        # Decision Matrix Compilation
        # -------------------------------------------------------------
        is_approved = True
        rejection_reason = None

        if not brand_safe:
            is_approved = False
            rejection_reason = "Flagged: Brand Unsafe Content"
        elif is_ai_slop:
            is_approved = False
            rejection_reason = "Flagged: AI Slop / Engagement Bait"
        elif not is_viral:
            is_approved = False
            rejection_reason = f"Rejected: Low Virality Score ({virality_score:.2f} < {self.min_virality_score})"

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        result = JevClassificationResult(
            item_id=item_id,
            is_approved=is_approved,
            rejection_reason=rejection_reason,
            brand_safe=brand_safe,
            brand_safety_score=brand_safety_score,
            is_viral=is_viral,
            virality_score=virality_score,
            is_ai_slop=is_ai_slop,
            slop_score=slop_score,
            latency_ms=elapsed_ms,
        )

        logger.debug("Jev matrix evaluation for [%s] finished in %.2f ms -> Approved: %s", item_id, elapsed_ms, is_approved)
        return result
