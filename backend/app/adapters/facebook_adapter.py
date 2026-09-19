"""Facebook adapter (source_type: ``facebook``). Desktop-only, UNAVAILABLE.

Per the inspected deployment constraints: Facebook collection needs the
desktop OpenCLI connector — a server deployment cannot do this, so this
adapter is permanently UNAVAILABLE on server and NEEDS_AUTH on desktop until
the OpenCLI session is configured. It never fabricates data.
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


class FacebookAdapter(SourceAdapter):
    source_type = "facebook"

    def is_configured(self) -> tuple[bool, str]:
        if os.environ.get("STOCKPULSE_DESKTOP", "").lower() == "true" and os.environ.get(
            "OPENCLI_FB_SESSION"
        ):
            return True, "desktop OpenCLI session present"
        return (
            False,
            "Facebook collection is desktop-only (OpenCLI); server cannot mint FB sessions",
        )

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured()
        if not configured:
            logger.warning("facebook collect skipped: %s", reason)
            return []
        logger.info("facebook collect: configured but request path not yet executed this run")
        return []

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        return [
            TrendSignalInput(
                signal_name=rec.title[:200],
                description=(rec.body or "")[:2000] or None,
                metric_name="fb_mentions",
                metric_value=rec.extra.get("engagement"),
                metric_unit="posts",
                provenance=DataProvenance.THIRD_PARTY,
                confidence=0.5,
                collection_method="opencli_desktop",
                data_timestamp=rec.published_at,
                raw_reference={"url": rec.url},
            )
            for rec in records
        ]

    def get_status(self) -> AdapterHealth:
        configured, reason = self.is_configured()
        if not configured:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"Facebook: {reason}",
            )
        return AdapterHealth(
            status=SourceStatus.NEEDS_AUTH,
            detail=f"Facebook desktop path ({reason})",
        )


__all__ = ["FacebookAdapter"]
