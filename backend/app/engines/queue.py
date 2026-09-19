"""Production queue state-machine helpers (docs: 20_PRODUCTION_PIPELINE §5–§6).

Legal transitions: the explicit T01–T29 map in schemas.enums
(ALLOWED_QUEUE_TRANSITIONS) is authoritative; unlisted transitions are
illegal. Pause is a flag, not a state; forbidden in
SUBMITTED/ACCEPTED/REJECTED/ARCHIVED.
"""

from __future__ import annotations

from app.schemas.enums import ALLOWED_QUEUE_TRANSITIONS, ProductionQueueStatus

# States where the pause flag is forbidden (docs: 20 §5)
PAUSE_FORBIDDEN_STATES = frozenset(
    {
        ProductionQueueStatus.SUBMITTED,
        ProductionQueueStatus.ACCEPTED,
        ProductionQueueStatus.REJECTED,
        ProductionQueueStatus.ARCHIVED,
    }
)

_TRANSITION_IDS: dict[tuple[ProductionQueueStatus, ProductionQueueStatus], str] = {}
for _from, _tos in ALLOWED_QUEUE_TRANSITIONS.items():
    for _to in _tos:
        # T-numbers are informational (T01…T29 per CONTRACT §4.3 table order)
        _TRANSITION_IDS[(_from, _to)] = "T??"


def allowed_transitions(from_status: ProductionQueueStatus) -> tuple[ProductionQueueStatus, ...]:
    """All legal target states from `from_status` — the T01–T29 map only."""
    return tuple(ALLOWED_QUEUE_TRANSITIONS.get(from_status, ()))


def is_legal_transition(
    from_status: ProductionQueueStatus, to_status: ProductionQueueStatus
) -> bool:
    return to_status in ALLOWED_QUEUE_TRANSITIONS.get(from_status, ())


def transition_error_message(
    from_status: ProductionQueueStatus, to_status: ProductionQueueStatus
) -> str:
    allowed = [s.value for s in allowed_transitions(from_status)]
    return (
        f"Illegal queue transition {from_status.value} → {to_status.value}. "
        f"Allowed from {from_status.value}: {', '.join(allowed) or 'none'}."
    )


def can_pause(status: ProductionQueueStatus) -> bool:
    return status not in PAUSE_FORBIDDEN_STATES


def deadline_state(target_date_str: str | None, today_str: str | None = None) -> str | None:
    """ON_TRACK | AT_RISK | OVERDUE from a target date (ISO date strings)."""
    if not target_date_str:
        return None
    from datetime import date

    target = date.fromisoformat(target_date_str)
    today = date.fromisoformat(today_str) if today_str else date.today()
    delta = (target - today).days
    if delta < 0:
        return "OVERDUE"
    if delta <= 7:
        return "AT_RISK"
    return "ON_TRACK"
