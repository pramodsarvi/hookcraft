from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TargetPlatform(str, Enum):
    X = "x_twitter"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    META_REELS = "meta_reels"


class ScrapedTrendBreakdown(BaseModel):
    """Deep structural analysis of a viral post captured in the Listen loop."""

    model_config = ConfigDict(arbitrary_types_allowed=True, str_strip_whitespace=True)

    trend_id: str
    topic: str = Field(..., description="Core subject or thematic anchor.")
    original_hook: str = Field(..., description="The opening 3-second hook or top tweet sentence.")
    viral_mechanic: str = Field(
        ...,
        description="Core psychological viral trigger (e.g., 'Contrarian Stance', 'Negative Constraint', 'Before-and-After', 'Social Proof').",
    )
    emotional_charge: str = Field(
        ...,
        description="Primary emotional resonance (e.g., 'Awe', 'FOMO', 'Righteous Indignation', 'Desire for Autonomy').",
    )
    linguistic_archetype: str = Field(
        default="Direct, Punchy",
        description="Pacing and sentence structure style.",
    )
    visual_cues: Optional[str] = Field(
        None,
        description="Key visual framing, text layout, or thumbnail aesthetics.",
    )


class DerivedMicroPersona(BaseModel):
    """Hyper-targeted buyer persona derived from the marketing brief and observed audience."""

    persona_id: str
    name: str = Field(..., description="Descriptive archetype name (e.g., 'The Skeptical Optimizer').")
    core_desire: str = Field(..., description="The ultimate transformation or outcome desired.")
    pain_points: List[str] = Field(..., description="Immediate daily friction points.")
    psychological_trigger: str = Field(..., description="What compels them to stop scrolling.")
    vocabulary_register: str = Field(
        default="Professional Tech",
        description="Tone of voice and vernacular (e.g., 'Executive', 'No-BS Founder', 'Pragmatic Dev').",
    )
    primary_objection: str = Field(..., description="Main hesitation to converting.")


class MediaHook(BaseModel):
    """Hook creative specification for video opening or image headline."""

    hook_id: str
    target_persona_id: str
    hook_text: str = Field(..., description="Exact verbatim text spoken or shown in first 3 seconds.")
    hook_type: str = Field(..., description="Curiosity Gap, Contrarian, Problem-First, Data-Shock, Story.")
    visual_scene_description: str = Field(
        ...,
        description="Detailed prompt for video generation or image art director.",
    )
    audio_overlay_cue: str = Field(
        default="Punchy, subtle synth swell",
        description="Music/sound effects timing.",
    )
    safe_zone_compliant: bool = Field(default=True)


class AdCopyVariation(BaseModel):
    """Complete multi-variant ad creative specification."""

    ad_id: str
    persona_id: str
    target_platform: TargetPlatform
    hook: MediaHook
    primary_text: str = Field(..., description="Body caption copy.")
    headline: str = Field(..., description="Bold display headline.")
    call_to_action: str = Field(default="Learn More", description="CTA button text.")
    estimated_ctr_tier: str = Field(default="High", description="Predicted tier based on viral trend alignment.")


class GenerationBatchOutput(BaseModel):
    """Container holding 50 generated hook variations across 5 micro-personas."""

    campaign_name: str
    brief_summary: str
    derived_personas: List[DerivedMicroPersona]
    ad_variations: List[AdCopyVariation]
    total_variations: int = Field(default=50)
    created_at: datetime = Field(default_factory=datetime.utcnow)
