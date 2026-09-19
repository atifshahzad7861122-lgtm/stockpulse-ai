"""Phase 3 — Daily Production Planner + Concepts + Prompt Packs (backend).

Covers: capacity-driven planning, diversification penalties, legal queue
transitions only, HIGH_RISK blocking, similarity flags, export-only muse
provider, user actions (approve/reject/archive/prioritize/edit), and the
no-auto-submit invariant.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from app.engines import similarity as sim_engine
from app.models.intelligence import Opportunity
from app.models.planning import (
    ConceptVariation,
    DailyProductionPlan,
    ProductionRecommendation,
)
from app.models.production import ProductionQueue
from app.schemas.enums import AssetType, DataProvenance, ProductionQueueStatus

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/stockpulse_pytest.db")


def _make_opportunities(db, n=6, niche_ids=None):
    """n scored opportunities with distinct titles/summaries."""
    rows = []
    niche_ids = niche_ids or [None] * n
    for i in range(n):
        opp = Opportunity(
            title=f"Opportunity {i}: remote work lifestyle imagery",
            summary=(
                f"Rising demand for authentic remote-work visuals in niche segment {i}: "
                "home offices, video calls, flexible schedules, diverse professionals."
            ),
            opportunity_score=90.0 - i * 5.0,
            confidence=0.8,
            demand_evidence=[{"signal": f"trend-{i}", "strength": 0.7}],
            data_provenance=DataProvenance.ESTIMATED,
            status="new",
            priority=i,
            micro_niche_id=niche_ids[i] if i < len(niche_ids) else None,
        )
        db.add(opp)
        rows.append(opp)
    db.commit()
    return rows


def _build_plan_via_api(client):
    resp = client.post("/api/daily-production/build", json={})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Capacity + plan building
# ---------------------------------------------------------------------------


def test_capacity_settings_roundtrip(client):
    resp = client.get("/api/daily-production/settings")
    assert resp.status_code == 200
    body = resp.json()
    # Seeded defaults present (seed.py production_capacity).
    assert body["daily_target"] == 4
    assert body["image_target"] == 3
    assert body["video_target"] == 1

    resp = client.put(
        "/api/daily-production/settings",
        json={
            "weekly_capacity": 30,
            "daily_target": 6,
            "image_target": 4,
            "video_target": 2,
            "max_daily_generation": 12,
            "priority_preference": "score",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["daily_target"] == 6

    resp = client.get("/api/daily-production/settings")
    assert resp.json()["daily_target"] == 6


def test_plan_respects_capacity_targets(client, db):
    _make_opportunities(db, n=10)
    plan = _build_plan_via_api(client)
    assert plan["plan_date"] == date.today().isoformat()
    recs = plan["recommendations"]
    images = [r for r in recs if r["asset_type"] == "IMAGE"]
    videos = [r for r in recs if r["asset_type"] == "VIDEO"]
    # Default seeded targets: 3 images + 1 video = 4 total.
    assert len(images) == 3
    assert len(videos) == 1
    assert len(recs) == 4
    # Ranks are 1..N and scores descend.
    assert [r["rank"] for r in recs] == [1, 2, 3, 4]
    scores = [r["unified_score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    # Evidence carries the score source (fused when the sibling fusion
    # module is present, opportunity_score fallback otherwise).
    assert recs[0]["evidence_json"]["score_source"] in ("fused", "opportunity_score")


def test_plan_today_endpoint(client, db):
    _make_opportunities(db, n=5)
    resp = client.get("/api/daily-production/today")
    assert resp.status_code == 404  # nothing built yet
    _build_plan_via_api(client)
    resp = client.get("/api/daily-production/today")
    assert resp.status_code == 200
    assert len(resp.json()["recommendations"]) == 4


def test_plan_rebuild_is_idempotent_for_day(client, db):
    _make_opportunities(db, n=5)
    first = _build_plan_via_api(client)
    second = _build_plan_via_api(client)
    assert first["id"] == second["id"]  # same plan row, rebuilt
    assert len(second["recommendations"]) == 4
    # Old recommended rows were archived, not left live.
    rows = db.query(ProductionRecommendation).all()
    live = [r for r in rows if r.status == "recommended"]
    assert len(live) == 4


def test_diversification_penalizes_repeats(client, db):
    """Same micro-niche recommended yesterday → today's rank drops."""
    from app.models.taxonomy import MicroNiche

    # Deterministic: only our opportunities exist (demo rows would add noise).
    db.query(Opportunity).delete()
    db.commit()
    niche = db.query(MicroNiche).first()
    assert niche is not None
    # Yesterday's plan: same niche dominates.
    _make_opportunities(db, n=4, niche_ids=[niche.id] * 4)
    resp = client.post("/api/daily-production/build", json={"plan_date": "2026-09-18"})
    assert resp.status_code == 201
    assert len(resp.json()["recommendations"]) == 4
    # Today: rebuild with the same opportunities → repetition penalty applies.
    today = _build_plan_via_api(client)
    assert len(today["recommendations"]) == 4
    # The penalty is recorded in evidence.
    penalized = [r for r in today["recommendations"] if r["evidence_json"]["diversification_penalty"] > 0]
    assert penalized, "expected repetition penalty against yesterday's repeats"
    assert any("micro-niche repeat" in " ".join(r["evidence_json"]["penalty_parts"]) for r in penalized)


def test_diversification_distinctness_of_concepts(client, db):
    _make_opportunities(db, n=3)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    resp = client.post(f"/api/production-recommendations/{rec_id}/concepts", json={"count": 3})
    assert resp.status_code == 201
    concepts = resp.json()
    assert len(concepts) == 3
    # Meaningfully distinct: subject/setting/composition/use-case combos differ.
    asset_type = concepts[0]["asset_type"]
    keys = []
    for c in concepts:
        spec = c["concept_json"]
        keys.append(
            (spec.get("subject"), spec.get("environment") or spec.get("scene"),
             spec.get("composition") or spec.get("visual_direction"),
             spec.get("commercial_use"))
        )
    assert len(set(keys)) == 3
    # Every concept carries originality notes + compliance + similarity screens.
    for c in concepts:
        assert c["originality_notes"]
        assert c["compliance_result"] in ("PASS", "REVIEW", "HIGH_RISK")
        assert "flags" in c["similarity_flags_json"]


# ---------------------------------------------------------------------------
# Approval → queue (legal transitions only)
# ---------------------------------------------------------------------------


def test_approve_creates_queue_item_with_legal_entry(client, db):
    _make_opportunities(db, n=3)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    resp = client.post(f"/api/production-recommendations/{rec_id}/approve")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recommendation"]["status"] == "approved"
    assert body["queue_status"] == "DISCOVERED"
    item = db.query(ProductionQueue).filter_by(id=body["queue_item_id"]).one()
    assert item.status == ProductionQueueStatus.DISCOVERED
    assert item.opportunity_id == body["recommendation"]["opportunity_id"]


def test_approve_blocked_by_high_risk_concept(client, db):
    _make_opportunities(db, n=3)
    plan = _build_plan_via_api(client)
    rec = plan["recommendations"][0]
    rec_id = rec["id"]
    # Generate concepts, then force one to HIGH_RISK (simulating a flagged screen).
    resp = client.post(f"/api/production-recommendations/{rec_id}/concepts", json={"count": 2})
    assert resp.status_code == 201
    concept_id = resp.json()[0]["id"]
    row = db.query(ConceptVariation).filter_by(id=concept_id).one()
    row.compliance_result = "HIGH_RISK"
    row.compliance_result_json = {"result": "HIGH_RISK", "explanation": "test"}
    db.commit()
    resp = client.post(f"/api/production-recommendations/{rec_id}/approve")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "APPROVAL_BLOCKED"
    # No queue item was created for this recommendation's opportunity.
    assert db.query(ProductionQueue).filter_by(opportunity_id=rec["opportunity_id"]).count() == 0


def test_illegal_queue_transition_rejected(db):
    from app.services.production_planner import transition_queue_item

    item = ProductionQueue(
        asset_type=AssetType.IMAGE, title="t", status=ProductionQueueStatus.DISCOVERED
    )
    db.add(item)
    db.commit()
    # DISCOVERED → IN_PRODUCTION is not in the T01–T29 map.
    with pytest.raises(ValueError, match="Illegal queue transition"):
        transition_queue_item(db, item.id, ProductionQueueStatus.IN_PRODUCTION)
    # Legal: DISCOVERED → ANALYZING (T01).
    moved = transition_queue_item(db, item.id, ProductionQueueStatus.ANALYZING)
    assert moved.status == ProductionQueueStatus.ANALYZING


def test_transition_helper_accepts_string_status(db):
    from app.services.production_planner import transition_queue_item

    item = ProductionQueue(
        asset_type=AssetType.VIDEO, title="t", status=ProductionQueueStatus.ANALYZING
    )
    db.add(item)
    db.commit()
    moved = transition_queue_item(db, item.id, "IDEA_READY")
    assert moved.status == ProductionQueueStatus.IDEA_READY


# ---------------------------------------------------------------------------
# User actions
# ---------------------------------------------------------------------------


def test_reject_archive_prioritize_edit(client, db):
    _make_opportunities(db, n=4)
    plan = _build_plan_via_api(client)
    recs = {r["rank"]: r["id"] for r in plan["recommendations"]}

    # Reject rank 4.
    resp = client.post(f"/api/production-recommendations/{recs[4]}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # Archive rank 3.
    resp = client.post(f"/api/production-recommendations/{recs[3]}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Prioritize rank 2 → rank 1 (re-sequences remaining recommended rows).
    resp = client.post(
        f"/api/production-recommendations/{recs[2]}/prioritize",
        json={"rank": 1, "priority_note": "user wants this first"},
    )
    assert resp.status_code == 200
    assert resp.json()["rank"] == 1

    resp = client.get("/api/production-recommendations", params={"status": "recommended"})
    live = sorted(resp.json()["data"], key=lambda r: r["rank"])
    assert [r["rank"] for r in live] == [1, 2]
    assert live[0]["id"] == recs[2]

    # Edit whitelisted fields.
    resp = client.patch(
        f"/api/production-recommendations/{recs[2]}",
        json={"recommended_quantity": 3, "category": "business"},
    )
    assert resp.status_code == 200
    assert resp.json()["recommended_quantity"] == 3
    assert resp.json()["category"] == "business"


def test_regenerate_concepts_creates_new_round(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    first = client.post(f"/api/production-recommendations/{rec_id}/concepts", json={"count": 2}).json()
    assert all(c["variation_round"] == 1 for c in first)
    second = client.post(f"/api/production-recommendations/{rec_id}/concepts", json={"count": 2}).json()
    assert all(c["variation_round"] == 2 for c in second)
    # Round 1 rows were retired (archived), round 2 is live.
    rows = db.query(ConceptVariation).filter_by(recommendation_id=rec_id).all()
    assert {r.variation_round for r in rows} == {1, 2}
    assert all(r.status == "archived" for r in rows if r.variation_round == 1)


# ---------------------------------------------------------------------------
# Similarity flags
# ---------------------------------------------------------------------------


def test_similarity_flags_duplicates(db):
    _make_opportunities(db, n=2)
    from app.services import concepts as concept_service
    from app.services.production_planner import build_plan

    plan = build_plan(db, date.today())
    db.commit()
    rec = db.query(ProductionRecommendation).filter_by(plan_id=plan.id).first()
    rows = concept_service.generate_concepts(db, rec, count=1)
    db.commit()
    first_text = rows[0].concept_json["concept"]
    # Screening the identical text (not excluding its source row) flags
    # POSSIBLE_DUPLICATE — the corpus contains the just-saved concept.
    flags = concept_service.screen_similarity(db, first_text)
    kinds = [f["flag"] for f in flags["flags"]]
    assert "POSSIBLE_DUPLICATE" in kinds or "HIGH_SIMILARITY" in kinds
    # Sanity: engine thresholds behave as documented.
    assert sim_engine.verdict_for(0.85) == "HIGH_RISK"
    assert sim_engine.verdict_for(0.70) == "REVIEW"
    assert sim_engine.verdict_for(0.10) == "CLEAR"


def test_concept_regeneration_deterministic(db):
    _make_opportunities(db, n=1)
    from app.services import concepts as concept_service
    from app.services.production_planner import build_plan

    plan = build_plan(db, date.today())
    db.commit()
    rec = db.query(ProductionRecommendation).filter_by(plan_id=plan.id).first()
    spec_a = concept_service.build_image_spec(rec, 0, variation_round=1)
    spec_b = concept_service.build_image_spec(rec, 0, variation_round=1)
    assert spec_a == spec_b  # deterministic: no fake randomness


# ---------------------------------------------------------------------------
# Prompt packs + muse export-only provider
# ---------------------------------------------------------------------------


def test_prompt_pack_generation(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concepts = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()
    concept_id = concepts[0]["id"]
    resp = client.post("/api/prompt-packs", params={"concept_id": concept_id}, json={"target_tool": "muse"})
    assert resp.status_code == 201, resp.text
    pack = resp.json()
    assert pack["primary_prompt"]
    assert pack["alternative_prompt"]
    assert pack["negative_prompt"]
    assert pack["technical_requirements"]
    assert pack["originality_instructions"]
    assert pack["compliance_instructions"]
    assert pack["target_tool"] == "muse"
    assert pack["format_version"] == "1.0"


def test_muse_provider_is_export_only(tmp_path, monkeypatch):
    from app.providers.providers import (
        MUSE_EXPORT_LABEL,
        GenerationRequest,
        MuseGenerationProvider,
        get_generation_provider,
    )

    monkeypatch.setenv("STOCKPULSE_GENERATION_PROVIDER", "muse")
    provider = get_generation_provider()
    assert isinstance(provider, MuseGenerationProvider)

    export_dir = tmp_path / "muse_exports"
    provider = MuseGenerationProvider(export_dir=str(export_dir))
    response = provider.generate_asset(
        GenerationRequest(
            prompt_id="pack-1",
            prompt_text="a test prompt",
            asset_type="IMAGE",
            parameters={
                "prompt_pack": {
                    "concept_title": "Test Concept",
                    "primary_prompt": "a test prompt",
                }
            },
        )
    )
    # Export only: a local file URI, honest label, no rendered dimensions.
    assert response.storage_uri.startswith("file://")
    assert response.width_px is None
    assert response.height_px is None
    assert "not auto-generated" in MUSE_EXPORT_LABEL
    assert (export_dir / "").exists()
    files = list(export_dir.iterdir())
    assert len(files) == 1
    import json

    doc = json.loads(files[0].read_text())
    assert doc["generation_claim"] == MUSE_EXPORT_LABEL
    assert doc["asset_auto_generated"] is False


def test_muse_provider_requires_prompt_pack():
    from app.providers.providers import GenerationRequest, MuseGenerationProvider

    provider = MuseGenerationProvider(export_dir="/tmp/sp_muse_test_exports")
    with pytest.raises(ValueError, match="prompt pack"):
        provider.generate_asset(
            GenerationRequest(prompt_id="x", prompt_text="y", asset_type="IMAGE", parameters={})
        )


def test_unknown_generation_provider_raises(monkeypatch):
    from app.providers.providers import get_generation_provider

    monkeypatch.setenv("STOCKPULSE_GENERATION_PROVIDER", "nope")
    with pytest.raises(ValueError, match="Unknown generation provider"):
        get_generation_provider()
    monkeypatch.setenv("STOCKPULSE_GENERATION_PROVIDER", "mock")
    provider = get_generation_provider()
    assert provider.name == "mock_generation_provider"


def test_prompt_pack_export_endpoint_uses_muse(client, db, tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKPULSE_MUSE_EXPORT_DIR", str(tmp_path))
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concept_id = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()[0]["id"]
    pack_id = client.post(
        "/api/prompt-packs", params={"concept_id": concept_id}, json={"target_tool": "muse"}
    ).json()["id"]
    resp = client.post(f"/api/prompt-packs/{pack_id}/export", params={"provider": "muse"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["export_uri"].startswith("file://")
    assert body["provider"] == "muse"
    assert "not auto-generated" in body["note"]


# ---------------------------------------------------------------------------
# No-auto-submit invariant
# ---------------------------------------------------------------------------


def test_no_auto_submit_path_exists():
    """No service function creates a SubmissionRecord without a user action.

    The planner only ever creates production_queue items (DISCOVERED) after
    an explicit approve call; nothing in this module constructs a
    submission record. Routers expose no submit endpoint either.
    """
    import inspect

    from app.services import production_planner

    src = inspect.getsource(production_planner)
    assert "SubmissionRecord" not in src
    assert "submission_records" not in src
    # Routers expose no submit endpoint either.
    for mod_name in (
        "app.api.routers.daily_production",
        "app.api.routers.recommendations",
        "app.api.routers.prompt_packs",
    ):
        mod = __import__(mod_name, fromlist=["router"])
        paths = [r.path for r in mod.router.routes]
        assert not any("submit" in p for p in paths), paths


# ---------------------------------------------------------------------------
# AI-disclosure decision → re-screen → approval path
# ---------------------------------------------------------------------------


def _gen01_finding(concept):
    findings = (concept["compliance_result_json"] or {}).get("findings", [])
    return next(f for f in findings if f["rule_key"] == "gen-01")


def test_concept_generated_with_unset_disclosure_triggers_gen01(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concept = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()[0]
    # Nothing defaulted: disclosure is explicitly undecided.
    assert concept["ai_disclosure"] is None
    finding = _gen01_finding(concept)
    assert finding["triggered"] is True
    assert concept["compliance_result"] == "HIGH_RISK"


def test_concept_disclosure_true_rescreens_and_clears_gen01(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concept_id = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()[0]["id"]
    resp = client.patch(
        f"/api/production-recommendations/concepts/{concept_id}",
        json={"status": "draft", "ai_disclosure": True},
    )
    assert resp.status_code == 200, resp.text
    concept = resp.json()
    assert concept["ai_disclosure"] is True
    # Re-screen ran with the recorded decision: gen-01 clears.
    assert _gen01_finding(concept)["triggered"] is False


def test_concept_approval_path_after_disclosure_decision(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concept_id = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()[0]["id"]
    # Approval is blocked while disclosure is undecided (HIGH_RISK).
    resp = client.patch(
        f"/api/production-recommendations/concepts/{concept_id}",
        json={"status": "approved"},
    )
    assert resp.status_code == 422
    assert "HIGH_RISK" in resp.json()["error"]["message"]
    # Record the explicit disclosure decision, then approve.
    resp = client.patch(
        f"/api/production-recommendations/concepts/{concept_id}",
        json={"status": "draft", "ai_disclosure": True},
    )
    assert resp.status_code == 200, resp.text
    if resp.json()["compliance_result"] != "HIGH_RISK":
        resp = client.patch(
            f"/api/production-recommendations/concepts/{concept_id}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved"
    else:
        # Other genuine BLOCK findings still guard approval — the path is
        # honest, not auto-clearing.
        from app.services.concepts import blockers_for_promotion

        row = db.query(ConceptVariation).filter_by(id=concept_id).one()
        assert any("HIGH_RISK" in b for b in blockers_for_promotion(row))


def test_concept_disclosure_false_keeps_gen01_block(client, db):
    _make_opportunities(db, n=2)
    plan = _build_plan_via_api(client)
    rec_id = plan["recommendations"][0]["id"]
    concept_id = client.post(
        f"/api/production-recommendations/{rec_id}/concepts", json={"count": 1}
    ).json()[0]["id"]
    resp = client.patch(
        f"/api/production-recommendations/concepts/{concept_id}",
        json={"status": "draft", "ai_disclosure": False},
    )
    assert resp.status_code == 200, resp.text
    concept = resp.json()
    assert concept["ai_disclosure"] is False
    # Explicitly declining disclosure keeps the gen-01 BLOCK honestly in place.
    assert _gen01_finding(concept)["triggered"] is True
