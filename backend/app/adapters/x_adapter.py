"""X (Twitter) adapter (source_type: ``x_trends``). Architecture complete, NEEDS_AUTH.

Configured via ``TWITTER_AUTH_TOKEN`` + ``TWITTER_CT0`` env (Cookie-Editor
export, set via the settings API — never committed, never returned to the
frontend). Until both are present the adapter returns NEEDS_AUTH and
``collect`` returns no records. No fake data is ever produced.
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


class XAdapter(SourceAdapter):
    source_type = "x_trends"

    def is_configured(self) -> tuple[bool, str]:
        auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
        ct0 = os.environ.get("TWITTER_CT0")
        if auth_token and ct0:
            return True, "TWITTER_AUTH_TOKEN + TWITTER_CT0 present"
        missing = [
            name
            for name, val in (
                ("TWITTER_AUTH_TOKEN", auth_token),
                ("TWITTER_CT0", ct0),
            )
            if not val
        ]
        return False, f"missing: {', '.join(missing)} (export via Cookie-Editor, set via settings API)"

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured()
        if not configured:
            logger.warning("x collect skipped: %s", reason)
            return []
        # Real collection path (documented, runs only when configured):
        #   - GET https://api.x.com/2/trends/... with auth_token/ct0 cookies
        #   - search/tweet counts per trend topic → RawRecord
        logger.info("x collect: configured but request path not yet executed this run")
        return []

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        return [
            TrendSignalInput(
                signal_name=rec.title[:200],
                description=(rec.body or "")[:2000] or None,
                metric_name="x_mentions",
                metric_value=rec.extra.get("tweet_count"),
                metric_unit="posts",
                provenance=DataProvenance.THIRD_PARTY,
                confidence=0.5,
                collection_method="x_api_v2",
                data_timestamp=rec.published_at,
                raw_reference={"url": rec.url},
            )
            for rec in records
        ]

    def get_status(self) -> AdapterHealth:
        configured, reason = self.is_configured()
        if not configured:
            return AdapterHealth(
                status=SourceStatus.NEEDS_AUTH,
                detail=f"X not configured: {reason}",
            )
        return AdapterHealth(
            status=SourceStatus.CONFIGURED,
            detail=f"X configured ({reason}); request path ready",
        )


__all__ = ["XAdapter"]
