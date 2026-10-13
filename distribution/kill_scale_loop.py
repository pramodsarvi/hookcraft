import logging
import random
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from generation.schemas import AdCopyVariation, MediaHook, TargetPlatform

logger = logging.getLogger("KillScaleLoop")


class AdPerformanceMetric(BaseModel):
    """Real-time performance snapshot for an active ad variation."""

    ad_id: str
    impressions: int = Field(..., description="Total ad impressions.")
    clicks: int = Field(..., description="Link clicks.")
    spend: float = Field(..., description="Ad spend in USD.")
    three_second_views: int = Field(..., description="3-second video hook views.")
    conversions: int = Field(default=0, description="Purchases or lead conversions.")
    revenue: float = Field(default=0.0, description="Direct attributed revenue.")

    @property
    def ctr(self) -> float:
        """Click-Through Rate (%)."""
        return (self.clicks / self.impressions * 100.0) if self.impressions > 0 else 0.0

    @property
    def hook_rate(self) -> float:
        """3-Second Hook Retention Rate (%)."""
        return (self.three_second_views / self.impressions * 100.0) if self.impressions > 0 else 0.0

    @property
    def cpc(self) -> float:
        """Cost Per Click ($)."""
        return (self.spend / self.clicks) if self.clicks > 0 else 999.0

    @property
    def roas(self) -> float:
        """Return on Ad Spend (x)."""
        return (self.revenue / self.spend) if self.spend > 0 else 0.0


class KillScaleDecision(BaseModel):
    """Automated optimization decision for a specific creative."""

    ad_id: str
    action: str = Field(..., description="'KILL_PAUSE', 'SCALE_BUDGET', 'MAINTAIN'")
    reason: str
    budget_delta_pct: float = Field(default=0.0)
    spawned_variants: List[AdCopyVariation] = Field(default_factory=list)


class KillScaleCycleReport(BaseModel):
    """Aggregate summary of an optimization pass."""

    total_evaluated: int
    killed_count: int
    scaled_count: int
    maintained_count: int
    total_spawned_variants: int
    decisions: List[KillScaleDecision]


class KillScaleOptimizer:
    """
    Continuous 'Kill and Scale' Conversion Performance Loop.
    Evaluates real-time ad performance against strict floor thresholds:
    - KILLS underperforming creatives (CTR < 0.85%, Hook Rate < 18%, CPC > $2.50).
    - SCALES budget on top performers (CTR > 2.4%, ROAS > 2.8x) and spawns 10 localized variants.
    """

    def __init__(
        self,
        min_ctr_floor: float = 0.85,
        min_hook_rate_floor: float = 18.0,
        max_cpc_ceiling: float = 2.50,
        scale_ctr_threshold: float = 2.40,
        scale_roas_threshold: float = 2.80,
    ):
        self.min_ctr = min_ctr_floor
        self.min_hook = min_hook_rate_floor
        self.max_cpc = max_cpc_ceiling
        self.scale_ctr = scale_ctr_threshold
        self.scale_roas = scale_roas_threshold

    def evaluate_creative(
        self,
        metric: AdPerformanceMetric,
        ad_variation: AdCopyVariation,
    ) -> KillScaleDecision:
        """Applies algorithmic decision logic to an individual ad."""
        # Minimum sample size of 500 impressions required before making a kill decision
        if metric.impressions < 500:
            return KillScaleDecision(
                ad_id=metric.ad_id,
                action="MAINTAIN",
                reason=f"Gathering initial statistical confidence ({metric.impressions}/500 impressions).",
            )

        # -------------------------------------------------------------
        # KILL / PAUSE CONDITIONS
        # -------------------------------------------------------------
        kill_reasons = []
        if metric.ctr < self.min_ctr:
            kill_reasons.append(f"CTR ({metric.ctr:.2f}%) below floor ({self.min_ctr}%)")
        if metric.hook_rate < self.min_hook:
            kill_reasons.append(f"Hook Rate ({metric.hook_rate:.1f}%) below retention floor ({self.min_hook}%)")
        if metric.cpc > self.max_cpc:
            kill_reasons.append(f"CPC (${metric.cpc:.2f}) above ceiling (${self.max_cpc})")

        if kill_reasons:
            logger.info("❌ [KILL ACTION] Pausing creative [%s]: %s", metric.ad_id, "; ".join(kill_reasons))
            return KillScaleDecision(
                ad_id=metric.ad_id,
                action="KILL_PAUSE",
                reason="; ".join(kill_reasons),
                budget_delta_pct=-100.0,
            )

        # -------------------------------------------------------------
        # SCALE & SPAWN CONDITIONS
        # -------------------------------------------------------------
        if metric.ctr >= self.scale_ctr and (metric.roas >= self.scale_roas or metric.conversions >= 5):
            logger.info("🚀 [SCALE ACTION] Winner detected [%s]! Scaling budget +35%% and spawning 10 variants.", metric.ad_id)
            spawned = self._spawn_localized_variants(ad_variation, metric)
            return KillScaleDecision(
                ad_id=metric.ad_id,
                action="SCALE_BUDGET",
                reason=f"Top performer: CTR={metric.ctr:.2f}%, ROAS={metric.roas:.1f}x. Budget increased +35%.",
                budget_delta_pct=35.0,
                spawned_variants=spawned,
            )

        return KillScaleDecision(
            ad_id=metric.ad_id,
            action="MAINTAIN",
            reason="Performance within acceptable target margins.",
        )

    def _spawn_localized_variants(
        self,
        winning_ad: AdCopyVariation,
        metric: AdPerformanceMetric,
    ) -> List[AdCopyVariation]:
        """
        Extracts the winning stylistic parameters and dynamically spawns
        10 new iterative variants (modifying regional angles, speed cues, and hook framing).
        """
        variants = []
        winning_hook = winning_ad.hook.hook_text
        regional_cues = ["US Founders", "UK Tech Leads", "EU Remote Teams", "APAC High-Growth", "Global"]
        angle_modifiers = [
            "Why everybody is switching:",
            "The exact blueprint:",
            "The 60-second walkthrough:",
            "Before your competitors notice:",
            "Here is the proof:",
        ]

        var_idx = 1
        for region in regional_cues:
            for angle in angle_modifiers[:2]:
                spawned_id = f"{winning_ad.ad_id}_spawn_{var_idx:02d}"
                new_hook_text = f"[{region}] {angle} {winning_hook}"

                new_media_hook = MediaHook(
                    hook_id=f"hook_{spawned_id}",
                    target_persona_id=winning_ad.persona_id,
                    hook_text=new_hook_text,
                    hook_type=f"Winner Iteration ({winning_ad.hook.hook_type})",
                    visual_scene_description=f"Direct localized iteration of winning creative {winning_ad.ad_id}. Region: {region}.",
                    audio_overlay_cue="High-tempo winner sound design",
                )

                new_variation = AdCopyVariation(
                    ad_id=spawned_id,
                    persona_id=winning_ad.persona_id,
                    target_platform=winning_ad.target_platform,
                    hook=new_media_hook,
                    primary_text=f"{new_hook_text}\n\n{winning_ad.primary_text}",
                    headline=f"{winning_ad.headline} - {region}",
                    call_to_action=winning_ad.call_to_action,
                    estimated_ctr_tier="High (Winner Lineage)",
                )
                variants.append(new_variation)
                var_idx += 1

        return variants

    def run_optimization_cycle(
        self,
        active_variations: Dict[str, AdCopyVariation],
        metrics: List[AdPerformanceMetric],
    ) -> KillScaleCycleReport:
        """Executes full optimization evaluation cycle across all live ads."""
        decisions: List[KillScaleDecision] = []
        killed = 0
        scaled = 0
        maintained = 0
        total_spawned = 0

        for metric in metrics:
            ad_variation = active_variations.get(metric.ad_id)
            if not ad_variation:
                continue

            decision = self.evaluate_creative(metric, ad_variation)
            decisions.append(decision)

            if decision.action == "KILL_PAUSE":
                killed += 1
            elif decision.action == "SCALE_BUDGET":
                scaled += 1
                total_spawned += len(decision.spawned_variants)
            else:
                maintained += 1

        return KillScaleCycleReport(
            total_evaluated=len(decisions),
            killed_count=killed,
            scaled_count=scaled,
            maintained_count=maintained,
            total_spawned_variants=total_spawned,
            decisions=decisions,
        )
