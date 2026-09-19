"""Production queue transitions: every legal T01–T29 edge succeeds; every other
(valid-enum) pair returns 422 with an explanation (CONTRACT.md §5.11)."""

from __future__ import annotations

import pytest

from app.engines.queue import is_legal_transition
from app.models.compliance import ComplianceCheck
from app.models.ideation import ImageIdea
from app.models.production import ProductionQueue
from app.schemas.enums import (
    ALLOWED_QUEUE_TRANSITIONS,
    AssetType,
    ComplianceCheckType,
    ComplianceResult,
    IdeaStatus,
    ProductionQueueStatus,
    RiskLevel,
)

# Transitions gated on a compliance PASS (production.py: transition).
COMPLIANCE_GATED = {
    ProductionQueueStatus.APPROVED,
    ProductionQueueStatus.READY_TO_UPLOAD,
    ProductionQueueStatus.SUBMITTED,
}

ALL_STATES = list(ProductionQueueStatus)
EXPECTED_T_COUNT = 29


def _make_item(
    db, status: ProductionQueueStatus, to_status: ProductionQueueStatus | None = None
) -> ProductionQueue:
    item = ProductionQueue(
        asset_type=AssetType.IMAGE,
        title=f"transition test {status.value}",
        status=status,
        priority_band="P2",
    )
    db.add(item)
    db.flush()
    if to_status in COMPLIANCE_GATED:
        # Compliance-sensitive transitions require a linked subject with a PASS check.
        idea = ImageIdea(
            title="gated idea",
            concept="A gated test concept for compliance-sensitive transitions.",
            originality_notes="Test originality notes.",
            status=IdeaStatus.DRAFT,
        )
        db.add(idea)
        db.flush()
        item.image_idea_id = idea.id
        db.add(
            ComplianceCheck(
                check_type=ComplianceCheckType.PROMPT_SCREEN,
                image_idea_id=idea.id,
                result=ComplianceResult.PASS,
                risk_level=RiskLevel.LOW,
                findings=[],
                explanation="Test PASS for compliance-gated transitions.",
            )
        )
    db.commit()
    db.refresh(item)
    return item


def test_t01_t29_map_has_29_edges():
    total = sum(len(v) for v in ALLOWED_QUEUE_TRANSITIONS.values())
    assert total == EXPECTED_T_COUNT


def test_legal_transitions_engine_level():
    assert is_legal_transition(ProductionQueueStatus.DISCOVERED, ProductionQueueStatus.ANALYZING)
    assert is_legal_transition(
        ProductionQueueStatus.ARCHIVED, ProductionQueueStatus.DISCOVERED
    )  # T29 unarchive
    assert not is_legal_transition(ProductionQueueStatus.DISCOVERED, ProductionQueueStatus.APPROVED)


@pytest.mark.parametrize(
    "from_status,to_status",
    [(f, t) for f, targets in ALLOWED_QUEUE_TRANSITIONS.items() for t in targets],
    ids=lambda p: p.value,
)
def test_all_legal_transitions_succeed(client, db, from_status, to_status):
    item = _make_item(db, from_status, to_status)
    r = client.post(f"/api/production/queue/{item.id}/transition", json={"to": to_status.value})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == to_status.value


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (f, t)
        for f in ALL_STATES
        for t in ALL_STATES
        if t not in ALLOWED_QUEUE_TRANSITIONS.get(f, ())
    ],
    ids=lambda p: p.value,
)
def test_all_illegal_transitions_return_422(client, db, from_status, to_status):
    item = _make_item(db, from_status)
    r = client.post(f"/api/production/queue/{item.id}/transition", json={"to": to_status.value})
    assert r.status_code == 422, f"{from_status}->{to_status}: {r.text}"
    body = r.json()["error"]
    assert body["code"] == "ILLEGAL_TRANSITION"
    assert "message" in body and body["message"]


def test_archived_not_reachable_from_every_state():
    # The T01–T29 map is authoritative: ARCHIVED is reachable only from the
    # states that list it explicitly (not "from every state").
    archived_sources = {
        f
        for f, targets in ALLOWED_QUEUE_TRANSITIONS.items()
        if ProductionQueueStatus.ARCHIVED in targets
    }
    assert archived_sources == {
        ProductionQueueStatus.DISCOVERED,
        ProductionQueueStatus.ANALYZING,
        ProductionQueueStatus.IDEA_READY,
        ProductionQueueStatus.PROMPT_READY,
        ProductionQueueStatus.APPROVED,
        ProductionQueueStatus.COMPLIANCE_REVIEW,
        ProductionQueueStatus.READY_TO_UPLOAD,
        ProductionQueueStatus.ACCEPTED,
        ProductionQueueStatus.REJECTED,
    }
    # e.g. SUBMITTED cannot archive directly
    assert ProductionQueueStatus.SUBMITTED not in archived_sources
