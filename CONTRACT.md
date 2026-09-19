# StockPulse AI — API Contract (Phase 1 + Phase 2 additions)

**Version:** 0.3.0 · **Date:** 2026-09-19 · **Status:** BINDING for all later implementers.

This is the single contract between the FastAPI backend (`backend/`) and the Next.js
frontend (`frontend/`). Both sides MUST follow it exactly. It is derived from
`docs/12_API_SPECIFICATION.md` with the Phase-1 deviations listed in §1.2 and the
Phase-2 additions listed in §11. Where this contract and the docs disagree,
**this contract wins** (deviations are explicit and logged in `CHANGELOG.md`).

Related docs: `docs/08_DATABASE_SCHEMA.md` (entities), `docs/15_*` (scores),
`docs/20_PRODUCTION_PIPELINE.md` (queue transitions), `docs/26_ERROR_HANDLING.md`
(errors), `docs/18_COMPLIANCE_ENGINE_SPECIFICATION.md` (checks).

---

## 1. Scope & deviations from the documentation package

### 1.1 Single-user deviation (overrides all multi-user docs)

StockPulse AI is a **personal, single-user** application. The following are
**NOT implemented** and MUST NOT appear in code, routes, or the database:

- login / signup / password reset / one-time codes
- JWT access/refresh tokens, token rotation, `Authorization: Bearer` headers
- roles, permissions, multi-tenancy, organizations, teams
- user management, workspace switching, invitations
- `/auth/*` and `/users/*` endpoints
- the `users` table and every `user_id` column

The app opens directly into the Dashboard. All requests are implicitly the single
user's. `settings` remains as the single-user capacity/config store.

### 1.2 Contract deviations from docs/12_API_SPECIFICATION.md

| # | Docs say | This contract says | Reason |
|---|---|---|---|
| D1 | Base path `/api/v1` | Base path `/api` (version via `API_VERSION` env; path versioning deferred) | Simpler local dev; version header can be re-added later |
| D2 | Cursor pagination (`cursor`/`limit`) | Page pagination `{page, page_size, total, total_pages}` | Task-specified; deterministic for UI grids |
| D3 | JWT auth on all endpoints | No auth on any endpoint (single-user) | §1.1 |
| D4 | `request_id` only in error envelope | Envelope carries `code, message, severity, details, request_id, trace_id, retryable` (+ optional `retry_in_seconds`, `help`) | Task-specified fields + docs/26 fields; `trace_id` is the primary correlation id |
| D5 | Enum values transported as documented | Enums serialize as their UPPER_SNAKE_CASE string values everywhere | Unambiguous across Python/TS |
| D6 | `/notifications`, `/library` not specified | Added as contract extensions (§5.16, §5.17) | Required by schema tables (`notifications`, `saved_items`) and frontend nav |

---

## 2. Global conventions

### 2.1 Transport

- **Base URL:** `http://localhost:8000/api`
- **Content type:** `application/json` for requests and responses. No content negotiation.
- **Auth:** none (single-user, §1.1).

### 2.2 Error envelope (from docs/26_ERROR_HANDLING §3 + task spec)

Every error response (4xx/5xx) returns exactly this shape:

```json
{
  "error": {
    "code": "E-AI-202",
    "message": "The AI service is rate-limited. Your request is queued and will retry automatically.",
    "severity": "warning",
    "retryable": true,
    "retry_in_seconds": 60,
    "request_id": "req_7d1a2b3c",
    "trace_id": "tr_9f2c44ab01de",
    "details": { "provider": "primary", "endpoint_group": "prompt-generation" },
    "help": "https://docs.stockpulse.local/errors/E-AI-202"
  }
}
```

Field rules:

| Field | Required | Meaning |
|---|---|---|
| `code` | yes | Machine code. Domain codes use `E-<DOMAIN>-<NNN>` (doc 26 §2); resource errors use `<RESOURCE>_<PROBLEM>` (e.g. `OPPORTUNITY_NOT_FOUND`, `INVALID_TRANSITION`, `VALIDATION_ERROR`, `COMPLIANCE_BLOCKED`, `RATE_LIMITED`, `IDEMPOTENCY_REPLAY_MISMATCH`) |
| `message` | yes | Human-readable, safe to display verbatim. Never implies guaranteed outcomes |
| `severity` | yes | `info` \| `warning` \| `error` \| `critical` |
| `details` | yes | Technical context object (never secrets, never credential material) |
| `trace_id` | yes | Primary cross-service correlation id (`tr_` + 12 hex) |
| `retryable` | yes | Client may retry without parsing `message`. Honored with backoff |
| `request_id` | no | Per-request id (`req_` + 12 hex), set by middleware |
| `retry_in_seconds` | no | Hint for how long to wait before retry |
| `help` | no | Link to error documentation |

Common HTTP mapping: 400 `VALIDATION_ERROR` / `INVALID_TRANSITION` / `PAGINATION_LIMIT_EXCEEDED`;
404 `<RESOURCE>_NOT_FOUND`; 409 `CONFLICT` / `DUPLICATE_RESOURCE` / `IDEMPOTENCY_REPLAY_MISMATCH`;
413 `PAYLOAD_TOO_LARGE`; 415 `UNSUPPORTED_MEDIA_TYPE`; 422 `PROVIDER_ERROR` / `AGENT_FAILED` /
`COMPLIANCE_BLOCKED`; 429 `RATE_LIMITED` (with `Retry-After`); 500 `INTERNAL_ERROR`.

### 2.3 Pagination

List endpoints accept `?page=` (default 1) and `?page_size=` (default 20, max 100).
Responses wrap lists as:

```json
{
  "data": [ /* items */ ],
  "pagination": { "page": 1, "page_size": 20, "total": 137, "total_pages": 7 }
}
```

`page_size` > 100 → 400 `PAGINATION_LIMIT_EXCEEDED`.

### 2.4 Timestamps, ids, money

- Timestamps: ISO-8601 in UTC, e.g. `2026-09-18T10:00:00Z`. Fields: `created_at`, `updated_at`
  (audit, on every entity), plus domain-specific `*_at` fields. No unix epochs on the wire.
- Ids: UUID strings (36 chars, `id` field on every entity). No sequential ids in URLs/exports.
- Money: decimal numbers as JSON numbers; `revenue`/`avg_price_estimate` carry a `currency`
  field (ISO 4217, default `USD`).

### 2.5 Sorting & filtering

- Sorting: `?sort=-opportunity_score,created_at` (`-` = descending). Unknown fields → 400 `INVALID_SORT_FIELD`.
- Filtering: `?status=approved&category=technology,business` (comma = OR within a field).

### 2.6 Idempotency

Mutating POSTs on queue/submission/compliance/agent endpoints accept an `Idempotency-Key`
header. Same key + same payload → original result replayed. Same key + different payload →
409 `IDEMPOTENCY_REPLAY_MISMATCH`.

### 2.7 Async pattern

Expensive operations return `202 Accepted` with `{ "job_id": "<uuid>" }`; the client polls
`GET /api/agents/jobs/{job_id}` (job statuses: `queued | running | succeeded | failed |
cancelled | dead_letter`, plus `progress` 0–1 and `result`/`error` payloads).

### 2.8 Rate limiting

Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
On 429: `Retry-After` header + `RATE_LIMITED` envelope.

---

## 3. Mock-data labeling (binding)

- Any response carrying placeholder/demo data MUST include `"provenance": "MOCK"` on each
  affected record and `"mock": true` at the payload level where applicable.
- The frontend MUST render a visible **"Demo data"** badge (warning chip) whenever
  `provenance === "MOCK"` or `mock === true`.
- **NEVER present mock data as real Adobe Stock data.** No invented Adobe sales numbers —
  anywhere, ever (docs core principle).

### 3.1 Dev mode (v0.3.0 — Phase 2)

- New setting `dev_mode` (default `false`; honoured from the `STOCKPULSE_DEV_MODE`
  env var, with plain `DEV_MODE` accepted as a backward-compatible alias).
  The frontend shows a visible **"DEV MODE — demo data active"** banner when it is on.
- Intelligence listing endpoints (`GET /api/trends`, `GET /api/trends/{id}/signals`,
  `GET /api/opportunities`) **exclude** rows with `data_provenance == MOCK` unless dev
  mode is on. Seeded MOCK demo rows stay in the DB but stop driving production
  intelligence. No `is_mock` booleans — provenance stays `DataProvenance` (per §4.1).

---

## 4. Enum reference (all values, verbatim)

Enums serialize as their string values. Frontend `types/index.ts` and backend
`app/schemas/enums.py` MUST match this list exactly.

### 4.1 `data_provenance`
`VERIFIED` — confirmed from an authoritative source ·
`USER_PROVIDED` — entered by the user ·
`THIRD_PARTY` — external provider/public dataset ·
`ESTIMATED` — derived by calculation, approximate ·
`PREDICTED` — forward-looking model output, probabilistic with confidence ·
`MOCK` — demo/placeholder data (contract extension; never real)

Display labels: Verified / User-provided / Third-party / Estimated / Predicted / Demo data.

### 4.2 `production_queue_status` (13 states, docs/20 §4)
`DISCOVERED` · `ANALYZING` · `IDEA_READY` · `PROMPT_READY` · `APPROVED` ·
`IN_PRODUCTION` · `QUALITY_CHECK` · `COMPLIANCE_REVIEW` · `READY_TO_UPLOAD` ·
`SUBMITTED` · `ACCEPTED` · `REJECTED` · `ARCHIVED`

### 4.3 Legal queue transitions (docs/20 §5, T01–T29)
Any pair not listed → 400 `INVALID_TRANSITION`. Every transition writes an audit log row.

| # | From → To | Trigger |
|---|---|---|
| T01 | DISCOVERED → ANALYZING | user starts analysis |
| T02 | DISCOVERED → ARCHIVED | user discards (reason recorded) |
| T03 | ANALYZING → IDEA_READY | analysis completes (≥1 concept + originality attestation) |
| T04 | ANALYZING → ARCHIVED | user cancels / 14-day stale auto-expire |
| T05 | IDEA_READY → PROMPT_READY | user approves a concept |
| T06 | IDEA_READY → IDEA_READY | user requests regeneration (versions retained) |
| T07 | IDEA_READY → ARCHIVED | user rejects all concepts |
| T08 | PROMPT_READY → APPROVED | user approves prompt |
| T09 | PROMPT_READY → PROMPT_READY | user edits prompt (new version, diffed) |
| T10 | PROMPT_READY → IDEA_READY | user requests new concept |
| T11 | PROMPT_READY → ARCHIVED | user shelves |
| T12 | APPROVED → IN_PRODUCTION | user starts / scheduled start |
| T13 | APPROVED → PROMPT_READY | user unfreezes for edits |
| T14 | APPROVED → ARCHIVED | user shelves |
| T15 | IN_PRODUCTION → QUALITY_CHECK | user marks batch complete |
| T16 | QUALITY_CHECK → COMPLIANCE_REVIEW | checks pass (or user override, logged) |
| T17 | QUALITY_CHECK → IN_PRODUCTION | checks fail (rework, `rework_count`+1) |
| T18 | COMPLIANCE_REVIEW → READY_TO_UPLOAD | compliance outcome PASS |
| T19 | COMPLIANCE_REVIEW → IN_PRODUCTION | outcome REVIEW, remediable |
| T20 | COMPLIANCE_REVIEW → ARCHIVED | outcome HIGH_RISK, user abandons (explicit confirm) |
| T21 | READY_TO_UPLOAD → SUBMITTED | planner slot + user-confirmed upload |
| T22 | READY_TO_UPLOAD → IN_PRODUCTION | user spots late issue (rework) |
| T23 | READY_TO_UPLOAD → ARCHIVED | user shelves (planner slot released) |
| T24 | SUBMITTED → ACCEPTED | Adobe acceptance recorded |
| T25 | SUBMITTED → REJECTED | Adobe rejection recorded (reason captured) |
| T26 | REJECTED → IN_PRODUCTION | user reworks per feedback (acknowledge reason) |
| T27 | REJECTED → ARCHIVED | user abandons |
| T28 | ACCEPTED → ARCHIVED | user archives / 90-day auto-archive |
| T29 | ARCHIVED → DISCOVERED | user unarchives (explicit; history preserved) |

Additional rules: `ARCHIVED` reachable from any state; backward moves (e.g. COMPLIANCE_REVIEW
→ IN_PRODUCTION) allowed and logged. Pause is a flag, not a state (valid pre-submission;
forbidden in SUBMITTED/ACCEPTED/REJECTED/ARCHIVED).

### 4.4 `compliance_result`
`PASS` — may proceed · `REVIEW` — human review required before proceeding ·
`HIGH_RISK` — strongly recommended not to proceed without changes.
One HIGH_RISK finding → HIGH_RISK overall. Never implies guaranteed Adobe acceptance.

### 4.5 `compliance_check_type`
`PROMPT_SCREEN` · `ASSET_SCREEN` · `SIMILARITY_SCAN` · `METADATA_SCREEN`

### 4.6 `rule_severity`
`INFO` (advisory) · `WARN` (→ REVIEW) · `BLOCK` (→ HIGH_RISK)

### 4.7 `risk_level`
`LOW` · `MEDIUM` · `HIGH` · `CRITICAL`

### 4.8 `idea_status`
`DRAFT` · `READY` · `IN_QUEUE` · `ARCHIVED` · `DISCARDED`

### 4.9 `prompt_status`
`DRAFT` · `READY` · `APPROVED` · `ARCHIVED`

### 4.10 `asset_type` / 4.11 `asset_status`
`IMAGE` · `VIDEO` / `DRAFT` · `IN_REVIEW` · `FINAL` · `REJECTED`

### 4.12 `prediction_horizon`
`H30_DAYS` (~30 days) · `H90_DAYS` (~90 days) · `H6_MONTHS` (~6 months) · `H12_MONTHS` (~12 months)

### 4.13 `predicted_direction`
`up` · `flat` · `down`

### 4.14 `notification_type`
`BRIEFING_READY` · `OPPORTUNITY_FOUND` · `TREND_ALERT` · `COMPLIANCE_ALERT` ·
`SUBMISSION_UPDATE` · `PRODUCTION_REMINDER` · `PERFORMANCE_DIGEST` · `SYSTEM`

### 4.15 `notification_channel`
`IN_APP` · `EMAIL`

### 4.16 `agent_status` / 4.17 `agent_log_level`
`PENDING` · `RUNNING` · `COMPLETED` · `FAILED` · `CANCELLED` /
`DEBUG` · `INFO` · `WARNING` · `ERROR`

### 4.18 `agent_run_kind`
`TREND_INGEST` · `MARKET_ANALYSIS` · `OPPORTUNITY_SCAN` · `IDEA_GENERATION` ·
`PROMPT_GENERATION` · `COMPLIANCE_SCREEN` · `METADATA_DRAFT` · `PERFORMANCE_DIGEST` ·
`BRIEFING_BUILD`

### 4.19 `job_status`
`queued` · `running` · `succeeded` · `failed` · `cancelled` · `dead_letter`

### 4.20 `saved_item_kind`
`TREND_SIGNAL` · `OPPORTUNITY` · `IMAGE_IDEA` · `VIDEO_IDEA` · `PROMPT` · `PREDICTION`

### 4.21 `submission_status`
`PLANNED` · `SUBMITTED` · `UNDER_REVIEW` · `ACCEPTED` · `REJECTED`

### 4.22 `trend_source_type`
`adobe_report` · `search_trends` · `social_trends` · `marketplace_feed` · `user_upload` · `other`

### 4.25 `source_status` (v0.3.0 — Phase 2)
`AVAILABLE` — healthy, returning real data ·
`CONFIGURED` — credentials set, not yet verified ·
`NEEDS_AUTH` — needs user credentials/config ·
`UNAVAILABLE` — cannot run in this environment ·
`TEMP_FAILING` — transient failure.

### 4.26 `collection_run_status` / `collection_run_trigger` (v0.3.0 — Phase 2)
Status: `QUEUED` · `RUNNING` · `SUCCESS` · `PARTIAL` · `FAILED` · `SKIPPED`
(skipped = source not collectable, e.g. NEEDS_AUTH/UNAVAILABLE — never fabricates data).
Trigger: `SCHEDULED` · `MANUAL` · `API`.

### 4.23 Score ranges
All scores are 0–100 numbers (integers on the wire; 2 decimals allowed in storage).
Score bands (docs/07): high ≥ 70 → accent · medium 40–69 → text.secondary · low < 40 → text.muted.
Confidence 0–1 on the wire as decimal (e.g. `0.825`); displayed as percent.
Saturation bands: 0–30 Open · 31–55 Moderate · 56–75 Crowded · 76–100 Saturated.

### 4.24 The 13 agent names (canonical, docs/13 §2)
`trend_research` · `market_analysis` · `category_intelligence` · `opportunity` ·
`image_ideation` · `video_ideation` · `prediction` · `prompt` · `compliance` ·
`originality` · `metadata` · `production_planning` · `performance_analysis`

---

## 5. Endpoint groups

Notation per endpoint: **Method Path** — purpose. Request shape, response shape,
error cases, and DB entities touched. All paths are prefixed with `/api`.
`(ext)` marks contract extensions beyond docs/12. All endpoints are single-user
(no auth) per §1.1.

### 5.1 `/health` — service health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + DB reachability. Public. |

Response `200`: `{ status: "ok", service: "stockpulse-ai", version: "0.2.0",
timestamp: ISO-8601, database: "ok" | "degraded" }`.
Entities: none (DB ping only). **Implemented in Phase 1.**

### 5.2 `/trends` — trend discovery (entities: `trend_sources`, `trend_snapshots`, `trend_signals`, `micro_niches`, `categories`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/trends` | List trends. Filters: `category` (slug), `window` (`7d`\|`30d`\|`90d`), `min_score` (0–100). Sort: `-score`, `velocity`. |
| GET | `/trends/{id}` | Trend detail: signal breakdown + provenance per signal. |
| GET | `/trends/{id}/signals` | Raw contributing signals with source attribution. |
| POST | `/trends/refresh` | Trigger on-demand aggregation → `202 { job_id }`. Rate-limited (5/hr). |

Trend item: `{ id: uuid, title: string, score: 0–100, window: "7d",
provenance: DataProvenance, categories: string[], signal_count: int,
created_at, updated_at }`.
Errors: 404 `TREND_NOT_FOUND`, 429 `RATE_LIMITED`.

### 5.3 `/categories` — taxonomy (entities: `categories`, `subcategories`, `micro_niches`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/categories` | List 39 top-level categories with trend coverage + taxonomy version. |
| GET | `/categories/{id}` | Detail: subcategories, top micro-niches, saturation notes. |

Category: `{ id, name, slug, description, sort_order, is_system, subcategories?: [...],
trend_coverage: { signal_count: int, avg_score: number|null }, created_at, updated_at }`.
Errors: 404 `CATEGORY_NOT_FOUND`.

### 5.4 `/opportunities` — opportunities (entities: `opportunities`, `micro_niches`, `projects`, `audit_logs`)

Opportunity: `{ id, project_id: uuid|null, micro_niche_id: uuid|null, title,
summary, opportunity_score: 0–100, confidence: 0–1, demand_evidence: [{signal_id,
metric_id, note}], risk_notes: string|null, data_provenance, status: "new"|"approved"|
"rejected"|"in_progress"|"archived", priority: int, reviewed_at: ISO|null,
personal_fit_score: 0–100|null (v0.3.0 — Phase 2: fit of the opportunity against the
user's own private performance; `null` when no private data, never guessed; kept
separate from opportunity_score), agent_run_id: uuid|null, created_at, updated_at }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/opportunities` | List. Filters: `status`, `category`, `min_score`. Sort: `-opportunity_score`, `priority`. |
| POST | `/opportunities` | Create manually. Body: `{ title, summary, micro_niche_id?, project_id?, priority? }`. |
| GET | `/opportunities/{id}` | Detail incl. evidence + scores + provenance. |
| PATCH | `/opportunities/{id}` | Edit fields / reprioritize. |
| POST | `/opportunities/{id}/approve` | Approve → human gate to ideation. Body: `{ priority?: "high"\|"normal"\|"low", note?: string }`. Idempotent via `Idempotency-Key`. |
| POST | `/opportunities/{id}/reject` | Reject with `{ reason: string }`. |
| POST | `/opportunities/{id}/archive` | Archive. |
| DELETE | `/opportunities/{id}` | Hard delete (explicit; audit-logged). |

Errors: 404 `OPPORTUNITY_NOT_FOUND`, 400 `INVALID_TRANSITION` (approve from wrong status),
409 `DUPLICATE_RESOURCE`. Approve response: `{ id, status: "approved", approved_at }`.

### 5.5 `/ideas` — image & video ideation (entities: `image_ideas`, `video_ideas`, `opportunities`, `agent_runs`)

Idea (both kinds): `{ id, kind: "image"|"video", project_id?, opportunity_id?,
micro_niche_id?, title, concept: string, originality_notes: string (required),
reference_mood: string[]|null, duration_target_seconds?: int|null (video),
shot_list?: [{shot, camera_move, duration_s, notes}]|null (video),
status: IdeaStatus, priority: int, reviewed_at?, agent_run_id?, created_at, updated_at }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/ideas` | List. Filters: `kind=image\|video`, `opportunity_id`, `status`. |
| POST | `/ideas` | Create from approved opportunity (or freeform). Body: `{ kind, title, concept, originality_notes (required), opportunity_id?, micro_niche_id?, reference_mood?, duration_target_seconds?, shot_list? }`. |
| GET | `/ideas/{id}` | Detail with linked opportunity + concepts. |
| PATCH | `/ideas/{id}` | Edit. |
| POST | `/ideas/{id}/generate-concepts` | Enqueue ideation agent run → `202 { job_id }`. `Idempotency-Key` supported. |
| POST | `/ideas/{id}/archive` | Archive. |

Errors: 404 `IDEA_NOT_FOUND`, 422 `AGENT_FAILED`.

### 5.6 `/prompts` — prompt packages (entities: `prompts`, `prompt_versions`, `image_ideas`, `video_ideas`, `agent_runs`)

Prompt: `{ id, image_idea_id: uuid|null, video_idea_id: uuid|null, asset_type,
name, status: PromptStatus, current_version: { version_number, prompt_text,
negative_prompt_text?, parameters: {...}, change_summary?, created_by: "user"|"agent",
created_at }, versions_count: int, approved_version_number: int|null, created_at, updated_at }`.
Exactly one of `image_idea_id`/`video_idea_id` is set.

| Method | Path | Purpose |
|---|---|---|
| GET | `/prompts` | List. Filters: `idea_id`, `status`, `asset_type`. |
| POST | `/prompts` | Generate via PromptAgent → `202 { job_id }`. Body: `{ idea_id, asset_type, tool?: string }`. |
| GET | `/prompts/{id}` | Detail incl. current version text + originality note. |
| GET | `/prompts/{id}/versions` | Immutable version history (ascending). |
| POST | `/prompts/{id}/versions` | Save edited version → new immutable version. Body: `{ prompt_text, negative_prompt_text?, parameters?, change_summary }`. |
| POST | `/prompts/{id}/regenerate` | Regenerate with feedback → `202 { job_id }`. Body: `{ feedback: string }`. |
| PATCH | `/prompts/{id}` | Update metadata (name, status) — never rewrites latest version. |

Errors: 404 `PROMPT_NOT_FOUND`, 422 `AGENT_FAILED`. Generate/regenerate: 60/hr, `Idempotency-Key`.

### 5.7 `/compliance` — compliance checks (entities: `compliance_checks`, `compliance_rules`, `similarity_records`, `agent_runs`)

Check: `{ id, check_type: ComplianceCheckType, subject: { kind: "prompt"|"asset"|"image_idea"|"video_idea"|"metadata"|"production_queue", id, version_id? },
result: PASS|REVIEW|HIGH_RISK, risk_level, findings: [{ check_id, rule_key, rule_version,
severity, triggered: bool, explanation, matched_excerpt?, remediation }],
explanation: string, rules_version: string, review_decision?: "accepted"|"accepted_with_changes"|"rejected",
reviewed_at?, agent_run_id?, created_at }`.
Language rule: outcomes say "assessed as", never "guaranteed acceptance".

| Method | Path | Purpose |
|---|---|---|
| POST | `/compliance/checks` | Run check → `202 { job_id }` (or `201` with result if fast). Body: `{ check_type, subject_kind, subject_id, subject_version_id? }`. `Idempotency-Key`. |
| GET | `/compliance/checks` | List. Filters: `result`, `check_type`, `subject_kind`, `pending_review=true`. |
| GET | `/compliance/checks/{id}` | Result with findings + explanations. |
| POST | `/compliance/checks/{id}/review` | Human review decision. Body: `{ decision: "accepted"|"accepted_with_changes"|"rejected", note?: string }`. Audit-logged. |

Errors: 404 `COMPLIANCE_CHECK_NOT_FOUND`, 422 `COMPLIANCE_BLOCKED` (HIGH_RISK blocks
queue entry). 120/hr. Fail-closed: check errors → REVIEW, never PASS (docs/26 §4.7).

### 5.8 `/similarity` — similarity risk (entities: `similarity_records`, `compliance_checks`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/similarity/checks` | Embedding scan vs market clusters → `202 { job_id }`. Body: `{ subject_kind: "image_idea"|"video_idea"|"prompt"|"asset", subject_id }`. |
| GET | `/similarity/checks/{id}` | Result: `{ id, subject, risk_level, records: [{ compared_cluster_label, similarity_score: 0–1, risk_level, cluster_sample_count, differentiators }], data_provenance, created_at }`. Cluster labels are descriptive; never identify individual artists. |

Errors: 422 `AGENT_FAILED` / `E-SIM-501`. 120/hr. Service down → items held in REVIEW
(`similarity-unavailable`), never assumed unique (docs/26 §4.8).

### 5.9 `/assets` — assets & uploads (entities: `assets`, `asset_versions`, `production_queue`, `prompts`)

Asset: `{ id, project_id?, production_queue_id?, image_idea_id?, video_idea_id?,
prompt_id?, prompt_version_id?, asset_type, title, status: AssetStatus,
current_version: { version_number, storage_uri, mime_type, file_size_bytes?,
width_px?, height_px?, duration_seconds?, file_hash? }|null,
width_px?, height_px?, duration_seconds?, created_at, updated_at }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/assets` | List. Filters: `asset_type`, `status`, `idea_id`, `queue_id`. |
| POST | `/assets` | Register upload/preview → `201 { id, type, status: "processing", upload_url (signed, 15-min), expires_at }`. Client PUTs bytes to `upload_url`. Body: `{ title, asset_type, mime_type, production_queue_id?, idea_id?, prompt_id? }`. |
| GET | `/assets/{id}` | Metadata + signed download URL. |
| POST | `/assets/{id}/versions` | Register a new file version (edit/re-export). |
| DELETE | `/assets/{id}` | Delete asset + storage object (explicit confirm; audit-logged). |

Errors: 404 `ASSET_NOT_FOUND`, 413 `PAYLOAD_TOO_LARGE`, 415 `UNSUPPORTED_MEDIA_TYPE`.

### 5.10 `/metadata` — metadata bundles (entities: `metadata`, `assets`, `agent_runs`)

Bundle: `{ id, asset_id, version_number, title, description?, keywords: string[],
adobe_category?, micro_niche_id?, language: "en" (BCP-47), is_current: bool,
created_by: "user"|"agent", agent_run_id?, created_at }`. Only one `is_current` per asset.

| Method | Path | Purpose |
|---|---|---|
| GET | `/metadata` | List. Filters: `asset_id`, `is_current`. |
| POST | `/metadata` | Generate draft via MetadataAgent → `202 { job_id }`. Body: `{ asset_id }`. |
| GET | `/metadata/{id}` | Detail. |
| PATCH | `/metadata/{id}` | Human edit of title/keywords/description (creates new version, flips `is_current`). |
| POST | `/metadata/{id}/validate` | Validate against marketplace rules → `{ valid: bool, issues: [{ code, message, severity }] }`. 400 `VALIDATION_ERROR` on hard violations (e.g. keyword count). |

Errors: 404 `METADATA_NOT_FOUND`.

### 5.11 `/production` — production queue (entities: `production_queue`, `assets`, `compliance_checks`, `audit_logs`)

Queue item: `{ id, project_id?, opportunity_id?, image_idea_id?, video_idea_id?,
prompt_id?, asset_type, title, status: ProductionQueueStatus (13 states),
priority_band: "P0"|"P1"|"P2"|"P3"|"P4", priority_score: 0–100 (+ components breakdown),
target_date: date|null, deadline_state: "ON_TRACK"|"AT_RISK"|"OVERDUE"|null,
paused: bool, target_quantity: int, produced_count: int, generation_tool: string|null,
rework_count: int, blocked_reason: string|null, compliance: { result, check_id }|null,
notes: string|null, status_changed_at, created_at, updated_at }`.
`priority_score` formula: `0.35·trend_momentum + 0.25·deadline_urgency + 0.25·predicted_value +
0.15·user_boost − 5·min(rework_count,3)`, clamped 0–100 (docs/20 §6; components always shown).

| Method | Path | Purpose |
|---|---|---|
| GET | `/production/queue` | Board list. Filters: `status` (multi), `project_id`, `paused`, `overdue=true`. Sort: band, `-priority_score`. |
| POST | `/production/queue` | Enqueue → `201`. Requires compliance PASS for the attached prompt/concept, else 422 `COMPLIANCE_BLOCKED`. `Idempotency-Key`. |
| GET | `/production/queue/{id}` | Detail incl. history (append-only events). |
| POST | `/production/queue/{id}/transition` | State transition. Body: `{ to: ProductionQueueStatus, note?: string }`. Enforces T01–T29 (§4.3); illegal → 400 `INVALID_TRANSITION` with the allowed list. Audit-logged. |
| POST | `/production/queue/{id}/assign` | Set assignee (reserved; single-user → informational). |
| POST | `/production/queue/{id}/pause` | Toggle pause flag. Body: `{ paused: bool, reason?: string }`. Forbidden in SUBMITTED/ACCEPTED/REJECTED/ARCHIVED. |

Errors: 404 `QUEUE_ITEM_NOT_FOUND`, 400 `INVALID_TRANSITION`, 422 `COMPLIANCE_BLOCKED`.

### 5.12 `/submissions` — submission planner (entities: `submission_records`, `assets`, `asset_versions`, `metadata`, `production_queue`, `audit_logs`)

Submission: `{ id, asset_id, asset_version_id, metadata_id, production_queue_id?,
project_id?, status: SubmissionStatus, submitted_at?, reviewed_at?, adobe_reference?,
rejection_reason?, notes?, created_at, updated_at }`.
Hard rule: the API **never submits to Adobe Stock**; `mark-submitted` records the human's action.

| Method | Path | Purpose |
|---|---|---|
| GET | `/submissions` | List. Filters: `status`, `from`/`to` (date range on `submitted_at`). |
| POST | `/submissions` | Create submission plan from `ready` queue items. Body: `{ queue_ids: uuid[], week_start: date }`. `Idempotency-Key`. |
| GET | `/submissions/{id}` | Detail + item checklist + capacity context. |
| POST | `/submissions/{id}/mark-submitted` | Human confirms manual upload. Body: `{ submitted_at?, adobe_reference? }`. `Idempotency-Key`. |
| POST | `/submissions/{id}/record-outcome` | Record accepted/rejected per item → feeds analytics. Body: `{ items: [{ queue_id, outcome: "accepted"|"rejected", reason? }] }`. Rejection requires `reason`. |

Errors: 404 `SUBMISSION_NOT_FOUND`, 400 `INVALID_TRANSITION`.

### 5.13 `/analytics` — performance analytics (entities: `performance_metrics`, `submission_records`, `predictions`, `opportunities`, `agent_runs`)

Every metric carries `data_provenance`; predictions show confidence intervals, never guarantees.
No invented Adobe sales numbers — USER_PROVIDED/VERIFIED rows come only from the user's
own dashboard imports.

| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/overview` | KPI summary for date range. Params: `from`, `to`. Response: `{ range, kpis: { submitted, accepted, acceptance_rate, views?, downloads?, revenue? (each with provenance) }, provenance_notes }`. |
| GET | `/analytics/funnel` | TREND→…→PERFORMANCE conversion counts per stage. |
| GET | `/analytics/opportunities/{id}/performance` | Per-opportunity outcome attribution (sample-size aware). |
| POST | `/analytics/events` | Ingest client events. Body: `{ events: [{ name: "domain.action", entity_id?, route?, at }] }`. |
| GET | `/analytics/exports` | List generated exports. |
| POST | `/analytics/exports` | Request CSV/PDF export → `202 { job_id }`. 10/hr. |

Errors: 400 `VALIDATION_ERROR` (bad date range).

### 5.14 `/agents` — agent runs & jobs (entities: `agent_runs`, `agent_logs`)

Run/job: `{ job_id, run_id?, agent: <one of the 13 canonical names>, run_kind: AgentRunKind,
status: JobStatus, progress: 0–1, input_summary: {...} (no secrets),
output_summary: {...}|null, error: { code, message }|null, instructions_version,
started_at?, finished_at?, created_at }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | List the 13 agent definitions + capabilities + enabled flags. |
| GET | `/agents/jobs` | List jobs. Filters: `status`, `agent`, `run_kind`. |
| GET | `/agents/jobs/{job_id}` | Job status + progress + result/error. (Poll target for all 202 flows.) |
| POST | `/agents/jobs/{job_id}/cancel` | Cancel queued/running job. Terminal job → 409 `CONFLICT`. |
| GET | `/agents/dead-letters` | Dead-letter jobs. |
| POST | `/agents/dead-letters/{id}/retry` | Requeue. `Idempotency-Key`. |

Errors: 404 `JOB_NOT_FOUND`, 409 `CONFLICT`.

### 5.15 `/settings` — settings (entities: `settings`) — single-user

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings/public` | Non-sensitive subset: `{ app_env, api_version, feature_flags: {...safe...} }`. |
| GET | `/settings` | All settings as `{ key: value }` map (+ canonical key list). |
| PATCH | `/settings` | Update. Body: `{ key: value }` or `{ settings: [{ key, value }] }`. Unknown keys → 400 `VALIDATION_ERROR`. Audit-logged. |
| GET | `/settings/feature-flags` | Effective flag values. |

Canonical keys (docs/08 §3.3 + docs/21): `briefing.time`, `briefing.timezone`,
`briefing.days`, `opportunity.min_score`, `opportunity.min_confidence`,
`compliance.strictness` (`standard`|`strict`), `notifications.email_enabled`,
`notifications.digest_time`, `production.default_language`, `retention.soft_delete_days`,
`planner.daily_capacity`, `planner.weekly_capacity`, `planner.blackout_dates`.

### 5.16 `/notifications` — inbox **(ext)** (entities: `notifications`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications` | Inbox list. Filters: `unread=true`, `type`. Returns unread count. Item: `{ id, type: NotificationType, title, body, link_entity_kind?, link_entity_id?, channel, is_read, read_at?, created_at }`. |
| POST | `/notifications/{id}/read` | Mark read. |
| POST | `/notifications/read-all` | Mark all read. |

### 5.17 `/library` — saved items **(ext)** (entities: `saved_items`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/library` | Saved bookmarks. Filters: `kind` (SavedItemKind), `q`. Item: `{ id, item_kind, item_id, note?, created_at }`. |
| POST | `/library` | Save. Body: `{ item_kind, item_id, note? }`. Duplicate → 409 `DUPLICATE_RESOURCE`. |
| DELETE | `/library/{id}` | Unsave (hard delete of the row). |

### 5.18 `/sources` — data sources & collection runs **(v0.3.0 — Phase 2, ext)**

Source: `{ id, name, source_type: string, endpoint_or_reference?, fetch_schedule?,
is_active, data_provenance, last_fetched_at, health: SourceHealth|null,
created_at, updated_at }`.
SourceHealth: `{ id, trend_source_id, status: SourceStatus, last_success_at?,
last_failure_at?, last_error?, records_collected, avg_duration_ms?,
consecutive_failures, checked_at?, auth_state?, fallback_status? }`.
CollectionRun: `{ id, trend_source_id, status: CollectionRunStatus,
trigger: CollectionRunTrigger, started_at?, finished_at?, records_collected,
records_stored, duration_ms?, error?, created_at, updated_at }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/sources` | List sources with health summary + provenance. |
| GET | `/sources/health` | All SourceHealth rows. |
| GET | `/sources/runs` | Collection runs (newest first). |
| GET | `/sources/runs/{id}` | Run detail. |
| GET | `/sources/{id}` | Source detail + recent runs. |
| POST | `/sources/{id}/collect` | Manual collection → `202 { run_id, job_id, status: "queued" }`. Rate-limited (5/hr). Sources in NEEDS_AUTH/UNAVAILABLE record SKIPPED, never fake data. |

Errors: 404 `SOURCE_NOT_FOUND`, 404 `COLLECTION_RUN_NOT_FOUND`, 429 `RATE_LIMITED`.

### 5.19 `/private` — Adobe Contributor connection & private performance **(v0.3.0 — Phase 2, ext)**

Hard rules: session config is stored server-side in the settings table and is
NEVER echoed in any response (only presence/configured flags); `PATCH /settings`
on the `adobe_contributor` key is rejected; `/connection/test` validates
presence/format only and never simulates success; no earnings/downloads are ever
fabricated — performance endpoints return honest empty states when no data.

| Method | Path | Purpose |
|---|---|---|
| GET | `/private/connection` | Connection status: `{ status: "NOT_CONFIGURED"\|"CONFIGURED"\|"ERROR", configured, session_type?, required_config: string[], last_sync?, error? }`. Honest NOT_CONFIGURED default. |
| PUT | `/private/connection` | Store session config. Body: `{ session_type, session_data: {...}, notes? }`. Response never echoes secrets. |
| POST | `/private/connection/test` | Validate config presence/format → `{ valid, missing: string[], message }`. Never contacts Adobe. |
| GET | `/private/performance/summary` | `{ has_data, totals: { earnings, downloads, currency, assets_tracked }?, earnings_trend: [{date, earnings, downloads}], downloads_trend, by_category, acceptance_rate?, message? }`. Honest empty state when no data. |
| GET | `/private/performance/categories` | Per-category latest snapshot: `[{ category, downloads, earnings, asset_count, snapshot_date? }]`. |
| GET | `/private/performance/keywords` | Per-keyword latest snapshot: `[{ keyword, downloads, earnings, snapshot_date? }]`. |

---

## 6. Frontend route map (no login — app opens into Dashboard)

| Route | Screen | Primary API groups |
|---|---|---|
| `/` | Dashboard | `/analytics/overview`, `/opportunities`, `/notifications` |
| `/daily` | Daily Intelligence (briefing) | `/agents` (BRIEFING_BUILD runs), `/opportunities`, `/trends` |
| `/trends` | Trend Explorer | `/trends`, `/categories` |
| `/opportunities` | Opportunity Explorer (+ `/opportunities/[id]`) | `/opportunities`, `/ideas` |
| `/image-ideas`, `/video-ideas` | Image / Video Ideas | `/ideas` |
| `/prompt-studio` | Prompt Studio (+ `/prompt-studio/[id]`) | `/prompts` |
| `/compliance` | Compliance Center | `/compliance` |
| `/similarity` | Similarity Center | `/similarity` |
| `/queue` | Production Queue | `/production` |
| `/planner` | Submission Planner | `/submissions`, `/settings` (capacity) |
| `/metadata` | Metadata Studio (+ `/metadata/[assetId]`) | `/metadata`, `/assets` |
| `/library` | Content Library | `/library` |
| `/analytics` | Analytics | `/analytics` |
| `/agents` | AI Agent Center (+ `/agents/runs/[runId]`) | `/agents` |
| `/settings` | Settings | `/settings` |
| `/help` | Help | static |

There is NO `/login` route. Detail drawers use query params (`?concept=`, `?review=`);
shareable deep routes use path segments (`/opportunities/[id]`, `/prompt-studio/[id]`).

---

## 7. Type discipline

- Backend: Pydantic v2 models for every request/response (no `dict` payloads on the wire
  except `details`/`parameters` JSON fields, which are typed as `dict[str, Any]` with
  documented shapes). Enums as `str, Enum` (see `app/schemas/enums.py`).
- Frontend: TypeScript strict; `types/index.ts` mirrors every enum and envelope.
  No `any` in domain types; API calls go through `services/api.ts` only.
- Score math lives in `frontend/lib/scores.ts` and `backend/app/engines/` — both MUST
  implement §8 identically.

---

## 8. Scoring formulas (docs/15 — both sides interpret identically)

All scores 0–100. `norm100(x) = 100 × (x − p5) / (p95 − p5)`, clipped [0,100], where
p5/p95 are the 5th/95th percentiles of the metric's trailing 12-week per-category history.
Raw metric inputs (clipped): TV/SG/KM ∈ [−1,+3]; EG/SE/CR/CD/CO/CS/MC/freshness ∈ [0,1].

### 8.1 Trend Score (TS) — "How hot is this trend right now?"
`TS = clip(0.30·TV₁₀₀ + 0.25·SG₁₀₀ + 0.20·KM₁₀₀ + 0.15·EG₁₀₀ + 0.10·(SE×100), 0, 100)`
Inputs: Trend Velocity (Third-party) 0.30 · Search Growth (Third-party) 0.25 ·
Keyword Momentum (Third-party) 0.20 · Engagement Signals (Third-party) 0.15 ·
Seasonality (Estimated) 0.10.

*Worked example* (micro-niche "Data Center AI Computing", 2026-09-18):
TV₁₀₀=78, SG₁₀₀=71, KM₁₀₀=66, EG₁₀₀=58, SE=0.40 →
TS = 0.30×78 + 0.25×71 + 0.20×66 + 0.15×58 + 0.10×40 = 23.4+17.75+13.2+8.7+4.0 = **67**.

### 8.2 Opportunity Score (OS) — "Should we act on this?"
`OS = clip(0.35·TS + 0.25·(CR×100) + 0.20·(CD×100) + 0.20·(100 − CS×100), 0, 100)`
Inputs: Trend Score (derived, Third-party) 0.35 · Commercial Relevance (Estimated) 0.25 ·
Content Demand (Estimated) 0.20 · niche room = 100 − saturation (Estimated) 0.20.

**Confidence gating (binding):** an opportunity is actionable only if OS ≥ 55 AND
data-confidence ≥ 0.5, where
`data-confidence = 0.5·MC + 0.3·source_freshness + 0.2·(min(n_sources,4)/4)`.
If data-confidence < 0.5 the score is reported but flagged *"insufficient evidence —
do not act"*. At PC < 35 the opportunity is blocked from the actionable list regardless of OS.

*Worked example:* TS=67, CR=0.72, CD=0.61, CS=0.44 →
OS = 0.35×67 + 0.25×72 + 0.20×61 + 0.20×56 = 23.45+18.0+12.2+11.2 = **65**.
Data-confidence: MC=0.71, freshness=0.9, n=5 → 0.5×0.71+0.3×0.9+0.2×1.0 = **0.825** → actionable.

### 8.3 Commercial Potential Score (CPS) — "How sellable is this niche?"
`CPS = clip(0.35·(CR×100) + 0.25·(CD×100) + 0.15·(SE×100) + 0.15·(100 − CO×100) + 0.10·format_fit, 0, 100)`

*Worked example:* CR=72, CD=61, SE=40, CO=0.52 → 48, format_fit=80 →
CPS = 0.35×72+0.25×61+0.15×40+0.15×48+0.10×80 = 25.2+15.25+6.0+7.2+8.0 = **62**.

### 8.4 Content Saturation Score (CSS) — "How crowded is this niche?" (higher = more saturated)
`CSS = clip(100 × (0.55·CS + 0.45·CO), 0, 100)`
Bands: 0–30 Open · 31–55 Moderate · 56–75 Crowded · 76–100 Saturated.
Saturated → max 2 assets guidance; Open → up to 8.

*Worked example:* CS=0.44, CO=0.52 → CSS = 100×(0.55×0.44+0.45×0.52) = **48** (Moderate).

### 8.5 Prediction Confidence (PC) — "How much should we trust these numbers?"
`PC = clip(0.30·(MC×100) + 0.25·freshness₁₀₀ + 0.20·(min(n,5)/5×100) + 0.15·stability₁₀₀ + 0.10·user_agreement₁₀₀, 0, 100)`
where stability = 100 − norm100(volatility of TS over 12 wks); user_agreement = 100 (agrees) /
50 (absent) / 0 (contradicts).

*Good data:* MC=71, freshness=90, n=5, stability=68, user=50 → PC = **79**.
*Poor data:* MC=30, freshness=25, n=1, stability=40, user=50 → PC = **30** → outputs marked
"low confidence — directional only"; PC < 50 requires the degraded badge in UI and
`"prediction_status": "degraded"` for API consumers.

### 8.6 Priority score (production queue, docs/20 §6)
`priority_score = 0.35·trend_momentum + 0.25·deadline_urgency + 0.25·predicted_value +
0.15·user_boost − 5·min(rework_count, 3)`, clamped [0,100].
`deadline_urgency = 100×(1 − days_remaining/30)` clamped [0,100] (100 when overdue; 0 if no
deadline). `user_boost`: P0=100, P1=75, P2=50, P3=25, P4=0. Components always shown as a
breakdown — never a bare number.

---

## 9. Compliance language rules (binding on both sides)

- Outcomes are `PASS` / `REVIEW` / `HIGH_RISK` with written evidence + rule citation.
  Never "will be accepted" / "guaranteed".
- Predictions are probabilistic: "estimated", "with X% confidence". Never "will sell".
- No Adobe Stock sales statistics may be invented or displayed unless
  `provenance` is `USER_PROVIDED`/`VERIFIED` (user's own dashboard imports).
- Similarity evidence describes clusters, never individual artists.

---

## 10. Contract change process

1. Propose the change against this file (PR description references the CONTRACT section).
2. Update `CONTRACT.md`, `backend/app/schemas/`, and `frontend/types/` in the same change.
3. Bump the contract version in `CHANGELOG.md` and in `GET /api/health` (`version` field).
4. Non-breaking additions (new optional fields/endpoints) need no version bump beyond the
   changelog entry. Breaking changes require a migration note in the changelog.

*End of CONTRACT.md — v0.2.0*
