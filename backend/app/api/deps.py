"""Shared API dependencies: DB session, pagination, typed API errors, audit log."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, TypeVar

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import error_response
from app.db.session import SessionLocal
from app.schemas.common import Page, PageInfo

MAX_PAGE_SIZE = 100


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Depends(get_db)


class APIError(Exception):
    """Typed API failure → rendered as the CONTRACT error envelope."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable


async def api_error_handler(request, exc: APIError):
    return error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        retryable=exc.retryable,
        details=exc.details,
    )


def not_found(code: str, message: str, **details: Any) -> APIError:
    return APIError(code=code, message=message, status_code=404, details=details)


def bad_request(code: str, message: str, **details: Any) -> APIError:
    return APIError(code=code, message=message, status_code=400, details=details)


def unprocessable(code: str, message: str, **details: Any) -> APIError:
    return APIError(code=code, message=message, status_code=422, details=details)


def conflict(code: str, message: str, **details: Any) -> APIError:
    return APIError(code=code, message=message, status_code=409, details=details)


def rate_limited(
    message: str = "Rate limit exceeded. Please retry later.", **details: Any
) -> APIError:
    return APIError(code="RATE_LIMITED", message=message, status_code=429, details=details)


T = TypeVar("T")


def paginate(items: list[T], *, page: int, page_size: int, total: int) -> Page[T]:
    total_pages = math.ceil(total / page_size) if page_size else 0
    return Page[T](
        data=items,
        pagination=PageInfo(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> dict[str, int]:
    return {"page": page, "page_size": page_size}


def audit_log(
    db: Session,
    *,
    action: str,
    entity_kind: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
    agent_run_id: str | None = None,
) -> None:
    """Append an immutable audit record (docs: 08 §11.4)."""
    from app.models.platform import AuditLog

    db.add(
        AuditLog(
            actor_kind="user",
            action=action,
            entity_kind=entity_kind,
            entity_id=entity_id,
            before=before,
            after=after,
            note=note,
            agent_run_id=agent_run_id,
        )
    )


# ---------------------------------------------------------------------------
# Rate limiting (in-memory token bucket, per key) + idempotency store
# ---------------------------------------------------------------------------

_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
_IDEMPOTENCY_STORE: dict[str, Any] = {}


def check_rate_limit(key: str, max_calls: int, per_seconds: int) -> None:
    """Raise 429 RATE_LIMITED when `key` exceeds max_calls per per_seconds."""
    now = time.monotonic()
    window_start = now - per_seconds
    calls = [t for t in _RATE_BUCKETS[key] if t > window_start]
    if len(calls) >= max_calls:
        raise rate_limited(
            f"Rate limit exceeded: {max_calls} calls per {per_seconds}s.",
            key=key,
            retry_in_seconds=int(per_seconds),
        )
    calls.append(now)
    _RATE_BUCKETS[key] = calls


def idempotent(key: str | None, response: Any) -> Any:
    """Return the stored response for a repeated Idempotency-Key, else store."""
    if not key:
        return response
    if key in _IDEMPOTENCY_STORE:
        return _IDEMPOTENCY_STORE[key]
    _IDEMPOTENCY_STORE[key] = response
    return response


def get_idempotency_key(request) -> str | None:
    return request.headers.get("Idempotency-Key")
