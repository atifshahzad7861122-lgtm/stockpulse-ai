"""Regression tests for the 2026-09-20 live UI audit crash batch.

Covers every root cause found by the interactive production audit:
  1. Compliance subject contract — the API returned an id-column dict
     ({"prompt_id": ...}) while the frontend reads subject.kind/.id,
     which threw a client-side exception on /, /compliance and /planner.
  2. Opportunities sort contract — ascending score and priority sorts
     were rejected with 422, and the error state was unrecoverable.
  3. Ideas detail/edit/archive without the `kind` query hint returned
     422 (drawer showed "Idea not found"); the archive endpoint did not
     exist at all (404).
  4. Frontend: React-19 `use(params)` on React 18 (typecheck/build
     coverage), QueryView empty-Page handling, generate-concepts route.
"""

from __future__ import annotations


def _seed_check(db, **kw):
    from app.models.compliance import ComplianceCheck

    row = ComplianceCheck(
        check_type="PROMPT_SCREEN",
        result="REVIEW",
        risk_level="MEDIUM",
        findings=[],
        explanation="ui audit regression",
        **kw,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. Compliance subject contract: {kind, id, version_id?}
# ---------------------------------------------------------------------------


def test_compliance_subject_shape_kind_id(client, db):
    """Subject must serialize as {kind, id} per the frontend contract."""
    row = _seed_check(db, image_idea_id="11111111-2222-3333-4444-555555555555")
    r = client.get("/api/compliance/checks", params={"page": 1, "page_size": 50})
    assert r.status_code == 200, r.text
    rows = [c for c in r.json()["data"] if c["id"] == row.id]
    assert len(rows) == 1
    subject = rows[0]["subject"]
    assert subject["kind"] == "image_idea"
    assert subject["id"] == "11111111-2222-3333-4444-555555555555"
    # Old broken shape must be gone.
    assert "image_idea_id" not in subject
    assert "prompt_id" not in subject


def test_compliance_subject_includes_version_id(client, db):
    row = _seed_check(
        db,
        prompt_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt_version_id="99999999-8888-7777-6666-555555555555",
    )
    r = client.get("/api/compliance/checks", params={"page": 1, "page_size": 50})
    assert r.status_code == 200, r.text
    rows = [c for c in r.json()["data"] if c["id"] == row.id]
    assert rows[0]["subject"] == {
        "kind": "prompt",
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "version_id": "99999999-8888-7777-6666-555555555555",
    }


def test_compliance_detail_subject_shape(client, db):
    row = _seed_check(db, asset_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    r = client.get(f"/api/compliance/checks/{row.id}")
    assert r.status_code == 200, r.text
    assert r.json()["subject"]["kind"] == "asset"
    assert r.json()["subject"]["id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# 2. Opportunities sort contract
# ---------------------------------------------------------------------------


def _seed_opportunity(db, title, score, priority=0):
    from app.models.intelligence import Opportunity

    row = Opportunity(
        title=title,
        summary=f"summary for {title} — long enough to pass validation",
        opportunity_score=score,
        confidence=0.6,
        demand_evidence=[],
        data_provenance="USER_PROVIDED",
        status="NEW",
        priority=priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_opportunities_sort_ascending_score(client, db):
    _seed_opportunity(db, "QA sort low", 10.0)
    _seed_opportunity(db, "QA sort high", 90.0)
    r = client.get("/api/opportunities", params={"sort": "opportunity_score", "page_size": 50})
    assert r.status_code == 200, r.text
    scores = [o["opportunity_score"] for o in r.json()["data"]]
    assert scores == sorted(scores), scores


def test_opportunities_sort_priority_both_directions(client, db):
    _seed_opportunity(db, "QA prio low", 50.0, priority=1)
    _seed_opportunity(db, "QA prio high", 50.0, priority=9)
    for sort, first in (("-priority", 9), ("priority", 1)):
        r = client.get("/api/opportunities", params={"sort": sort, "page_size": 50})
        assert r.status_code == 200, r.text
        got = [o["priority"] for o in r.json()["data"] if o["title"].startswith("QA prio")]
        assert got[0] == first, (sort, got)


def test_opportunities_sort_still_rejects_garbage(client, db):
    r = client.get("/api/opportunities", params={"sort": "bogus; DROP TABLE"})
    assert r.status_code == 422, r.text
    body = r.json()
    assert set(body.keys()) == {"error"}


# ---------------------------------------------------------------------------
# 3. Ideas: kind-optional detail / patch / delete / promote / archive
# ---------------------------------------------------------------------------


def _make_idea(client, kind="image"):
    body = {
        "kind": kind,
        "title": f"QA idea {kind}",
        "concept": "a concept long enough to pass validation rules",
        "originality_notes": "original notes",
    }
    if kind == "video":
        body["duration_target_seconds"] = 10
    r = client.post("/api/ideas", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_idea_detail_without_kind(client, db):
    idea = _make_idea(client, "image")
    r = client.get(f"/api/ideas/{idea['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == idea["id"]
    assert r.json()["kind"] == "image"


def test_idea_detail_video_without_kind(client, db):
    idea = _make_idea(client, "video")
    r = client.get(f"/api/ideas/{idea['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "video"


def test_idea_detail_unknown_id_404(client, db):
    r = client.get("/api/ideas/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, r.text


def test_idea_patch_without_kind(client, db):
    idea = _make_idea(client, "image")
    r = client.patch(f"/api/ideas/{idea['id']}", json={"title": "QA idea edited title"})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "QA idea edited title"


def test_idea_archive_without_kind(client, db):
    idea = _make_idea(client, "image")
    r = client.post(f"/api/ideas/{idea['id']}/archive")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ARCHIVED"
    # Second archive is a conflict, not a silent no-op.
    r2 = client.post(f"/api/ideas/{idea['id']}/archive")
    assert r2.status_code == 409, r2.text


def test_idea_promote_without_kind(client, db):
    idea = _make_idea(client, "video")
    r = client.post(f"/api/ideas/{idea['id']}/promote")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "READY"


def test_idea_delete_without_kind(client, db):
    idea = _make_idea(client, "image")
    r = client.delete(f"/api/ideas/{idea['id']}")
    assert r.status_code == 204, r.text
    assert client.get(f"/api/ideas/{idea['id']}").status_code == 404


def test_generate_concepts_route_registered():
    """The frontend calls POST /api/ideas/generate-concepts — it must exist."""
    from app.main import app

    paths = {
        (tuple(sorted(route.methods or [])), route.path)
        for route in app.routes
        if hasattr(route, "methods") and hasattr(route, "path")
    }
    assert any(
        "POST" in methods and path == "/api/ideas/generate-concepts"
        for methods, path in paths
    ), sorted(p for _, p in paths if "generate-concepts" in p)


# ---------------------------------------------------------------------------
# 5. Trend detail must agree with list signal_count (FK, not fuzzy name match)
# ---------------------------------------------------------------------------


def test_trend_detail_signals_match_list_count(client, db):
    """Regression: detail used signal_name.contains(topic[:20]) while the list
    counts by trend_snapshot_id FK — a topic like 'GitHub trending AI repos'
    (signals named 'owner/repo') showed signal_count=20 but signals=[]."""
    from app.models.intelligence import TrendSignal, TrendSnapshot

    snapshot = TrendSnapshot(
        trend_source_id="3cfaa5d3-cfde-4451-b96b-2c383819939c",
        payload={"topic": "GitHub trending AI repos", "provenance": "VERIFIED"},
        payload_hash="qa" + "0" * 62,
    )
    db.add(snapshot)
    db.flush()
    for i in range(3):
        db.add(
            TrendSignal(
                trend_snapshot_id=snapshot.id,
                signal_name=f"some-owner/some-repo-{i}",  # does NOT contain topic[:20]
                data_provenance="VERIFIED",
                confidence=0.8,
            )
        )
    db.commit()

    r_list = client.get("/api/trends", params={"page": 1, "page_size": 50})
    assert r_list.status_code == 200, r_list.text
    rows = [t for t in r_list.json()["data"] if t["id"] == snapshot.id]
    assert len(rows) == 1
    assert rows[0]["signal_count"] == 3

    r_detail = client.get(f"/api/trends/{snapshot.id}")
    assert r_detail.status_code == 200, r_detail.text
    detail = r_detail.json()
    assert detail["signal_count"] == 3
    assert len(detail["signals"]) == 3

    r_signals = client.get(f"/api/trends/{snapshot.id}/signals")
    assert r_signals.status_code == 200, r_signals.text
    assert len(r_signals.json()) == 3


def test_trend_detail_signal_breakdown_shape(client, db):
    """SignalBreakdown must carry the documented contract fields, including
    source_name — the frontend renders them directly (a missing field caused
    a client-side crash on the trend detail page)."""
    from app.models.intelligence import TrendSignal, TrendSnapshot, TrendSource
    from app.schemas.enums import DataProvenance, TrendSourceType

    src = TrendSource(
        name="QA Source",
        source_type=TrendSourceType.MARKETPLACE_FEED,
        data_provenance=DataProvenance.VERIFIED,
    )
    db.add(src)
    db.flush()
    snapshot = TrendSnapshot(
        trend_source_id=src.id,
        payload={"topic": "QA topic", "provenance": "VERIFIED"},
        payload_hash="qb" + "0" * 62,
    )
    db.add(snapshot)
    db.flush()
    db.add(
        TrendSignal(
            trend_snapshot_id=snapshot.id,
            signal_name="qa-owner/qa-repo",
            metric_name="stars",
            metric_value=1234,
            metric_unit="count",
            data_provenance="VERIFIED",
            confidence=0.9,
        )
    )
    db.commit()

    r = client.get(f"/api/trends/{snapshot.id}")
    assert r.status_code == 200, r.text
    signals = r.json()["signals"]
    assert len(signals) == 1
    s = signals[0]
    assert s["signal_name"] == "qa-owner/qa-repo"
    assert s["metric_name"] == "stars"
    assert s["metric_value"] == 1234
    assert s["source_name"] == "QA Source"
    assert s["provenance"] == "VERIFIED"
