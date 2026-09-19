# StockPulse AI — Changelog

All notable changes to the StockPulse AI implementation, newest first.
Format follows Keep a Changelog (Added / Changed / Deprecated / Removed / Fixed / Notes).

---

## [0.5.0] — 2026-09-19 — Personal intelligence + opportunity fusion + daily production planner (Phase 3)

Answers "WHAT SHOULD I CREATE TODAY?": public market intelligence +
private contributor intelligence + personal performance history + trends +
seasonality + saturation + commercial relevance → Opportunity Fusion Engine
→ Personal Fit Score → prediction → Daily Production Planner → image/video
concepts → prompt packs → compliance → production queue. Full backend suite:
**528 passed, 0 failed** (455 baseline + 73 new), verified independently on
an isolated test DB 2026-09-19 ~13:05 PKT (second independent run — the
coordinator's own 524 count was from before its final 4 regression-fix tests);
frontend `npm run build` clean (exit 0, no errors); backend boots clean and
new API groups respond (`/api/personal-performance`, `/api/opportunity-fusion`,
`/api/daily-production`, `/api/prompt-packs`). Note: the dev `stockpulse.db`
had been left as a 0-byte file by the smoke-test cleanup; `init_db()` was
re-run and the dev DB is healthy and seeded again. Acceptance evidence:
PHASE3_ACCEPTANCE.md. Formula reference: `backend/PHASE3_FORMULAS.md`.

### Added
- **Personal Performance Engine** (`backend/app/services/personal_performance.py`,
  `backend/app/models/personal.py`): 6 tables (`personal_performance_snapshots`,
  `personal_category_metrics`, `personal_content_type_metrics`,
  `personal_theme_metrics`, `personal_keyword_metrics`, `personal_fit_scores`);
  7d/30d/90d windows vs equal prior windows; momentum labels
  (growing >+15% / declining <−15% / stable); consistency `100·(1−CV)` over
  trailing 12 weeks; IMAGE/VIDEO measured independently; themes derived from
  the user's own asset titles (never hard-coded); MOCK excluded unless dev
  mode; honest `not_configured` with nulls when Adobe is unconnected.
  Routes: `GET /api/personal-performance[/categories|/content-types|/themes]`,
  `POST /api/personal-performance/snapshot`.
- **Opportunity Fusion Engine** (`backend/app/engines/fusion.py`):
  `UNIFIED = clip(Σ(w·c)/Σ(w) − 0.15·saturation_risk, 0, 100)`; label FUSED
  when personal fit present, **MARKET-ONLY** (confidence −10) when absent —
  never a fake number; special cases `market_personal_mismatch` and
  `personal_performance` explained, never auto-rejected; evidence-only WHY
  explanations with a banned-language assert ("guaranteed"/"will sell"/
  "will rank"); optional local-Ollama phrasing with deterministic fallback.
  Routes: `POST /api/opportunity-fusion/compute`,
  `GET /api/opportunity-fusion/{opportunity_id}`.
- **Personal Fit Score** (full spec in `engines/opportunities.py`
  `personal_fit_breakdown`): weighted average renormalized over components
  WITH data; missing components skipped, never zeroed; `None` when no private
  data (null = "no data", never "bad fit").
- **Daily Production Planner** (`backend/app/services/production_planner.py`):
  capacity settings (weekly/daily/image/video targets, max daily generation,
  priority preference), greedy diversification with per-pick penalty
  recalculation, IMAGE/VIDEO balance, archived recommendations excluded.
  Routes: `/api/daily-production/...` (today/build/list/settings/status).
- **Concepts + compliance gate** (`backend/app/services/concepts.py`):
  deterministic template-built concept variations, each screened for
  similarity and compliance at generation; HIGH_RISK blocks approval;
  `ConceptVariation.ai_disclosure` records the user's explicit AI-disclosure
  decision and triggers a re-screen (never defaulted); archived concepts no
  longer gate recommendation approval.
- **Prompt packs** (export-only): `PromptPackGenerator` builds deterministic
  packs from screened concepts; Muse provider is export-only
  (`export_only: true`, no network, local JSON); `POST /api/prompt-packs`,
  `POST /api/prompt-packs/{id}/export`.
- **Frontend — Daily Intelligence** (`/daily`): MARKET / PERSONAL / FUSION /
  ACTION layout; "WHAT TO CREATE TODAY"; honest MARKET-ONLY and Personal Fit
  N/A states; recommendation approve/reject/archive; concept generation,
  disclosure recording, concept approval, prompt-pack creation.
- **Frontend — design system**: near-black luxury base, champagne-gold
  primary accent, racing red alerts-only, Inter + Bodoni Moda Didone serif for
  hero moments, F1-grade tabular telemetry numerals; Motion (framer-motion)
  for UI animation (150–400ms, `prefers-reduced-motion` respected); React
  Three Fiber 3D data viz (lazy-loaded, 2D fallbacks); Remotion
  `ConceptPreview` + `DailyBriefing` compositions with an on-demand render
  queue (never background; headless Chrome documented).
- **Private Performance page** (`/private`): honest NOT_CONFIGURED state,
  time filters, category/content-type/theme breakdowns.

### Fixed
- Concept approval dead-end: generated concepts were permanently HIGH_RISK
  (gen-01 disclosure BLOCK with no clearance path) — now clearable via
  explicit disclosure decision + re-screen.
- Archived concepts blocked recommendation approval indefinitely — now skipped.
- Frontend/backend contract mismatches: daily plan endpoint (`/today` +
  `plan_date`), recommendation status vocabulary (`recommended` not
  `pending` — Approve/Reject buttons previously never rendered).

### Notes
- Adobe Contributor remains honestly **NOT_CONFIGURED** until Atif supplies
  an authorized user-controlled session; no private metrics are fabricated.
- Predictions are probabilistic estimates with confidence — never guaranteed
  sales/downloads/ranking/acceptance/revenue. Compliance results are advisory
  and do not guarantee Adobe acceptance.

---

## [0.4.0] — 2026-09-19 — Real-data integration layer (Phase 2)

MOCK DATA → REAL DATA. The app stays fully functional; adapters, scheduler,
provenance, and UI additions below. Full test suite: **455 passed, 0 failed**
(264 baseline + 191 new), verified independently on a fresh DB 2026-09-19
11:05 PKT (one post-report regression in `test_mock_snapshot_hidden_unless_dev_mode`
fixed: dev-mode ON now correctly reveals the seeded demo batch alongside the
test's mock snapshot, instead of assuming an empty table). Acceptance evidence: PHASE2_ACCEPTANCE.md.

### Added
- **Source adapters** (`backend/app/adapters/`): `SourceAdapter` ABC
  (collect/validate/normalize/deduplicate/score_quality/store/get_status),
  guarded registry (14 types — a broken adapter never kills startup).
  ScrapeGraphAI (keyless Tier 1: DuckDuckGo `search_on_web` + `MarkdownifyGraph`;
  Tier 2 `SmartScraperGraph` with `OPENAI_API_KEY`), Agent-Reach (web via Jina
  Reader, V2EX hot topics, Xueqiu via real v1.5.0 channel APIs; `doctor` health
  mapped ok/warn/off/error), RSS (feedparser), YouTube channel RSS (no yt-dlp),
  GitHub official API (`VERIFIED` provenance), Huginn (self-hosted event
  polling; confidence capped 0.35 — noisy signal, never a demand feed),
  Reddit/X/Instagram/Facebook (honest `NEEDS_AUTH`/`UNAVAILABLE` until the user
  configures credentials), Adobe Contributor (private; authorized user-owned
  browser-export session; never simulates data), custom passthrough.
  Adapters never write intelligence tables directly — all writes go through
  `TrendSnapshot`/`TrendSignal` normalization (payload-hash dedup) or the
  append-only private tables.
- **Ollama local LLM provider:** `OllamaLLMProvider` against the local REST API
  (`/api/chat`, `format:"json"`), selectable via
  `STOCKPULSE_LLM_PROVIDER=ollama` (+ `OLLAMA_BASE_URL`, `OLLAMA_MODEL`).
  Private earnings/performance data stays on localhost, never sent to external
  services; provenance labeled `LOCAL`; graceful degradation when Ollama is down.
- **Adapter candidates (documented, not implemented):**
  `backend/app/adapters/CANDIDATES.md` — ExifTool (metadata preflight; cannot
  judge quality/originality/legality), ComfyUI (generation-tool list candidate;
  GPLv3 core, checkpoint/LoRA rights need separate review, Adobe generative-AI
  disclosure still required). Kdenlive: no action, not an integration target.
- **Models:** `SourceHealth` (status, last success/failure, counts, freshness,
  auth state), `CollectionRun` (QUEUED/RUNNING/SUCCESS/PARTIAL/FAILED/SKIPPED),
  `RawPayload` (raw response archive with hash + parser/adapter versions);
  nine append-only private tables (daily_earnings, downloads, sales,
  asset_performance, submission_results, category_performance,
  keyword_performance, snapshots, collection_runs). History is never overwritten.
- **Scheduler** (APScheduler): Adobe daily 06:00, public trends daily 07:00,
  RSS/YouTube/GitHub every 6h, source health checks every 15min. Writes
  `CollectionRun` rows, records `SKIPPED` for unconfigured sources, updates
  `SourceHealth`. Guarded by `STOCKPULSE_SCHEDULER_ENABLED` (default true);
  scheduler failure never blocks boot.
- **API:** `/api/sources` — list sources with health summary, `GET /health`,
  `GET /runs`, `GET /{id}`, `POST /{id}/collect` → 202 (rate-limited 5/hr;
  unconfigured sources record `SKIPPED`, never fake data). `/api/private` —
  Adobe connection (`NOT_CONFIGURED` default; `PUT /connection` stores the
  session server-side and never echoes secrets; `POST /connection/test`
  validates presence/format only, never simulates success), performance
  summary/categories/keywords with honest empty states when no data.
- **Personal Fit Score:** `personal_fit_score()` 0–100 measuring fit vs the
  user's own private performance (category/keyword/asset/acceptance factors),
  `None` when no private data exists; returned separately from
  `opportunity_score`, never mixed with market-wide scores.
- **Provenance & dev mode:** `DataProvenance` stays the mechanism (CONTRACT §3 —
  no `is_mock` flag added). Intelligence listings exclude `MOCK` rows unless
  `dev_mode` is on (default off); the UI shows a visible DEV MODE banner when on.
- **Security:** the `adobe_contributor` settings key is redacted in the settings
  API and rejected on PATCH (use `PUT /api/private/connection`); secrets are
  never logged, echoed to the frontend, or committed.
- **Frontend:** new pages `/sources` (Data Sources), `/sources/health` (Source
  Health), `/runs` (Collection Runs), `/private` (Private Performance + Adobe
  setup screen with required steps, last sync, sync button, error details).
  Dashboard widgets: source status chips, last-data-update freshness line,
  private performance summary (or setup CTA), market summary. Badges:
  LIVE (green, only when genuinely healthy+fresh), REAL, MOCK, ESTIMATED,
  PREDICTED — mock is never presented as real.
- **Seed:** 8 new `TrendSource` rows (19 total); `dev_mode=false` and default
  `rss_feeds` settings; seed stays idempotent.

### Fixed
- `init_db()` now runs the idempotent seed on every boot — previously new seed
  rows never reached existing databases (Phase 2 sources were missing from the
  dev DB until this fix).
- Removed a fake `adobe_contributor` session config (`{"cookie": "SECRET123"}`)
  left in the dev DB by integration verification; `/api/private/connection`
  returns honest `NOT_CONFIGURED` again. Private tables verified empty — no
  fake Adobe data anywhere.

### Notes
- Contract bumped to v0.3.0 (CONTRACT.md); `GET /api/health` version → 0.3.0.
- `.env.example` §11 documents all new vars (prefix-less convention):
  `DEV_MODE`, `RSS_FEEDS`, `OPENAI_API_KEY`, `SCRAPEGRAPHAI_TELEMETRY_ENABLED`,
  `GROQ_API_KEY`, `TWITTER_AUTH_TOKEN`/`TWITTER_CT0`, `GITHUB_TOKEN`,
  `ADOBE_CONTRIBUTOR_SESSION`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
  `HUGINN_BASE_URL`, `HUGINN_API_KEY`, `STOCKPULSE_SCHEDULER_ENABLED`.
- Dependencies: `scrapegraphai==2.2.4`, `agent-reach==1.5.0` (installed from
  source — PyPI serves 0.1.0 without the channel/health APIs),
  `feedparser==6.0.14`, `apscheduler==3.11.3`, `ddgs==9.16.0`.
- Design: `PHASE2_DESIGN.md` (integration contract). Evidence:
  `PHASE2_ACCEPTANCE.md` + `acceptance/accept_phase2.py`.
- Known limitations: ScrapeGraph `MarkdownifyGraph` body extraction is blocked
  by this sandbox's proxy env (keyless search tier works; records store URL
  titles, nothing fabricated); seeded YouTube channel IDs 404 here (adapter
  reports `TEMP_FAILING`); Xueqiu needs user login cookies; `test_queue_transitions`
  has a pre-existing intermittent SQLite flake (clean pass after removing the
  stale test DB file).
- Deviations from `PHASE2_DESIGN.md`: env names use the repo's prefix-less
  convention (not `STOCKPULSE_*`); YouTube via channel RSS, not yt-dlp;
  Agent-Reach statuses `ok|warn|off|error` mapped to the five `SourceStatus`
  values (the brief's READY/NEEDS_AUTH names don't exist upstream).
---

## [0.3.0] — 2026-09-19 — Full implementation complete (Phases 2–18)

All 18 implementation phases are done: database, backend API, frontend, engines,
agents, and tests. Verified end-to-end (see Notes).

### Added
- **Database:** all 28 tables per SEED_PLAN/CONTRACT (minus auth entities):
  categories, subcategories, micro_niches, trend_sources, trend_snapshots,
  trend_signals, market_metrics, opportunities, image_ideas, video_ideas,
  predictions, prompts, prompt_versions, compliance_rules, compliance_checks,
  similarity_records, assets, asset_versions, metadata, production_queue,
  submission_records, performance_metrics, saved_items, agent_runs, agent_logs,
  notifications, settings, audit_logs. UUID String(36) PKs, created_at/updated_at,
  soft-delete where specified. Seed is idempotent: 39 categories, 85
  subcategories, 171 micro-niches, 11 trend sources, 28 versioned compliance
  rules (v1.0.0), 13 settings rows, plus demo rows all labeled `provenance=MOCK`.
- **Backend API:** all CONTRACT endpoint groups implemented —
  /trends, /categories, /opportunities, /ideas, /prompts, /compliance,
  /similarity, /assets, /metadata, /production (queue), /submissions,
  /analytics, /agents, /settings, /notifications, /library — with the error
  envelope, pagination, idempotency keys, and rate limits per contract.
- **Engines:** scoring (Trend/Opportunity/Commercial/Saturation/Confidence 0–100
  with documented formulas + explainable factor breakdowns), 7-day trend
  analysis (W0 vs W1 vs baseline), rules-based v1 prediction (score + confidence
  + factors + model_version + timestamp + "estimate, not a guarantee"
  disclaimer), prompt generator (primary + alternative + negative +
  technical/originality/compliance blocks, immutable versioning), compliance
  engine (28 rules → PASS/REVIEW/HIGH_RISK with per-check explanations;
  never claims guaranteed acceptance), similarity (fingerprint + token-set
  Jaccard, thresholds 0.60 review / 0.80 high-risk), metadata generator with
  7 anti-spam rules enforced, queue state machine (T01–T29 enforced; illegal
  transitions → 400 with the allowed list; SUBMITTED gated on compliance PASS).
- **Providers:** abstract TrendProvider/LLMProvider/GenerationProvider with
  deterministic MockTrendProvider + MockLLMProvider (env-selected, MOCK
  default). No real credentials, no network calls.
- **Agents:** 13 agents as orchestrated service functions with run/log
  persistence, failure handling, and confidence; `POST /agents/daily-run`
  executes the 16-step daily workflow with human-in-the-loop gates
  (verified: a demo run paused at step 3 awaiting taxonomy review).
  Agents never auto-submit; created queue items land in DISCOVERED/IDEA_READY.
- **Frontend:** all 17 routes functional against the contract — Dashboard
  ("What should I create today?" hero, KPI strip, image/video opportunity
  panels, rising categories, prediction signals, queue snapshot, compliance
  alerts, agent runs, capacity bar), Daily Intelligence, Trends (Recharts
  time-series + score cards with factor breakdowns), Opportunities
  (actionability gating: score ≥55 & confidence ≥0.5), Image/Video Ideas hubs,
  Prompt Studio (versioned editor), Compliance (findings + manual review
  decisions), Similarity (threshold legend), Queue board (legal moves only),
  Submission Planner (user-configurable capacity; plan→mark-submitted→
  record-outcome — StockPulse never uploads), Metadata Studio, Library,
  Analytics, Agents (13-agent grid, run history, dead-letters), Settings,
  Help. Every page has loading/empty/error/partial-data states; mock rows
  render a visible "Demo data" badge; predictions show confidence + evidence
  + disclaimer; responsive desktop-first.
- **Tests:** 264 pytest tests green — scoring formulas (incl. CONTRACT worked
  example), 7-day math, prediction structure, prompt versioning, compliance
  classification, similarity thresholds, queue transitions, metadata spam
  rules, API smoke tests, DB constraints, rate limits, seed idempotency.
  Frontend: `tsc --noEmit` clean, `npm run build` passes (20/20 pages).

### Fixed
- Root `.env.example` frontend var renamed `NEXT_PUBLIC_API_BASE_URL` →
  `NEXT_PUBLIC_API_URL` for consistency with `frontend/.env.example`.
- Removed ruff B008 global ignore; converted all 25 violations to
  `Annotated[..., Depends(...)]` patterns.

### Notes
- Integration verified 2026-09-19: backend seeded, uvicorn served
  `/api/health` → 200, categories/opportunities/trends/compliance/queue/agents
  exercised via curl (illegal transition rejected with allowed list;
  COMPLIANCE_BLOCKED gate fired on SUBMITTED attempt without PASS);
  frontend `next start` served all 17 routes 200, `/login` 404, dashboard
  hero + Demo badge present in HTML. No secrets in code (scan clean).
- Known limitations: SQLite local-dev fallback (Postgres switch documented in
  README); compliance engine analyzes text/metadata only (no pixel-level
  artifact detection — documented); trend providers are mock/deterministic
  until real credentials are configured; mobile layout functional but
  desktop-first; browser-console check not performed in this environment.

---

## [0.2.0] — 2026-09-18 — Implementation begins (Phase 1: foundation + API contract)

First implementation release. The documentation package (`../stockpulse-ai-docs/`,
v0.1.0) remains the source of truth; this changelog tracks the build.

### Added
- Monorepo scaffold `stockpulse/`: `backend/` (FastAPI + SQLAlchemy + Pydantic layout:
  `app/{main,api/routers,core,models,schemas,services,engines,agents,workers,db}`),
  `frontend/` (Next.js 14 App Router + TypeScript + Tailwind scaffold).
- `CONTRACT.md` v0.2.0 — the binding backend↔frontend contract: base URL
  `http://localhost:8000/api`, error envelope (code/message/severity/details/
  request_id/trace_id/retryable), page-based pagination, all 17 endpoint groups,
  full enum reference (13 production-queue states + T01–T29 legal transitions,
  compliance results, provenance labels, risk levels, idea/prompt/asset statuses,
  prediction horizons, notification types, agent names), scoring formulas with worked
  examples, and the mock-data labeling convention (`provenance: "MOCK"` + visible
  "Demo data" badge).
- `SEED_PLAN.md` v0.2.0 — seed plan: 39 categories verbatim, subcategory/micro-niche
  structure, 11 trend sources with access method + provenance, 28 compliance checks
  summarized for seeding into `compliance_rules` (versioned, with source_reference).
- Working `GET /api/health` (verified 200, includes DB reachability).
- Frontend design tokens as CSS variables + Tailwind theme (docs/07 verbatim:
  bg #080A0F, surface #151923, accent #FF5C35, …), Inter + Space Grotesk typography,
  17 placeholder routes (no `/login`), shared `Shell` nav + `PageShell`,
  typed API client (`services/api.ts`), score helpers (`lib/scores.ts`) mirroring
  CONTRACT.md §8, shared TS domain types.
- Lint/format configs: backend `pyproject.toml` (black + ruff), frontend
  `.eslintrc.js` (next/core-web-vitals) + `.prettierrc`.
- Root `.env.example` (all vars from docs/30 minus auth secrets; `DATABASE_URL`
  defaults to `sqlite:///./stockpulse.db`), backend `.env.example`, frontend `.env.example`.
- Backend `settings` table model (the single user's config store) + SQLAlchemy
  Base/mixins (UUID String(36) PKs, UTC audit timestamps, soft-delete mixin).
- Pinned `backend/requirements.txt` and `frontend/package.json`.

### Changed — deviations from the documentation package (binding)
- **Single-user deviation (overrides multi-user docs):** NOT implemented and banned
  from code/routes/DB — login, signup, password reset, JWT auth, roles, permissions,
  multi-tenancy, organizations, teams, user management, workspace switching,
  invitations, `/auth/*` and `/users/*` endpoints, the `users` table, and every
  `user_id` column. The app opens directly into the Dashboard. `settings` remains as
  the single-user capacity/config store.
- **SQLite-fallback deviation (docs/08 targets PostgreSQL 14+):** the build
  environment has no Docker and no PostgreSQL server, so local dev uses SQLite via
  SQLAlchemy. Types are Postgres-compatible (UUID as String(36), tz-aware datetimes,
  JSON columns). See README "How to switch to Postgres".
- **Contract deviations from docs/12:** base path `/api` (not `/api/v1`); page-based
  pagination `{page, page_size, total, total_pages}` (not cursor); error envelope adds
  `trace_id` (primary correlation id) and `retryable` alongside docs/26 fields;
  `/notifications` and `/library` added as contract extensions (required by schema
  tables + frontend nav).
- **Docs-package inconsistency noted:** `docs/00_INDEX.md`'s directory hierarchy
  lists different filenames than the files on disk (e.g. `12_API_CONTRACT.md` vs
  actual `12_API_SPECIFICATION.md`, `26_SCORE_METHODOLOGY.md` vs actual
  `26_ERROR_HANDLING.md`, `30_OPERATIONS_RUNBOOK.md` vs actual
  `30_ENVIRONMENT_VARIABLES.md`). The on-disk filenames are authoritative.
- **Compliance check count:** docs/18's "27 checks" line is off — the coverage table
  lists 28 (4 GEN + 8 IP + 8 TQ + 8 MH). SEED_PLAN.md seeds all 28.

### Notes
- Phase 1 ships layout + contract only: domain routes beyond `/api/health` return
  nothing yet; full models/schemas/services/engines/agents land in later phases
  per the roadmap (docs/32).

---

## [0.1.0] — 2026-09-18 — Documentation complete

The 36-document specification package in `../stockpulse-ai-docs/` (v0.1.0) —
product, architecture, engines, operations. Documentation-only phase; no code.
