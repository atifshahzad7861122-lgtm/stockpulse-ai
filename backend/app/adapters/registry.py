"""Adapter registry — maps source_type → SourceAdapter class.

Contract with sibling children: adapter method names and NormalizedSignal
field names are frozen by PHASE2_DESIGN.md §1; enum strings UPPER_SNAKE_CASE.
"""

from __future__ import annotations

import logging

from app.adapters.base import SourceAdapter

logger = logging.getLogger(__name__)


def _load_adapters() -> dict[str, type[SourceAdapter]]:
    registry: dict[str, type[SourceAdapter]] = {}
    for module_name, class_names in [
        ("scrapegraph_adapter", ["ScrapeGraphAdapter"]),
        ("agentreach_adapter", ["AgentReachAdapter", "V2EXAdapter", "XueqiuAdapter"]),
        ("rss_adapter", ["RSSAdapter"]),
        ("youtube_adapter", ["YouTubeRSSAdapter"]),
        ("github_adapter", ["GitHubAdapter"]),
        ("reddit_adapter", ["RedditAdapter"]),
        ("x_adapter", ["XAdapter"]),
        ("instagram_adapter", ["InstagramAdapter"]),
        ("facebook_adapter", ["FacebookAdapter"]),
        ("adobe_adapter", ["AdobeContributorAdapter"]),
        ("huginn_adapter", ["HuginnAdapter"]),
        ("custom_adapter", ["CustomAdapter"]),
    ]:
        try:
            module = __import__(f"app.adapters.{module_name}", fromlist=class_names)
        except Exception as exc:  # guarded: a broken adapter never kills startup
            logger.warning("adapter %s failed to import: %s", module_name, exc)
            continue
        for class_name in class_names:
            try:
                cls = getattr(module, class_name)
                registry[cls.source_type] = cls
            except Exception as exc:
                logger.warning("adapter class %s.%s failed: %s", module_name, class_name, exc)
    return registry


ADAPTERS: dict[str, type[SourceAdapter]] = _load_adapters()

# Phase-2 source name → adapter ``source_type``.
#
# TrendSource rows carry the coarse ``TrendSourceType`` enum (e.g.
# "marketplace_feed") in their ``source_type`` column, while the adapter
# registry is keyed by the fine-grained adapter type (e.g. "rss",
# "github_trending"). Both the scheduler AND the API ``/{id}/collect``
# endpoint must resolve through this map — passing the enum value straight to
# ``get_adapter()`` returns None for every seeded source and every manual
# collect ends SKIPPED with "No adapter registered ...".
ADAPTER_TYPE_BY_SOURCE_NAME: dict[str, str] = {
    "RSS feeds (blogs + photography press)": "rss",
    "ScrapeGraphAI web discovery": "scrapegraph_web",
    "Agent-Reach web channels": "agentreach_web",
    "V2EX hot topics": "v2ex",
    "Xueqiu hot stocks": "xueqiu",
    "YouTube channel RSS": "youtube_rss",
    "GitHub trending AI repos": "github_trending",
    "Adobe Contributor dashboard (private)": "adobe_contributor",
}


def adapter_type_for_source(source_name: str | None) -> str | None:
    """Return the adapter ``source_type`` for a TrendSource name (or None)."""
    return ADAPTER_TYPE_BY_SOURCE_NAME.get((source_name or "").strip())


def get_adapter(source_type: str) -> type[SourceAdapter] | None:
    """Return the adapter class for ``source_type`` (or None if unknown)."""
    return ADAPTERS.get(source_type)


def get_all_adapter_types() -> list[str]:
    return sorted(ADAPTERS.keys())


__all__ = [
    "ADAPTERS",
    "ADAPTER_TYPE_BY_SOURCE_NAME",
    "adapter_type_for_source",
    "get_adapter",
    "get_all_adapter_types",
]
