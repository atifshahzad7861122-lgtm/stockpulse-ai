"""QA audit remediation tests (SP-001/SP-002/SP-003 + pending_review filter).

Covers the end-to-end QA audit findings fixed in the Pass-A/B repair batch:
- SP-001: queue page_size contract (100 ok, 200 rejected)
- SP-002: compliance checks list returns 200 (no legacy 500)
- SP-003: /api/sources/health lists every registered source (NOT_CHECKED
  until the scheduler runs), reconciling with /api/sources
- pending_review filter: only unreviewed checks
"""

from __future__ import annotations


def test_queue_page_size_contract(client):
    r = client.get("/api/production/queue", params={"page_size": 100})
    assert r.status_code == 200, r.text
    r = client.get("/api/production/queue", params={"page_size": 200})
    assert r.status_code == 422, r.text


def test_compliance_checks_list_200(client):
    r = client.get("/api/compliance/checks", params={"page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body and "pagination" in body


def test_compliance_pending_review_filter(client, db):
    from datetime import UTC, datetime

    from app.models.compliance import ComplianceCheck

    def make_check(reviewed: bool) -> str:
        row = ComplianceCheck(
            check_type="PROMPT_SCREEN",
            prompt_id="qa-audit-probe",
            result="REVIEW",
            risk_level="MEDIUM",
            findings=[],
            explanation="QA audit probe check.",
            review_decision="APPROVED" if reviewed else None,
            reviewed_at=datetime.now(UTC) if reviewed else None,
        )
        db.add(row)
        db.commit()
        return row.id

    pending_id = make_check(False)
    reviewed_id = make_check(True)

    r = client.get(
        "/api/compliance/checks",
        params={"pending_review": True, "page_size": 100},
    )
    assert r.status_code == 200, r.text
    ids = {c["id"] for c in r.json()["data"]}
    assert pending_id in ids
    assert reviewed_id not in ids

    r = client.get("/api/compliance/checks", params={"page_size": 100})
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()["data"]}
    assert pending_id in ids and reviewed_id in ids


def test_source_health_lists_every_source(client, db):
    from app.models.intelligence import TrendSource

    sources = db.query(TrendSource).all()
    assert len(sources) > 0

    r = client.get("/api/sources/health")
    assert r.status_code == 200, r.text
    rows = r.json()
    # One row per registered source — reconciles with /api/sources (SP-003).
    assert len(rows) == len(sources)
    by_source = {h["trend_source_id"]: h for h in rows}
    assert set(by_source) == {s.id for s in sources}
    for s in sources:
        h = by_source[s.id]
        assert h["source_name"] == s.name
        assert h["status"] == "NOT_CHECKED"
        assert h["checked_at"] is None


def test_source_health_surfaces_real_check(client, db):
    from app.models.intelligence import TrendSource
    from app.models.sources import SourceHealth

    src = db.query(TrendSource).first()
    db.add(
        SourceHealth(
            trend_source_id=src.id,
            status="AVAILABLE",
            records_collected=42,
        )
    )
    db.commit()

    rows = client.get("/api/sources/health").json()
    h = next(r for r in rows if r["trend_source_id"] == src.id)
    assert h["status"] == "AVAILABLE"
    assert h["records_collected"] == 42
    assert h["source_name"] == src.name
