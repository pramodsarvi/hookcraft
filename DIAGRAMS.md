# 🗺️ System Architecture & Visual Flowcharts

This document compiles all visual architecture and operational diagrams generated for the **Autonomous Marketing Flywheel Agent** (InstaAgent Clone), covering the end-to-end cyclical pipeline, state machines, decentralized device swarms, and ad network interactions.

---

## Table of Contents
1. [Master 4-Phase Autonomous Marketing Flywheel](#1-master-4-phase-autonomous-marketing-flywheel)
2. [Phase 2: Ingestion Pipeline & LangGraph State Machine](#2-phase-2-ingestion-pipeline--langgraph-state-machine)
3. [Decentralized Mobile Edge Swarm (5 Physical Devices)](#3-decentralized-mobile-edge-swarm-5-physical-devices)
4. [Household Wi-Fi Staggered Velocity Governor (Same Wi-Fi Anti-Ban Protocol)](#4-household-wi-fi-staggered-velocity-governor-same-wi-fi-anti-ban-protocol)
5. [Autonomous Flywheel vs. Meta & Google Ads (Creative Factory vs. Delivery Truck)](#5-autonomous-flywheel-vs-meta--google-ads-creative-factory-vs-delivery-truck)
6. [Continuous Kill & Scale Optimization Loop](#6-continuous-kill--scale-optimization-loop)

---

## 1. Master 4-Phase Autonomous Marketing Flywheel

This diagram illustrates the complete, cyclical 4-phase architecture: continuous ingestion on X/Instagram, sub-100ms Laya/Jev gating, brief-to-hook multiplexing, pre-flight visual safety QA, programmatic distribution, and automated performance feedback.

```mermaid
flowchart TD
    subgraph ListenLoop ["Phase 1 & 2: The Listen Loop (Ingestion & Gating)"]
        AccPool["Enterprise Account Pool\n(Round-Robin + Proxy Pinning)"] --> Launch["Persistent Context Launch\n(Cubic Bézier + Canvas Noise)"]
        Launch --> Scrape["Stealth Feed Traversal\n(Adaptive Infinite Scroll Engine)"]
        Scrape --> MediaCap["Stream Interceptor\n(XHR .mp4 Buffering + OpenCV Fallback)"]
        Scrape --> JevGate{"Laya / Jev AI Gate\n(Sub-100ms Non-Autoregressive)"}
        JevGate -->|Brand Unsafe / AI Slop| Drop["❌ Discard Record (<1ms)"]
        JevGate -->|Verified Viral Trend| DB_Trend["Save to SQLite Lineage DB"]
    end

    subgraph CreateLoop ["Phase 3: The Create Loop (Multiplexing & QA)"]
        DB_Trend --> Multiplex["Brief-to-Hook Multiplexer\n(1 Brief ➔ 5 Personas ➔ 50 Hooks)"]
        Brief["Markdown Product Brief"] --> Multiplex
        Multiplex --> CanvasQA{"Canvas Safety Analyzer\n(Visual Margin Inspection)"}
        CanvasQA -->|UI Icon Collision| Adjust["Re-pad Text Bounds (-22% Bottom)"]
        Adjust --> CanvasQA
        CanvasQA -->|Compliant| DB_Creative["Save 50 Ad Creatives to DB"]
    end

    subgraph DistributeLoop ["Phase 4a: The Distribute Loop (Deployment)"]
        DB_Creative --> Deploy["Headless Account Publisher\n(Meta Graph API + Playwright Staging)"]
        Deploy --> LiveAds["Stage Active Ad Sets in Meta/X Ads"]
    end

    subgraph OptimizeLoop ["Phase 4b: The Optimize Loop (Kill & Scale Feedback)"]
        LiveAds --> PollMetrics["Poll Conversion Metrics\n(CTR, Hook Rate, CPC, ROAS)"]
        PollMetrics --> DecisionGate{"Kill & Scale Rules Engine"}
        DecisionGate -->|CTR < 0.85% or CPC > $2.50| KillAd["❌ Pause Creative\n(-100% Budget)"]
        DecisionGate -->|CTR > 2.4% & ROAS > 2.8x| ScaleAd["🚀 Scale Budget (+35%)\nExtract Winning Angle"]
        ScaleAd --> Spawn["Spawn 10 Localized Winner Variants"]
        Spawn -.->|Cyclical Lineage Feedback| Multiplex
    end
```

---

## 2. Phase 2: Ingestion Pipeline & LangGraph State Machine

This diagram details the deterministic node transitions within `pipeline.py` during timeline scraping, handling network degradation and conditional routing to Laya/Jev decision gates.

```mermaid
flowchart LR
    Init["initialize_session\n(Resolve Context & Proxy)"] --> Scrape["scrape_and_capture_streams\n(Persistent Context + Video Interceptor)"]
    Scrape -->|Health: OK| JevGate["jev_validation_gate\n(Sub-100ms Brand & Virality Matrix)"]
    Scrape -->|Rate Limit / Degraded| Audit["audit_and_checkpoint\n(Log Telemetry & Pass to Create Loop)"]
    JevGate --> Audit
```

---

## 3. Decentralized Mobile Edge Swarm (5 Physical Devices)

This diagram shows how 5 physical consumer devices (phones, tablets, laptops) act as a decentralized edge scraping cluster reporting back to the central Mac Hub without paid proxies ($0.00).

```mermaid
flowchart TD
    subgraph Master["Your Main Mac (Hub)"]
        Hub["Swarm Coordinator\n(flywheel.db + Laya Master)"]
    end

    subgraph Devices["Your 5 Decentralized Edge Devices"]
        D1["Device 1: Laptop A\n(Home Wi-Fi)"]
        D2["Device 2: Phone 1\n(Cellular 5G Hotspot / Termux)"]
        D3["Device 3: Phone 2\n(Cellular 4G)"]
        D4["Device 4: Tablet\n(Guest Wi-Fi / Hotspot)"]
        D5["Device 5: Laptop B\n(Office / Coffee Shop Wi-Fi)"]
    end

    Hub -->|Dispatches Scrape Tasks| D1
    Hub -->|Dispatches Scrape Tasks| D2
    Hub -->|Dispatches Scrape Tasks| D3
    Hub -->|Dispatches Scrape Tasks| D4
    Hub -->|Dispatches Scrape Tasks| D5

    D1 -->|Reports Scraped Data| Hub
    D2 -->|Reports Scraped Data| Hub
    D3 -->|Reports Scraped Data| Hub
    D4 -->|Reports Scraped Data| Hub
    D5 -->|Reports Scraped Data| Hub
```

---

## 4. Household Wi-Fi Staggered Velocity Governor (Same Wi-Fi Anti-Ban Protocol)

When all 5 devices share the **same home Wi-Fi network** (sharing a single public external IP), the Central Hub coordinates a token-bucket slot schedule. This staggers requests across time slots to simulate an organic family browsing social apps simultaneously.

```mermaid
flowchart TD
    subgraph LAN["Your Home Wi-Fi Network (192.168.1.x)"]
        Mac["Mac Master Hub\n(Port 8080)\nGlobal Velocity Governor"]
        
        D1["Device 1: Mac / Laptop\n(Slot: Second 0)"]
        D2["Device 2: iPhone / Android\n(Slot: Second 4)"]
        D3["Device 3: iPad / Tablet\n(Slot: Second 8)"]
        D4["Device 4: Laptop 2\n(Slot: Second 12)"]
        D5["Device 5: Phone 2\n(Slot: Second 16)"]
    end

    Mac -->|Task 1: Elon Musk X| D1
    Mac -->|Task 2: Competitor IG| D2
    Mac -->|Task 3: AI Trends| D3
    Mac -->|Task 4: Tech News| D4
    Mac -->|Task 5: Reels Audio| D5

    D1 -.->|Reports JSON Data| Mac
    D2 -.->|Reports JSON Data| Mac
    D3 -.->|Reports JSON Data| Mac
    D4 -.->|Reports JSON Data| Mac
    D5 -.->|Reports JSON Data| Mac
```

---

## 5. Autonomous Flywheel vs. Meta & Google Ads (Creative Factory vs. Delivery Truck)

This diagram illustrates why Meta and Google Ads are merely distribution/auction pipes, while our Autonomous Flywheel acts as the creative laboratory and intelligence layer that feeds them high-converting assets.

```mermaid
flowchart LR
    A["Your App Idea\n(1-Page Brief)"] --> B["Autonomous Flywheel\n• Viral Trend Extraction\n• Laya Gating\n• 50 Hooks / 5 Personas\n• Canvas Safe-Zone QA"]
    B --> C["Meta Ads / Google Ads\n(Delivery Network & Auction)"]
    C --> D["Kill & Scale Loop\n• Kills Losers\n• Scales Winners\n• Spawns 10 New Variants"]
    D -.->|Feedback| B
```

---

## 6. Continuous Kill & Scale Optimization Loop

This diagram illustrates the high-level circular feedback between scraping, multi-persona creation, headless ad deployment, metric polling, and automated variant generation.

```mermaid
flowchart TD
    subgraph ListenLoop ["Phase 2: Listen Loop"]
        Scrape["Scrape Timeline\n(Playwright Stealth + Video Stream Interceptor)"]
        JevFilter["Laya / Jev Sub-100ms Gate\n(Brand Safety, Virality Score, Anti-Slop)"]
        Scrape --> JevFilter
    end

    subgraph CreateLoop ["Phase 3: Create Loop"]
        Multiplex["Brief-to-Hook Multiplexer\n(5 Buyer Personas x 10 Angles = 50 Hooks)"]
        CanvasQA["Canvas Safety Analyzer\n(UI Overlay Bounds QA)"]
        Multiplex --> CanvasQA
    end

    subgraph DistributeLoop ["Phase 4: Distribute Loop"]
        AdsDeploy["Headless Ads Manager Publisher\n(Stage Drafts & Upload Assets)"]
    end

    subgraph OptimizeLoop ["Phase 4: Optimize Loop"]
        MetricsAgg["Poll CTR, Hook Rate, CPC, ROAS"]
        KillDecision{"Performance Floor?"}
        KillAction["❌ Kill & Pause Creative\n(-100% Budget)"]
        ScaleAction["🚀 Scale Budget (+35%)\nSpawn 10 Localized Winner Variants"]
        
        MetricsAgg --> KillDecision
        KillDecision -->|Underperforming| KillAction
        KillDecision -->|Winner| ScaleAction
    end

    JevFilter --> Multiplex
    CanvasQA --> AdsDeploy
    AdsDeploy --> MetricsAgg
    ScaleAction -.->|Cyclical Feedback| CreateLoop
```
