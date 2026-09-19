"""Custom adapter (source_type: ``custom``). Passthrough.

Lets the user register their own webhooks/feeds: raw records are injected
through the scheduler/API path as ``ctx.queries`` entries (JSON lines) or via
``inject_records``. No source is invented — only what the user explicitly
supplies is stored, labeled USER_PROVIDED.
"""

from __future__ import annotations

import json
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


class CustomAdapter(SourceAdapter):
    source_type = "custom"

    _injected: list[RawRecord] = []

    @classmethod
    def inject_records(cls, records: list[RawRecord]) -> None:
        cls._injected.extend(records)

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        records = list(self._injected)
        self._injected.clear()
        for q in ctx.queries:
            try:
                obj = json.loads(q)
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=obj.get("title", "custom record"),
                        body=obj.get("body"),
                        url=obj.get("url"),
                        published_at=datetime.now(UTC),
                        extra={"custom": True, "payload": obj},
                    )
                )
            except json.JSONDecodeError:
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=q[:200],
                        published_at=datetime.now(UTC),
                        extra={"custom": True},
                    )
                )
        return records

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        return [
            TrendSignalInput(
                signal_name=rec.title[:200],
                description=(rec.body or "")[:2000] or None,
                metric_name="custom_observation",
                metric_value=1.0,
                metric_unit="observations",
                observed_at=datetime.now(UTC),
                provenance=DataProvenance.USER_PROVIDED,
                confidence=0.5,
                collection_method="custom_inject",
                data_timestamp=rec.published_at,
                raw_reference={"url": rec.url},
            )
            for rec in records
        ]

    def get_status(self) -> AdapterHealth:
        return AdapterHealth(
            status=SourceStatus.AVAILABLE,
            detail="custom passthrough ready — inject records via the API/scheduler path",
        )


__all__ = ["CustomAdapter"]
