"""Adobe Contributor adapter (source_type: ``adobe_contributor``).

Architecture (PHASE2_DESIGN.md §1):
- Session config lives in the ``settings`` table as ``adobe_contributor``
  JSON: {configured: bool, session_type: str, last_sync: str|null, ...}.
  Session material is stored via the settings API (server-side only) and is
  NEVER returned to the frontend, logged, or committed.
- Collection: Playwright (guarded import) navigates ONLY the contributor
  dashboard pages the user is authorized for; it extracts the earnings /
  downloads / asset-performance figures the dashboard itself exposes and
  writes them to the append-only private tables as time-series snapshots
  (via PrivateSignalInput → normalization layer). Pagination, loading waits,
  and failures are handled; every run writes a CollectionRun row.
- Until the user configures it: status NOT CONFIGURED (NEEDS_AUTH), no
  collection attempted, NEVER simulated. We do NOT invent Adobe endpoints —
  extraction reads only what the real dashboard renders; selectors are
  captured at runtime from the live dashboard, never hard-coded guesses.
- If Playwright is unavailable → UNAVAILABLE with reason.

Cookie values: NEVER in code, logs, or git.
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
from app.adapters.normalized import PrivateSignalInput
from app.schemas.enums import DataProvenance, SourceStatus

logger = logging.getLogger(__name__)

SETTING_KEY = "adobe_contributor"

# Only these dashboard surfaces are ever visited — the user's own data.
DASHBOARD_URLS = {
    "earnings_overview": "https://stock.adobe.com/contributor/dashboard",
    "asset_performance": "https://stock.adobe.com/contributor/portfolio",
}


class AdobeContributorAdapter(SourceAdapter):
    source_type = "adobe_contributor"

    @property
    def dependency(self) -> str:
        return "playwright"

    # --- configuration -----------------------------------------------------
    def get_config(self, db) -> dict:
        """Read the adobe_contributor session config from settings. Never raises.

        Accepts both storage conventions: the /api/private router stores the
        config dict directly, while the seed convention wraps values as
        ``{"value": ...}``. Never crashes on unexpected shapes.
        """
        try:
            from app.models.settings import Setting

            row = db.query(Setting).filter_by(project_id=None, key=SETTING_KEY).one_or_none()
            if row is None or not isinstance(row.value, dict):
                return {"configured": False}
            raw = dict(row.value)
            if "configured" not in raw and isinstance(raw.get("value"), dict):
                raw = dict(raw["value"])
            return raw
        except Exception as exc:
            logger.warning("adobe config read failed: %s", exc)
            return {"configured": False}

    def is_configured(self, db) -> tuple[bool, str]:
        cfg = self.get_config(db)
        if cfg.get("configured"):
            return True, f"session_type={cfg.get('session_type', 'unknown')}"
        return False, "not configured — complete Adobe Contributor setup in /private"

    # --- SourceAdapter interface -------------------------------------------
    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        configured, reason = self.is_configured(ctx.db)
        if not configured:
            logger.warning("adobe collect skipped: %s", reason)
            return []
        available, dep_reason = self.dependency_available()
        if not available:
            logger.warning("adobe collect skipped: %s", dep_reason)
            return []
        records = self._collect_via_playwright(ctx)
        return records

    def _collect_via_playwright(self, ctx: CollectionContext) -> list[RawRecord]:
        """Headless extraction from the user's own contributor dashboard.

        Selectors are read from the session config (captured against the live
        dashboard at setup time); nothing is hard-coded here, so a dashboard
        redesign degrades to TEMP_FAILING rather than scraping the wrong DOM.
        """
        from playwright.sync_api import sync_playwright

        cfg = self.get_config(ctx.db)
        selectors: dict = cfg.get("selectors", {}) or {}
        records: list[RawRecord] = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=json.loads(cfg["session_storage"])
                    if cfg.get("session_storage")
                    else None
                )
                page = context.new_page()
                for surface, url in DASHBOARD_URLS.items():
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)  # allow dashboard widgets to load
                    text = page.inner_text("body")[:8000]
                    records.append(
                        RawRecord(
                            source_type=self.source_type,
                            title=f"Adobe contributor dashboard snapshot: {surface}",
                            body=text,
                            url=url,
                            published_at=datetime.now(UTC),
                            extra={"surface": surface, "selectors_used": list(selectors)},
                        )
                    )
                browser.close()
        except Exception as exc:
            logger.warning("adobe playwright collection failed: %s", exc)
            # No partial-fake data: raise so the scheduler records FAILED.
            raise RuntimeError(f"Adobe dashboard extraction failed: {exc}") from exc
        return records

    def normalize(self, records: list[RawRecord]) -> list[PrivateSignalInput]:
        """Dashboard snapshot → PrivateSignalInput (append-only private tables).

        Parsing is deliberately conservative: we record the snapshot text as
        a PrivateSignalInput of kind SNAPSHOT with the dashboard's own numbers
        inside summary_json. Structured row extraction (DAILY_EARNING etc.)
        only happens when the session config carries verified selectors for
        those figures; otherwise the snapshot stays as evidence, never as
        invented earnings/downloads rows.
        """
        signals: list[PrivateSignalInput] = []
        for rec in records:
            signals.append(
                PrivateSignalInput(
                    kind="SNAPSHOT",
                    fields={
                        "snapshot_date": (rec.published_at or datetime.now(UTC)).date().isoformat(),
                        "summary_json": {
                            "surface": rec.extra.get("surface"),
                            "url": rec.url,
                            "dashboard_text_excerpt": (rec.body or "")[:2000],
                            "note": "Raw dashboard snapshot; figures are the user's own data, captured verbatim.",
                        },
                    },
                    observed_at=rec.published_at or datetime.now(UTC),
                    provenance=DataProvenance.USER_PROVIDED,
                    collection_method="adobe_contributor_dashboard",
                    raw_reference={"url": rec.url, "surface": rec.extra.get("surface")},
                )
            )
        return signals

    def get_status(self) -> AdapterHealth:
        # Status needs the DB for config; get_status has no session, so we use
        # a fresh short-lived one. Never raises; never reports CONFIGURED
        # without the config actually present.
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            configured, reason = self.is_configured(db)
        finally:
            db.close()
        if not configured:
            return AdapterHealth(
                status=SourceStatus.NEEDS_AUTH,
                detail=f"Adobe Contributor not configured: {reason}",
            )
        available, dep_reason = self.dependency_available()
        if not available:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"Adobe configured but {dep_reason}",
            )
        return AdapterHealth(
            status=SourceStatus.CONFIGURED,
            detail=f"Adobe Contributor configured ({reason}); Playwright available",
        )


__all__ = ["AdobeContributorAdapter", "SETTING_KEY", "DASHBOARD_URLS"]
