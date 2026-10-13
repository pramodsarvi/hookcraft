import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("LineageDatabase")


class FlywheelDatabase:
    """
    Persistent SQLite storage for campaign lineage, creative variants,
    performance metrics, and kill/scale decision audits.
    Guarantees state survival across process restarts.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("./data/flywheel.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Scraped Viral Trends Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS viral_trends (
                    trend_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    topic TEXT,
                    raw_text TEXT,
                    likes_count INTEGER,
                    retweets_or_shares INTEGER,
                    virality_score REAL,
                    is_brand_safe INTEGER,
                    is_ai_slop INTEGER,
                    jev_latency_ms REAL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Generated Ad Creatives & Persona Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ad_creatives (
                    ad_id TEXT PRIMARY KEY,
                    campaign_name TEXT NOT NULL,
                    persona_id TEXT NOT NULL,
                    persona_name TEXT,
                    target_platform TEXT NOT NULL,
                    hook_text TEXT NOT NULL,
                    hook_type TEXT NOT NULL,
                    primary_text TEXT,
                    headline TEXT,
                    call_to_action TEXT,
                    safe_zone_compliant INTEGER DEFAULT 1,
                    parent_winner_id TEXT,
                    generation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Live Deployment & Performance Log Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad_id TEXT NOT NULL,
                    impressions INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    three_second_views INTEGER DEFAULT 0,
                    spend REAL DEFAULT 0.0,
                    conversions INTEGER DEFAULT 0,
                    revenue REAL DEFAULT 0.0,
                    ctr REAL,
                    hook_rate REAL,
                    cpc REAL,
                    roas REAL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ad_id) REFERENCES ad_creatives (ad_id)
                )
            """)

            # 4. Optimization Decisions Audit Table (Kill & Scale Events)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS optimization_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    budget_delta_pct REAL,
                    spawned_variants_count INTEGER DEFAULT 0,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("Flywheel SQLite lineage database verified at: %s", self.db_path)

    def record_trend(self, item: Dict[str, Any]) -> None:
        jev = item.get("jev_metrics", {})
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO viral_trends 
                (trend_id, platform, topic, raw_text, likes_count, retweets_or_shares, virality_score, is_brand_safe, is_ai_slop, jev_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(item.get("tweet_id") or item.get("shortcode") or "item"),
                item.get("platform", "unknown"),
                (item.get("tweet_text") or item.get("caption") or "")[:40],
                item.get("tweet_text") or item.get("caption") or "",
                int(item.get("likes_count") or 0),
                int(item.get("retweets_count") or 0),
                float(jev.get("virality_score", 0.0)),
                1 if jev.get("brand_safe", True) else 0,
                1 if jev.get("is_ai_slop", False) else 0,
                float(jev.get("latency_ms", 0.0)),
            ))
            conn.commit()

    def record_ad_variation(self, var: Dict[str, Any], campaign_name: str, parent_id: Optional[str] = None) -> None:
        hook = var.get("hook", {})
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ad_creatives
                (ad_id, campaign_name, persona_id, persona_name, target_platform, hook_text, hook_type, primary_text, headline, call_to_action, safe_zone_compliant, parent_winner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                var.get("ad_id"),
                campaign_name,
                var.get("persona_id"),
                var.get("persona_name", var.get("persona_id")),
                str(var.get("target_platform", "meta_reels")),
                hook.get("hook_text", ""),
                hook.get("hook_type", "Standard"),
                var.get("primary_text", ""),
                var.get("headline", ""),
                var.get("call_to_action", "Get Started"),
                1 if hook.get("safe_zone_compliant", True) else 0,
                parent_id,
            ))
            conn.commit()

    def record_performance_snapshot(self, metric: Any) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO performance_metrics
                (ad_id, impressions, clicks, three_second_views, spend, conversions, revenue, ctr, hook_rate, cpc, roas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.ad_id,
                metric.impressions,
                metric.clicks,
                metric.three_second_views,
                metric.spend,
                metric.conversions,
                metric.revenue,
                metric.ctr,
                metric.hook_rate,
                metric.cpc,
                metric.roas,
            ))
            conn.commit()

    def record_decision(self, ad_id: str, action: str, reason: str, budget_delta_pct: float, spawned_count: int) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO optimization_decisions
                (ad_id, action, reason, budget_delta_pct, spawned_variants_count)
                VALUES (?, ?, ?, ?, ?)
            """, (ad_id, action, reason, budget_delta_pct, spawned_count))
            conn.commit()

    def get_campaign_analytics(self) -> Dict[str, Any]:
        """Calculates live aggregate metrics across campaigns."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viral_trends WHERE virality_score >= 0.6")
            approved_trends = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM ad_creatives")
            total_creatives = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM optimization_decisions WHERE action = 'KILL_PAUSE'")
            killed_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM optimization_decisions WHERE action = 'SCALE_BUDGET'")
            scaled_count = cursor.fetchone()[0]

            return {
                "verified_viral_trends_ingested": approved_trends,
                "total_ad_variations_synthesized": total_creatives,
                "total_creatives_killed": killed_count,
                "total_creatives_scaled": scaled_count,
            }
