"""Application settings, loaded from environment variables.

See repo-root .env.example (derived from docs: 30_ENVIRONMENT_VARIABLES).
Single-user deviation: all JWT_*/auth variables are REMOVED — there is no
login, no users table, no auth layer. (docs/30 §4 does not apply)
"""

import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # accept both STOCKPULSE_-prefixed aliases and plain field names
    )

    app_env: str = Field(default="local", description="local | staging | production")
    app_name: str = Field(default="stockpulse-ai")
    log_level: str = Field(default="INFO")
    api_version: str = Field(default="v1")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_allowed_origins: str = Field(default="http://localhost:3000")
    request_timeout_seconds: int = Field(default=30)

    # Database. Local dev default: SQLite file.
    # Postgres switch: postgresql+psycopg://<user>:<pass>@<host>:5432/stockpulse
    database_url: str = Field(default="sqlite:///./stockpulse.db")

    redis_url: str = Field(default="redis://localhost:6379/0")

    # AI provider keys (placeholders; injected at runtime, never committed)
    llm_primary_api_key: str = Field(default="")
    llm_primary_model: str = Field(default="")
    embed_api_key: str = Field(default="")
    ai_monthly_token_budget: int = Field(default=0)

    # Object storage (placeholders)
    storage_endpoint: str = Field(default="")
    storage_region: str = Field(default="auto")
    storage_bucket_assets: str = Field(default="stockpulse-assets")
    storage_bucket_uploads: str = Field(default="stockpulse-uploads")
    storage_access_key: str = Field(default="")
    storage_secret_key: str = Field(default="")
    storage_signed_url_ttl_minutes: int = Field(default=15)
    upload_max_mb: int = Field(default=50)

    # Trend sources (generic N-source pattern; see .env.example)
    trend_aggregation_window_hours: int = Field(default=168)

    # Observability
    sentry_dsn: str = Field(default="")
    metrics_enabled: bool = Field(default=True)
    tracing_enabled: bool = Field(default=False)

    # Feature flags (auth/signup flags removed — single-user)
    feature_trend_agent: bool = Field(default=True)
    feature_insight_agent: bool = Field(default=True)
    feature_opportunity_agent: bool = Field(default=True)
    feature_concept_agent: bool = Field(default=True)
    feature_prompt_agent: bool = Field(default=True)
    feature_compliance_agent: bool = Field(default=True)
    feature_auto_refresh: bool = Field(default=True)
    feature_experimental_models: bool = Field(default=False)

    # Scheduler
    scheduler_enabled: bool = Field(
        default=True,
        validation_alias="STOCKPULSE_SCHEDULER_ENABLED",
        description="Phase 2 collection scheduler (daily + 6h + 15min jobs)",
    )
    scheduler_daily_pipeline: bool = Field(default=True)
    scheduler_pipeline_cron: str = Field(default="0 2 * * *")
    scheduler_trend_aggregation: bool = Field(default=True)
    scheduler_missed_run_grace_minutes: int = Field(default=30)

    # Phase 2 — real-data layer (PHASE2_DESIGN.md §8). Canonical env names are
    # the STOCKPULSE_-prefixed ones; plain DEV_MODE / RSS_FEEDS are accepted
    # as backward-compatible aliases (populate_by_name=True).
    dev_mode: bool = Field(
        default=False,
        validation_alias="STOCKPULSE_DEV_MODE",
        description="When true, seeded MOCK/demo rows drive intelligence (visible banner).",
    )
    rss_feeds: str = Field(
        default="",
        description="JSON list of {name, url, category} RSS feeds; parsed via parsed_rss_feeds().",
    )

    def parsed_rss_feeds(self) -> list[dict[str, str]]:
        """Parse the RSS_FEEDS JSON env var. Never raises — [] on unset/invalid."""
        raw = (self.rss_feeds or "").strip()
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(items, list):
            return []
        return [
            {
                "name": str(i.get("name", "")),
                "url": str(i.get("url", "")),
                "category": str(i.get("category", "")),
            }
            for i in items
            if isinstance(i, dict) and i.get("url")
        ]


settings = Settings()
