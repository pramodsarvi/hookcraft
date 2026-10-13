from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from generation.schemas import AdCopyVariation, DerivedMicroPersona, TargetPlatform


class TrendIngestionState(TypedDict):
    """Ingestion & Filtration ('Listen' Loop) State."""

    account_id: str
    platform: Literal["x", "instagram"]
    target_query_or_handle: str
    target_count: int
    raw_scraped_items: List[Dict[str, Any]]
    validated_viral_trends: List[Dict[str, Any]]
    rejected_items: List[Dict[str, Any]]
    media_assets: Dict[str, str]
    scroll_cycles: int
    depth_reached_px: int
    status: Literal["init", "scraping", "filtering", "completed", "degraded", "error"]
    error_message: Optional[str]


class MarketingFlywheelMasterState(TypedDict):
    """
    Unified Master State for the complete 4-Phase Flywheel:
    1. Listen (Scraping + Jev Viral Filtration)
    2. Create (Brief-to-Hook Multiplexing + Canvas Safety QA)
    3. Distribute (Headless Ad Staging)
    4. Optimize (Kill & Scale Automated Conversion Feedback)
    """

    campaign_name: str
    marketing_brief_md: str
    target_platform: TargetPlatform
    account_id: str
    target_handle_or_query: str

    # Listen loop outputs
    validated_viral_trends: List[Dict[str, Any]]
    intercepted_media_files: Dict[str, str]

    # Create loop outputs
    derived_personas: List[Dict[str, Any]]
    generated_ad_variations: List[Dict[str, Any]]
    canvas_qa_passed_count: int

    # Distribute loop outputs
    staged_ad_sets: List[Dict[str, Any]]

    # Optimize loop outputs
    killed_ad_ids: List[str]
    scaled_ad_ids: List[str]
    spawned_winner_variants: List[Dict[str, Any]]

    # Workflow lifecycle
    current_phase: Literal["listen", "create", "distribute", "optimize", "complete", "failed"]
    status_summary: str
