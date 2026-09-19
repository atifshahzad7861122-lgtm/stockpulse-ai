# StockPulse AI — Phase 2 Integration Design (REAL DATA LAYER)

Extension, not rebuild. Baseline: v0.3.0, 264 tests passing, FastAPI + SQLAlchemy + Pydantic backend, Next.js 14 frontend, SQLite dev DB, no login. Source of truth: `~/workspace/stockpulse-ai-docs/`, CONTRACT.md (v0.2.0, binding).

Inspections completed 2026-09-19 (all source-verified, no guessing):
- **ScrapeGraphAI** (`/tmp/scrapegraph-ai`): keyless `MarkdownifyGraph(llm_model=None).execute({"url": ...})` → `result["markdown"]`; keyless `search_on_web(query, max_results, search_engine="duckduckgo")` in `scrapegraphai/utils/research_web.py`. All `SmartScraper*`/`SearchGraph` classes require `config["llm"]`. Pydantic `schema=` param supported. Heavy deps: langchain>=1.2.0, playwright+undetected-playwright, ddgs, html2text. Python>=3.12 (backend is 3.12.3 — OK).
- **Agent-Reach** (`/tmp/agent-reach`, v1.5.0): NOT a data library — installer + health router + skill refs. Real no-auth Python methods only: `WebChannel().read(url)` (Jina Reader, stdlib urllib), `V2EXChannel().get_hot_topics()`, `XueqiuChannel().get_stock_quote()/get_hot_stocks()/get_hot_posts()`, RSS via `feedparser` directly. Health: `check_all(Config(read_only=True))` → statuses `ok|warn|off|error` (NO ready/needs_auth — map them ourselves). YouTube = yt-dlp (heavy, needs JS runtime) — NOT used; use YouTube channel RSS via feedparser instead. Reddit/X/IG/FB need cookies or desktop OpenCLI — server deployment cannot do these → honest NOT CONFIGURED states. GitHub public search via `gh` CLI or `api.github.com` (10 req/min unauth) — use api.github.com via urllib (lighter, no binary).
- No LLM/provider API keys exist in this environment → keyless paths are mandatory for the acceptance test.

## 1. Adapter layer — `backend/app/adapters/`

New package. Base interface (`base.py`):

```python
class SourceStatus(str, Enum): AVAILABLE, CONFIGURED, NEEDS_AUTH, UNAVAILABLE, TEMP_FAILING
class SourceAdapter(ABC):
    source_type: str            # e.g. "scrapegraph_web", "rss", "youtube_rss"
    def collect(self, ctx) -> list[RawRecord]      # fetch raw
    def validate(self, records) -> list[RawRecord] # drop malformed
    def normalize(self, records) -> list[NormalizedSignal]  # -> TrendSignalInput / MarketMetricInput / PrivateSignalInput
    def deduplicate(self, signals, session) -> list[...]    # hash/URL/timestamp
    def score_quality(self, signals) -> float               # 0-100
    def store(self, signals, session) -> StoredResult       # via normalization layer ONLY
    def get_status(self) -> AdapterHealth                   # real runtime check, never hard-coded
```

Normalized dataclasses in `adapters/normalized.py`: `TrendSignalInput(micro_niche_id?, signal_name, description, metric_name, metric_value, metric_unit, observed_at, provenance, confidence, source_id, collection_method, data_timestamp, raw_reference)`, `MarketMetricInput(...)`, `PrivateSignalInput(...)`.

**CRITICAL RULE:** adapters never write intelligence tables directly. `store()` writes `TrendSnapshot` (payload, payload_hash dedup — existing uq) + `TrendSignal` rows via the existing `agents/trend_research.py` path, or private tables for private data. Provenance for real public rows: `DataProvenance.THIRD_PARTY` (VERIFIED only for official APIs: api.github.com, YouTube RSS is THIRD_PARTY). Private user rows: `DataProvenance.USER_PROVIDED`.

Concrete adapters (`backend/app/adapters/`):
- `scrapegraph_adapter.py` — guarded `import scrapegraphai`. Tier 1 keyless: `search_on_web` for discovery + `MarkdownifyGraph(llm_model=None)` for article extraction. Tier 2: `SmartScraperGraph` + pydantic schema when `OPENAI_API_KEY` set. `get_status()`: import ok + trial `search_on_web` probe → AVAILABLE/UNAVAILABLE.
- `agentreach_adapter.py` — guarded `import agent_reach`. Sub-channels: `web` (WebChannel.read), `v2ex`, `xueqiu`; RSS via `feedparser` (import feedparser, not agent_reach). Health via `check_all(Config(read_only=True))` mapped: ok→AVAILABLE, warn→NEEDS_AUTH or TEMP_FAILING (by channel message), off→UNAVAILABLE, error→TEMP_FAILING.
- `rss_adapter.py` — feedparser over feed URLs from settings (`rss_feeds` setting: list of {name, url, category}). Zero config.
- `youtube_adapter.py` — YouTube channel RSS: `https://www.youtube.com/feeds/videos.xml?channel_id=...` via feedparser. Seeded with 3–5 real design/stock/AI-trend channels (real channel IDs, verified fetchable). Document yt-dlp+Groq path as optional future.
- `github_adapter.py` — `https://api.github.com/search/repositories?q=...` via stdlib urllib, unauth (10 req/min; respect via rate-limit tracking). Trending AI repos → opportunity signals.
- `reddit_adapter.py`, `x_adapter.py`, `instagram_adapter.py`, `facebook_adapter.py` — architecture complete, `get_status()` returns NEEDS_AUTH/NOT CONFIGURED until user configures cookies/session. Reddit: rdt-cli path documented. X: TWITTER_AUTH_TOKEN env. IG/FB: desktop OpenCLI only — document as desktop-only, server UNAVAILABLE.
- `adobe_adapter.py` — `AdobeContributorAdapter`. Full architecture: session config stored in `settings` table (`adobe_contributor` JSON: {configured: bool, session_type, last_sync, ...}) — NEVER real cookies in code/git; cookie values stored via settings API (server-side only, never returned to frontend). Collection: Playwright-based (guarded import) navigating only contributor-dashboard pages the user is authorized for; extracts earnings/downloads/asset performance; writes private tables as time-series snapshots; handles pagination/loading/failures; records collection runs. **Until user configures: status NOT CONFIGURED, no collection attempted, never simulated.** Do NOT invent Adobe endpoints — extract only what the real dashboard exposes; if Playwright unavailable, adapter reports UNAVAILABLE with reason.
- `custom_adapter.py` — passthrough for user-defined webhooks/feeds.

Registry: `backend/app/adapters/registry.py` — `ADAPTERS: dict[str, type[SourceAdapter]]`, `get_adapter(source_type)`.

## 2. Provenance & dev mode

- CONTRACT §3 is binding: provenance is the mechanism (`DataProvenance` enum). Do NOT add `is_mock` booleans. New rows carry `data_provenance`: real public → THIRD_PARTY/VERIFIED, private real → USER_PROVIDED, mock/demo → MOCK.
- New tables (below) include the brief's metadata fields: `source_id, source_type, collection_method, collected_at, data_timestamp, data_quality, data_status, raw_reference`. For existing tables (TrendSignal etc.), the chain `TrendSignal.trend_snapshot_id → TrendSnapshot.trend_source_id` + `data_provenance` + `CollectionRun` linkage provides provenance — do not add columns to existing tables unless a test demands it.
- Dev mode: new setting `dev_mode` (default `false`). Intelligence queries exclude `data_provenance == MOCK` unless dev_mode is on. Frontend shows a visible "DEV MODE — demo data active" banner when on. Seeded MOCK demo rows stay in DB but stop driving production intelligence.

## 3. New DB models — `backend/app/models/sources.py`, `backend/app/models/private.py`

UUID String(36) PKs, created_at/updated_at (utcnow mixin), soft-delete where noted. Follow existing model style.

`SourceHealth`: id, trend_source_id (FK, unique), status (SourceStatus str), last_success_at, last_failure_at, last_error (Text), records_collected (int), avg_duration_ms (float), consecutive_failures (int), checked_at, auth_state (str), fallback_status (str).
`CollectionRun`: id, trend_source_id (FK), started_at, finished_at, status (QUEUED/RUNNING/SUCCESS/PARTIAL/FAILED/SKIPPED), records_collected, records_stored, error (Text), trigger (SCHEDULED/MANUAL/API), duration_ms.
`RawPayload`: id, source (str), collection_time, raw_payload (JSON), payload_hash (str, unique-ish index), parser_version, adapter_version, collection_run_id (FK nullable).

Private tables (all time-series, append-only — never update history rows):
`PrivateDailyEarning`: id, date (unique index), earnings, currency, downloads, source, collection_run_id, data_provenance=USER_PROVIDED.
`PrivateDownload`: id, date, asset_external_id, downloads, collection_run_id.
`PrivateSale`: id, date, asset_external_id, earnings, license_type, collection_run_id.
`PrivateAssetPerformance`: id, asset_external_id, title, snapshot_date, downloads_total, earnings_total, views?, collection_run_id. (unique on (asset_external_id, snapshot_date))
`PrivateSubmissionResult`: id, asset_external_id, submitted_at, status (ACCEPTED/REJECTED/PENDING), reviewed_at, rejection_reason, collection_run_id.
`PrivateCategoryPerformance`: id, category (str), snapshot_date, downloads, earnings, asset_count, collection_run_id. (unique on (category, snapshot_date))
`PrivateKeywordPerformance`: id, keyword, snapshot_date, downloads, earnings, collection_run_id. (unique on (keyword, snapshot_date))
`PrivateSnapshot`: id, snapshot_date (unique), summary_json (JSON: totals for the day), collection_run_id.
`PrivateCollectionRun`: id, started_at, finished_at, status, records_collected, error, trigger.

Seed new `TrendSource` rows for: rss feeds, scrapegraph_web, agentreach_web, v2ex, xueqiu, youtube_rss, github_trending, adobe_contributor (is_active=false until configured).

## 4. Scheduler — `backend/app/workers/scheduler.py`

Use `apscheduler` (add to requirements; pure-python, light). `BackgroundScheduler` started in `main.py` lifespan when `STOCKPULSE_SCHEDULER_ENABLED=true` (default true; tests set false).
Jobs: `collect_private_adobe` daily 06:00; `collect_public_trends` daily 07:00; `collect_social_fast` every 6h (rss/youtube/github — cheap); `source_health_check` every 15 min. Each job: creates CollectionRun row, calls adapter, respects per-source rate limits (track last run in SourceHealth), skips when adapter status is NEEDS_AUTH/UNAVAILABLE (records SKIPPED, no fake data). Manual trigger: `POST /api/sources/{id}/collect` → runs synchronously-ish via existing job pattern, returns CollectionRun id.

## 5. API — extend `backend/app/api/routers/`

New `sources.py` router (mounted `/api/sources`):
- `GET /` — list sources with health summary + provenance.
- `GET /{id}` — detail + recent runs.
- `GET /health` — all SourceHealth rows (status, last success/failure, counts, freshness, auth state).
- `POST /{id}/collect` — manual collection (rate-limited like /trends/refresh), returns 202 + run id.
- `GET /runs`, `GET /runs/{id}` — collection runs.
New `private.py` router (`/api/private`):
- `GET /connection` — Adobe Contributor connection status {status, required_config, last_sync, error} — honest NOT CONFIGURED default.
- `PUT /connection` — store session config (server-side only; response never echoes secrets).
- `POST /connection/test` — validates config presence/format only, never simulates success.
- `GET /performance/summary` — personal performance: by category, by asset type, earnings/download trends (empty-state when no data).
- `GET /performance/categories`, `/performance/keywords`.
Opportunities: add `personal_fit_score` (nullable 0–100) to response schema; computed by new service when private data exists, else null.

Enums: add `SourceStatus`, extend TS types in `frontend/types/index.ts` identically.

## 6. Engines

- `engines/opportunities.py`: add `personal_fit_score(category_perf, asset_type_perf, keyword_perf, acceptance_rate, downloads, earnings) -> float | None`. Returns None when no private data. Keep separate from opportunity_score; API returns both.
- Trend calc from real data: reuse `analyze_topic` — real TrendSignals feed it; confidence lowered when `n_sources` small or data stale (freshness factor already exists via `source_freshness`).
- No changes to scoring formulas (docs forbid unless required).

## 7. Frontend

New routes: `/sources` (Data Sources: cards per source, status chip, last sync, collect button), `/sources/health` (Source Health table), `/private` (Private Performance: connection setup panel + performance charts; honest NOT CONFIGURED setup screen for Adobe), `/runs` (Collection Runs). Sidebar nav additions.
Dashboard (`/`): widgets — source status chips row, "last data update" freshness line, private performance mini-summary (or setup CTA), market summary. Provenance badges: LIVE (green, only when SourceHealth.status==AVAILABLE and last_success_at fresh), REAL, MOCK ("Demo data" existing), ESTIMATED, PREDICTED. Dev-mode banner when `dev_mode` on.
Adobe setup screen (`/private` connection panel): status, required config steps (how to export session from their own browser), last sync, sync button, error details. Never shows cookie values.

## 8. .env.example additions

```
STOCKPULSE_SCHEDULER_ENABLED=true
STOCKPULSE_DEV_MODE=false
OPENAI_API_KEY=            # optional: enables ScrapeGraphAI LLM tier (SmartScraperGraph)
SCRAPEGRAPHAI_TELEMETRY_ENABLED=false
GROQ_API_KEY=              # optional: Agent-Reach transcription
TWITTER_AUTH_TOKEN=        # optional: X channel (from Cookie-Editor export)
TWITTER_CT0=               # optional: X channel
GITHUB_TOKEN=              # optional: raises GitHub API rate limit
RSS_FEEDS=                 # optional JSON list; defaults seeded
ADOBE_CONTRIBUTOR_SESSION= # set via UI/API only, never commit
```
Document each; no real values.

## 9. Tests (backend/tests/test_phase2_*.py)

Keep all 264 green. New: adapter interface contract (all adapters implement 7 methods), scrapegraph adapter with guarded import (skip if not installed; mock boundary test), agentreach adapter with mocked channels, adobe adapter config/failure paths (NO real creds; NOT CONFIGURED default), normalization, dedup (hash/URL), source health mapping (ok/warn/off/error → our statuses), trend calc from real-shaped signals, private performance aggregation, combined opportunity + Personal Fit Score (None when no private data), failure handling (source down → marked, confidence lowered), dev-mode MOCK exclusion. Frontend: smoke test that new routes render (existing pattern).

## 10. Acceptance test (must actually run)

1. Install `scrapegraphai`, `agent-reach`, `feedparser`, `apscheduler` into backend/.venv (document versions; if scrapegraphai fails, adapter degrades honestly and acceptance uses the remaining paths — report truthfully).
2. Real collection A: `search_on_web("stock photography trends 2026", ...)` + `MarkdownifyGraph` on 1–2 real article URLs → store TrendSnapshot+TrendSignal (provenance THIRD_PARTY).
3. Real collection B: Agent-Reach RSS (feedparser) on a real feed (e.g. a design/AI blog) → signals.
4. Real collection C: Agent-Reach V2EX hot topics and/or Xueqiu hot stocks + YouTube channel RSS → signals.
5. GitHub trending AI repos → signals (optional 4th).
6. Run trend analysis (`analyze_topic`) on collected signals → trend scores; generate one Opportunity with evidence (source names + timestamps); verify it appears via API and in UI (curl the endpoints; frontend render check via existing pattern).
7. Adobe: setup screen reachable, status NOT CONFIGURED, no fake data anywhere.

## 11. Hard rules (non-negotiable)

- Never mark connected without real data retrieved. Never fake earnings/downloads. Never label mock as live.
- On failure: mark source, show last success, lower freshness/confidence, never fabricate replacements.
- Secrets: env or settings-table only; never logged, never to frontend, never in git. Tests use fake values.
- Update CHANGELOG.md (new version entry) + README.md at the end; note deviations (e.g. provenance-vs-is_mock per CONTRACT, SourceStatus mapping, SQLite still, YouTube via RSS not yt-dlp).

## 12. Work split for implementation children

- CHILD-BACKEND-CORE: adapters package (all adapters + registry + normalized + guarded imports), models/sources.py + models/private.py, seed additions, scheduler, normalization enforcement, requirements additions.
- CHILD-BACKEND-API: routers sources.py + private.py, settings dev_mode, opportunities personal_fit_score wiring, enums sync, .env.example, seed wiring into init.
- CHILD-FRONTEND: 4 new pages, sidebar, dashboard widgets, provenance/LIVE badges, dev-mode banner, Adobe setup screen, types/index.ts sync.
- CHILD-TESTS: all Phase 2 tests + full suite green + acceptance test execution (real collections) with evidence log.

Contract between children: adapter method names and NormalizedSignal field names above; API paths in §5; enum strings UPPER_SNAKE_CASE; provenance stays DataProvenance.
