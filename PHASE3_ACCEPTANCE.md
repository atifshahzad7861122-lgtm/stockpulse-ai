# Phase 3 — Acceptance Evidence: Personal Intelligence + Opportunity Fusion + Daily Production Planner

**Date:** 2026-09-19
**Workspace:** `~/workspace/stockpulse/`
**Version:** v0.5.0
**Question answered:** "WHAT SHOULD I CREATE TODAY?"

This document records independently verified evidence for Phase 3. Every claim
below was verified by running the code — nothing here is a worker's
self-report.

---

## 1. Test results

| Scope | Result |
|---|---|
| Full backend suite (isolated DB, `STOCKPULSE_TEST_DB=/tmp/stockpulse_phase3_final.db`) | **524 passed, 0 failed** in 257s |
| Phase 3 focused re-run (after coordinator fixes: disclosure flow + archived-skip) | **73 passed, 0 failed** |
| Baseline (pre-Phase 3) | 455 passing |
| New Phase 3 tests | 69 passing |

New test files and what they cover:

- `tests/test_phase3_personal_performance.py` (27) — 6 private-intelligence
  tables, 7d/30d/90d windows vs prior windows, image/video independence,
  token-derived themes, consistency score, honest `not_configured` on every
  endpoint, MOCK exclusion.
- `tests/test_phase3_fusion.py` (22) — unified-score formula, confidence
  formula, MARKET-ONLY labeling + lowered confidence, banned-language assert,
  `market_personal_mismatch` and `personal_performance` special cases,
  evidence-only explanations, API round-trips.
- `tests/test_phase3_planning.py` (24, incl. 4 coordinator-added) —
  capacity-driven planning, diversification penalties, legal queue transitions
  only, HIGH_RISK blocking, similarity flags, export-only Muse provider,
  approve/reject/archive/prioritize/edit, no-auto-submit, AI-disclosure
  decision → re-screen → approval path, archived concepts no longer gating
  recommendation approval.

**Test-infra note:** the default `/tmp/stockpulse_pytest.db` races when
multiple pytest processes run concurrently (function-scoped
`drop_all/create_all` fixture). All green runs above used per-run
`STOCKPULSE_TEST_DB` paths. This is environmental, not code.

Frontend: `npm run build` — **clean, exit 0** (verified twice, incl. after
all coordinator contract fixes).

---

## 2. Tables added (Phase 3)

| Table | Purpose |
|---|---|
| `personal_performance_snapshots` | Persisted private-performance snapshots (period + metrics JSON) |
| `personal_category_metrics` | Per-category downloads/earnings/acceptance/momentum |
| `personal_content_type_metrics` | IMAGE vs VIDEO measured independently |
| `personal_theme_metrics` | Themes derived from the user's own asset titles |
| `personal_keyword_metrics` | Per-keyword private performance |
| `personal_fit_scores` | Recorded fit scores + full `component_json` + `formula_version="ppf-v1"` |
| `opportunity_fusion_scores` | Unified scores, provenance `PREDICTED`, per-input lineage |
| `daily_production_plans` | One plan per day with capacity + targets |
| `production_recommendations` | Ranked, diversified recommendations w/ evidence |
| `concept_variations` | Screened concept variations (+ `ai_disclosure` decision column) |
| `prompt_packs` | Export-only generation prompt packs |

## 3. Routes added (Phase 3, all under `/api`)

- `POST /opportunity-fusion/compute`, `GET /opportunity-fusion/{opportunity_id}`
- `GET /personal-performance`, `GET /personal-performance/categories`,
  `GET /personal-performance/content-types`, `GET /personal-performance/themes`,
  `POST /personal-performance/snapshot`
- `GET /daily-production/today`, `POST /daily-production/build`,
  `GET /daily-production`, `GET/PUT /daily-production/settings`,
  `GET /daily-production/{plan_id}`, `POST /daily-production/{plan_id}/status`
- `GET/POST /production-recommendations`, `GET /production-recommendations/{id}`,
  `POST .../{id}/approve|reject|archive`, `PATCH .../{id}`,
  `POST .../{id}/prioritize`,
  `POST/GET /production-recommendations/{id}/concepts`,
  `GET/PATCH /production-recommendations/concepts/{concept_id}`
- `POST /prompt-packs?concept_id=`, `GET /prompt-packs`,
  `GET /prompt-packs/{id}`, `POST /prompt-packs/{id}/export`

## 4. Formulas (exact)

Full documentation: `backend/PHASE3_FORMULAS.md`.

**Personal Fit Score**
```
PFS = Σ(w_i · c_i) / Σ(w_i)        over components i that HAVE data
```
Rounded to 2 decimals, clipped to [0,100]. Weights: category 0.25, keyword
0.15, asset 0.10, content_type 0.10, theme 0.05, momentum 0.10, acceptance
0.15, historical_downloads 0.05, historical_earnings 0.05. A component with no
private data is **skipped, never zeroed**; weights renormalize over present
components. **No component with data → `None`** (null = "no private data",
never "bad fit"). Documented in `personal_fit_score()`'s docstring.

**Opportunity Fusion — unified score**
```
UNIFIED = clip( Σ(w_i·c_i) / Σ(w_i)  −  0.15 × saturation_risk , 0, 100 )
```
Weights: market_opportunity 0.25, trend_momentum 0.20, commercial_potential
0.15, seasonality 0.10, prediction_confidence 0.05, personal_fit 0.15
(optional), personal_momentum 0.05 (optional), historical_performance 0.05
(optional). `saturation_risk` is purely subtractive. Label **FUSED** when
personal_fit present, **MARKET-ONLY** when absent (confidence −10).

**Confidence** = f(freshness, source count, consistency, prediction
confidence, private-data availability, market strength) — see
`PHASE3_FORMULAS.md` §3.

---

## 5. Acceptance scenarios (verified)

### Scenario A — Private data available → Personal Fit calculated
- `tests/test_phase3_fusion.py` — engine computes `label="FUSED"` with
  `personal_fit` present; breakdown stores every component + renormalized
  weights + `missing` list.
- Formula doc worked example (71.00) verified against the engine.

### Scenario B — Private data unavailable → Personal Fit N/A; public market analysis still works
- **Live smoke test** (backend on :8123, fresh DB, Adobe NOT_CONFIGURED):
  - `GET /api/personal-performance` → `{"status":"not_configured",
    "earnings_total":null, ... "has_private_data":false}` — nulls, no fakes.
  - `POST /api/opportunity-fusion/compute` → `label="MARKET-ONLY"`,
    `unified_score=47.83`, `personal_fit=null`.
- `tests/test_phase3_fusion.py::test_*market_only*` — confidence lowered,
  no personal numbers invented.

### Scenario C — High market opportunity + poor personal fit → explained, not auto-rejected
- `tests/test_phase3_fusion.py::test_high_market_poor_fit_explained_not_rejected`:
  market=85, fit=20 → `special_case="market_personal_mismatch"`,
  `label="FUSED"`, score still computed; explanation cites both numbers and
  states entering would rely on market demand rather than proven strengths.

### Scenario D — High personal fit + weak market → labeled personal-performance opportunity
- `tests/test_phase3_fusion.py::test_high_fit_weak_market_labeled_personal_performance`:
  market=30, fit=85 → `special_case="personal_performance"`, explanation
  labels it a personal-performance opportunity, never a market trend.

### Scenario E — Repeated similar recommendations → diversification lowers repetition
- `tests/test_phase3_planning.py::test_diversification_penalizes_repeats` —
  yesterday's micro-niche repeats receive a recorded penalty and drop in rank.

### Scenario F — Full production flow (live smoke test, :8123)
1. `POST /daily-production/build` → plan with 4 recommendations.
2. `POST /production-recommendations/{id}/concepts` → 2 concepts, both
   `HIGH_RISK` / `ai_disclosure=null` (gen-01 disclosure BLOCK, undecided).
3. `POST .../approve` → **422 APPROVAL_BLOCKED** — nothing auto-promotes.
4. `PATCH /concepts/{id} {"ai_disclosure": true}` → re-screen →
   `compliance_result="REVIEW"`, gen-01 cleared.
5. Concept approved; `POST /prompt-packs?concept_id=` → pack built
   (`target_tool="muse"`, export-only).
6. Second (still HIGH_RISK) concept archived → `POST .../approve` →
   **200, queue item created at DISCOVERED**. Archived concepts no longer
   gate approval (coordinator fix, tested).

### Approval & auto-submit invariants
- `test_approve_blocked_by_high_risk_concept`, `test_illegal_queue_transition_rejected`,
  no-auto-submit tests — all passing.
- Muse provider: `export_only: true`, `asset_auto_generated: false`; no
  network, local JSON export only.

---

## 6. Coordinator-found issues (fixed during integration)

1. **Concept approval was permanently blocked.** Every generated concept
   screened HIGH_RISK because gen-01 (AI-disclosure BLOCK) had no path to
   clear — no disclosure field, no re-screen. Fix: `ConceptVariation.ai_disclosure`
   (nullable, never defaulted) + `PATCH /concepts/{id}` accepts an explicit
   disclosure decision and re-screens. 4 new tests.
2. **Archived concepts gated recommendation approval forever.** Fix:
   `approve_recommendation` skips `status == "archived"` concepts.
3. **Frontend/backend contract mismatches.** Frontend called
   `GET /daily-production?date=` (nonexistent; backend list endpoint is
   paginated) and POSTed `{date}` (backend expects `plan_date`). Fix: frontend
   now uses `GET /daily-production/today` (404 → honest "no plan yet" empty
   state) and sends `plan_date`. Frontend also used status `"pending"` while
   the backend uses `"recommended"` — Approve/Reject buttons would never have
   appeared; fixed in both daily and opportunity-detail pages.
4. **Frontend had no concept/prompt-pack UI at all.** Added: concept
   generation + screening display + disclosure recording + concept
   approval/archive + prompt-pack creation, wired into the Daily Intelligence
   Action zone (`ConceptsSection` / `ConceptCard`).

---

## 7. Frontend verification

- `npm run build`: clean, exit 0 (after all fixes).
- Dev server smoke: `/daily` → 200, `/private` → 200, no page errors.
- Design system: near-black base, champagne-gold primary accent
  (`#D6B25E`), racing red alerts-only, warm steel replaces info blue,
  Inter UI + Bodoni Moda Didone serif for hero moments, F1-style tabular
  telemetry numerals, Motion (framer-motion) for UI animation with
  `prefers-reduced-motion` respected, React Three Fiber for 3D data viz
  (lazy-loaded, 2D fallbacks), Remotion `ConceptPreview` + `DailyBriefing`
  compositions with on-demand render queue (never background).
  Note: dev log shows a cosmetic next/font warning ("font override values"
  for Bodoni Moda) — variable-font fallback metrics only; the font itself
  loads from Google Fonts.
- Banned-language scan: no "guaranteed"/"will sell"/"will rank" anywhere
  except banned-word lists and honesty copy.

---

## 8. Honest pending configuration (unchanged)

- **Adobe Contributor: NOT_CONFIGURED** — private performance tables are
  empty until Atif supplies an authorized user-controlled session. No Adobe
  earnings/downloads/private metrics are fabricated anywhere.
- Reddit/X/Instagram/Facebook: need auth or supported sessions.
- Ollama: requires `ollama serve` + a local model (`STOCKPULSE_LLM_PROVIDER=ollama`).
- Huginn: requires a self-hosted instance.
- Remotion rendering: requires headless Chrome (`npx remotion browser ensure`;
  documented in `frontend/remotion/REMOTION.md`).

---

*Verified independently 2026-09-19 by the Phase 3 coordinator. Backend:
524 passed / 0 failed. Frontend: build clean. Live API smoke: all Phase 3
flows exercised against a fresh DB.*
