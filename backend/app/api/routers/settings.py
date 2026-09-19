"""Settings (CONTRACT.md §5.15). Single-user: no auth, no project scoping."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import audit_log, bad_request, get_db, not_found
from app.models.settings import Setting
from app.schemas.common import FeatureFlags
from app.schemas.settings import CANONICAL_SETTING_KEYS, SettingOut, SettingUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

_CANONICAL = set(CANONICAL_SETTING_KEYS)

# Settings keys whose values contain secret material. These are NEVER returned
# verbatim — readers get a redacted presence-only view instead.
_SENSITIVE_KEYS = {"adobe_contributor"}


def _redact_value(key: str, value):
    """Strip secret material from sensitive settings (Phase 2, design §11)."""
    if key not in _SENSITIVE_KEYS or not isinstance(value, dict):
        return value
    return {
        "configured": bool(value.get("configured")),
        "session_type": value.get("session_type"),
        "last_sync": value.get("last_sync"),
        "error": value.get("error"),
        "updated_at": value.get("updated_at"),
        "redacted": True,
    }


def _public_value(key: str, value):
    """Unwrap the {"value": ...} storage envelope so readers get raw values.

    Seed rows store {"value": x}; the redaction step runs first for sensitive
    keys. Anything not in envelope form passes through untouched.
    """
    v = _redact_value(key, value)
    if isinstance(v, dict) and set(v.keys()) == {"value"}:
        return v["value"]
    return v


def _out(row: Setting) -> SettingOut:
    return SettingOut.model_validate(row)


@router.get("", response_model=dict[str, Any])
def get_all_settings(db: Annotated[Session, Depends(get_db)]):
    """Full settings map (single-user; no project scoping).

    Secret-bearing keys (e.g. ``adobe_contributor``) are redacted — only
    presence/configured flags are exposed, never session material.
    """
    rows = db.query(Setting).order_by(Setting.key).all()
    return {r.key: _public_value(r.key, r.value) for r in rows}


@router.patch("", response_model=dict[str, Any])
def bulk_update_settings(body: dict[str, Any], db: Annotated[Session, Depends(get_db)]):
    """Bulk update settings. Accepts {"key": value} or {"settings": [{"key": k, "value": v}]}."""
    if isinstance(body.get("settings"), list):
        updates = {item["key"]: item.get("value") for item in body["settings"] if isinstance(item, dict) and "key" in item}
    else:
        updates = {k: v for k, v in body.items() if k != "settings"}
    if not updates:
        raise bad_request("EMPTY_SETTINGS_PATCH", "No settings provided.")
    for key, value in updates.items():
        if key in _SENSITIVE_KEYS:
            raise bad_request(
                "SENSITIVE_SETTING_KEY",
                f"Setting '{key}' cannot be written here — use PUT /api/private/connection.",
                key=key,
            )
        if key not in _CANONICAL and not key.startswith("feature."):
            raise bad_request(
                "UNKNOWN_SETTING_KEY",
                f"Setting '{key}' is not a canonical key and cannot be created.",
                key=key,
            )
        row = db.query(Setting).filter_by(key=key).one_or_none()
        if row is None:
            row = Setting(key=key, value={"value": value})
            db.add(row)
        else:
            before = row.value
            row.value = {"value": value}
            audit_log(
                db,
                action="update_setting",
                entity_kind="setting",
                entity_id=row.id,
                before={"value": before},
                after={"value": value},
            )
    db.commit()
    rows = db.query(Setting).order_by(Setting.key).all()
    return {r.key: _public_value(r.key, r.value) for r in rows}


@router.get("/keys", response_model=list[str])
def list_canonical_keys():
    return list(CANONICAL_SETTING_KEYS)


@router.get("/feature-flags", response_model=FeatureFlags)
def feature_flags(db: Annotated[Session, Depends(get_db)]):
    rows = db.query(Setting).filter(Setting.key.like("feature.%")).all()
    return FeatureFlags(flags={r.key[len("feature.") :]: bool(r.value) for r in rows})


@router.get("/{key}", response_model=SettingOut)
def get_setting(key: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(Setting).filter_by(key=key).one_or_none()
    if row is None:
        raise not_found("SETTING_NOT_FOUND", f"Setting '{key}' not found.")
    if key in _SENSITIVE_KEYS:
        # Never echo secret material (Phase 2, design §11).
        row = Setting(
            id=row.id,
            key=row.key,
            value=_redact_value(key, row.value),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    return _out(row)


@router.patch("/{key}", response_model=SettingOut)
def update_setting(key: str, body: SettingUpdate, db: Annotated[Session, Depends(get_db)]):
    if key in _SENSITIVE_KEYS:
        # Secret-bearing keys are managed through their dedicated router so the
        # stored secret can never be echoed back (Phase 2, design §11).
        raise bad_request(
            "SENSITIVE_SETTING_KEY",
            f"Setting '{key}' cannot be written here — use PUT /api/private/connection.",
            key=key,
        )
    row = db.query(Setting).filter_by(key=key).one_or_none()
    if row is None:
        if key not in _CANONICAL and not key.startswith("feature."):
            raise bad_request(
                "UNKNOWN_SETTING_KEY",
                f"Setting '{key}' is not a canonical key and cannot be created.",
            )
        row = Setting(key=key, value=body.value)
        db.add(row)
    else:
        before = row.value
        row.value = body.value
        audit_log(
            db,
            action="update_setting",
            entity_kind="setting",
            entity_id=row.id,
            before={"value": before},
            after={"value": body.value},
        )
    db.commit()
    db.refresh(row)
    return _out(row)
