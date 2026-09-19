"""StockPulse AI backend — core package.

Modules:
    config:     application settings (pydantic-settings, env-driven)
    errors:     standard error envelope (doc 26) + error codes
    deps:       FastAPI dependencies (DB session, settings access)
    security:   single-user mode — no auth; placeholder for rate limiting etc.
"""
