"""GitHub adapter (source_type: ``github_trending``).

``https://api.github.com/search/repositories?q=...`` via stdlib urllib —
no binary, no pip package. Unauthenticated: 10 req/min; a GITHUB_TOKEN
(optional, env) raises the limit. The GitHub REST API is an official API →
provenance VERIFIED.

Rate-limit discipline: the adapter tracks the X-RateLimit-Reset header in a
module-level record and sleeps/skips when exhausted.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
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

API_URL = "https://api.github.com/search/repositories"

# module-level rate-limit state (shared across runs in-process)
_RATE_STATE = {"remaining": 10, "reset_at": 0.0}


def _github_get(path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{API_URL}{path}?{qs}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "stockpulse-ai/0.3",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        try:
            _RATE_STATE["remaining"] = int(resp.headers.get("X-RateLimit-Remaining", 10))
            _RATE_STATE["reset_at"] = float(resp.headers.get("X-RateLimit-Reset", 0))
        except Exception:
            pass
        return json.loads(resp.read().decode())


class GitHubAdapter(SourceAdapter):
    source_type = "github_trending"

    DEFAULT_QUERIES = [
        "topic:generative-ai stars:>500 pushed:>2026-01-01",
        "topic:stable-diffusion stars:>200 pushed:>2026-01-01",
        "topic:text-to-image stars:>200 pushed:>2026-01-01",
    ]

    def _rate_ok(self) -> bool:
        if _RATE_STATE["remaining"] > 0:
            return True
        wait = _RATE_STATE["reset_at"] - time.time()
        return wait <= 0  # window already reset → allow

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        if not self._rate_ok():
            logger.warning(
                "github collect skipped: rate limit exhausted until %s",
                _RATE_STATE["reset_at"],
            )
            return []
        queries = ctx.queries or self.DEFAULT_QUERIES
        records: list[RawRecord] = []
        for q in queries:
            if not self._rate_ok():
                break
            try:
                data = _github_get(
                    "",
                    {"q": q, "sort": "stars", "order": "desc", "per_page": min(ctx.limit, 30)},
                )
            except Exception as exc:
                logger.warning("github search failed for %r: %s", q, exc)
                continue
            for item in data.get("items", [])[: ctx.limit]:
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=f"{item.get('full_name')}: {item.get('description') or ''}".strip(),
                        body=item.get("description"),
                        url=item.get("html_url"),
                        author=item.get("owner", {}).get("login"),
                        published_at=datetime.now(UTC),
                        extra={
                            "stars": item.get("stargazers_count"),
                            "language": item.get("language"),
                            "topics": item.get("topics", []),
                            "query": q,
                        },
                    )
                )
                if len(records) >= ctx.limit:
                    break
            if len(records) >= ctx.limit:
                break
        return records[: ctx.limit]

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            stars = rec.extra.get("stars")
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    description=(rec.body or "")[:2000] or None,
                    metric_name="github_stars",
                    metric_value=float(stars) if stars is not None else None,
                    metric_unit="stars",
                    # Stable content identity: dedup keys on (signal_name, observed_at),
                    # so use the content timestamp when known (else collection time).
                    observed_at=rec.published_at or datetime.now(UTC),
                    provenance=DataProvenance.VERIFIED,  # official GitHub API
                    confidence=0.65,
                    collection_method="github_search_api",
                    data_timestamp=rec.published_at,
                    raw_reference={
                        "url": rec.url,
                        "language": rec.extra.get("language"),
                        "topics": rec.extra.get("topics"),
                    },
                )
            )
        return signals

    def get_status(self) -> AdapterHealth:
        # Real probe: the rate-limit endpoint needs no auth.
        try:
            data = self._probe_rate_limit()
            remaining = data.get("resources", {}).get("core", {}).get("remaining")
            return AdapterHealth(
                status=SourceStatus.AVAILABLE,
                detail=f"api.github.com reachable; core rate-limit remaining={remaining}",
                records_collected=0,
            )
        except Exception as exc:
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"api.github.com probe failed: {exc}",
                last_error=str(exc),
            )

    @staticmethod
    def _probe_rate_limit() -> dict:
        url = "https://api.github.com/rate_limit"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "stockpulse-ai/0.3"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())


__all__ = ["GitHubAdapter"]
