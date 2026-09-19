"""Agent registry: the 13 canonical agents (CONTRACT.md §4.24, docs/13 §2).

Each module exposes `run(db, run, input) -> dict` (output summary). Supervised:
agents never auto-submit and automated queue recommendations stop at
DISCOVERED/IDEA_READY. All outputs from mock providers are labeled MOCK.
"""

from __future__ import annotations

from typing import Any

AGENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "trend_research",
        "description": "Collects and normalizes trend data from configured sources into trend_snapshots.",
        "capabilities": ["source_fetch", "normalization", "snapshot_write"],
        "enabled": True,
    },
    {
        "name": "market_analysis",
        "description": "Aggregates snapshots into market metrics: W0/W1/baseline analysis, velocity, momentum.",
        "capabilities": ["seven_day_analysis", "metric_aggregation"],
        "enabled": True,
    },
    {
        "name": "category_intelligence",
        "description": "Proposes subcategories/micro-niches for user approval; never auto-creates taxonomy.",
        "capabilities": ["niche_proposal"],
        "enabled": True,
    },
    {
        "name": "opportunity",
        "description": "Generates scored, gated opportunities from trend analysis (min 3 topics).",
        "capabilities": ["opportunity_generation", "scoring", "gating"],
        "enabled": True,
    },
    {
        "name": "image_ideation",
        "description": "Generates original still-image concepts from approved opportunities.",
        "capabilities": ["concept_generation", "originality_notes"],
        "enabled": True,
    },
    {
        "name": "video_ideation",
        "description": "Generates original video/motion concepts with shot lists.",
        "capabilities": ["concept_generation", "shot_lists"],
        "enabled": True,
    },
    {
        "name": "prediction",
        "description": "Probabilistic demand forecasts per micro-niche + horizon. Never guarantees sales.",
        "capabilities": ["demand_forecast", "confidence_gating"],
        "enabled": True,
    },
    {
        "name": "prompt",
        "description": "Builds versioned prompt packages (primary/alternative/negative + blocks).",
        "capabilities": ["prompt_drafting", "versioning", "tool_adaptation"],
        "enabled": True,
    },
    {
        "name": "compliance",
        "description": "Screens prompts/metadata against the 28 rules. Fail-closed: errors → REVIEW.",
        "capabilities": ["rule_screening", "explanations"],
        "enabled": True,
    },
    {
        "name": "originality",
        "description": "Similarity scans vs market clusters (CLEAR < 0.60 ≤ REVIEW < 0.80 ≤ HIGH_RISK).",
        "capabilities": ["similarity_scan", "cluster_comparison"],
        "enabled": True,
    },
    {
        "name": "metadata",
        "description": "Drafts titles/descriptions/keywords with SPAM-01…SPAM-07 enforcement.",
        "capabilities": ["metadata_drafting", "spam_check", "quality_score"],
        "enabled": True,
    },
    {
        "name": "production_planning",
        "description": "Computes queue priority scores and suggests production ordering.",
        "capabilities": ["priority_scoring", "capacity_planning"],
        "enabled": True,
    },
    {
        "name": "performance_analysis",
        "description": "Digests performance metrics; sample-size aware, never invents Adobe sales data.",
        "capabilities": ["kpi_digest", "funnel_analysis"],
        "enabled": True,
    },
]

AGENT_NAMES = [d["name"] for d in AGENT_DEFINITIONS]


def get_definition(name: str) -> dict[str, Any] | None:
    return next((d for d in AGENT_DEFINITIONS if d["name"] == name), None)
