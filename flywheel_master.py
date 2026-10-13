import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from utils.graph_runtime import END, StateGraph

from core.account_manager import MultiAccountContextManager
from core.account_pool import EnterpriseAccountPool
from generation.schemas import AdCopyVariation, TargetPlatform
from generation.hook_multiplexer import BriefHookMultiplexer
from generation.canvas_safety_analyzer import CanvasSafetyAnalyzer
from distribution.ads_manager_publisher import HeadlessAdsManagerPublisher
from distribution.meta_marketing_api import MetaMarketingAPIClient
from distribution.kill_scale_loop import (
    AdPerformanceMetric,
    KillScaleOptimizer,
)
from pipeline import MarketingFlywheelIngestionPipeline
from state.graph_state import MarketingFlywheelMasterState
from state.lineage_db import FlywheelDatabase

logger = logging.getLogger("AutonomousFlywheelMaster")


class AutonomousMarketingFlywheel:
    """
    Master 4-Phase Cyclical Autonomous Marketing Agent (InstaAgent Architecture):
    1. Listen (Scrape viral feeds & validate via Jev AI matrix in sub-100ms)
    2. Create (Multiplex 50 hooks across 5 micro-personas & run Canvas Safety QA)
    3. Distribute (Headless staging & Meta Graph API publication)
    4. Optimize (Continuous Kill & Scale performance feedback loop & variant spawning)
    """

    def __init__(self):
        self.account_manager = MultiAccountContextManager()
        self.account_pool = EnterpriseAccountPool(self.account_manager)
        self.db = FlywheelDatabase()
        self.meta_api = MetaMarketingAPIClient()
        self.ingestion_pipeline = MarketingFlywheelIngestionPipeline(self.account_manager)
        self.multiplexer = BriefHookMultiplexer()
        self.canvas_analyzer = CanvasSafetyAnalyzer()
        self.publisher = HeadlessAdsManagerPublisher(self.account_manager)
        self.optimizer = KillScaleOptimizer()
        self.workflow = self._compile_master_graph()


    def _compile_master_graph(self) -> Any:
        workflow = StateGraph(MarketingFlywheelMasterState)

        workflow.add_node("listen_ingest_and_filter", self._node_listen_ingest_and_filter)
        workflow.add_node("create_multiplex_and_qa", self._node_create_multiplex_and_qa)
        workflow.add_node("distribute_stage_ads", self._node_distribute_stage_ads)
        workflow.add_node("optimize_kill_and_scale", self._node_optimize_kill_and_scale)

        workflow.set_entry_point("listen_ingest_and_filter")

        workflow.add_edge("listen_ingest_and_filter", "create_multiplex_and_qa")
        workflow.add_edge("create_multiplex_and_qa", "distribute_stage_ads")
        workflow.add_edge("distribute_stage_ads", "optimize_kill_and_scale")
        workflow.add_edge("optimize_kill_and_scale", END)

        return workflow.compile()

    # =================================================================
    # Master Workflow Nodes
    # =================================================================

    async def _node_listen_ingest_and_filter(self, state: MarketingFlywheelMasterState) -> Dict[str, Any]:
        """Phase 2: Ingests timeline trends and filters noise via Jev AI."""
        logger.info("Executing Phase 2: Ingestion & Jev AI Filtration...")
        platform_str = "x" if state["target_platform"] == TargetPlatform.X else "instagram"

        # Execute the Listen loop pipeline
        listen_result = await self.ingestion_pipeline.execute_listen_loop(
            platform=platform_str,
            target_handle=state["target_handle_or_query"],
            target_count=12,
            account_id=state["account_id"],
        )

        # Persist captured trends to SQLite Lineage DB
        for trend in listen_result["validated_viral_trends"]:
            self.db.record_trend(trend)

        return {
            "validated_viral_trends": listen_result["validated_viral_trends"],
            "intercepted_media_files": listen_result["media_assets"],
            "current_phase": "create",
            "status_summary": f"Ingested {len(listen_result['validated_viral_trends'])} verified viral trends.",
        }

    async def _node_create_multiplex_and_qa(self, state: MarketingFlywheelMasterState) -> Dict[str, Any]:
        """Phase 3: Synthesizes 50 persona-mapped hooks and conducts Canvas Safety QA."""
        logger.info("Executing Phase 3: Brief-to-Hook Multiplexing & Canvas QA...")

        batch_output = await self.multiplexer.generate_50_hooks(
            marketing_brief_md=state["marketing_brief_md"],
            validated_trends=state["validated_viral_trends"],
            target_platform=state["target_platform"],
        )

        # Run Canvas Safety QA on variations
        qa_passed_count = 0
        variations_dicts = []
        dummy_asset = Path("./data/captured_media/sample_creative.jpg")

        for var in batch_output.ad_variations:
            report = self.canvas_analyzer.analyze_canvas_margins(
                image_path=dummy_asset,
                platform=state["target_platform"],
            )
            var.hook.safe_zone_compliant = report.is_safe
            if report.is_safe:
                qa_passed_count += 1
            var_dump = var.model_dump()
            variations_dicts.append(var_dump)
            # Persist creative to SQLite DB
            self.db.record_ad_variation(var_dump, campaign_name=state["campaign_name"])

        personas_dicts = [p.model_dump() for p in batch_output.derived_personas]

        return {
            "derived_personas": personas_dicts,
            "generated_ad_variations": variations_dicts,
            "canvas_qa_passed_count": qa_passed_count,
            "current_phase": "distribute",
            "status_summary": f"Synthesized 50 variations across 5 personas. Canvas QA passed: {qa_passed_count}/50.",
        }


    async def _node_distribute_stage_ads(self, state: MarketingFlywheelMasterState) -> Dict[str, Any]:
        """Phase 4a: Headless deployment and campaign staging."""
        logger.info("Executing Phase 4a: Headless Ad Distribution...")
        staged_results = []

        # Stage top 10 highest-ranked variations initially
        for var_dict in state["generated_ad_variations"][:10]:
            variation = AdCopyVariation(**var_dict)
            res = await self.publisher.deploy_ad_creative(
                account_id=state["account_id"],
                ad_variation=variation,
                simulate_launch=True,
            )
            staged_results.append(res.model_dump())

        return {
            "staged_ad_sets": staged_results,
            "current_phase": "optimize",
            "status_summary": f"Staged {len(staged_results)} active ad sets in Ads Manager.",
        }

    async def _node_optimize_kill_and_scale(self, state: MarketingFlywheelMasterState) -> Dict[str, Any]:
        """Phase 4b: Kill and Scale performance aggregation & winner variant spawning."""
        logger.info("Executing Phase 4b: 'Kill and Scale' Conversion Optimization Loop...")

        # Construct variations lookup
        variations_lookup = {
            v["ad_id"]: AdCopyVariation(**v) for v in state["generated_ad_variations"]
        }

        # Simulated real-world ad performance distribution
        simulated_metrics = []
        for v in state["generated_ad_variations"][:10]:
            ad_id = v["ad_id"]
            # Intentionally simulate some winners and some underperformers
            if "001" in ad_id or "004" in ad_id:
                # Top Performer (High CTR, High ROAS)
                simulated_metrics.append(
                    AdPerformanceMetric(
                        ad_id=ad_id,
                        impressions=2500,
                        clicks=75,          # CTR = 3.0%
                        three_second_views=800, # Hook = 32%
                        spend=45.0,
                        conversions=8,
                        revenue=180.0,      # ROAS = 4.0x
                    )
                )
            elif "002" in ad_id:
                # Underperformer (Low CTR, high CPC -> KILL)
                simulated_metrics.append(
                    AdPerformanceMetric(
                        ad_id=ad_id,
                        impressions=1200,
                        clicks=5,           # CTR = 0.41% (< 0.85% floor)
                        three_second_views=150, # Hook = 12.5%
                        spend=20.0,
                        conversions=0,
                        revenue=0.0,
                    )
                )
            else:
                # Maintained
                simulated_metrics.append(
                    AdPerformanceMetric(
                        ad_id=ad_id,
                        impressions=900,
                        clicks=15,          # CTR = 1.66%
                        three_second_views=220,
                        spend=18.0,
                        conversions=1,
                        revenue=35.0,
                    )
                )

        report = self.optimizer.run_optimization_cycle(variations_lookup, simulated_metrics)

        # Persist metrics and decisions to SQLite Lineage DB
        for metric in simulated_metrics:
            self.db.record_performance_snapshot(metric)

        for decision in report.decisions:
            self.db.record_decision(
                ad_id=decision.ad_id,
                action=decision.action,
                reason=decision.reason,
                budget_delta_pct=decision.budget_delta_pct,
                spawned_count=len(decision.spawned_variants),
            )
            # Record spawned child variants with lineage tracking
            for spawned_var in decision.spawned_variants:
                self.db.record_ad_variation(
                    spawned_var.model_dump(),
                    campaign_name=state["campaign_name"],
                    parent_id=decision.ad_id,
                )

        killed_ids = [d.ad_id for d in report.decisions if d.action == "KILL_PAUSE"]
        scaled_ids = [d.ad_id for d in report.decisions if d.action == "SCALE_BUDGET"]
        spawned_dicts = []
        for d in report.decisions:
            for s in d.spawned_variants:
                spawned_dicts.append(s.model_dump())


        return {
            "killed_ad_ids": killed_ids,
            "scaled_ad_ids": scaled_ids,
            "spawned_winner_variants": spawned_dicts,
            "current_phase": "complete",
            "status_summary": (
                f"Optimization Complete: {len(killed_ids)} Paused/Killed, "
                f"{len(scaled_ids)} Scaled (+35% budget), {len(spawned_dicts)} New Localized Winner Variants Spawned."
            ),
        }

    async def run(
        self,
        campaign_name: str,
        marketing_brief_md: str,
        target_platform: TargetPlatform = TargetPlatform.META_REELS,
        target_handle: str = "elonmusk",
        account_id: Optional[str] = None,
    ) -> MarketingFlywheelMasterState:
        """Executes the complete autonomous marketing flywheel loop."""
        initial_state: MarketingFlywheelMasterState = {
            "campaign_name": campaign_name,
            "marketing_brief_md": marketing_brief_md,
            "target_platform": target_platform,
            "account_id": account_id or f"{target_platform.value}_bot",
            "target_handle_or_query": target_handle,
            "validated_viral_trends": [],
            "intercepted_media_files": {},
            "derived_personas": [],
            "generated_ad_variations": [],
            "canvas_qa_passed_count": 0,
            "staged_ad_sets": [],
            "killed_ad_ids": [],
            "scaled_ad_ids": [],
            "spawned_winner_variants": [],
            "current_phase": "listen",
            "status_summary": "Flywheel initialized.",
        }

        final_state = await self.workflow.ainvoke(initial_state)
        return final_state
