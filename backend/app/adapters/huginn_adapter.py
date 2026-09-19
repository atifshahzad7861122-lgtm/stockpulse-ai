"""Huginn adapter (source_type: ``huginn``).

Huginn (MIT licence, self-hosted event automation) as a trend source: poll the
USER-HOSTED Huginn instance's event output and map website-change / RSS-digest
events into normalized trend signals.

Config — env first, then the ``huginn`` settings row (placeholders only, never
committed):
    HUGINN_BASE_URL    e.g. https://huginn.example.com
    HUGINN_API_KEY     token accepted by the instance's JSON endpoints
    HUGINN_EVENTS_PATH (optional, default "/events.json")

API contract assumed (conventional Huginn JSON routes; adjustable per
deployment via HUGINN_EVENTS_PATH):
    GET {base}{events_path}?limit=N
        → JSON array, or {"events": [...]}, of event objects shaped like
          {"id", "agent_id" | "agent": {"name"}, "payload": {...},
           "created_at": "<iso>"}.
    Auth: ``Authorization: Bearer <HUGINN_API_KEY>``.

Guardrails (research report — automate repetition, not judgment):
- Huginn web-frequency is a NOISY signal, never a demand feed: provenance is
  THIRD_PARTY and confidence is capped at 0.35.
- An event means "this page changed", never "this will sell". The human keeps
  final decisions on originality, rights, quality, metadata truthfulness and
  submission; this adapter only surfaces repetition for review.
- The adapter polls ONLY the user's own Huginn instance (one GET per collect,
  ``limit``-bounded, 20s timeout). Configure the Huginn scenarios themselves
  to respect target sites' robots.txt, rate limits and terms of service.

Not configured → get_status() returns NEEDS_AUTH honestly; unreachable /
unexpected responses → TEMP_FAILING/UNAVAILABLE with the reason. Never fakes
data. Stdlib only (urllib) — dependency guard stays green without new packages.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
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

SETTING_KEY = "huginn"
DEFAULT_EVENTS_PATH = "/events.json"
REQUEST_TIMEOUT_S = 20

# Noisy-signal cap: Huginn frequency hints at attention, never at demand.
MAX_CONFIDENCE = 0.35


class HuginnAdapter(SourceAdapter):
    source_type = "huginn"

    # --- config ---------------------------------------------------------
    def get_config(self, db) -> dict:
        """Huginn connection config: env first, then the ``huginn`` settings row.

        Never raises; never returns secrets to callers (only used internally).
        """
        cfg: dict = {
            "base_url": os.environ.get("HUGINN_BASE_URL", "").strip(),
            "api_key": os.environ.get("HUGINN_API_KEY", "").strip(),
            "events_path": os.environ.get("HUGINN_EVENTS_PATH", "").strip()
            or DEFAULT_EVENTS_PATH,
        }
        try:
            from app.models.settings import Setting

            row = db.query(Setting).filter_by(project_id=None, key=SETTING_KEY).one_or_none()
            if row is not None and isinstance(row.value, dict):
                raw = dict(row.value)
                if "base_url" not in raw and isinstance(raw.get("value"), dict):
                    raw = dict(raw["value"])
                for key in ("base_url", "api_key", "events_path"):
                    if not cfg[key] and raw.get(key):
                        cfg[key] = str(raw[key]).strip()
        except Exception as exc:
            logger.warning("huginn config read failed: %s", exc)
        return cfg

    def is_configured(self, db) -> tuple[bool, str]:
        cfg = self.get_config(db)
        if not cfg["base_url"]:
            return False, "not configured — set HUGINN_BASE_URL (+ HUGINN_API_KEY)"
        return True, f"base_url={cfg['base_url']}"

    # --- HTTP -------------------------------------------------------------
    def _fetch_events(self, cfg: dict, limit: int) -> list[dict]:
        """GET the instance's event JSON. Raises on transport/HTTP/parse errors."""
        url = cfg["base_url"].rstrip("/") + cfg["events_path"]
        query = urllib.parse.urlencode({"limit": max(1, min(limit, 100))})
        req = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
        if cfg["api_key"]:
            req.add_header("Authorization", f"Bearer {cfg['api_key']}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Huginn returned HTTP {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict):
            for key in ("events", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            raise RuntimeError("unexpected Huginn JSON envelope (no event list found)")
        if isinstance(data, list):
            return data
        raise RuntimeError("unexpected Huginn JSON shape (expected a list of events)")

    @staticmethod
    def _event_to_record(event: dict) -> RawRecord | None:
        if not isinstance(event, dict):
            return None
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        title = (
            payload.get("title")
            or payload.get("name")
            or event.get("title")
            or f"Huginn event {event.get('id', '?')}"
        )
        url = payload.get("url") or event.get("url")
        published_at = None
        for key in ("created_at", "published_at", "updated_at"):
            raw = event.get(key) or payload.get(key)
            if raw:
                try:
                    published_at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                    break
                except ValueError:
                    continue
        agent = event.get("agent")
        agent_name = agent.get("name") if isinstance(agent, dict) else event.get("agent_name")
        return RawRecord(
            source_type="huginn",
            title=str(title)[:300],
            body=json.dumps(payload, default=str)[:4000] or None,
            url=url,
            published_at=published_at,
            extra={
                "huginn_event_id": event.get("id"),
                "agent": agent_name,
                "scenario": event.get("scenario_name") or payload.get("scenario"),
            },
        )

    # --- SourceAdapter interface -------------------------------------------
    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured(ctx.db)
        if not configured:
            logger.warning("huginn collect skipped: %s", reason)
            return []
        cfg = self.get_config(ctx.db)
        try:
            events = self._fetch_events(cfg, ctx.limit)
        except Exception as exc:
            logger.warning("huginn event fetch failed: %s", exc)
            return []
        records = []
        for event in events[: ctx.limit]:
            rec = self._event_to_record(event)
            if rec is not None:
                records.append(rec)
        return self.validate(records)

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    # Noisy-signal caveat, stated on the record itself.
                    description=(
                        (rec.body or "")[:1500]
                        or "Huginn website-change/RSS-digest event (noisy attention signal, not demand)."
                    ),
                    metric_name="huginn_event_mentions",
                    metric_value=1.0,
                    metric_unit="events",
                    # Stable content identity for dedup: event time when known.
                    observed_at=rec.published_at or datetime.now(UTC),
                    provenance=DataProvenance.THIRD_PARTY,
                    confidence=min(0.3, MAX_CONFIDENCE),
                    collection_method="huginn_events",
                    data_timestamp=rec.published_at,
                    raw_reference={
                        "url": rec.url,
                        "huginn_event_id": rec.extra.get("huginn_event_id"),
                        "agent": rec.extra.get("agent"),
                    },
                )
            )
        return signals

    def get_status(self) -> AdapterHealth:
        # Status needs the DB for config; get_status has no session, so we use
        # a fresh short-lived one. Never raises; never claims more than the
        # probe actually observed.
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            configured, reason = self.is_configured(db)
            cfg = self.get_config(db)
        finally:
            db.close()
        if not configured:
            return AdapterHealth(
                status=SourceStatus.NEEDS_AUTH,
                detail=f"Huginn not configured: {reason}",
            )
        try:
            events = self._fetch_events(cfg, 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return AdapterHealth(
                    status=SourceStatus.NEEDS_AUTH,
                    detail=f"Huginn rejected credentials (HTTP {exc.code}) — check HUGINN_API_KEY",
                    last_error=str(exc),
                )
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"Huginn HTTP {exc.code} on event probe",
                last_error=str(exc),
            )
        except Exception as exc:
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"Huginn event probe failed: {exc}",
                last_error=str(exc),
            )
        return AdapterHealth(
            status=SourceStatus.AVAILABLE,
            detail=f"Huginn reachable at {cfg['base_url']} (event probe returned {len(events)} row(s))",
            records_collected=len(events),
        )


__all__ = ["HuginnAdapter", "SETTING_KEY", "DEFAULT_EVENTS_PATH", "MAX_CONFIDENCE"]
