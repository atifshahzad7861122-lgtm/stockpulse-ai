"""End-to-end flow: opportunity → idea → prompt → compliance → production queue.

Uses the API surface exactly as the frontend would.
"""

from __future__ import annotations

from app.schemas.enums import AssetType


def _poll_job(client, job_id: str) -> dict:
    r = client.get(f"/api/agents/jobs/{job_id}")
    assert r.status_code == 200, r.text
    return r.json()


def test_full_pipeline_flow(client, db):
    # 1. Opportunity (human-created record).
    r = client.post(
        "/api/opportunities",
        json={
            "title": "Solar installers at golden hour",
            "summary": "Commercial demand for renewable-energy workforce imagery.",
        },
    )
    assert r.status_code == 201, r.text
    opp_id = r.json()["id"]

    # Approve it.
    r = client.post(f"/api/opportunities/{opp_id}/approve", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # 2. Image idea from the opportunity.
    r = client.post(
        "/api/ideas",
        json={
            "kind": "image",
            "title": "Solar crew on a rooftop at sunset",
            "concept": (
                "Two installers in safety gear securing a solar panel on a residential "
                "rooftop, warm backlight, shallow depth of field, commercial energy theme."
            ),
            "originality_notes": "Workforce angle differentiates from empty-panel stock.",
            "opportunity_id": opp_id,
        },
    )
    assert r.status_code == 201, r.text
    idea_id = r.json()["id"]

    # 3. Prompt via the prompt agent (job runs synchronously).
    r = client.post(
        "/api/prompts/generate",
        json={"idea_id": idea_id, "asset_type": AssetType.IMAGE.value, "tool": "midjourney"},
    )
    assert r.status_code == 202, r.text
    job = _poll_job(client, r.json()["job_id"])
    assert job["status"] == "succeeded"
    prompt_id = job["output_summary"].get("prompt_id")
    assert prompt_id, job["output_summary"]

    # Prompt versioning: add a second version, then activate it.
    r = client.post(
        f"/api/prompts/{prompt_id}/versions",
        json={
            "prompt_text": "Revised prompt text with warmer light direction.",
            "change_summary": "Warmer light direction per review.",
        },
    )
    assert r.status_code == 201, r.text
    v2 = r.json()["version_number"]
    assert v2 == 2

    r = client.post(f"/api/prompts/{prompt_id}/versions/{v2}/activate")
    assert r.status_code == 200
    assert r.json()["current_version"]["version_number"] == 2

    # 4. Compliance screen on the prompt.
    r = client.post(
        "/api/compliance/checks",
        json={
            "check_type": "PROMPT_SCREEN",
            "subject_kind": "prompt",
            "subject_id": prompt_id,
        },
    )
    assert r.status_code == 202, r.text
    check_job = _poll_job(client, r.json()["job_id"])
    assert check_job["status"] == "succeeded"
    assert check_job["output_summary"]["result"] in ("PASS", "REVIEW", "HIGH_RISK")

    # 5. Enqueue for production (compliance gate enforced when subject linked).
    r = client.post(
        "/api/production/queue",
        json={
            "asset_type": AssetType.IMAGE.value,
            "title": "Solar crew rooftop",
            "opportunity_id": opp_id,
            "image_idea_id": idea_id,
            "prompt_id": prompt_id,
            "priority_band": "P1",
        },
    )
    assert r.status_code in (201, 422), r.text
    if r.status_code == 201:
        queue_id = r.json()["id"]
        assert r.json()["status"] == "DISCOVERED"
        # Automated recommendations stop at DISCOVERED/IDEA_READY (no auto-advance).
        r = client.get(f"/api/production/queue/{queue_id}")
        assert r.json()["status"] == "DISCOVERED"
