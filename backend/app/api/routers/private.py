"""Private Adobe Contributor data (CONTRACT.md §5.19, PHASE2_DESIGN.md §5).

Hard rules (design §11): never mark connected without real data; never fake
earnings/downloads; session config is stored server-side in the settings table
and NEVER echoed back in any response — only presence flags and config state.
``POST /connection/test`` validates config presence/format only; it never
simulates a connection or a successful sync.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import audit_log, bad_request, get_db
from app.models.settings import Setting
from app.schemas.private import (
    AdobeConnectionOut,
    AdobeConnectionUpdate,
    AdobeConnectionUpdateOut,
    CategoryPerformanceOut,
    ConnectionTestOut,
    KeywordPerformanceOut,
    PerformanceSummaryOut,
    PerformanceTotals,
    TrendPoint,
)

router = APIRouter(prefix="/private", tags=["private"])

_ADOBE_KEY = "adobe_contributor"

REQUIRED_CONFIG_STEPS = [
    "session_type: how the session was captured (e.g. 'browser_export')",
    "session_data: cookie/session export from YOUR OWN browser via PUT /api/private/connection "
    "(stored server-side only, never returned)",
]


def _private_models():
    """Phase-2 private models (sibling agent); None until they land."""
    try:
        import app.models.private as pm  # noqa: F401

        return pm
    except ImportError:
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_config(db: Session) -> dict[str, Any]:
    row = db.query(Setting).filter_by(key=_ADOBE_KEY).one_or_none()
    if row is None or not isinstance(row.value, dict):
        return {}
    return dict(row.value)


def _connection_out(cfg: dict[str, Any]) -> AdobeConnectionOut:
    configured = bool(cfg.get("configured"))
    return AdobeConnectionOut(
        status="CONFIGURED" if configured else "NOT_CONFIGURED",
        configured=configured,
        session_type=cfg.get("session_type"),
        required_config=REQUIRED_CONFIG_STEPS,
        last_sync=_parse_dt(cfg.get("last_sync")),
        error=cfg.get("error"),
    )


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


@router.get("/connection", response_model=AdobeConnectionOut)
def get_connection(db: Annotated[Session, Depends(get_db)]):
    """Adobe Contributor connection status. Honest NOT_CONFIGURED default."""
    return _connection_out(_load_config(db))


@router.put("/connection", response_model=AdobeConnectionUpdateOut)
def update_connection(body: AdobeConnectionUpdate, db: Annotated[Session, Depends(get_db)]):
    """Store session config server-side. The response NEVER echoes secrets."""
    if not body.session_data:
        raise bad_request(
            "VALIDATION_ERROR",
            "session_data is required (export it from your own browser).",
        )
    now = datetime.now(UTC).isoformat()
    value = {
        "configured": True,
        "session_type": body.session_type,
        # Secret material: server-side only. Redacted from every API response
        # (see _connection_out and the settings router redaction).
        "session_value": body.session_data,
        "notes": body.notes,
        "last_sync": None,
        "error": None,
        "updated_at": now,
    }
    row = db.query(Setting).filter_by(key=_ADOBE_KEY).one_or_none()
    if row is None:
        db.add(Setting(key=_ADOBE_KEY, value=value))
    else:
        row.value = value
    db.commit()
    # Audit WITHOUT the secret — only presence is logged.
    audit_log(
        db,
        action="update_adobe_connection",
        entity_kind="setting",
        entity_id=_ADOBE_KEY,
        note=f"session_type={body.session_type}; session present (value never logged)",
    )
    db.commit()
    return AdobeConnectionUpdateOut(
        status="CONFIGURED",
        configured=True,
        session_type=body.session_type,
        last_sync=None,
        message="Session config stored server-side. Run POST /connection/test to validate, "
        "then the next scheduled sync will collect real data.",
    )


@router.post("/connection/test", response_model=ConnectionTestOut)
def test_connection(db: Annotated[Session, Depends(get_db)]):
    """Validate config presence/format only — never simulates success or a sync."""
    cfg = _load_config(db)
    missing = [f for f in ("session_type", "session_value") if not cfg.get(f)]
    if not cfg.get("configured"):
        return ConnectionTestOut(
            valid=False,
            missing=REQUIRED_CONFIG_STEPS,
            message="Adobe Contributor is not configured. Store a session via "
            "PUT /api/private/connection first. This check never simulates success.",
        )
    if missing:
        return ConnectionTestOut(
            valid=False,
            missing=missing,
            message=f"Configuration incomplete — missing: {', '.join(missing)}.",
        )
    return ConnectionTestOut(
        valid=True,
        missing=[],
        message="Configuration present and well-formed. This validates presence/format "
        "only — it does not contact Adobe or simulate a successful sync.",
    )


# ---------------------------------------------------------------------------
# Performance (honest empty states when no data)
# ---------------------------------------------------------------------------

_EMPTY_MESSAGE = (
    "No private performance data yet. Configure the Adobe Contributor connection "
    "(PUT /api/private/connection) to start collecting real data from your own "
    "dashboard. Nothing here is estimated or fabricated."
)


def _empty_summary() -> PerformanceSummaryOut:
    return PerformanceSummaryOut(has_data=False, message=_EMPTY_MESSAGE)


@router.get("/performance/summary", response_model=PerformanceSummaryOut)
def performance_summary(db: Annotated[Session, Depends(get_db)]):
    """Personal performance: totals, earnings/download trends, by-category."""
    pm = _private_models()
    if pm is None:
        return _empty_summary()
    try:
        daily = (
            db.query(pm.PrivateDailyEarning)
            .order_by(pm.PrivateDailyEarning.date.asc())
            .limit(365)
            .all()
        )
    except Exception:
        return _empty_summary()
    if not daily:
        return _empty_summary()

    totals = PerformanceTotals(
        earnings=round(sum(float(r.earnings or 0) for r in daily), 2),
        downloads=int(sum(int(r.downloads or 0) for r in daily)),
        currency=getattr(daily[0], "currency", None) or "USD",
        assets_tracked=_assets_tracked(db, pm),
    )
    trend = [
        TrendPoint(
            date=r.date,
            earnings=round(float(r.earnings or 0), 2),
            downloads=int(r.downloads or 0),
        )
        for r in daily[-30:]
    ]
    return PerformanceSummaryOut(
        has_data=True,
        totals=totals,
        earnings_trend=trend,
        downloads_trend=trend,
        by_category=_category_list(db, pm),
        acceptance_rate=_acceptance_rate(db, pm),
    )


@router.get("/performance/categories", response_model=list[CategoryPerformanceOut])
def performance_categories(db: Annotated[Session, Depends(get_db)]):
    """Per-category performance (latest snapshot). Empty list when no data."""
    pm = _private_models()
    if pm is None:
        return []
    return _category_list(db, pm)


@router.get("/performance/keywords", response_model=list[KeywordPerformanceOut])
def performance_keywords(db: Annotated[Session, Depends(get_db)]):
    """Per-keyword performance (latest snapshot). Empty list when no data."""
    pm = _private_models()
    if pm is None:
        return []
    try:
        from sqlalchemy import func as _func

        latest = db.query(_func.max(pm.PrivateKeywordPerformance.snapshot_date)).scalar()
        if latest is None:
            return []
        rows = (
            db.query(pm.PrivateKeywordPerformance)
            .filter(pm.PrivateKeywordPerformance.snapshot_date == latest)
            .order_by(pm.PrivateKeywordPerformance.earnings.desc())
            .limit(100)
            .all()
        )
        return [
            KeywordPerformanceOut(
                keyword=str(r.keyword),
                downloads=int(r.downloads or 0),
                earnings=round(float(r.earnings or 0), 2),
                snapshot_date=r.snapshot_date,
            )
            for r in rows
        ]
    except Exception:
        return []


def _category_list(db: Session, pm) -> list[CategoryPerformanceOut]:
    try:
        from sqlalchemy import func as _func

        latest = db.query(_func.max(pm.PrivateCategoryPerformance.snapshot_date)).scalar()
        if latest is None:
            return []
        rows = (
            db.query(pm.PrivateCategoryPerformance)
            .filter(pm.PrivateCategoryPerformance.snapshot_date == latest)
            .order_by(pm.PrivateCategoryPerformance.earnings.desc())
            .limit(100)
            .all()
        )
        return [
            CategoryPerformanceOut(
                category=str(r.category),
                downloads=int(r.downloads or 0),
                earnings=round(float(r.earnings or 0), 2),
                asset_count=int(r.asset_count or 0),
                snapshot_date=r.snapshot_date,
            )
            for r in rows
        ]
    except Exception:
        return []


def _acceptance_rate(db: Session, pm) -> float | None:
    try:
        from sqlalchemy import func as _func

        accepted = (
            db.query(_func.count())
            .select_from(pm.PrivateSubmissionResult)
            .filter(pm.PrivateSubmissionResult.status == "ACCEPTED")
            .scalar()
            or 0
        )
        rejected = (
            db.query(_func.count())
            .select_from(pm.PrivateSubmissionResult)
            .filter(pm.PrivateSubmissionResult.status == "REJECTED")
            .scalar()
            or 0
        )
        total = accepted + rejected
        return round(accepted / total, 3) if total else None
    except Exception:
        return None


def _assets_tracked(db: Session, pm) -> int:
    try:
        from sqlalchemy import func as _func

        return (
            db.query(_func.count(_func.distinct(pm.PrivateAssetPerformance.asset_external_id)))
            .scalar()
            or 0
        )
    except Exception:
        return 0
