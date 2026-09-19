"""ScrapeGraphAI adapter (source_type: ``scrapegraph_web``).

Tier 1 (keyless): ``search_on_web`` discovery + ``MarkdownifyGraph(llm_model=None)``
for article extraction — needs no API keys.
Tier 2: ``SmartScraperGraph`` with a Pydantic schema when ``OPENAI_API_KEY`` is set.

Guarded import: if ``scrapegraphai`` is missing, the adapter imports and
reports UNAVAILABLE with a reason; it never crashes app startup.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.adapters.base import (
    AdapterHealth,
    CollectionContext,
    RawRecord,
    SourceAdapter,
)
from app.adapters.normalized import TrendSignalInput
from app.schemas.enums import DataProvenance, SourceStatus

logger = logging.getLogger(__name__)


class ScrapeGraphAdapter(SourceAdapter):
    source_type = "scrapegraph_web"

    @property
    def dependency(self) -> str:
        return "scrapegraphai"

    DEFAULT_QUERIES = [
        "stock photography trends 2026",
        "AI stock image trends",
        "Adobe Stock trending collections",
    ]

    # --- Tier 1: keyless discovery + extraction -----------------------------
    def _search_on_web(self, query: str, max_results: int = 5) -> list[str]:
        """Keyless DuckDuckGo discovery. scrapegraphai 2.x returns a plain
        list of URL strings (List[str]) — not hit dicts."""
        from scrapegraphai.utils.research_web import search_on_web

        hits = search_on_web(query, max_results=max_results, search_engine="duckduckgo")
        urls: list[str] = []
        for hit in hits or []:
            if isinstance(hit, str) and hit.startswith("http"):
                urls.append(hit)
            elif isinstance(hit, dict):
                url = hit.get("url") or hit.get("link")
                if url:
                    urls.append(url)
        return urls

    def _markdownify(self, url: str) -> str:
        # 2.x: MarkdownifyGraph is not re-exported from scrapegraphai.graphs —
        # import from the submodule, with a fallback to the package root.
        try:
            from scrapegraphai.graphs.markdownify_graph import MarkdownifyGraph
        except ImportError:
            from scrapegraphai.graphs import MarkdownifyGraph

        graph = MarkdownifyGraph(llm_model=None, prompt="Extract the article text")
        result = graph.execute({"url": url})
        return result.get("markdown", "") if isinstance(result, dict) else ""

    # --- Tier 2: LLM smart scraping (optional) --------------------------------
    def _smart_scrape(self, url: str, schema) -> dict | None:
        from scrapegraphai.graphs import SmartScraperGraph

        graph = SmartScraperGraph(
            prompt="Extract stock-content trend insights",
            source=url,
            config={"llm": {"api_key": os.environ["OPENAI_API_KEY"], "model": "gpt-4o-mini"}},
            schema=schema,
        )
        result = graph.execute()
        return result if isinstance(result, dict) else None

    # --- SourceAdapter interface ----------------------------------------------
    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("scrapegraph_web collect skipped: %s", reason)
            return []
        queries = ctx.queries or self.DEFAULT_QUERIES
        records: list[RawRecord] = []
        llm_tier = bool(os.environ.get("OPENAI_API_KEY"))
        for query in queries:
            try:
                hits = self._search_on_web(query, max_results=ctx.limit)
            except Exception as exc:
                logger.warning("search_on_web failed for %r: %s", query, exc)
                continue
            for url in hits:
                title = url
                body = None
                extra = {"query": query, "search_hit": True}
                if llm_tier and len(records) < ctx.limit:
                    try:
                        extracted = self._smart_scrape(url, None)
                        if extracted:
                            body = str(extracted)[:4000]
                            extra["tier"] = 2
                    except Exception as exc:
                        logger.warning("smart scrape failed for %s: %s", url, exc)
                if body is None:
                    try:
                        markdown = self._markdownify(url)
                        body = markdown[:4000] if markdown else None
                    except Exception as exc:
                        logger.warning("markdownify failed for %s: %s", url, exc)
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=title or url,
                        body=body,
                        url=url,
                        published_at=datetime.now(UTC),
                        extra=extra,
                    )
                )
                if len(records) >= ctx.limit:
                    break
            if len(records) >= ctx.limit:
                break
        return records

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    description=(rec.body or "")[:2000] or None,
                    metric_name="web_mentions",
                    metric_value=1.0,
                    metric_unit="mentions",
                    observed_at=datetime.now(UTC),
                    provenance=DataProvenance.THIRD_PARTY,
                    confidence=0.45,
                    collection_method="scrapegraph_search_web+markdownify",
                    data_timestamp=rec.published_at,
                    raw_reference={
                        "url": rec.url,
                        "query": rec.extra.get("query"),
                        "tier": rec.extra.get("tier", 1),
                    },
                )
            )
        return signals

    def get_status(self) -> AdapterHealth:
        available, reason = self.dependency_available()
        if not available:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"scrapegraphai not installed: {reason}",
            )
        try:
            hits = self._search_on_web("test probe stockpulse", max_results=1)
            ok = isinstance(hits, list) and len(hits) > 0
        except Exception as exc:
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"search_on_web probe failed: {exc}",
                last_error=str(exc),
            )
        if ok:
            tier = " + SmartScraperGraph" if os.environ.get("OPENAI_API_KEY") else ""
            return AdapterHealth(
                status=SourceStatus.AVAILABLE,
                detail=f"search_on_web probe succeeded (Tier 1 keyless{tier})",
            )
        return AdapterHealth(
            status=SourceStatus.TEMP_FAILING,
            detail="search_on_web probe returned no results",
        )


__all__ = ["ScrapeGraphAdapter"]
