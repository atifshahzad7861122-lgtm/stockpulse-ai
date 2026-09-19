"""YouTube adapter (source_type: ``youtube_rss``).

Uses public YouTube channel RSS feeds
(``https://www.youtube.com/feeds/videos.xml?channel_id=...``) parsed with
feedparser — NO yt-dlp (PHASE2_DESIGN.md §1; yt-dlp needs a JS runtime and is
deliberately excluded). YouTube RSS is a public, no-auth feed →
provenance THIRD_PARTY (not VERIFIED — not an official API).

Seeded channel list: design / stock-photography / AI-trend channels.
A future optional path (yt-dlp + Groq transcription) is documented in notes
but not implemented here.
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

# Real channel IDs — canonical channel IDs extracted 2026-09-19 from each
# channel's own page (<link rel="canonical" href=".../channel/UC...">).
# Design / stock-photography / creative channels:
CHANNELS = [
    {"channel_id": "UC5_SBQbLA9Kg7Jh5GpXoP3g", "name": "Adobe"},
    {"channel_id": "UC8lxnUR_CzruT2KA6cb7p0Q", "name": "Envato Tuts+"},
    {"channel_id": "UC-b3c7kxa5vU-bnmaROgvog", "name": "The Futur"},
    {"channel_id": "UCoYATiiqNT7csPFqtWWfc5w", "name": "Skillshare"},
    {"channel_id": "UCSLeoz5odIGS2GdlbHbCAUg", "name": "Matthew Encina"},
]


def channel_rss_url(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


class YouTubeRSSAdapter(SourceAdapter):
    source_type = "youtube_rss"

    @property
    def dependency(self) -> str:
        return "feedparser"

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("youtube_rss collect skipped: %s", reason)
            return []
        import feedparser

        records: list[RawRecord] = []
        channels = ctx.queries or [c["channel_id"] for c in CHANNELS]
        for channel_id in channels[: len(CHANNELS)]:
            name = next(
                (c["name"] for c in CHANNELS if c["channel_id"] == channel_id), channel_id
            )
            try:
                parsed = feedparser.parse(channel_rss_url(channel_id))
            except Exception as exc:
                logger.warning("youtube rss parse failed %s: %s", name, exc)
                continue
            for entry in parsed.get("entries", [])[: ctx.limit]:
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
                        title=entry.get("title", ""),
                        body=entry.get("summary", "")[:1000] or None,
                        url=entry.get("link"),
                        author=entry.get("author"),
                        published_at=published_at,
                        extra={"channel": name, "channel_id": channel_id},
                    )
                )
        return records[: ctx.limit]

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    description=(rec.body or "")[:2000] or None,
                    metric_name="video_mentions",
                    metric_value=1.0,
                    metric_unit="videos",
                    # Stable content identity: dedup keys on (signal_name, observed_at),
                    # so use the content timestamp when known (else collection time).
                    observed_at=rec.published_at or datetime.now(UTC),
                    provenance=DataProvenance.THIRD_PARTY,
                    confidence=0.5,
                    collection_method="youtube_channel_rss",
                    data_timestamp=rec.published_at,
                    raw_reference={
                        "url": rec.url,
                        "channel": rec.extra.get("channel"),
                        "channel_id": rec.extra.get("channel_id"),
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
        # Real probe: fetch the seeded channels' RSS; never claim success
        # without entries actually parsed.
        import feedparser

        total_entries = 0
        failures = []
        for ch in CHANNELS:
            try:
                parsed = feedparser.parse(channel_rss_url(ch["channel_id"]))
                n = len(parsed.get("entries", []))
                total_entries += n
                if parsed.get("bozo"):
                    failures.append(f"{ch['name']}: {parsed.get('bozo_exception')}")
            except Exception as exc:
                failures.append(f"{ch['name']}: {exc}")
        if total_entries > 0:
            return AdapterHealth(
                status=SourceStatus.AVAILABLE,
                detail=f"parsed {total_entries} video entries from {len(CHANNELS)} channels (RSS)",
                records_collected=total_entries,
            )
        return AdapterHealth(
            status=SourceStatus.TEMP_FAILING,
            detail=(
                "YouTube RSS feeds/videos.xml returned no entries for any seeded "
                f"channel (failures: {'; '.join(failures)[:300]}). "
                "Endpoint may be deprecated/retired — under investigation."
            ),
            last_error="; ".join(failures)[:500] or None,
        )


__all__ = ["YouTubeRSSAdapter", "CHANNELS", "channel_rss_url"]
