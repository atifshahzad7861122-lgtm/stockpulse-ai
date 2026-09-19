# StockPulse AI — Seed Data Plan (Phase 1)

**Version:** 0.2.0 · **Date:** 2026-09-18 · **Status:** plan; seeding runs in Phase 2+.

Sources: `docs/15_TREND_INTELLIGENCE_SPECIFICATION.md` (§2 source catalog, §5 taxonomy),
`docs/18_COMPLIANCE_ENGINE_SPECIFICATION.md` (§2 check coverage, §4 rule schema),
`docs/08_DATABASE_SCHEMA.md` (§5.1 `trend_sources`, §8.1 `compliance_rules`).

Single-user note: seed rows are owned by the single user (no `user_id` column in this
build). Categories carry `is_system = true` (not user-deletable).

---

## 1. Category taxonomy seed — 39 categories (verbatim from docs/15 §5)

Taxonomy version: `taxonomy_v1.0`. Slugs are the lowercase hyphenated form of the name.

| # | Name | Slug | Description (verbatim) |
|---|---|---|---|
| 1 | AI | `ai` | Artificial intelligence concepts, applications, abstract representations |
| 2 | Technology | `technology` | Computing, devices, software, networks, general tech |
| 3 | Business | `business` | Corporate life, strategy, meetings, entrepreneurship |
| 4 | Finance | `finance` | Banking, investing, markets, fintech, insurance |
| 5 | Cybersecurity | `cybersecurity` | Security operations, threats, protection, privacy |
| 6 | Healthcare | `healthcare` | Medical professionals, facilities, treatment, care |
| 7 | Wellness | `wellness` | Mental health, fitness, mindfulness, self-care |
| 8 | Education | `education` | Learning, classrooms, e-learning, training |
| 9 | E-commerce | `e-commerce` | Online shopping, retail tech, logistics, unboxing |
| 10 | Marketing | `marketing` | Advertising, branding, campaigns, analytics |
| 11 | Social Media | `social-media` | Platforms, content creation, influencers, community |
| 12 | Sustainability | `sustainability` | Green living, conservation, eco practices |
| 13 | Renewable Energy | `renewable-energy` | Solar, wind, hydro, clean energy infrastructure |
| 14 | Environment | `environment` | Nature conservation, climate, pollution, ecosystems |
| 15 | Travel | `travel` | Destinations, tourism, hospitality, adventure |
| 16 | Nature | `nature` | Landscapes, wildlife, plants, natural phenomena |
| 17 | Food | `food` | Cuisine, cooking, restaurants, food production |
| 18 | Lifestyle | `lifestyle` | Daily life, hobbies, leisure, personal style |
| 19 | Family | `family` | Parenting, children, home life, generations |
| 20 | People | `people` | Portraits, diversity, emotions, human interaction |
| 21 | Workplace | `workplace` | Offices, remote work, collaboration, coworkers |
| 22 | Industry | `industry` | Factories, heavy machinery, industrial processes |
| 23 | Manufacturing | `manufacturing` | Production lines, assembly, quality control |
| 24 | Architecture | `architecture` | Buildings, interiors, urban design, construction |
| 25 | Transportation | `transportation` | Vehicles, aviation, shipping, public transit |
| 26 | Science | `science` | Research, laboratories, experiments, discovery |
| 27 | Space | `space` | Astronomy, space exploration, satellites, cosmos |
| 28 | Abstract | `abstract` | Non-representational art, shapes, patterns |
| 29 | Backgrounds | `backgrounds` | Generic backgrounds, gradients, scenes for compositing |
| 30 | Textures | `textures` | Surfaces, materials, close-up detail textures |
| 31 | 3D | `3d` | 3D renders, CGI aesthetics, digital objects |
| 32 | Seasonal | `seasonal` | Holiday/season-specific content (Christmas, Ramadan, etc.) |
| 33 | Events | `events` | Weddings, conferences, concerts, ceremonies |
| 34 | Local Culture | `local-culture` | Regional traditions, festivals, crafts, heritage |
| 35 | Crafts | `crafts` | Handmade goods, artisans, DIY, traditional skills |
| 36 | Fashion | `fashion` | Clothing, style, runway, apparel industry |
| 37 | Beauty | `beauty` | Cosmetics, skincare, grooming, aesthetics |
| 38 | Home | `home` | Interior living spaces, decor, domestic life |
| 39 | Real Estate | `real-estate` | Properties, housing market, construction, listings |

Seed rule: insert all 39 with `is_system = true`, `sort_order` = the `#` above,
`created_at = updated_at = seed time`.

---

## 2. Subcategory / micro-niche structure

Five levels (docs/15 §6): **Category → Subcategory → Micro-niche → Specific Opportunity
→ Content Format**. Naming conventions:

| Level | Convention | Example |
|---|---|---|
| Category | Title Case, from taxonomy | Technology |
| Subcategory | Title Case, ≤ 3 words | Artificial Intelligence |
| Micro-niche | Title Case, specific domain | AI Infrastructure |
| Specific opportunity | Sentence-case action phrase | Data Center AI Computing |
| Content format | `Image` or `Video` (+ aspect/duration in production) | Image / Video |

Worked example (docs/15 §6.2): **Technology → Artificial Intelligence →
AI Infrastructure → Data Center AI Computing → Image / Video.**

Depth rules (docs/15 §6.3):
1. Minimum depth for scoring: micro-niche (category/subcategory alone are too broad).
2. Max one Specific Opportunity per (micro-niche × format) per 7-day run.
3. A micro-niche must have ≥ 3 distinct topics with signals before it can carry scores.
4. Micro-niche names must stay distinguishable from buyer-facing Adobe Stock search categories.

Seed rule: subcategories/micro-niches are NOT bulk-seeded in Phase 1 — they are
proposed by the Category Intelligence Agent (user-approved, docs/13 §5) or added
manually. The taxonomy version `taxonomy_v1.0` is recorded on every classified row.

---

## 3. Trend sources seed (docs/15 §2, docs/08 §5.1)

Seed into `trend_sources` with `is_active = true`. `source_type` uses the contract enum
(§4.22). Access methods below are the ONLY legitimate methods (docs/15: "Do not assume
unauthorized scraping is allowed"). **No credentials are stored by the seed** —
`endpoint_or_reference` holds a public URL or citation, never keys.

| # | Name | source_type | Access method | Provenance | Fetch cadence | Notes |
|---|---|---|---|---|---|---|
| 1 | Adobe Stock public trends | `adobe_report` | Public trend/collection pages via documented/allowed endpoints only | THIRD_PARTY | weekly | Counts + themes only; no artwork/description copying; ≤1 req/10s, ≤200/day; respect robots.txt |
| 2 | Adobe Stock contributor resources | `adobe_report` | Public contributor blog / help pages | VERIFIED | weekly | Official guidance; summarize + cite, never republish full articles |
| 3 | Adobe creative trend reports | `adobe_report` | Public download pages (PDF reports) | VERIFIED | per publication | Extract theme names + paraphrased direction; no report images/long excerpts |
| 4 | Search trend sources (general) | `search_trends` | Official provider APIs only | THIRD_PARTY | daily | Indices/aggregates; never de-anonymize queries |
| 5 | Google Trends | `search_trends` | Sanctioned public interface within its terms (no unofficial scraping) | THIRD_PARTY | daily (7d + 90d windows) | Indices are relative 0–100, not absolute volumes — documented on every derived metric |
| 6 | Social media trend signals | `social_trends` | Official platform APIs with developer credentials; public trend endpoints only | THIRD_PARTY | daily | Aggregates only; no personal data; per-platform terms |
| 7 | YouTube trend signals | `social_trends` | YouTube Data API v3 (official) | THIRD_PARTY | daily | API quota units; 24h cache; quota exhausted → serve cached, mark stale |
| 8 | Public market research | `marketplace_feed` | Public report landing pages, press releases, open datasets | THIRD_PARTY | monthly | Cite sources; use figures with stated methodology |
| 9 | Seasonal calendars | `other` | Internal curated dataset (built from public holiday/event calendars) | ESTIMATED | quarterly review | Date-anchored events; buyers search 4–8 weeks ahead |
| 10 | Commercial keyword demand | `search_trends` | Official keyword-research provider APIs (user-provisioned credentials) | THIRD_PARTY | weekly | Directional indices, not buyer counts |
| 11 | Internal user performance data | `user_upload` | User-provided CSV/export upload or manual entry | USER_PROVIDED | on upload | User's own portfolio data only; never pooled; absence lowers confidence |

Seed fields per row: `name`, `source_type`, `endpoint_or_reference` (public URL/citation or
NULL for #11), `fetch_schedule` (`weekly`/`daily`/`monthly`/`quarterly`/`per_publication`/
`on_upload`), `is_active=true`, `data_provenance` (as above), `notes` (legal caveats).

---

## 4. Compliance rules seed (docs/18 §2 + §4)

Seed into `compliance_rules` (versioned: `rule_key`, `version`, `effective_from`,
`applies_to`, `severity`, `rule_config`, `source_reference`, `is_enabled`).
Rules are retired via `effective_to`, never deleted.

The check coverage in docs/18 §2 defines **28 checks** (the docs package says "27" in
one place — count below is authoritative: 4 GEN + 8 IP + 8 TQ + 8 MH = 28).
Seed one rule per check (rule_key = check id, lowercased with dashes), version `1.0.0`,
`effective_from` = seed date, `applies_to` per family. Severity mapping (docs/18 §10):
blocker → HIGH_RISK · major → REVIEW · minor → REVIEW (low weight; 3 minors in one
report escalate to HIGH_RISK).

### 4.1 Generative AI disclosure (GEN) — applies_to: PROMPT_SCREEN, ASSET_SCREEN

| rule_key | What it screens (summary) | severity | check_method | source_reference |
|---|---|---|---|---|
| `gen-01` | AI-generated disclosure flag present and set correctly on the asset record | blocker | automated | Adobe Stock contributor guidelines — generative AI disclosure (verify current section at implementation) |
| `gen-02` | Generating tool/model named accurately (matches generation record, not a guess) | major | automated | Adobe Stock contributor guidelines — generative AI disclosure |
| `gen-03` | Generation date recorded | minor | automated | Adobe Stock contributor guidelines — generative AI disclosure |
| `gen-04` | Prompt package does not instruct the generator to hide AI origin | blocker | model_assisted | Adobe Stock contributor guidelines — generative AI disclosure |

### 4.2 Intellectual property & likeness (IP) — applies_to: PROMPT_SCREEN, ASSET_SCREEN, METADATA_SCREEN

| rule_key | What it screens (summary) | severity | check_method | source_reference |
|---|---|---|---|---|
| `ip-01` | No logos or brand marks visible (or flagged for removal/review) | blocker | model_assisted | Adobe Stock contributor guidelines — intellectual property |
| `ip-02` | No trademarks (names, slogans, distinctive packaging) in image, video, or metadata | blocker | model_assisted | Adobe Stock contributor guidelines — intellectual property |
| `ip-03` | No copyrighted characters (cartoon, film, game, mascot) | blocker | model_assisted | Adobe Stock contributor guidelines — intellectual property |
| `ip-04` | No celebrity likeness or identifiable public figure | blocker | model_assisted | Adobe Stock contributor guidelines — releases & likeness |
| `ip-05` | No living-artist name or distinctive living-artist style requested in the prompt | blocker | automated | Adobe Stock contributor guidelines — intellectual property; platform originality policy |
| `ip-06` | No recognizable copyrighted material (artwork, album/book covers, distinctive designs) | blocker | model_assisted | Adobe Stock contributor guidelines — intellectual property |
| `ip-07` | Metadata contains no brand/artist/celebrity names as keywords (spam + IP risk) | major | automated | Adobe Stock contributor guidelines — metadata policy |
| `ip-08` | "Inspired by" language audit: concept descriptions must not reference identifiable individual works | major | model_assisted | Platform originality policy — TREND → INSIGHT, never TREND → COPY |

### 4.3 Technical quality (TQ) — applies_to: ASSET_SCREEN

| rule_key | What it screens (summary) | severity | check_method | source_reference |
|---|---|---|---|---|
| `tq-01` | Resolution meets minimum (image ≥ 4 MP or platform minimum in force; video ≥ 1080p) | blocker | automated | Adobe Stock contributor guidelines — technical requirements (verify current minimums at implementation) |
| `tq-02` | Noise/grain within acceptable bounds (not destructive) | major | automated | Adobe Stock contributor guidelines — technical requirements |
| `tq-03` | Blur/focus: subject acceptably sharp (motion blur only where intentional and noted) | major | automated | Adobe Stock contributor guidelines — technical requirements |
| `tq-04` | Compression artifacts: no blocking/banding beyond threshold | major | automated | Adobe Stock contributor guidelines — technical requirements |
| `tq-05` | Anatomical errors (AI people/animals): hands, faces, limbs — failures → HIGH_RISK | blocker | model_assisted | Adobe Stock contributor guidelines — generative AI quality |
| `tq-06` | Image artifacts: extra limbs, merged objects, garbled text, watermark-like marks | blocker | model_assisted | Adobe Stock contributor guidelines — generative AI quality |
| `tq-07` | Video artifacts: flicker, temporal inconsistency, frame glitches | blocker | model_assisted | Adobe Stock contributor guidelines — video requirements |
| `tq-08` | Exposure/color: not critically over/underexposed; no destructive clipping | major | automated | Adobe Stock contributor guidelines — technical requirements |

### 4.4 Metadata & submission hygiene (MH) — applies_to: METADATA_SCREEN, ASSET_SCREEN

| rule_key | What it screens (summary) | severity | check_method | source_reference |
|---|---|---|---|---|
| `mh-01` | Title present, within length limits, accurately describes content | minor | automated | Adobe Stock contributor guidelines — metadata (docs/19) |
| `mh-02` | Description present, accurate, within limits | minor | automated | Adobe Stock contributor guidelines — metadata (docs/19) |
| `mh-03` | Keyword count within limits; ordering strategy followed | minor | automated | Adobe Stock contributor guidelines — metadata (docs/19) |
| `mh-04` | Spam detection: no keyword stuffing, irrelevant trending terms, misleading claims | major | automated | Adobe Stock contributor guidelines — metadata policy (docs/19) |
| `mh-05` | Category/subcategory mapping valid against Adobe Stock categories | minor | automated | Adobe Stock category list (verify current list at implementation) |
| `mh-06` | Near-duplicate submission check: asset fingerprint vs already-submitted assets | major | automated | Platform originality policy (docs/17) |
| `mh-07` | Commercial usefulness: not pure filler (blank backgrounds without purpose, unusable crops) | minor | model_assisted | Adobe Stock contributor guidelines — commercial value |
| `mh-08` | Release logic: recognizable real people/property need releases; AI people still pass IP-04 | major | human_review | Adobe Stock contributor guidelines — model/property releases |

### 4.5 Seed mechanics

- `rule_config` (JSON) per rule: `{ "check_id": "GEN-01", "thresholds": {...}, "patterns": [...] }`
  — concrete patterns/thresholds are defined at implementation from the check method.
- `requirement_text`: plain-language requirement (one sentence, from the "What it screens" column).
- `rationale`: one paragraph per rule (why it exists — rejection-risk reduction).
- `source_reference` entries marked "(verify … at implementation)" MUST be verified
  against the current Adobe Stock contributor guidelines before the rules go live;
  unverified community advice is labeled as such, never as Adobe guidance.
- Rule update process (docs/18 §4.2): detect → draft new version → user approves →
  new version pinned for new runs (in-flight assets keep their pinned version) → notify.
- Quarterly rule-effectiveness review: compare findings vs user-reported Adobe outcomes;
  downgrade noisy rules, add rules for uncovered rejection reasons (both user-approved).

---

## 5. Seed order & idempotency

1. `categories` (39 rows, taxonomy_v1.0) — idempotent on `slug`.
2. `trend_sources` (11 rows) — idempotent on `name`.
3. `compliance_rules` (28 rows, v1.0.0) — idempotent on (`rule_key`, `version`).
4. `settings` defaults: `briefing.time="08:00"`, `briefing.timezone` (user's),
   `opportunity.min_score=55`, `opportunity.min_confidence=0.5`,
   `compliance.strictness="standard"`, `planner.daily_capacity=0`,
   `planner.weekly_capacity=0` (0 = no cap; planner orders by score).

Rerunning the seed must be a no-op for existing rows (upsert on the idempotency keys
above). Seed provenance for taxonomy/rules: VERIFIED (from the spec package);
trend-source rows: per-source provenance in §3.

*End of SEED_PLAN.md — v0.2.0*
