"""Backend QA hardening regression tests (2026-09-20).

Covers:
1. The two black-box 500s reported on old production — GET /api/compliance/checks
   (legacy findings rows missing rule_version/explanation) and GET /api/assets
   (Asset.versions relationship) — must return 200.
2. C2: /docs, /redoc and /openapi.json are disabled when APP_ENV=production,
   exposed otherwise.
3. 422 normalization: raw FastAPI RequestValidationError responses are wrapped
   in the CONTRACT error envelope (E-VAL-801, severity warning, retryable False,
   HTTP 422 kept, field errors under details.errors); explicit APIError 422s
   (e.g. ILLEGAL_TRANSITION) keep their own codes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_SCRIPT = r"""
import asyncio, httpx, sys
sys.path.insert(0, {backend_dir!r})
from app.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        out = []
        for path in ("/docs", "/redoc", "/openapi.json"):
            r = await c.get(path)
            out.append((path, r.status_code))
        print(__import__("json").dumps(out))

asyncio.run(main())
""".replace(
    "{backend_dir!r}", repr(BACKEND_DIR)
)


def _docs_statuses(app_env: str) -> dict[str, int]:
    env = dict(os.environ)
    env["APP_ENV"] = app_env
    env["DATABASE_URL"] = "sqlite:////tmp/qa_docs_probe.db"
    env["STOCKPULSE_SCHEDULER_ENABLED"] = "false"
    proc = subprocess.run(
        [sys.executable, "-c", PROBE_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        cwd=BACKEND_DIR,
        timeout=120,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr[-2000:]}"
    return dict(json.loads(proc.stdout.strip()))


def test_docs_disabled_in_production():
    statuses = _docs_statuses("production")
    assert statuses["/docs"] == 404
    assert statuses["/redoc"] == 404
    assert statuses["/openapi.json"] == 404


def test_docs_exposed_in_dev():
    statuses = _docs_statuses("local")
    assert statuses["/docs"] == 200
    assert statuses["/redoc"] == 200
    assert statuses["/openapi.json"] == 200


def test_compliance_checks_legacy_findings_no_500(client, db):
    """Legacy findings rows without rule_version/explanation must not 500."""
    from app.models.compliance import ComplianceCheck

    row = ComplianceCheck(
        check_type="PROMPT_SCREEN",
        result="REVIEW",
        risk_level="MEDIUM",
        findings=[
            {
                "check_id": "legacy",
                "rule_key": "LOGO",
                "severity": "high",
                "triggered": True,
            }
        ],
        explanation="legacy row",
    )
    db.add(row)
    db.commit()

    r = client.get("/api/compliance/checks", params={"page": 1, "page_size": 50})
    assert r.status_code == 200, r.text
    rows = [c for c in r.json()["data"] if c["id"] == row.id]
    assert len(rows) == 1
    finding = rows[0]["findings"][0]
    assert finding["rule_version"] == "1.0.0"
    assert finding["explanation"] == ""


def test_assets_list_with_versions_no_500(client, db):
    """Asset.versions relationship must serialize (pre-fix AttributeError → 500)."""
    from app.models.production import Asset, AssetVersion

    asset = Asset(title="QA asset", asset_type="IMAGE", status="DRAFT")
    db.add(asset)
    db.flush()
    db.add(
        AssetVersion(
            asset_id=asset.id,
            version_number=1,
            storage_uri="file:///tmp/qa.png",
            mime_type="image/png",
        )
    )
    db.commit()

    r = client.get("/api/assets")
    assert r.status_code == 200, r.text
    rows = [a for a in r.json()["data"] if a["id"] == asset.id]
    assert len(rows) == 1
    assert rows[0]["current_version"] is not None
    assert rows[0]["current_version"]["version_number"] == 1


def test_validation_422_uses_error_envelope(client):
    """Raw FastAPI 422s are wrapped in the CONTRACT envelope, HTTP 422 kept."""
    r = client.get("/api/production/queue", params={"page_size": 200})
    assert r.status_code == 422, r.text
    body = r.json()
    assert set(body.keys()) == {"error"}, body.keys()
    err = body["error"]
    assert err["code"] == "E-VAL-801"
    assert err["severity"] == "warning"
    assert err["retryable"] is False
    assert err["message"]
    assert err["request_id"]
    assert err["trace_id"]
    field_errors = err["details"]["errors"]
    assert isinstance(field_errors, list) and field_errors
    assert field_errors[0]["field"] == "query.page_size"
    assert "message" in field_errors[0] and "type" in field_errors[0]


def test_validation_422_body_error_envelope(client):
    """Body validation errors (e.g. bad enum) also use the envelope."""
    r = client.post(
        "/api/production/queue/00000000-0000-0000-0000-000000000000/transition",
        json={"to": "BOGUS_STATUS"},
    )
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "E-VAL-801"
    assert err["severity"] == "warning"
    assert "body.to" in err["details"]["errors"][0]["field"]
