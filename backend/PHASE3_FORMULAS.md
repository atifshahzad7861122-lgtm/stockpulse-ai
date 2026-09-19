# Phase 3 Formulas — Personal Fit Score & Opportunity Fusion

Exact, auditable formulas for the Phase 3 Personal Intelligence backend.
Every weight is a named constant in code (`app/engines/opportunities.py`,
`app/engines/fusion.py`); this document is the human-readable contract.
**No guarantees language anywhere**: scores describe signals, never promises
of sales, rank, or earnings.

---

## 1. Personal Fit Score (PFS) — full spec

`app/engines/opportunities.py::personal_fit_breakdown` (scalar wrapper:
`personal_fit_score`). Answers: *"Is this opportunity one of YOUR strongest
areas, based on your own private Adobe data?"*

### Formula

```
PFS = Σ(w_i · c_i) / Σ(w_i)        over components i that HAVE data
```

Rounded to 2 decimals, clipped to [0, 100].

### Components (each 0–100)

| Component | Weight | Definition |
|---|---|---|
| `category` | 0.25 | Relative strength of the opportunity's category vs the user's own portfolio max |
| `keyword` | 0.15 | Mean relative strength of matched opportunity keywords |
| `asset` | 0.10 | Mean relative strength across asset-type rows *(currently unavailable — private asset snapshots carry no `asset_type`; skipped, never zeroed)* |
| `content_type` | 0.10 | Relative strength per content type, scored for IMAGE and VIDEO **independently** (sibling Phase 3 `PersonalContentTypeMetric` table, read-only), averaged over the opportunity's formats (all types when formats unknown; the `"unknown"` bucket is never used as a proxy) |
| `theme` | 0.05 | Mean relative strength of matched themes (themes derived from the user's **own asset titles** — a different data source than keywords) |
| `momentum` | 0.10 | Mean over {downloads, earnings} of `clip(50 + 50·(cur7−prev7)/prev7)`; flat = 50, doubled = 100, halved = 0; new activity from zero baseline = 100; zero/zero = no data |
| `acceptance` | 0.15 | `100 × overall_acceptance_rate` |
| `historical_downloads` | 0.05 | Track-record depth: `clip(100·log10(1+total_downloads)/4)` (saturates ≈ 10k downloads) |
| `historical_earnings` | 0.05 | Track-record depth: `clip(100·log10(1+total_earnings_usd)/5)` (saturates ≈ $100k) |

### Normalization

- **Relative strength** (category/keyword/asset/content_type/theme rows): for one
  performance row, `100 × value / portfolio_max` computed separately for
  `earnings` and `downloads`, then averaged. Returns `None` when the portfolio
  max ≤ 0 or the row's own value ≤ 0 (no data, not a low score).
- **Momentum**: percent change mapped to 0–100 with 50 = flat (see table).
- **Depth** (historical totals): `log10`-scaled so a genuinely deep track record
  saturates at 100; `None` when the total is unknown.

### Renormalization over available components

Weights are **renormalized over the components that have data**: the
denominator is the sum of weights of present components only. A score computed
from 3 components and one from 9 are both honest weighted averages over what
is actually known.

### None-means-no-data rule

A component with no private data is **skipped**, never treated as 0. When **no**
component has data, the function returns `None` — null means *"no private
data"*, never *"bad fit"*. Adobe private data NOT_CONFIGURED (empty private
tables) therefore yields `None`, never a fake number.

### Explainability

`personal_fit_breakdown` returns a `PersonalFitResult`: `score`,
`components` (name → 0–100 for components with data), `weights` (renormalized
weights actually used, summing to 1.0), and `missing` (components skipped for
lack of data).

---

## 2. Opportunity Fusion — Unified Score

`app/engines/fusion.py::OpportunityFusionEngine.compute`. Answers: *"Given
market signals AND my own track record, how strong is this opportunity?"*

### Formula

```
UNIFIED = clip( Σ(w_i·c_i) / Σ(w_i)  −  0.15 × saturation_risk , 0, 100 )
```

Rounded to 2 decimals.

### Components and weights

| Component | Weight | Required? |
|---|---|---|
| `market_opportunity` | 0.25 | yes (opportunity's market score) |
| `trend_momentum` | 0.20 | yes |
| `commercial_potential` | 0.15 | yes |
| `seasonality` | 0.10 | yes |
| `prediction_confidence` | 0.05 | yes |
| `personal_fit` | 0.15 | **no** — `None` when no private data |
| `personal_momentum` | 0.05 | **no** |
| `historical_performance` | 0.05 | **no** |
| `saturation_risk` | subtractive | yes — `0.15 × saturation_risk` is **subtracted** from the weighted average and never enters the weight denominator |

The weighted average renormalizes over present components. `saturation_risk`
is purely subtractive: high saturation drags the score down without
diluting the other components' weights.

### Labels

- **`FUSED`** — `personal_fit` present: market + personal signals combined.
- **`MARKET-ONLY`** — `personal_fit` is `None`: no private data. The score
  renormalizes over market components, confidence is lowered by 10 points
  (see §3), and **no personal numbers are invented**.

### Special cases (explained, never auto-rejected)

- **High market + poor personal fit** (`market_opportunity ≥ 70` and
  `personal_fit ≤ 35`) → `special_case = "market_personal_mismatch"`. The
  score is still computed; the explanation states the split plainly: entering
  would rely on market demand rather than proven personal strengths.
- **High personal fit + weak market** (`personal_fit ≥ 70` and
  `market_opportunity ≤ 40`) → `special_case = "personal_performance"`. Labeled
  a **personal-performance opportunity**, never presented as a market trend.

### Storage provenance

Persisted `OpportunityFusionScore` rows carry `data_provenance = PREDICTED`:
the unified score is the engine's computed prediction, not a user-supplied
fact. Per-input lineage is preserved in `component_json.inputs` — every
component records its own provenance (`USER_PROVIDED`, `ESTIMATED`, or
`ABSENT`).

---

## 3. Confidence Score (fusion)

```
CONF = clip( 0.20·freshness₁₀₀ + 0.20·sources₁₀₀ + 0.15·consistency₁₀₀
           + 0.15·prediction_confidence + 0.15·private_availability₁₀₀
           + 0.15·market_signal_strength
           − (10 if label == "MARKET-ONLY" else 0) , 0, 100 )
```

| Factor | Weight | 0–100 mapping |
|---|---|---|
| `data_freshness` | 0.20 | `100 × freshness` (0–1 input) |
| `n_sources` | 0.20 | `100 × min(n_sources, 4)/4` |
| `historical_consistency` | 0.15 | `100 × consistency` (0–1 input) |
| `prediction_confidence` | 0.15 | as-is (0–100) |
| `private_data_availability` | 0.15 | 100 if personal fit present, else 0 |
| `market_signal_strength` | 0.15 | as-is (0–100; defaults to the market opportunity score) |

MARKET-ONLY outputs additionally lose **10 points**: no private data means a
weaker evidence base. The stored `confidence_factors_json` records every
factor value plus the penalty applied, so the number is fully auditable.

---

## 4. Explanation (WHY paragraph)

`OpportunityFusionEngine.explain` builds the WHY paragraph **only** from:

1. the component values actually computed,
2. `demand_evidence_notes` — market evidence strings passed in by the caller,
3. `personal_evidence_notes` — personal evidence strings from real private data,
4. the label (`FUSED` / `MARKET-ONLY`) and `special_case`.

Rules enforced in code (an `assert` guards the banned list):

- **Never** guarantee language: "guarantee(d)", "will sell", "will rank",
  "certain to sell", "sure thing", "can't miss", "cannot fail".
- **Never** a claim not present in the evidence: the paragraph quotes observed
  notes and cites component values; it describes signals, not certainties.
- MARKET-ONLY explanations state plainly that personal fit could not be
  evaluated and the score is a market view only.
- Mismatch explanations describe the market/personal split and suggest small,
  differentiated batches — they never auto-reject.
- Personal-performance explanations frame the opportunity as playing to
  personal strengths, not chasing a trend.
- The confidence sentence frames the number as evidence strength, *"not a
  promise of sales"*.

### Optional local-LLM phrasing

`app/services/fusion_explanation.py::render_explanation`: when
`STOCKPULSE_LLM_PROVIDER=ollama`, the local Ollama model (localhost only —
private data never leaves this machine, and the helper refuses any non-local
provider) rewrites the evidence + components into natural language. The
deterministic evidence-based template is the **default** and the **always-on
fallback**: if Ollama is unreachable or returns anything unusable, the
template is used and the endpoint never fails or fakes text. The renderer
used is recorded in `component_json.explanation_renderer`.

---

## 5. Worked example

Inputs: market_opportunity=80, trend_momentum=70, commercial_potential=75,
seasonality=60, prediction_confidence=80, saturation_risk=30, personal_fit=90,
personal_momentum=65, historical_performance=70.

```
base = (80·0.25 + 70·0.20 + 75·0.15 + 60·0.10 + 80·0.05
      + 90·0.15 + 65·0.05 + 70·0.05) / 1.00
     = (20 + 14 + 11.25 + 6 + 4 + 13.5 + 3.25 + 3.5) / 1.00
     = 75.50
UNIFIED = 75.50 − 0.15 × 30 = 75.50 − 4.50 = 71.00
```

Same inputs with `personal_fit = None` (MARKET-ONLY):

```
base = (20 + 14 + 11.25 + 6 + 4) / 0.75 = 55.25 / 0.75 = 73.67
UNIFIED = 73.67 − 4.50 = 69.17 ; confidence −10 ; label = MARKET-ONLY
```
