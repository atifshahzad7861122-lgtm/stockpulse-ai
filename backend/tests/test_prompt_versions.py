"""Prompt versioning: immutable history, latest never rewritten, activation."""

from __future__ import annotations

from app.models.ideation import ImageIdea
from app.models.prompts import Prompt, PromptVersion
from app.schemas.enums import AssetType, IdeaStatus


def _idea(db) -> ImageIdea:
    idea = ImageIdea(
        title="prompt version fixture",
        concept="A desert caravan at dusk.",
        originality_notes="Fixture notes.",
        status=IdeaStatus.DRAFT,
    )
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea


def test_prompt_generate_creates_v1_and_sets_current(client, db):
    idea = _idea(db)
    r = client.post(
        "/api/prompts/generate",
        json={"idea_id": idea.id, "asset_type": AssetType.IMAGE.value, "tool": "midjourney"},
    )
    assert r.status_code == 202
    job = client.get(f"/api/agents/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "succeeded"
    prompt_id = job["output_summary"]["prompt_id"]

    prompt = db.query(Prompt).filter_by(id=prompt_id).one()
    assert prompt.current_version_id is not None
    versions = db.query(PromptVersion).filter_by(prompt_id=prompt_id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].id == prompt.current_version_id


def test_new_version_never_rewrites_latest(client, db):
    idea = _idea(db)
    r = client.post(
        "/api/prompts/generate",
        json={"idea_id": idea.id, "asset_type": AssetType.IMAGE.value, "tool": "midjourney"},
    )
    prompt_id = client.get(f"/api/agents/jobs/{r.json()['job_id']}").json()["output_summary"][
        "prompt_id"
    ]
    v1_text = (
        db.query(PromptVersion).filter_by(prompt_id=prompt_id, version_number=1).one().prompt_text
    )

    r = client.post(
        f"/api/prompts/{prompt_id}/versions",
        json={"prompt_text": "Second version text.", "change_summary": "Refined."},
    )
    assert r.status_code == 201
    assert r.json()["version_number"] == 2

    # v1 text untouched.
    v1 = db.query(PromptVersion).filter_by(prompt_id=prompt_id, version_number=1).one()
    assert v1.prompt_text == v1_text
    # current_version_id still points at v1 until activation.
    prompt = db.query(Prompt).filter_by(id=prompt_id).one()
    assert prompt.current_version_id == v1.id

    # Activate v2.
    r = client.post(f"/api/prompts/{prompt_id}/versions/2/activate")
    assert r.status_code == 200
    assert r.json()["current_version"]["version_number"] == 2

    # Version list is complete history.
    r = client.get(f"/api/prompts/{prompt_id}/versions")
    assert [v["version_number"] for v in r.json()] == [2, 1]


def test_patch_prompt_never_rewrites_version(client, db):
    idea = _idea(db)
    r = client.post(
        "/api/prompts/generate",
        json={"idea_id": idea.id, "asset_type": AssetType.IMAGE.value, "tool": "midjourney"},
    )
    prompt_id = client.get(f"/api/agents/jobs/{r.json()['job_id']}").json()["output_summary"][
        "prompt_id"
    ]

    r = client.patch(f"/api/prompts/{prompt_id}", json={"name": "Renamed prompt"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed prompt"
    # Exactly one version still; the latest version text was not rewritten.
    assert r.json()["versions_count"] == 1
