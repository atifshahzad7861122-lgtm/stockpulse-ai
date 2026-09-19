"""Core API endpoints: health, categories, opportunities, settings, queue,
production flow, metadata CRUD, MOCK labeling."""

from __future__ import annotations

from app.models.ideation import ImageIdea
from app.models.intelligence import Opportunity, TrendSnapshot
from app.models.production import Asset, MetadataRecord, ProductionQueue
from app.schemas.enums import AssetType, IdeaStatus, ProductionQueueStatus


def _enable_dev_mode(db) -> None:
    """Flip the seeded dev_mode setting on (MOCK rows drive intelligence)."""
    from app.models.settings import Setting

    row = db.query(Setting).filter_by(key="dev_mode").one()
    row.value = {"value": True}
    db.commit()


def _add_mock_trend(db) -> None:
    db.add(
        TrendSnapshot(
            trend_source_id="demo-source",
            payload={"topic": "solar panels", "trend_score": 67.05},
            payload_hash="test-hash-1",
        )
    )
    db.commit()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["service"] == "stockpulse-ai"


def test_categories_full_depth(client):
    r = client.get("/api/categories", params={"page_size": 50})
    assert r.status_code == 200
    cats = r.json()["data"]
    assert len(cats) == 39
    # Full depth lives on the detail endpoint.
    for cat in cats:
        r = client.get(f"/api/categories/{cat['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert 2 <= len(detail["subcategories"]) <= 4
        for sub in detail["subcategories"]:
            assert 2 <= len(sub["micro_niches"]) <= 3


def test_opportunities_list(client):
    r = client.get("/api/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body and "pagination" in body


def test_settings_get_put(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "opportunity.min_score" in r.json()

    r = client.patch("/api/settings/opportunity.min_score", json={"value": 60})
    assert r.status_code == 200
    assert r.json()["value"] == 60

    r = client.get("/api/settings")
    assert r.json()["opportunity.min_score"] == 60


def test_queue_create_and_legal_transition(client, db):
    r = client.post(
        "/api/production/queue",
        json={"asset_type": "IMAGE", "title": "Test queue item", "priority_band": "P2"},
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]
    assert r.json()["status"] == "DISCOVERED"

    r = client.post(f"/api/production/queue/{item_id}/transition", json={"to": "ANALYZING"})
    assert r.status_code == 200
    assert r.json()["status"] == "ANALYZING"


def test_queue_illegal_transition_422_explains(client, db):
    item = ProductionQueue(
        asset_type=AssetType.IMAGE,
        title="illegal transition fixture",
        status=ProductionQueueStatus.READY_TO_UPLOAD,
        priority_band="P2",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    r = client.post(
        f"/api/production/queue/{item.id}/transition",
        json={"to": "DISCOVERED"},
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "ILLEGAL_TRANSITION"
    assert err["message"]
    assert "allowed" in err.get("details", {}) or "details" in err


def test_trends_mock_label(client, db):
    _enable_dev_mode(db)  # Phase 2: MOCK rows are excluded unless dev_mode is on
    _add_mock_trend(db)
    r = client.get("/api/trends")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]
    for t in body["data"]:
        assert t["provenance"] == "MOCK"
        assert t["mock"] is True


def test_opportunities_mock_label(client, db):
    _enable_dev_mode(db)  # Phase 2: MOCK rows are excluded unless dev_mode is on
    db.add(
        Opportunity(
            title="Demo opportunity",
            summary="Demo row for MOCK labeling.",
            opportunity_score=64.85,
            confidence=0.825,
            data_provenance="MOCK",
            status="new",
        )
    )
    db.commit()
    r = client.get("/api/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]
    for o in body["data"]:
        assert o["provenance"] == "MOCK"
        assert o["mock"] is True


def test_ideas_mock_label(client, db):
    db.add(
        ImageIdea(
            title="Demo image idea",
            concept="A demo concept",
            originality_notes="Demo originality notes.",
            agent_run_id="test-run-id",
            status=IdeaStatus.DRAFT,
        )
    )
    db.commit()
    r = client.get("/api/ideas?kind=image")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]
    for idea in body["data"]:
        assert idea["provenance"] == "MOCK"
        assert idea["mock"] is True


def test_metadata_crud_contract(client, db):
    asset = Asset(
        asset_type=AssetType.IMAGE,
        title="Metadata test asset",
        status="DRAFT",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    # POST /metadata starts a job (body: { asset_id } per CONTRACT §5.10)
    r = client.post("/api/metadata", json={"asset_id": asset.id})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    r = client.get(f"/api/agents/jobs/{job_id}")
    assert r.status_code == 200

    # GET /metadata lists generated rows
    r = client.get("/api/metadata")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) >= 1
    meta_id = rows[0]["id"]

    # GET /metadata/{id}
    r = client.get(f"/api/metadata/{meta_id}")
    assert r.status_code == 200

    # PATCH /metadata/{id} creates a new version
    r = client.patch(f"/api/metadata/{meta_id}", json={"title": "Updated title here"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated title here"
    new_id = r.json()["id"]
    assert new_id != meta_id

    # Old row is no longer current
    r = client.get(f"/api/metadata/{meta_id}")
    assert r.json()["is_current"] is False


def test_metadata_validate_hard_violation_400(client, db):
    row = MetadataRecord(
        asset_id="test-asset-id",
        title="x",
        keywords=[f"keyword{i}" for i in range(60)],  # exceeds KEYWORDS_MAX → hard error
        version_number=1,
        is_current=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    r = client.post(f"/api/metadata/{row.id}/validate")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
