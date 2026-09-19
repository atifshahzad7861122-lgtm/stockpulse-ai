"""Instagram adapter (source_type: ``instagram``). Desktop-only, UNAVAILABLE.

Per the inspected deployment constraints: Instagram/Threads collection needs
the desktop OpenCLI connector — a server deployment cannot do this, so this
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


class InstagramAdapter(SourceAdapter):
    source_type = "instagram"

    def is_configured(self) -> tuple[bool, str]:
        if os.environ.get("STOCKPULSE_DESKTOP", "").lower() == "true" and os.environ.get(
            "OPENCLI_IG_SESSION"
        ):
            return True, "desktop OpenCLI session present"
        return (
            False,
            "Instagram collection is desktop-only (OpenCLI); server cannot mint IG sessions",
        )

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured()
        if not configured:
            logger.warning("instagram collect skipped: %s", reason)
            return []
        logger.info("instagram collect: configured but request path not yet executed this run")
        return []

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        return [
            TrendSignalInput(
                signal_name=rec.title[:200],
                description=(rec.body or "")[:2000] or None,
                metric_name="ig_mentions",
                metric_value=rec.extra.get("like_count"),
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
                detail=f"Instagram: {reason}",
            )
        return AdapterHealth(
            status=SourceStatus.NEEDS_AUTH,
            detail=f"Instagram desktop path ({reason})",
        )


__all__ = ["InstagramAdapter"]
