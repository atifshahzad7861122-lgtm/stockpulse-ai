"""RSS adapter (source_type: ``rss``). Zero config.

Uses ``feedparser`` over the feed list from the ``rss_feeds`` setting
(list of {name, url, category}). Guarded import: reports UNAVAILABLE when
feedparser is missing.
"""

from __future__ import annotations

import logging
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

DEFAULT_FEEDS = [
    {"name": "Adobe Blog", "url": "https://blog.adobe.com/en/feed", "category": "creative"},
    {"name": "PetaPixel", "url": "https://petapixel.com/feed/", "category": "photography"},
    {
        "name": "Design Milk",
        "url": "https://design-milk.com/feed/",
        "category": "design",
    },
]


class RSSAdapter(SourceAdapter):
    source_type = "rss"

    @property
    def dependency(self) -> str:
        return "feedparser"

    def _feeds(self, db) -> list[dict]:
        """Feed list from the rss_feeds setting; falls back to DEFAULT_FEEDS."""
        try:
            from app.models.settings import Setting

            row = db.query(Setting).filter_by(project_id=None, key="rss_feeds").one_or_none()
            if row is not None:
                value = (row.value or {}).get("value")
                if isinstance(value, list) and value:
                    return value
        except Exception as exc:
            logger.warning("rss_feeds setting read failed: %s", exc)
        return DEFAULT_FEEDS

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("rss collect skipped: %s", reason)
            return []
        import feedparser

        records: list[RawRecord] = []
        for feed in self._feeds(ctx.db):
            try:
                parsed = feedparser.parse(feed.get("url", ""))
            except Exception as exc:
                logger.warning("feed parse failed %s: %s", feed.get("name"), exc)
                continue
            for entry in parsed.get("entries", [])[: ctx.limit]:
                title = entry.get("title", "")
                link = entry.get("link")
                summary = entry.get("summary") or entry.get("description")
                published = entry.get("published_parsed")
                published_at = None
                if published:
                    try:
                        published_at = datetime(*published[:6], tzinfo=UTC)
                    except Exception:
                        published_at = None
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=title,
                        body=(summary or "")[:2000] or None,
                        url=link,
                        author=entry.get("author"),
                        published_at=published_at,
                        extra={"feed": feed.get("name"), "category": feed.get("category")},
                    )
                )
                if len(records) >= ctx.limit * len(self._feeds(ctx.db)):
                    break
        return records[: ctx.limit]

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    description=(rec.body or "")[:2000] or None,
                    metric_name="feed_mentions",
                    metric_value=1.0,
                    metric_unit="mentions",
                    # Stable content identity: dedup keys on (signal_name, observed_at),
                    # so use the content timestamp when known (else collection time).
                    observed_at=rec.published_at or datetime.now(UTC),
                    provenance=DataProvenance.THIRD_PARTY,
                    confidence=0.5,
                    collection_method="rss_feed",
                    data_timestamp=rec.published_at,
                    raw_reference={
                        "url": rec.url,
                        "feed": rec.extra.get("feed"),
                        "category": rec.extra.get("category"),
                    },
                )
            )
        return signals

    def get_status(self) -> AdapterHealth:
        available, reason = self.dependency_available()
        if not available:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"feedparser not installed: {reason}",
            )
        # Real probe: try each feed until one returns entries; never claim
        # success without entries actually parsed.
        import feedparser

        tried: list[str] = []
        for feed in DEFAULT_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                entries = parsed.get("entries", [])
            except Exception:
                entries = []
            tried.append(f"{feed['name']}={len(entries)}")
            if entries:
                return AdapterHealth(
                    status=SourceStatus.AVAILABLE,
                    detail=(
                        f"parsed {len(entries)} entries from '{feed['name']}'; "
                        f"{len(DEFAULT_FEEDS)} feeds configured"
                    ),
                )
        return AdapterHealth(
            status=SourceStatus.TEMP_FAILING,
            detail=f"no feed returned entries ({'; '.join(tried)})",
        )


__all__ = ["RSSAdapter"]
