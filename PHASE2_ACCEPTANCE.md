# Phase 2 — Test & Real-Data Acceptance Evidence

**Date:** 2026-09-19
**Workspace:** `~/workspace/stockpulse/`
**Acceptance script:** `acceptance/accept_phase2.py`
**Acceptance DB:** `acceptance/acceptance.db`
**Acceptance summary (machine-readable):** `acceptance/acceptance_summary.json`

## 1. Test results

| Scope | Result |
|---|---|
| Full suite (single uninterrupted run) | **419 passed, 0 failed** — see §7 |
| Baseline (pre-Phase 2, user-supplied) | 264 passing |
| New Phase 2 tests (`backend/tests/test_phase2_*.py`) | 155 passing |
| Total collected | 419 (264 + 155) |

New test files and what they cover:

- `test_phase2_adapter_contract.py` — adapter registry contracts (13 adapters), method signatures
- `test_phase2_scrapegraph.py` — ScrapeGraph Tier-1/Tier-2/failure paths; regression for the real
  `List[str]` return shape of scrapegraphai 2.x `search_on_web` (was crashing with
  `AttributeError: 'str' object has no attribute 'get'` on real data)
- `test_phase2_agentreach.py` — Agent-Reach Web/V2EX/Xueqiu mocked collection and health mapping
- `test_phase2_adobe.py` — Adobe default `NOT_CONFIGURED`, secret redaction, validation, browser failure
- `test_phase2_normalization.py` — RSS/YouTube/GitHub normalization and provenance; snapshot
  payload now carries a `topic` (query → source name) so real collections are visible in `/api/trends`
- `test_phase2_private.py` — private append-only tables and aggregation
- `test_phase2_scoring.py` — Personal Fit Score `None` without private data; bounded 0–100 with
  evidence; Opportunity Score kept separate; source-down confidence penalty
- `test_phase2_mock_boundary.py` — MOCK excluded unless dev mode; legacy MOCK default
- `test_phase2_api.py` — source/private/run API queryability
- `test_phase2_scheduler.py` — scheduler success, skip, failure, recovery, persisted failure state

Unit tests never touch the network (external boundaries mocked). Acceptance below used real
network/data.

## 2. Real-data acceptance (2026-09-19, ~05:36–05:37 UTC)

Fresh SQLite DB; real scheduler collections; real network calls; no credentials used anywhere.

| Source | Run status | Collected | Stored | Health | Notes |
|---|---|---|---|---|---|
| RSS feeds (blogs + photography press) | SUCCESS | 20 | 20 | AVAILABLE | Real PetaPixel/press articles |
| ScrapeGraphAI web discovery | SUCCESS | 20 | 20 | AVAILABLE | Keyless DuckDuckGo search; real URLs |
| Agent-Reach web channels | SUCCESS | 2 | 2 | AVAILABLE | Jina Reader fetch of default URLs |
| V2EX hot topics | SUCCESS | 8 | 8 | AVAILABLE | Real topics, e.g. `找工作暂时完结，转行啦` (v2ex.com/t/1243028, 40 replies) |
| Xueqiu | SKIPPED | 0 | 0 | NEEDS_AUTH | Probe flags auth; direct call → HTTP 400 without login cookies |
| YouTube RSS | SUCCESS | 0 | 0 | AVAILABLE | All 5 seeded channel IDs → HTTP 404; one independently real channel ID also 404 → egress/YouTube-side block or stale seeds |
| GitHub trending AI repos | SUCCESS | 20 | 20 | AVAILABLE | Real repos via official GitHub API |
| Adobe Contributor | SKIPPED | 0 | 0 | NEEDS_AUTH | Remains `NOT_CONFIGURED`; no credentials used or simulated |

**DB census:** 5 `TrendSnapshot` rows, 70 `TrendSignal` rows —
`THIRD_PARTY`: 50, `VERIFIED`: 20 (GitHub, authoritative official API).
8 `CollectionRun` rows persisted (6 SUCCESS incl. one 0-record, 2 SKIPPED).
Zero `MOCK` rows drove any intelligence (dev_mode off).

**ScrapeGraph Tier-1 explicit attempt:**
- `search_on_web("AI stock photo trends 2026")` → OK, 3 hits in 2.0 s;
  first hit `https://ltx.io/blog/ai-image-trends` (real).
- `MarkdownifyGraph` on that URL → FAILED with
  `httpx.InvalidURL: Invalid port: ':1]'`. Root cause: sandbox `no_proxy` env contains
  bracketed IPv6 `[::1]`, which httpx 0.28.1 cannot parse (fails even with all other proxy
  vars unset; `httpx.Client()` raises at import time inside the ollama/langchain import chain
  of scrapegraphai). Environmental, not an app bug. The adapter degrades per-URL with a
  logged warning and stores records with title=URL, body=None — no fake content.

**Trend analysis (`analyze_topic`, real signals):** topic "AI", trend_velocity 0.25
(rising), momentum narrow, market_consistency 0.364, provenance THIRD_PARTY,
sources used: RSS 3, GitHub 17.

**Opportunity created (THIRD_PARTY):** id `90f3deba-…`,
"AI-generated commercial imagery demand", 5 evidence items with real source names,
URLs, and timestamps.

**API verification (real app + real DB):**
- `GET /api/trends` → 200, `total: 5` — all five real snapshots visible with correct
  provenance (THIRD_PARTY ×4, VERIFIED ×1), none flagged mock.
- `GET /api/adobe/connection` → `status: "NOT_CONFIGURED"`, `configured: false`.
- Source-health endpoint → rows returned.

## 3. Code corrections made during this phase

1. `app/api/routers/trends.py` — provenance now derives from `payload["provenance"]`
   (was hard-coded MOCK); real THIRD_PARTY snapshots no longer hidden when dev mode is off;
   trend-detail note distinguishes real collection from demo data.
2. `app/workers/scheduler.py` — successful runs set source health `AVAILABLE`; failed runs
   set `TEMP_FAILING`, increment the failure count, keep error/timestamp; fixed a critical
   bug where `session.rollback()` discarded the flushed `CollectionRun`, so FAILED runs
   were never persisted.
3. `app/adapters/scrapegraph_adapter.py` — `_search_on_web` normalizes the real
   scrapegraphai 2.x `List[str]` return shape (was written against dict hits and crashed on
   real data); `collect()` handles URL strings.
4. `app/adapters/store.py` — snapshot payload now includes `topic` (explicit query first,
   else the trend source's name); previously real snapshots were invisible in `/api/trends`
   because the list groups by topic and the payload had none.

## 4. Honest limitations and deviations

1. **ScrapeGraph Markdownify unavailable in this environment** — Tier-1 search works
   (real URLs collected); body extraction fails on the sandbox proxy env
   (`no_proxy=[::1]` vs httpx 0.28.1). Records are stored with URL titles and no body;
   nothing is fabricated to fill the gap.
2. **YouTube RSS: 0 records** — seeded channel IDs all 404; a real control channel ID
   also 404s, pointing to an egress/YouTube-side block rather than (only) stale seeds.
   Adapter handled it without fake data. Seeds need refreshing with verified IDs.
3. **Xueqiu: NEEDS_AUTH** — requires user login cookies; skipped honestly (direct call
   confirmed HTTP 400). Per the single-user design, auth would come from the user's own
   session export, which was not provided and not simulated.
4. **Adobe: NOT_CONFIGURED** — no credentials used, none simulated; no Adobe data claimed.
5. **Predictions are probabilistic** — scores are estimates with confidence, never guarantees
   (per standing integrity boundaries).
6. **Test flakiness (pre-existing):** `test_queue_transitions.py` drops/recreates a
   file-backed SQLite schema per parametrized test and intermittently fails with
   `no such table: production_queue` when run in the full suite; a stale
   `/tmp/stockpulse_pytest.db` previously caused disk I/O errors. The final reported run
   below was a single clean pass after removing the stale DB file.
7. **Scope:** StockPulse remains single-user — no auth, roles, organizations, or
   multi-tenancy were added.

## 5. Dependencies (installed, real)

- `scrapegraphai==2.2.4` (optional/guarded; Tier-1 keyless used)
- `agent-reach==1.5.0` (installed from `/tmp/agent-reach`; PyPI serves 0.1.0 which lacks
  channel APIs — documented in `requirements.txt`)
- `feedparser==6.0.14`, `httpx==0.28.1`, `apscheduler==3.11.3`
- 13 registered adapters: adobe_contributor, agentreach_web, custom, facebook,
  github_trending, instagram, reddit, rss, scrapegraph_web, v2ex, x_trends, xueqiu,
  youtube_rss

## 6. Reproduce

```bash
cd ~/workspace/stockpulse/backend
rm -f /tmp/stockpulse_pytest.db
.venv/bin/python -m pytest -q -p no:cacheprovider        # tests (mocked boundaries)

cd ~/workspace/stockpulse
rm -f acceptance/acceptance.db acceptance/acceptance_summary.json
backend/.venv/bin/python acceptance/accept_phase2.py     # real-data acceptance (network)
```

## 7. Full-suite log tail

(Pasted from the single uninterrupted run at the time of writing.)

```
419 passed, 6 warnings in 133.26s (0:02:13)
exit=0
```

Warnings are pre-existing third-party deprecations (pytest-asyncio loop scope,
Starlette BlockingPortal, ScrapeGraph/Pydantic v1 validators, langchain-community
sunset) — none from Phase 2 code.
