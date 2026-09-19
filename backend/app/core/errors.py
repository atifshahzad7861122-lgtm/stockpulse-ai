"""Standard error envelope (docs: 26_ERROR_HANDLING §3).

All API errors return:
    {"error": {"code", "message", "severity", "retryable", "retry_in_seconds",
               "request_id", "trace_id", "details", "help"}}
The CONTRACT.md error shape requires: code, message, details, trace_id, retryable.
Extra fields (severity, request_id, retry_in_seconds, help) follow doc 26 and are
safe for clients to ignore.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    request: Request | None = None,
    severity: str = "error",
    retryable: bool = False,
    retry_in_seconds: int | None = None,
    details: dict[str, Any] | None = None,
    help_url: str | None = None,
) -> JSONResponse:
    trace_id = new_trace_id()
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "severity": severity,
            "retryable": retryable,
            "request_id": request_id,
            "trace_id": trace_id,
            "details": details or {},
        }
    }
    if retry_in_seconds is not None:
        payload["error"]["retry_in_seconds"] = retry_in_seconds
    if help_url:
        payload["error"]["help"] = help_url
    return JSONResponse(status_code=status_code, content=payload)


# Error code registry (format E-<DOMAIN>-<NNN>, doc 26 §2).
# Exhaustive list lives in docs/26_ERROR_HANDLING.md; common codes referenced here.
COMMON_ERROR_CODES = {
    "E-TREND-101": "source timeout",
    "E-AI-201": "AI provider 5xx",
    "E-AI-202": "provider rate limit (429)",
    "E-PRED-301": "insufficient history for prediction",
    "E-COMP-401": "compliance rule engine error",
    "E-SIM-501": "embedding service failure",
    "E-DB-601": "database connection failure",
    "E-DB-602": "database constraint violation",
    "E-VAL-801": "input validation failure",
    "E-JOB-901": "missed schedule",
    "E-JOB-902": "retry budget exhausted",
    "E-SEC-001": "authentication failure",  # reserved; unused in single-user mode
}
