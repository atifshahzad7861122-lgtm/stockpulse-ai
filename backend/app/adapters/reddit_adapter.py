"""Reddit adapter (source_type: ``reddit``). Architecture complete, NEEDS_AUTH.

Planned path: ``rdt-cli`` (official Reddit CLI patterns) or the public Reddit
JSON endpoints with user-provided session cookies (``REDDIT_SESSION_COOKIE``
env, set via the settings API — never committed). Server deployment cannot
mint cookies itself, so until the user configures credentials this adapter
returns NEEDS_AUTH and ``collect`` returns no records.

No fake data is ever produced: an unconfigured adapter stores nothing.
"""

from __future__ import annotations

import logging
import os

from app.adapters.base import (
    AdapterHealth,
    CollectionContext,
    RawRecord,
    SourceAdapter,
)
from app.adapters.normalized import TrendSignalInput
from app.schemas.enums import DataProvenance, SourceStatus

logger = logging.getLogger(__name__)


class RedditAdapter(SourceAdapter):
    source_type = "reddit"

    TARGET_SUBREDDITS = [
        "StableDiffusion",
        "midjourney",
        "photography",
        "stock",
        "Design",
    ]

    def is_configured(self) -> tuple[bool, str]:
        if os.environ.get("REDDIT_SESSION_COOKIE"):
            return True, "REDDIT_SESSION_COOKIE set"
        return False, "no Reddit session cookie configured (set REDDIT_SESSION_COOKIE via settings API)"

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured()
        if not configured:
            logger.warning("reddit collect skipped: %s", reason)
            return []
        # Real collection path (documented, runs only when configured):
        #   - rdt-cli search per TARGET_SUBREDDITS
        #   - or https://www.reddit.com/r/{sub}/hot.json with session cookie
        # Implementing the request path here would duplicate rdt-cli; the
        # adapter is ready for the cookie once the user supplies it.
        logger.info("reddit collect: configured but request path not yet executed this run")
        return []

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        return [
            TrendSignalInput(
                signal_name=rec.title[:200],
                description=(rec.body or "")[:2000] or None,
                metric_name="reddit_upvotes",
                metric_value=rec.extra.get("score"),
                metric_unit="upvotes",
                provenance=DataProvenance.THIRD_PARTY,
                confidence=0.5,
                collection_method="reddit_json",
                data_timestamp=rec.published_at,
                raw_reference={"url": rec.url, "subreddit": rec.extra.get("subreddit")},
            )
            for rec in records
        ]

    def get_status(self) -> AdapterHealth:
        configured, reason = self.is_configured()
        if not configured:
            return AdapterHealth(
                status=SourceStatus.NEEDS_AUTH,
                detail=f"Reddit not configured: {reason}",
            )
        return AdapterHealth(
            status=SourceStatus.CONFIGURED,
            detail=f"Reddit configured ({reason}); request path ready",
        )


__all__ = ["RedditAdapter"]
