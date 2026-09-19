# StockPulse AI

Personal **single-user** Adobe Stock intelligence web app. It implements the product
pipeline from the specification package in `../stockpulse-ai-docs/` (36 documents, v0.1.0):

> **TREND → INSIGHT → OPPORTUNITY → ORIGINAL CONCEPT → ORIGINAL PROMPT → QUALITY CHECK → PRODUCTION → SUBMISSION → PERFORMANCE FEEDBACK**

Never TREND → COPY → RECREATE. The platform identifies market trends; it never
reproduces individual artists' work.

## Single-user by design

This is **not** SaaS. There is **no** login, signup, password reset, JWT auth, roles,
permissions, multi-tenancy, organizations, teams, user management, or `/auth`/`/users`
endpoints. The app opens directly into the Dashboard. UUID primary keys and
`created_at`/`updated_at` audit fields are kept. The `settings` table stores the single
user's capacity config and thresholds. See `CHANGELOG.md` (0.2.0) and `CONTRACT.md` §1.1.

## Monorepo layout

```
stockpulse/
├── CONTRACT.md        # Binding backend↔frontend API contract (read first)
├── SEED_PLAN.md       # Seed data plan: 39 categories, trend sources, compliance rules
├── README.md          # This file
├── CHANGELOG.md
├── .env.example       # All env vars (placeholders only — never real values)
├── backend/           # FastAPI + SQLAlchemy + Pydantic
│   ├── app/
│   │   ├── main.py            # App entrypoint; mounts /api routers
│   │   ├── api/routers/       # 17 endpoint groups (health implemented in Phase 1)
│   │   ├── core/              # config, error envelope, deps
│   │   ├── models/            # SQLAlchemy models (settings in Phase 1)
│   │   ├── adapters/          # Phase 2: source adapters (13 types, guarded registry)
│   │   ├── schemas/           # Pydantic schemas + full enum set
│   │   ├── services/          # Business logic (Phase 2+)
│   │   ├── engines/           # Scoring engines — formulas in CONTRACT.md §8 (Phase 3+)
│   │   ├── agents/            # 13 supervised agents (later phases)
│   │   ├── workers/           # Background jobs (later phases)
│   │   │                      # Phase 2: APScheduler collection (Adobe 06:00,
│   │   │                      # public trends 07:00, RSS/YT/GitHub 6-hourly,
│   │   │                      # health checks 15-min; Asia/Karachi)
│   │   └── db/                # Engine, session, Base + mixins, init_db
│   ├── requirements.txt       # Pinned versions
│   └── pyproject.toml         # black + ruff config
└── frontend/          # Next.js 14 (App Router) + TypeScript + Tailwind
    ├── app/                   # Routes: / (dashboard), /daily, /trends, /opportunities,
    │                          # /image-ideas, /video-ideas, /prompt-studio, /compliance,
    │                          # /similarity, /queue, /planner, /metadata, /library,
    │                          # /analytics, /agents, /settings, /help — NO /login
    ├── components/            # Shell (sidebar nav) + PageShell placeholder
    ├── lib/scores.ts          # Score helpers — mirrors CONTRACT.md §8
    ├── services/api.ts        # Typed API client (base: NEXT_PUBLIC_API_BASE_URL)
    ├── types/index.ts         # TS enums — mirrors CONTRACT.md §4
    └── styles/globals.css     # Design tokens as CSS vars (docs/07 verbatim)
```

## Run it (local dev)

**Backend** (Python 3.12):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL only if switching DB (see below)
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
# Health: curl http://localhost:8000/api/health
```

**Frontend** (Node 24):

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev   # http://localhost:3000
# Optional: headless Chrome for on-demand Remotion video renders
npm run remotion:browser   # see frontend/remotion/REMOTION.md
```

## Phase 2 — Real-data integration layer (v0.4.0)

Mock data no longer drives production intelligence. Fourteen source adapters
(`backend/app/adapters/`) collect real data behind one interface
(collect/validate/normalize/deduplicate/score_quality/store/get_status):

| Adapter | What it collects | Config needed |
|---|---|---|
| `rss` | Design/photography blog + press feeds | None (feed list in `rss_feeds` setting) |
| `scrapegraph_web` | Web search (DuckDuckGo, keyless) + article extraction | None; `OPENAI_API_KEY` unlocks the LLM tier |
| `agentreach_web` | Article fetch via Jina Reader | None |
| `v2ex` | Tech-community hot topics | None |
| `xueqiu` | Hot stocks / market posts | Login cookies for full access |
| `youtube_rss` | Channel video feeds (no yt-dlp) | None |
| `github_trending` | Trending AI repos (official API) | None (`GITHUB_TOKEN` raises rate limit) |
| `huginn` | Your self-hosted Huginn event output | `HUGINN_BASE_URL` + `HUGINN_API_KEY` |
| `reddit` / `x_trends` / `instagram` / `facebook` | Social signals | User-provided session/cookies (see each adapter) |
| `adobe_contributor` | YOUR private contributor performance | Browser-export session via the UI (below) |

Key pages: `/sources` (Data Sources), `/sources/health` (Source Health),
`/runs` (Collection Runs), `/private` (Private Performance + Adobe setup).
The dashboard shows live source status, data freshness, and private summaries.
Badges distinguish LIVE / REAL / MOCK / ESTIMATED / PREDICTED everywhere;
`dev_mode` (default off) gates whether MOCK rows influence intelligence.

**Run a collection manually:**

```bash
curl -X POST http://localhost:8000/api/sources/<source_id>/collect
```

The scheduler (APScheduler, in-process) runs collections automatically:
Adobe daily 06:00, public trends daily 07:00, fast sources every 6h, health
checks every 15min. Disable with `STOCKPULSE_SCHEDULER_ENABLED=false`.

**Ollama (local LLM, optional):** keeps private data on your machine —
`STOCKPULSE_LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL` (default
`http://localhost:11434`), `OLLAMA_MODEL`.

**Connect Adobe private data** (in the app: Private Performance page):
1. Open your Adobe Stock Contributor dashboard in your own browser.
2. Export the session (cookies) with a cookie-export extension.
3. Paste it into the Adobe Contributor Connection panel → Save.
4. Press **Sync now**. Status, last sync, and errors are shown honestly;
   until configured, the app reports `NOT_CONFIGURED` and uses no Adobe data.
Session material is stored server-side only, never shown in the UI, never
logged, never committed. No Adobe credentials → no Adobe data, ever — nothing
is simulated.

## Phase 3 — Personal intelligence + opportunity fusion + daily production planner (v0.5.0)

Answers **"WHAT SHOULD I CREATE TODAY?"** (`/daily` — MARKET / PERSONAL /
FUSION / ACTION zones):

- **Personal Performance Engine** — your private Adobe history (when
  connected): per-category, per-content-type (IMAGE/VIDEO separately), and
  theme metrics across 7d/30d/90d windows; momentum, consistency, acceptance.
  Honest `not_configured` when Adobe is unconnected — no invented numbers.
- **Opportunity Fusion Engine** — `UNIFIED = clip(Σ(w·c)/Σ(w) − 0.15·saturation_risk, 0, 100)`,
  labeled **FUSED** (market + personal) or **MARKET-ONLY** (public signals
  only, confidence lowered). High-market/poor-fit and high-fit/weak-market
  cases are explained, never auto-rejected. Exact formulas:
  `backend/PHASE3_FORMULAS.md`.
- **Daily Production Planner** — capacity-aware, diversified daily plan;
  recommendations carry evidence ("why") and require your explicit approval.
- **Concepts → compliance → prompt packs** — generate screened concept
  variations per recommendation; record your AI-disclosure decision to
  re-screen; HIGH_RISK blocks promotion until resolved; build export-only
  prompt packs (Muse = export only, nothing auto-generates).
- **Production queue** — approvals create DISCOVERED queue items; only legal
  T01–T29 transitions; nothing auto-submits, ever.
- **Video** — Remotion `ConceptPreview` (storyboard motion previz per video
  concept) and `DailyBriefing` (one-click "what to create today" MP4),
  rendered on demand only; see `frontend/remotion/REMOTION.md`.

Acceptance evidence: `PHASE3_ACCEPTANCE.md`. Design language: dark luxury
(champagne-gold accent, racing-red alerts only), F1-grade telemetry numerals,
Motion UI animation with `prefers-reduced-motion`, lazy 3D data viz.

## Database: SQLite fallback + Postgres switch

The environment has **no Docker and no PostgreSQL server**, so local dev defaults to
**SQLite** via SQLAlchemy (`DATABASE_URL=sqlite:///./stockpulse.db`).

Types are chosen to be Postgres-compatible from day one (docs/08):
- UUID primary keys stored as `String(36)` (app-generated `uuid4`), not native UUID
- Timezone-aware `DateTime` columns (UTC)
- `JSON` columns for flexible fields
- Enum values as `UPPER_SNAKE_CASE` strings (checked at the app layer in Phase 1;
  native PG enums in a later migration)

**How to switch to Postgres** (when a server is available):

1. Install the driver: `.venv/bin/pip install "psycopg[binary]"`
2. Set `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/stockpulse` in
   `backend/.env` (never commit real credentials).
3. Optional pool tuning: `DB_POOL_SIZE`, `DB_POOL_MAX_OVERFLOW` (add to settings loader).
4. Restart the API. No model changes are needed for the Phase-1 `settings` table.
   Later phases will introduce Alembic migrations; a data-migration note (SQLite →
   Postgres dump/load) belongs in the deployment docs then.

## Key documents

- `CONTRACT.md` — the binding API contract both sides must follow exactly.
- `SEED_PLAN.md` — seed data plan (categories, sources, compliance rules).
- `CHANGELOG.md` — version history incl. the single-user and SQLite deviations.
- `../stockpulse-ai-docs/` — the 36-document specification package (source of truth).

## Standing rules (from the spec package)

- No invented Adobe Stock sales numbers. Ever.
- Predictions are probabilistic with confidence — never guarantees.
- Compliance outcomes are PASS / REVIEW / HIGH_RISK with written explanations —
  never claims of guaranteed Adobe acceptance.
- Every datum carries a provenance label (Verified / User-provided / Third-party /
  Estimated / Predicted); mock data is labeled `MOCK` with a visible "Demo data" badge.
- No content is ever auto-submitted to Adobe Stock; the human submits.
- No secrets in code. `.env` is git-ignored; only `.env.example` is committed.
