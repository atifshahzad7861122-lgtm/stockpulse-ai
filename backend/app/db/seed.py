"""Seed script: ``python -m app.db.seed`` (also called by init_db on startup).

Order & idempotency (SEED_PLAN.md §5):
1. categories — 39 rows, idempotent on slug
2. subcategories (2–4 / category) + micro_niches (2–3 / subcategory) — idempotent
   on (parent, slug). NOTE: SEED_PLAN.md prose says not to bulk-seed these, but
   the binding assignment explicitly overrides: create 2–4 commercial
   subcategories per category and 2–3 micro-niches per subcategory.
3. trend_sources — 11 rows, idempotent on name
4. compliance_rules — 28 rows v1.0.0, idempotent on (rule_key, version)
5. settings — canonical defaults, idempotent on (project_id NULL, key)
6. demo MOCK rows (snapshots, opportunities, ideas, prompts, queue, …) — all
   labeled provenance=MOCK / mock:true; skipped entirely once seed.demo_batch
   is recorded.

Mapping notes:
- ComplianceRule.version is Integer; the "1.0.0" rule version string is stored
  in rule_config["version_string"].
- ComplianceRule.applies_to is a JSON list of ComplianceCheckType values (one
  row per rule, not per check type).
- Model columns cover requirement_text (description), rationale, check_method
  and source_reference via description + rule_config JSON.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.schemas.enums import (
    AssetType,
    ComplianceCheckType,
    ComplianceResult,
    DataProvenance,
    IdeaStatus,
    NotificationType,
    PredictedDirection,
    PredictionHorizon,
    ProductionQueueStatus,
    RiskLevel,
    RuleSeverity,
    TrendSourceType,
)

TAXONOMY_VERSION = "taxonomy_v1.0"
RULES_VERSION_INT = 1
RULES_VERSION_STR = "1.0.0"
DEMO_BATCH = "2026-09-18-v1"

# ---------------------------------------------------------------------------
# 1. Categories — verbatim from SEED_PLAN.md §1 (docs/15 §5)
# ---------------------------------------------------------------------------

CATEGORIES: list[tuple[str, str, str]] = [
    ("AI", "ai", "Artificial intelligence concepts, applications, abstract representations"),
    ("Technology", "technology", "Computing, devices, software, networks, general tech"),
    ("Business", "business", "Corporate life, strategy, meetings, entrepreneurship"),
    ("Finance", "finance", "Banking, investing, markets, fintech, insurance"),
    ("Cybersecurity", "cybersecurity", "Security operations, threats, protection, privacy"),
    ("Healthcare", "healthcare", "Medical professionals, facilities, treatment, care"),
    ("Wellness", "wellness", "Mental health, fitness, mindfulness, self-care"),
    ("Education", "education", "Learning, classrooms, e-learning, training"),
    ("E-commerce", "e-commerce", "Online shopping, retail tech, logistics, unboxing"),
    ("Marketing", "marketing", "Advertising, branding, campaigns, analytics"),
    ("Social Media", "social-media", "Platforms, content creation, influencers, community"),
    ("Sustainability", "sustainability", "Green living, conservation, eco practices"),
    ("Renewable Energy", "renewable-energy", "Solar, wind, hydro, clean energy infrastructure"),
    ("Environment", "environment", "Nature conservation, climate, pollution, ecosystems"),
    ("Travel", "travel", "Destinations, tourism, hospitality, adventure"),
    ("Nature", "nature", "Landscapes, wildlife, plants, natural phenomena"),
    ("Food", "food", "Cuisine, cooking, restaurants, food production"),
    ("Lifestyle", "lifestyle", "Daily life, hobbies, leisure, personal style"),
    ("Family", "family", "Parenting, children, home life, generations"),
    ("People", "people", "Portraits, diversity, emotions, human interaction"),
    ("Workplace", "workplace", "Offices, remote work, collaboration, coworkers"),
    ("Industry", "industry", "Factories, heavy machinery, industrial processes"),
    ("Manufacturing", "manufacturing", "Production lines, assembly, quality control"),
    ("Architecture", "architecture", "Buildings, interiors, urban design, construction"),
    ("Transportation", "transportation", "Vehicles, aviation, shipping, public transit"),
    ("Science", "science", "Research, laboratories, experiments, discovery"),
    ("Space", "space", "Astronomy, space exploration, satellites, cosmos"),
    ("Abstract", "abstract", "Non-representational art, shapes, patterns"),
    ("Backgrounds", "backgrounds", "Generic backgrounds, gradients, scenes for compositing"),
    ("Textures", "textures", "Surfaces, materials, close-up detail textures"),
    ("3D", "3d", "3D renders, CGI aesthetics, digital objects"),
    ("Seasonal", "seasonal", "Holiday/season-specific content (Christmas, Ramadan, etc.)"),
    ("Events", "events", "Weddings, conferences, concerts, ceremonies"),
    ("Local Culture", "local-culture", "Regional traditions, festivals, crafts, heritage"),
    ("Crafts", "crafts", "Handmade goods, artisans, DIY, traditional skills"),
    ("Fashion", "fashion", "Clothing, style, runway, apparel industry"),
    ("Beauty", "beauty", "Cosmetics, skincare, grooming, aesthetics"),
    ("Home", "home", "Interior living spaces, decor, domestic life"),
    ("Real Estate", "real-estate", "Properties, housing market, construction, listings"),
]

# ---------------------------------------------------------------------------
# 2. Subcategories (2–4 per category) → micro-niches (2–3 per subcategory)
# Commercially-oriented, buyer-searchable phrasing.
# ---------------------------------------------------------------------------

SUBCATEGORY_SEED: dict[str, list[tuple[str, list[str]]]] = {
    "ai": [
        (
            "Machine Learning",
            ["Neural Network Visualizations", "ML Model Training", "Data Labeling Workflows"],
        ),
        ("AI Applications", ["AI in Healthcare Diagnostics", "AI Customer Service"]),
        ("AI Concepts", ["Abstract AI Brains", "Human-Robot Collaboration"]),
    ],
    "technology": [
        ("Computing Devices", ["Laptop Workspaces", "Smartphone Close-ups"]),
        ("Software & Apps", ["App UI Mockups", "Code on Screens"]),
        ("Networks", ["Data Center Corridors", "5G Connectivity"]),
    ],
    "business": [
        ("Corporate Strategy", ["Boardroom Meetings", "Business Handshakes"]),
        ("Entrepreneurship", ["Startup Founders", "Small Business Owners"]),
    ],
    "finance": [
        ("Banking", ["Mobile Banking Apps", "Bank Vault Interiors"]),
        ("Investing", ["Stock Market Charts", "Crypto Trading Desks"]),
        ("Fintech", ["Contactless Payments", "Digital Wallets"]),
    ],
    "cybersecurity": [
        ("Security Operations", ["SOC Analyst Desks", "Firewall Visualizations"]),
        ("Privacy & Protection", ["Data Encryption Concepts", "Biometric Locks"]),
    ],
    "healthcare": [
        ("Medical Professionals", ["Doctor Portraits", "Nurse Teams"]),
        ("Treatment & Care", ["Modern Hospitals", "Telemedicine Consults"]),
    ],
    "wellness": [
        ("Mental Health", ["Mindfulness Meditation", "Stress Relief Practices"]),
        ("Fitness", ["Home Workouts", "Yoga Poses"]),
        ("Self Care", ["Spa Rituals", "Healthy Morning Routines"]),
    ],
    "education": [
        ("Classrooms", ["Teacher Student Interaction", "School Desk Details"]),
        ("E-Learning", ["Online Course Screens", "Remote Study Setups"]),
    ],
    "e-commerce": [
        ("Online Shopping", ["Unboxing Parcels", "Shopping Cart Concepts"]),
        ("Retail Tech", ["Warehouse Robots", "Last-mile Delivery"]),
    ],
    "marketing": [
        ("Advertising", ["Billboard Mockups", "Ad Campaign Shoots"]),
        ("Branding", ["Logo Design Process", "Brand Guideline Books"]),
        ("Analytics", ["Marketing Dashboards", "Social Media Metrics"]),
    ],
    "social-media": [
        ("Content Creation", ["Influencer Filming", "Ring Light Setups"]),
        ("Platforms", ["Smartphone Social Feeds", "Community Engagement"]),
    ],
    "sustainability": [
        ("Green Living", ["Zero Waste Kitchens", "Reusable Products"]),
        ("Conservation", ["Tree Planting", "Wildlife Protection"]),
    ],
    "renewable-energy": [
        ("Solar Power", ["Solar Panel Fields", "Rooftop Solar Installations"]),
        ("Wind & Hydro", ["Wind Turbines", "Hydroelectric Dams"]),
    ],
    "environment": [
        ("Climate", ["Melting Glaciers", "Drought Landscapes"]),
        ("Ecosystems", ["Coral Reefs", "Rainforest Canopies"]),
    ],
    "travel": [
        ("Destinations", ["Tropical Beaches", "Mountain Villages"]),
        ("Hospitality", ["Boutique Hotels", "Resort Pools"]),
        ("Adventure", ["Hiking Trails", "Desert Expeditions"]),
    ],
    "nature": [
        ("Landscapes", ["Misty Forests", "Volcanic Terrain"]),
        ("Wildlife", ["Big Cat Portraits", "Birds in Flight"]),
    ],
    "food": [
        ("Cuisine", ["Gourmet Plating", "Street Food Stalls"]),
        ("Cooking", ["Chef Hands at Work", "Fresh Ingredients"]),
        ("Food Production", ["Organic Farms", "Artisan Bakeries"]),
    ],
    "lifestyle": [
        ("Daily Life", ["Morning Coffee Rituals", "City Commutes"]),
        ("Hobbies", ["Urban Gardening", "Pottery Making"]),
    ],
    "family": [
        ("Parenting", ["Newborn Care", "Family Dinners"]),
        ("Generations", ["Grandparents and Grandchildren", "Multigenerational Homes"]),
    ],
    "people": [
        ("Portraits", ["Diverse Professional Headshots", "Candid Street Portraits"]),
        ("Emotions", ["Joyful Laughter", "Quiet Contemplation"]),
    ],
    "workplace": [
        ("Offices", ["Modern Open Offices", "Meeting Room Huddles"]),
        ("Remote Work", ["Home Office Desks", "Video Call Setups"]),
    ],
    "industry": [
        ("Factories", ["Assembly Lines", "Steel Mill Interiors"]),
        ("Heavy Equipment", ["Crane Operations", "Mining Machinery"]),
    ],
    "manufacturing": [
        ("Production Lines", ["Robotic Arms", "Quality Inspection"]),
        ("Craft Production", ["Workshop Benches", "Hand Tools Close-ups"]),
    ],
    "architecture": [
        ("Buildings", ["Glass Skyscrapers", "Historic Facades"]),
        ("Interiors", ["Minimalist Living Rooms", "Office Lobbies"]),
    ],
    "transportation": [
        ("Vehicles", ["Electric Cars", "Cargo Ships"]),
        ("Public Transit", ["Metro Stations", "High-speed Trains"]),
    ],
    "science": [
        ("Research", ["Lab Technicians", "Microscope Slides"]),
        ("Discovery", ["Space Telescopes", "DNA Helices"]),
    ],
    "space": [
        ("Astronomy", ["Milky Way Night Skies", "Nebula Renders"]),
        ("Exploration", ["Rocket Launches", "Astronaut Spacewalks"]),
    ],
    "abstract": [
        ("Geometric Art", ["Gradient Meshes", "Fractal Patterns"]),
        ("Fluid Art", ["Ink in Water", "Smoke Swirls"]),
    ],
    "backgrounds": [
        ("Gradients", ["Soft Pastel Gradients", "Dark Moody Backdrops"]),
        ("Scenes", ["Bokeh Light Scenes", "Studio Backdrop Setups"]),
    ],
    "textures": [
        ("Surfaces", ["Marble Textures", "Brushed Metal"]),
        ("Patterns", ["Fabric Weaves", "Wood Grain Details"]),
    ],
    "3d": [
        ("CGI Renders", ["Abstract 3D Shapes", "Isometric Illustrations"]),
        ("3D Objects", ["Product Mockup Renders", "Low-poly Characters"]),
    ],
    "seasonal": [
        ("Holidays", ["Christmas Decorations", "Ramadan Lanterns"]),
        ("Seasons", ["Autumn Foliage", "Winter Snow Scenes"]),
    ],
    "events": [
        ("Weddings", ["Bridal Portraits", "Ceremony Details"]),
        ("Conferences", ["Keynote Stages", "Networking Crowds"]),
    ],
    "local-culture": [
        ("Traditions", ["Folk Dancers", "Heritage Crafts"]),
        ("Festivals", ["Lantern Festivals", "Harvest Celebrations"]),
    ],
    "crafts": [
        ("Handmade Goods", ["Ceramic Pottery", "Woven Textiles"]),
        ("Artisans", ["Woodworking Shops", "Jewelry Makers"]),
    ],
    "fashion": [
        ("Clothing", ["Streetwear Looks", "Evening Gowns"]),
        ("Runway", ["Fashion Week Shows", "Model Backstage"]),
    ],
    "beauty": [
        ("Cosmetics", ["Lipstick Swatches", "Makeup Application"]),
        ("Skincare", ["Serum Bottles", "Facial Treatments"]),
    ],
    "home": [
        ("Interiors", ["Cozy Bedrooms", "Scandinavian Kitchens"]),
        ("Decor", ["Houseplant Corners", "Wall Art Displays"]),
    ],
    "real-estate": [
        ("Properties", ["Modern Villas", "City Apartments"]),
        ("Housing Market", ["For Sale Signs", "Construction Sites"]),
    ],
}

# ---------------------------------------------------------------------------
# 3. Trend sources — SEED_PLAN.md §3
# ---------------------------------------------------------------------------

TREND_SOURCES: list[dict] = [
    {
        "name": "Adobe Stock public trends",
        "source_type": TrendSourceType.ADOBE_REPORT,
        "endpoint_or_reference": "https://stock.adobe.com/ (public trend/collection pages)",
        "fetch_schedule": "weekly",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Counts + themes only; no artwork/description copying; ≤1 req/10s, ≤200/day; respect robots.txt",
    },
    {
        "name": "Adobe Stock contributor resources",
        "source_type": TrendSourceType.ADOBE_REPORT,
        "endpoint_or_reference": "Adobe Stock contributor blog / help pages (public)",
        "fetch_schedule": "weekly",
        "data_provenance": DataProvenance.VERIFIED,
        "notes": "Official guidance; summarize + cite, never republish full articles",
    },
    {
        "name": "Adobe creative trend reports",
        "source_type": TrendSourceType.ADOBE_REPORT,
        "endpoint_or_reference": "Public Adobe creative trend report download pages (PDF)",
        "fetch_schedule": "per publication",
        "data_provenance": DataProvenance.VERIFIED,
        "notes": "Extract theme names + paraphrased direction; no report images/long excerpts",
    },
    {
        "name": "Search trend sources (general)",
        "source_type": TrendSourceType.SEARCH_TRENDS,
        "endpoint_or_reference": "Official provider APIs only",
        "fetch_schedule": "daily",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Indices/aggregates; never de-anonymize queries",
    },
    {
        "name": "Google Trends",
        "source_type": TrendSourceType.SEARCH_TRENDS,
        "endpoint_or_reference": "Sanctioned public interface within its terms (no unofficial scraping)",
        "fetch_schedule": "daily (7d + 90d windows)",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Indices are relative 0–100, not absolute volumes — documented on every derived metric",
    },
    {
        "name": "Social media trend signals",
        "source_type": TrendSourceType.SOCIAL_TRENDS,
        "endpoint_or_reference": "Official platform APIs with developer credentials; public trend endpoints only",
        "fetch_schedule": "daily",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Aggregates only; no personal data; per-platform terms",
    },
    {
        "name": "YouTube trend signals",
        "source_type": TrendSourceType.SOCIAL_TRENDS,
        "endpoint_or_reference": "YouTube Data API v3 (official)",
        "fetch_schedule": "daily",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "API quota units; 24h cache; quota exhausted → serve cached, mark stale",
    },
    {
        "name": "Public market research",
        "source_type": TrendSourceType.MARKETPLACE_FEED,
        "endpoint_or_reference": "Public report landing pages, press releases, open datasets",
        "fetch_schedule": "monthly",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Cite sources; use figures with stated methodology",
    },
    {
        "name": "Seasonal calendars",
        "source_type": TrendSourceType.OTHER,
        "endpoint_or_reference": "Internal curated dataset (built from public holiday/event calendars)",
        "fetch_schedule": "quarterly review",
        "data_provenance": DataProvenance.ESTIMATED,
        "notes": "Date-anchored events; buyers search 4–8 weeks ahead",
    },
    {
        "name": "Commercial keyword demand",
        "source_type": TrendSourceType.SEARCH_TRENDS,
        "endpoint_or_reference": "Official keyword-research provider APIs (user-provisioned credentials)",
        "fetch_schedule": "weekly",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Directional indices, not buyer counts",
    },
    {
        "name": "Internal user performance data",
        "source_type": TrendSourceType.USER_UPLOAD,
        "endpoint_or_reference": "User-provided CSV/export upload or manual entry",
        "fetch_schedule": "on upload",
        "data_provenance": DataProvenance.USER_PROVIDED,
        "notes": "User's own portfolio data only; never pooled; absence lowers confidence",
    },
    # --- Phase 2 real-data sources (PHASE2_DESIGN.md §3) ---
    {
        "name": "RSS feeds (blogs + photography press)",
        "source_type": TrendSourceType.MARKETPLACE_FEED,
        "endpoint_or_reference": "adapter: rss (feedparser); feed list from rss_feeds setting",
        "fetch_schedule": "every 6h",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Public RSS of design/photography blogs (Adobe Blog, PetaPixel, Design Milk)",
    },
    {
        "name": "ScrapeGraphAI web discovery",
        "source_type": TrendSourceType.SEARCH_TRENDS,
        "endpoint_or_reference": "adapter: scrapegraph_web (search_on_web keyless Tier 1; SmartScraperGraph Tier 2 with OPENAI_API_KEY)",
        "fetch_schedule": "daily",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Keyless web search + article extraction; LLM tier optional",
    },
    {
        "name": "Agent-Reach web channels",
        "source_type": TrendSourceType.SEARCH_TRENDS,
        "endpoint_or_reference": "adapter: agentreach_web (WebChannel.read via Jina Reader)",
        "fetch_schedule": "daily",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Jina-Reader fetch of curated trend article URLs",
    },
    {
        "name": "V2EX hot topics",
        "source_type": TrendSourceType.SOCIAL_TRENDS,
        "endpoint_or_reference": "adapter: agentreach_web / V2EXChannel.get_hot_topics()",
        "fetch_schedule": "every 6h",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Chinese tech-community hot topics; no-auth method",
    },
    {
        "name": "Xueqiu hot stocks",
        "source_type": TrendSourceType.SOCIAL_TRENDS,
        "endpoint_or_reference": "adapter: agentreach_web / XueqiuChannel.get_hot_stocks()/get_hot_posts()",
        "fetch_schedule": "every 6h",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Xueqiu hot stocks + posts; no-auth method",
    },
    {
        "name": "YouTube channel RSS",
        "source_type": TrendSourceType.SOCIAL_TRENDS,
        "endpoint_or_reference": "adapter: youtube_rss (public channel feeds via feedparser; NO yt-dlp)",
        "fetch_schedule": "every 6h",
        "data_provenance": DataProvenance.THIRD_PARTY,
        "notes": "Design/creative YouTube channels; no auth required",
    },
    {
        "name": "GitHub trending AI repos",
        "source_type": TrendSourceType.MARKETPLACE_FEED,
        "endpoint_or_reference": "adapter: github_trending (api.github.com search, stdlib urllib; 10 req/min unauth)",
        "fetch_schedule": "every 6h",
        "data_provenance": DataProvenance.VERIFIED,
        "notes": "Official GitHub API → VERIFIED provenance",
    },
    {
        "name": "Adobe Contributor dashboard (private)",
        "source_type": TrendSourceType.ADOBE_REPORT,
        "endpoint_or_reference": "adapter: adobe_contributor (Playwright on the user's own contributor dashboard)",
        "fetch_schedule": "daily 06:00",
        "is_active": False,
        "data_provenance": DataProvenance.USER_PROVIDED,
        "notes": "NOT CONFIGURED until the user completes setup; never simulated; private rows only",
    },
]

# ---------------------------------------------------------------------------
# 4. Compliance rules — SEED_PLAN.md §4 (docs/18 §2). Exactly 28 rules.
# severity: blocker→BLOCK, major→WARN, minor→INFO (SEED_PLAN §4 severity mapping).
# applies_to per family: GEN→PROMPT_SCREEN+ASSET_SCREEN,
# IP→PROMPT_SCREEN+ASSET_SCREEN+METADATA_SCREEN, TQ→ASSET_SCREEN,
# MH→METADATA_SCREEN+ASSET_SCREEN.
# ---------------------------------------------------------------------------

_P = ComplianceCheckType.PROMPT_SCREEN
_A = ComplianceCheckType.ASSET_SCREEN
_M = ComplianceCheckType.METADATA_SCREEN

COMPLIANCE_RULES: list[dict] = [
    {
        "rule_key": "gen-01",
        "name": "GEN-01 — AI disclosure flag present",
        "description": "AI-generated disclosure flag is present and set correctly on the asset record.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "automated",
        "applies_to": [_P, _A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI disclosure (verify current section at implementation)",
        "rationale": "Undisclosed AI content is the fastest path to account-level rejection; the flag must be set before any submission.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "gen-02",
        "name": "GEN-02 — Generating tool named accurately",
        "description": "Generating tool/model is named accurately (matches the generation record, not a guess).",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_P, _A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI disclosure",
        "rationale": "A wrong tool name is a misrepresentation that undermines the disclosure; it must match the actual generation record.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "gen-03",
        "name": "GEN-03 — Generation date recorded",
        "description": "Generation date is recorded on the asset record.",
        "severity": RuleSeverity.INFO,
        "check_method": "automated",
        "applies_to": [_P, _A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI disclosure",
        "rationale": "Completes the disclosure record and supports auditability of the asset pipeline.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "gen-04",
        "name": "GEN-04 — Prompt must not hide AI origin",
        "description": "Prompt package does not instruct the generator to hide the AI origin of the asset.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI disclosure",
        "rationale": "Instructions to conceal AI origin convert a disclosure lapse into an intentional violation with account-level consequences.",
        "patterns": [
            r"hide.{0,20}(ai|artificial intelligence)",
            r"(don't|do not).{0,20}mention.{0,20}ai",
            r"pass.{0,20}as.{0,20}(real|genuine|photo)",
            r"undisclosed",
        ],
        "thresholds": {},
    },
    {
        "rule_key": "ip-01",
        "name": "IP-01 — No logos or brand marks",
        "description": "No logos or brand marks are visible (or they are flagged for removal/review).",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — intellectual property",
        "rationale": "Visible logos are trademark infringements that trigger certain rejection and expose the contributor to takedown.",
        "patterns": [r"\blogo(s)?\b", r"\bbrand(ing|ed)?\s+(mark|packaging)\b"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-02",
        "name": "IP-02 — No trademarks in image, video, or metadata",
        "description": "No trademarks (names, slogans, distinctive packaging) appear in the image, video, or metadata.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — intellectual property",
        "rationale": "Trademark terms in any field — including keywords — create infringement risk even when the visual is clean.",
        "patterns": ["brand keyword list (illustrative, non-exhaustive)"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-03",
        "name": "IP-03 — No copyrighted characters",
        "description": "No copyrighted characters (cartoon, film, game, mascot) are referenced or depicted.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — intellectual property",
        "rationale": "Character IP is aggressively enforced by rights holders; any reference is a rejection and strike risk.",
        "patterns": ["copyrighted-character keyword list (illustrative, non-exhaustive)"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-04",
        "name": "IP-04 — No celebrity likeness",
        "description": "No celebrity likeness or identifiable public figure is depicted or referenced.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — releases & likeness",
        "rationale": "Likeness rights apply regardless of whether the person is AI-generated; recognizable real people need releases.",
        "patterns": ["celebrity keyword list (illustrative, non-exhaustive)"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-05",
        "name": "IP-05 — No living-artist style requests",
        "description": "No living-artist name or distinctive living-artist style is requested in the prompt.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "automated",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — intellectual property; platform originality policy",
        "rationale": "Artist-name prompts produce derivative work and violate the originality policy; style must be described neutrally.",
        "patterns": [r"in the style of\s+([A-Z][a-zA-Z'’\- ]{1,40})"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-06",
        "name": "IP-06 — No recognizable copyrighted material",
        "description": "No recognizable copyrighted material (artwork, album/book covers, distinctive designs) is referenced.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — intellectual property",
        "rationale": "Distinctive protected designs are recognizable even in partial form; referencing them invites infringement review.",
        "patterns": [r"\b(album|book|movie)\s+(cover|poster)\b", "distinctive design"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-07",
        "name": "IP-07 — No brand/artist/celebrity names in metadata",
        "description": "Metadata contains no brand, artist, or celebrity names as keywords.",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_P, _A, _M],
        "source_reference": "Adobe Stock contributor guidelines — metadata policy",
        "rationale": "Name-keywords are both spam and an IP signal; they attract rejection and policy flags.",
        "patterns": ["brand/artist/celebrity keyword lists (illustrative, non-exhaustive)"],
        "thresholds": {},
    },
    {
        "rule_key": "ip-08",
        "name": "IP-08 — 'Inspired by' language audit",
        "description": "Concept descriptions do not reference identifiable individual works via 'inspired by' language.",
        "severity": RuleSeverity.WARN,
        "check_method": "model_assisted",
        "applies_to": [_P, _A, _M],
        "source_reference": "Platform originality policy — TREND → INSIGHT, never TREND → COPY",
        "rationale": "'Inspired by' ties a concept to a specific protected work; trends must be abstracted into original insight.",
        "patterns": [r"inspired by\s+([A-Z][a-zA-Z'’\- ]{1,40})"],
        "thresholds": {},
    },
    {
        "rule_key": "tq-01",
        "name": "TQ-01 — Resolution meets minimum",
        "description": "Resolution meets the minimum (image ≥ 4 MP or the platform minimum in force; video ≥ 1080p).",
        "severity": RuleSeverity.BLOCK,
        "check_method": "automated",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — technical requirements (verify current minimums at implementation)",
        "rationale": "Below-minimum resolution is an automatic technical rejection; it is cheap to check and expensive to miss.",
        "patterns": [],
        "thresholds": {"min_image_megapixels": 4.0, "min_video_height_px": 1080},
    },
    {
        "rule_key": "tq-02",
        "name": "TQ-02 — Noise/grain within bounds",
        "description": "Noise/grain is within acceptable bounds (not destructive).",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — technical requirements",
        "rationale": "Destructive noise reads as a technical defect at review and degrades buyer trust in the asset.",
        "patterns": [],
        "thresholds": {"note": "pixel analysis required; text engine flags for manual check"},
    },
    {
        "rule_key": "tq-03",
        "name": "TQ-03 — Blur/focus acceptable",
        "description": "Subject is acceptably sharp (motion blur only where intentional and noted).",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — technical requirements",
        "rationale": "Unintentional blur is a top technical rejection reason; intentional blur must be documented in metadata.",
        "patterns": [],
        "thresholds": {"note": "pixel analysis required; text engine flags for manual check"},
    },
    {
        "rule_key": "tq-04",
        "name": "TQ-04 — No destructive compression artifacts",
        "description": "No compression artifacts (blocking/banding) beyond the acceptable threshold.",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — technical requirements",
        "rationale": "Visible compression damage signals a low-quality source and fails technical review.",
        "patterns": [],
        "thresholds": {"note": "pixel analysis required; text engine flags for manual check"},
    },
    {
        "rule_key": "tq-05",
        "name": "TQ-05 — No anatomical errors",
        "description": "No anatomical errors in AI people/animals (hands, faces, limbs); failures are HIGH_RISK.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI quality",
        "rationale": "Anatomical errors are the signature defect of AI imagery and trigger immediate rejection.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "tq-06",
        "name": "TQ-06 — No image artifacts",
        "description": "No image artifacts: extra limbs, merged objects, garbled text, watermark-like marks.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — generative AI quality",
        "rationale": "Generative artifacts are trivially visible at review and guarantee rejection.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "tq-07",
        "name": "TQ-07 — No video artifacts",
        "description": "No video artifacts: flicker, temporal inconsistency, frame glitches.",
        "severity": RuleSeverity.BLOCK,
        "check_method": "model_assisted",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — video requirements",
        "rationale": "Temporal defects fail video review even when individual frames look acceptable.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "tq-08",
        "name": "TQ-08 — Exposure/color acceptable",
        "description": "Asset is not critically over/underexposed and has no destructive color clipping.",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_A],
        "source_reference": "Adobe Stock contributor guidelines — technical requirements",
        "rationale": "Clipped exposure destroys recoverable detail and fails technical review.",
        "patterns": [],
        "thresholds": {"note": "pixel analysis required; text engine flags for manual check"},
    },
    {
        "rule_key": "mh-01",
        "name": "MH-01 — Title present and accurate",
        "description": "Title is present, within length limits, and accurately describes the content.",
        "severity": RuleSeverity.INFO,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — metadata (docs/19)",
        "rationale": "The title is the primary buyer signal; missing or inaccurate titles suppress discoverability and risk rejection.",
        "patterns": [],
        "thresholds": {
            "title_max_chars": 200,
            "title_target_min_chars": 70,
            "title_target_max_chars": 140,
        },
    },
    {
        "rule_key": "mh-02",
        "name": "MH-02 — Description present and accurate",
        "description": "Description is present, accurate, and within length limits.",
        "severity": RuleSeverity.INFO,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — metadata (docs/19)",
        "rationale": "Descriptions feed search relevance; keyword-list descriptions read as spam to reviewers.",
        "patterns": [],
        "thresholds": {
            "description_max_chars": 1000,
            "description_target_min_chars": 200,
            "description_target_max_chars": 500,
            "max_keyword_density": 0.30,
        },
    },
    {
        "rule_key": "mh-03",
        "name": "MH-03 — Keyword count and ordering",
        "description": "Keyword count is within limits (10–25, target 15–20) and the ordering strategy is followed.",
        "severity": RuleSeverity.INFO,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — metadata (docs/19)",
        "rationale": "Count violations are mechanical rejections; ordering specific→general maximizes ranking.",
        "patterns": [],
        "thresholds": {
            "keywords_max": 25,
            "keywords_min": 10,
            "keywords_target_min": 15,
            "keywords_target_max": 20,
        },
    },
    {
        "rule_key": "mh-04",
        "name": "MH-04 — Spam detection",
        "description": "No spam: no keyword stuffing, irrelevant trending terms, or misleading claims.",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — metadata policy (docs/19)",
        "rationale": "Metadata spam is a policy violation that can escalate from rejection to account penalties.",
        "patterns": [
            "SPAM-01 keyword stuffing (term > 2× across title+keywords)",
            "SPAM-02 irrelevant trending terms",
            "SPAM-03 misleading claims",
            "SPAM-04 bait terms",
            "SPAM-05 prohibited names",
            "SPAM-06 title-keyword echo",
            "SPAM-07 description stuffing (>30% keyword density)",
        ],
        "thresholds": {},
    },
    {
        "rule_key": "mh-05",
        "name": "MH-05 — Category mapping valid",
        "description": "Category/subcategory mapping is valid against the current Adobe Stock categories.",
        "severity": RuleSeverity.INFO,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock category list (verify current list at implementation)",
        "rationale": "Miscategorized assets surface to the wrong buyers and waste review cycles.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "mh-06",
        "name": "MH-06 — Near-duplicate check",
        "description": "Asset fingerprint is checked against already-submitted assets for near-duplicates.",
        "severity": RuleSeverity.WARN,
        "check_method": "automated",
        "applies_to": [_M, _A],
        "source_reference": "Platform originality policy (docs/17)",
        "rationale": "Near-duplicate resubmission is treated as spam behavior and can trigger account-level review.",
        "patterns": [],
        "thresholds": {"near_duplicate_threshold": 0.90},
    },
    {
        "rule_key": "mh-07",
        "name": "MH-07 — Commercial usefulness",
        "description": "Asset is commercially useful (not pure filler such as purposeless blank backgrounds or unusable crops).",
        "severity": RuleSeverity.INFO,
        "check_method": "model_assisted",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — commercial value",
        "rationale": "Filler assets clog review and erode portfolio quality signals.",
        "patterns": [],
        "thresholds": {},
    },
    {
        "rule_key": "mh-08",
        "name": "MH-08 — Release logic",
        "description": "Recognizable real people or property have the required releases; AI people still pass IP-04.",
        "severity": RuleSeverity.WARN,
        "check_method": "human_review",
        "applies_to": [_M, _A],
        "source_reference": "Adobe Stock contributor guidelines — model/property releases",
        "rationale": "Missing releases are a legal exposure; AI-generated people do not need model releases but still need likeness screening.",
        "patterns": [],
        "thresholds": {},
    },
]

# ---------------------------------------------------------------------------
# 5. Canonical settings (CONTRACT.md §5.15)
# ---------------------------------------------------------------------------

SETTINGS_DEFAULTS: list[tuple[str, object]] = [
    ("briefing.time", "08:00"),
    ("briefing.timezone", "Asia/Karachi"),
    ("briefing.days", ["mon", "tue", "wed", "thu", "fri"]),
    ("opportunity.min_score", 55),
    ("opportunity.min_confidence", 0.5),
    ("compliance.strictness", "standard"),
    ("notifications.email_enabled", False),
    ("notifications.digest_time", "08:00"),
    ("production.default_language", "en"),
    ("retention.soft_delete_days", 30),
    ("planner.daily_capacity", 0),
    ("planner.weekly_capacity", 0),
    ("planner.blackout_dates", []),
    # --- Phase 3: daily production planner capacity (user-editable; no
    # hard-coded Adobe submission limits anywhere) ---
    (
        "production_capacity",
        {
            "weekly_capacity": 20,
            "daily_target": 4,
            "image_target": 3,
            "video_target": 1,
            "max_daily_generation": 10,
            "priority_preference": "score",
        },
    ),
    # --- Phase 2 (PHASE2_DESIGN.md §2) ---
    ("dev_mode", False),
    (
        "rss_feeds",
        [
            {"name": "Adobe Blog", "url": "https://blog.adobe.com/en/feed", "category": "creative"},
            {"name": "PetaPixel", "url": "https://petapixel.com/feed/", "category": "photography"},
            {"name": "Design Milk", "url": "https://design-milk.com/feed/", "category": "design"},
        ],
    ),
]

# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def seed_taxonomy(session: Session) -> dict[str, int]:
    """Seed 39 categories + subcategories + micro-niches. Returns row counts."""
    from app.models.taxonomy import Category, MicroNiche, Subcategory

    cat_count = sub_count = niche_count = 0
    for order, (name, slug, description) in enumerate(CATEGORIES, start=1):
        cat = session.query(Category).filter_by(slug=slug).one_or_none()
        if cat is None:
            cat = Category(
                name=name,
                slug=slug,
                description=description,
                sort_order=order,
                is_system=True,
            )
            session.add(cat)
            session.flush()
            cat_count += 1
        # Attach taxonomy version for classified rows (docs/15 §6).
        for sub_order, (sub_name, niches) in enumerate(SUBCATEGORY_SEED.get(slug, []), start=1):
            sub_slug = _slugify(sub_name)
            sub = (
                session.query(Subcategory)
                .filter_by(category_id=cat.id, slug=sub_slug)
                .one_or_none()
            )
            if sub is None:
                sub = Subcategory(
                    category_id=cat.id,
                    name=sub_name,
                    slug=sub_slug,
                    description=f"{sub_name} within {name}.",
                    sort_order=sub_order,
                    is_system=True,
                )
                session.add(sub)
                session.flush()
                sub_count += 1
            for niche_name in niches:
                niche_slug = _slugify(niche_name)
                niche = (
                    session.query(MicroNiche)
                    .filter_by(subcategory_id=sub.id, slug=niche_slug)
                    .one_or_none()
                )
                if niche is None:
                    niche = MicroNiche(
                        subcategory_id=sub.id,
                        name=niche_name,
                        slug=niche_slug,
                        description=f"{niche_name} — demand unit ({TAXONOMY_VERSION}).",
                        data_provenance=DataProvenance.ESTIMATED,
                        is_system=True,
                    )
                    session.add(niche)
                    session.flush()
                    niche_count += 1
    session.commit()
    return {"categories": cat_count, "subcategories": sub_count, "micro_niches": niche_count}


def seed_trend_sources(session: Session) -> int:
    from app.models.intelligence import TrendSource

    count = 0
    for spec in TREND_SOURCES:
        existing = session.query(TrendSource).filter_by(name=spec["name"]).one_or_none()
        if existing is None:
            spec = dict(spec)
            is_active = spec.pop("is_active", True)
            session.add(TrendSource(is_active=is_active, **spec))
            count += 1
    session.commit()
    return count


def seed_compliance_rules(session: Session) -> int:
    from app.models.compliance import ComplianceRule

    count = 0
    for spec in COMPLIANCE_RULES:
        existing = (
            session.query(ComplianceRule)
            .filter_by(rule_key=spec["rule_key"], version=RULES_VERSION_INT)
            .one_or_none()
        )
        if existing is None:
            check_id = spec["rule_key"].upper()
            session.add(
                ComplianceRule(
                    rule_key=spec["rule_key"],
                    version=RULES_VERSION_INT,
                    name=spec["name"],
                    description=spec["description"],
                    severity=spec["severity"],
                    applies_to=[t.value for t in spec["applies_to"]],
                    is_enabled=True,
                    rule_config={
                        "check_id": check_id,
                        "version_string": RULES_VERSION_STR,
                        "requirement_text": spec["description"],
                        "rationale": spec["rationale"],
                        "check_method": spec["check_method"],
                        "source_reference": spec["source_reference"],
                        "patterns": spec["patterns"],
                        "thresholds": spec["thresholds"],
                    },
                )
            )
            count += 1
    session.commit()
    return count


def seed_settings(session: Session) -> int:
    from app.models.settings import Setting

    count = 0
    for key, value in SETTINGS_DEFAULTS:
        existing = session.query(Setting).filter_by(project_id=None, key=key).one_or_none()
        if existing is None:
            session.add(Setting(project_id=None, key=key, value={"value": value}))
            count += 1
    session.commit()
    return count


# ---------------------------------------------------------------------------
# 6. Demo MOCK rows — clearly labeled, never presented as real data
# ---------------------------------------------------------------------------


def _demo_snapshot_payload(
    topic: str, window: str, w0: float, w1: float, baseline: float, seed_n: int
) -> dict:
    import hashlib

    def det(tag: str, lo: float, hi: float) -> float:
        h = hashlib.sha256(f"{topic}|{tag}|{seed_n}".encode()).hexdigest()
        return round(lo + (int(h[:8], 16) / 0xFFFFFFFF) * (hi - lo), 3)

    payload = {
        "topic": topic,
        "window": window,
        "w0_mean": w0,
        "w1_mean": w1,
        "baseline_mean": baseline,
        "keyword_tvs": [det(f"tv{i}", -1.0, 3.0) for i in range(5)],
        "source_z_scores": [det(f"z{i}", -2.0, 2.0) for i in range(3)],
        "mock": True,
        "note": "Demo snapshot — deterministic mock values, not real Adobe data.",
    }
    return payload


def seed_demo(session: Session) -> dict[str, int]:
    """Seed demo rows labeled provenance=MOCK. Skipped once seed.demo_batch exists."""
    from app.models.compliance import ComplianceCheck, SimilarityRecord
    from app.models.ideation import ImageIdea, VideoIdea
    from app.models.intelligence import (
        MarketMetric,
        Opportunity,
        Prediction,
        TrendSignal,
        TrendSnapshot,
        TrendSource,
    )
    from app.models.platform import Notification
    from app.models.production import Asset, AssetVersion, MetadataRecord, ProductionQueue
    from app.models.prompts import Prompt, PromptVersion
    from app.models.settings import Setting
    from app.models.taxonomy import MicroNiche

    if session.query(Setting).filter_by(key="seed.demo_batch").one_or_none():
        return {"skipped": 1}

    counts: dict[str, int] = {}
    now = datetime.now(UTC)

    def niche_id(slug: str) -> str:
        row = session.query(MicroNiche).filter_by(slug=slug).one()
        return row.id

    niches = {
        "ai-health": niche_id("ai-in-healthcare-diagnostics"),
        "solar": niche_id("solar-panel-fields"),
        "home-office": niche_id("home-office-desks"),
        "meditation": niche_id("mindfulness-meditation"),
        "streetwear": niche_id("streetwear-looks"),
    }
    source = session.query(TrendSource).filter_by(name="Google Trends").one()

    # -- Trend snapshots: 5 niches × 2 weekly aggregates (W1, W0) across 14 days --
    snapshot_values = {
        "ai-health": (78.0, 71.0, 66.0),
        "solar": (82.0, 74.0, 60.0),
        "home-office": (64.0, 66.0, 62.0),
        "meditation": (70.0, 68.0, 58.0),
        "streetwear": (59.0, 61.0, 55.0),
    }
    for i, (key, (w0, w1, base)) in enumerate(snapshot_values.items()):
        niche_name = session.query(MicroNiche).filter_by(id=niches[key]).one().name
        for window, captured_days_ago in (("W1", 10), ("W0", 3)):
            payload = _demo_snapshot_payload(niche_name, window, w0, w1, base, i)
            payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            session.add(
                TrendSnapshot(
                    trend_source_id=source.id,
                    captured_at=now - timedelta(days=captured_days_ago),
                    payload=payload,
                    payload_hash=payload_hash,
                )
            )
    counts["trend_snapshots"] = 10

    # -- Trend signals: rising topics --
    for i, (key, label) in enumerate(
        [
            ("ai-health", "Rising: AI diagnostics visual demand"),
            ("solar", "Rising: solar installation imagery"),
            ("meditation", "Rising: mindfulness at work"),
        ]
    ):
        session.add(
            TrendSignal(
                micro_niche_id=niches[key],
                signal_name=label,
                description=f"Demo signal ({DEMO_BATCH}): keyword momentum positive over the last 14 days.",
                metric_name="keyword_momentum",
                metric_value=1.4 + 0.3 * i,
                metric_unit="ratio",
                data_provenance=DataProvenance.MOCK,
                confidence=0.62,
            )
        )
    counts["trend_signals"] = 3

    # -- Market metrics: 5 niches × 2 periods --
    for key in niches:
        for j, (start, end) in enumerate(
            [("2026-08-24", "2026-08-30"), ("2026-08-31", "2026-09-06")]
        ):
            session.add(
                MarketMetric(
                    micro_niche_id=niches[key],
                    period_start=date.fromisoformat(start),
                    period_end=date.fromisoformat(end),
                    demand_index=55.0 + 5 * j + len(key),
                    supply_count=1200 + 100 * j,
                    competition_index=48.0 + 2 * j,
                    avg_price_estimate=3.20,
                    data_provenance=DataProvenance.MOCK,
                    notes=f"Demo metric ({DEMO_BATCH}).",
                )
            )
    counts["market_metrics"] = 10

    # -- Predictions: 5 niches × 2 horizons --
    pred_inputs = {
        "ai-health": (68, 0.79),
        "solar": (74, 0.81),
        "home-office": (58, 0.66),
        "meditation": (66, 0.72),
        "streetwear": (55, 0.61),
    }
    for key, (demand, conf) in pred_inputs.items():
        for horizon in (PredictionHorizon.H30_DAYS, PredictionHorizon.H90_DAYS):
            session.add(
                Prediction(
                    micro_niche_id=niches[key],
                    horizon=horizon,
                    predicted_demand_index=demand,
                    predicted_direction=PredictedDirection.UP,
                    confidence=conf,
                    methodology=(
                        "pred_rules_v1.0 (rules-based, 10 features). Demo prediction on "
                        "mock data — probabilistic estimate, never a guarantee of sales."
                    ),
                    data_provenance=DataProvenance.MOCK,
                    based_on_metrics_from=date(2026, 8, 24),
                    based_on_metrics_to=date(2026, 9, 6),
                )
            )
    counts["predictions"] = 10

    # -- Opportunities: 12 across statuses --
    opp_specs = [
        ("AI diagnostics hero images", "ai-health", 78.5, "new"),
        ("Solar farm aerial series", "solar", 81.2, "new"),
        ("Mindful work breaks", "meditation", 69.4, "new"),
        ("Home office ergonomics", "home-office", 63.8, "new"),
        ("Streetwear flat lays", "streetwear", 58.1, "new"),
        ("AI radiology concept set", "ai-health", 76.0, "new"),
        ("Rooftop solar installers", "solar", 79.6, "approved"),
        ("Meditation app visuals", "meditation", 68.2, "approved"),
        ("Standing desk setups", "home-office", 64.9, "approved"),
        ("Solar panel textures", "solar", 72.3, "in_progress"),
        ("AI nurse assistant concept", "ai-health", 74.1, "in_progress"),
        ("Winter streetwear lookbook", "streetwear", 55.7, "archived"),
    ]
    opp_ids: list[str] = []
    for i, (title, key, score, status) in enumerate(opp_specs):
        niche_name = session.query(MicroNiche).filter_by(id=niches[key]).one().name
        opp = Opportunity(
            micro_niche_id=niches[key],
            title=title,
            summary=f"Demo opportunity ({DEMO_BATCH}): produce commercial {title.lower()} for the {niche_name} niche.",
            opportunity_score=score,
            confidence=0.72,
            demand_evidence=[
                {"kind": "trend_snapshot", "topic": niche_name, "mock": True},
                {"kind": "keyword_momentum", "value": 1.4, "mock": True},
            ],
            risk_notes="Demo row — assess real saturation before producing.",
            data_provenance=DataProvenance.MOCK,
            status=status,
            priority=i,
        )
        session.add(opp)
        session.flush()
        opp_ids.append(opp.id)
    counts["opportunities"] = len(opp_specs)

    # -- Image ideas: 8 (linked to first 8 opportunities) --
    idea_titles = [
        (
            "Radiologist reviewing AI scan overlay",
            "ai-health",
            "Portrait of a clinician studying a glowing AI diagnostic overlay; differentiator: authentic clinical setting, no sci-fi clichés.",
        ),
        (
            "Solar farm at golden hour",
            "solar",
            "Aerial of panel rows at golden hour; differentiator: human maintenance crew for scale, not empty landscape.",
        ),
        (
            "Meditation corner in home office",
            "meditation",
            "Small meditation nook beside a desk; differentiator: lived-in realism, not spa stock.",
        ),
        (
            "Ergonomic desk side profile",
            "home-office",
            "Side-profile of an adjustable desk setup; differentiator: precise ergonomic angles, annotated feel.",
        ),
        (
            "Streetwear flat lay on concrete",
            "streetwear",
            "Top-down apparel flat lay on raw concrete; differentiator: harsh shadow play, editorial tone.",
        ),
        (
            "AI triage kiosk concept",
            "ai-health",
            "Patient interacting with a triage kiosk; differentiator: warm human-centered framing of clinical AI.",
        ),
        (
            "Installer on rooftop panels",
            "solar",
            "Worker securing a rooftop panel; differentiator: safety gear realism, documentary angle.",
        ),
        (
            "Breathing exercise close-up",
            "meditation",
            "Close-up of hands in breathing exercise; differentiator: macro texture, shallow depth of field.",
        ),
    ]
    image_idea_ids: list[str] = []
    for i, (title, key, concept) in enumerate(idea_titles):
        idea = ImageIdea(
            opportunity_id=opp_ids[i],
            micro_niche_id=niches[key],
            title=title,
            concept=concept,
            originality_notes=f"Demo idea ({DEMO_BATCH}): differentiators documented; originality scan recommended before production.",
            reference_mood=["documentary", "commercial", "authentic"],
            status=IdeaStatus.READY if i < 5 else IdeaStatus.DRAFT,
            priority=i,
        )
        session.add(idea)
        session.flush()
        image_idea_ids.append(idea.id)
    counts["image_ideas"] = len(idea_titles)

    # -- Video ideas: 6 --
    video_titles = [
        (
            "Solar panel installation timelapse",
            "solar",
            12,
            ["Drone approach", "Panel placement", "Sunset wide"],
        ),
        (
            "Meditation breath loop",
            "meditation",
            8,
            ["Inhale close-up", "Exhale wide", "Seamless loop point"],
        ),
        ("Home office setup tour", "home-office", 15, ["Desk pan", "Detail cuts", "Final wide"]),
        ("Streetwear motion lookbook", "streetwear", 10, ["Walk cycle", "Fabric detail", "Spin"]),
        ("AI scan visualization", "ai-health", 8, ["Scan sweep", "Data overlay", "Result reveal"]),
        ("Rooftop solar drone orbit", "solar", 12, ["Orbit start", "Mid orbit", "Pull back"]),
    ]
    video_idea_ids: list[str] = []
    for i, (title, key, duration, shots) in enumerate(video_titles):
        idea = VideoIdea(
            opportunity_id=opp_ids[i % len(opp_ids)],
            micro_niche_id=niches[key],
            title=title,
            concept=f"Demo video concept ({DEMO_BATCH}): {title.lower()} with clean commercial pacing.",
            originality_notes="Demo idea: shot list designed to avoid common stock clichés.",
            duration_target_seconds=duration,
            shot_list=[{"shot": s, "seconds": duration // len(shots)} for s in shots],
            reference_mood=["cinematic", "clean"],
            status=IdeaStatus.READY if i < 3 else IdeaStatus.DRAFT,
            priority=i,
        )
        session.add(idea)
        session.flush()
        video_idea_ids.append(idea.id)
    counts["video_ideas"] = len(video_titles)

    # -- Prompts: 3 prompt packages + versions for the first 3 image ideas --
    from app.schemas.enums import PromptStatus

    prompt_ids: list[str] = []
    for i, idea_id in enumerate(image_idea_ids[:3]):
        prompt = Prompt(
            image_idea_id=idea_id,
            asset_type=AssetType.IMAGE,
            name=f"Demo prompt package {i + 1}",
            status=PromptStatus.DRAFT,
        )
        session.add(prompt)
        session.flush()
        prompt_ids.append(prompt.id)
        current_version_id = None
        for v in (1, 2):
            pv = PromptVersion(
                prompt_id=prompt.id,
                version_number=v,
                prompt_text=(
                    f"Demo primary prompt v{v} ({DEMO_BATCH}): photorealistic commercial scene, "
                    "35mm, natural light. Alternative viewpoint available in parameters."
                ),
                negative_prompt_text="watermark, logo, text, blurry, low resolution, deformed, distorted, extra limbs",
                parameters={
                    "tool_family": "midjourney",
                    "mock": True,
                    "alternative_prompt": f"Demo alternative v{v}: same scene, alternate viewpoint.",
                    "technical_block": {"ar": "3:2", "quality": "high"},
                    "quality_block": {"sharpness": "tack-sharp subject"},
                    "originality_block": {"avoid": ["sci-fi clichés", "empty landscapes"]},
                    "compliance_block": {"ai_disclosure": True},
                    "provenance_note": "MOCK demo prompt — regenerate before real production.",
                },
                change_summary=(
                    "Demo seed version."
                    if v == 1
                    else "Demo seed revision: tightened negative prompt."
                ),
                created_by="seed",
            )
            session.add(pv)
            session.flush()
            current_version_id = pv.id
        prompt.current_version_id = current_version_id
    counts["prompts"] = 3
    counts["prompt_versions"] = 6

    # -- Compliance checks: demo evidence rows --
    session.add(
        ComplianceCheck(
            check_type=ComplianceCheckType.PROMPT_SCREEN,
            prompt_id=session.query(Prompt).first().id,
            result=ComplianceResult.PASS,
            risk_level=RiskLevel.LOW,
            findings=[
                {"rule_key": "gen-01", "severity": "BLOCK", "triggered": False, "mock": True}
            ],
            explanation=f"Demo check ({DEMO_BATCH}): assessed as PASS on text fields; does not guarantee Adobe Stock acceptance.",
        )
    )
    session.add(
        ComplianceCheck(
            check_type=ComplianceCheckType.METADATA_SCREEN,
            result=ComplianceResult.REVIEW,
            risk_level=RiskLevel.MEDIUM,
            findings=[{"rule_key": "mh-05", "severity": "INFO", "triggered": True, "mock": True}],
            explanation=f"Demo check ({DEMO_BATCH}): assessed as REVIEW — category mapping needs human confirmation.",
        )
    )
    counts["compliance_checks"] = 2

    # -- Similarity records: demo scans --
    session.add(
        SimilarityRecord(
            subject_kind="image_idea",
            image_idea_id=image_idea_ids[0],
            compared_cluster_label="clinical AI visualization cluster",
            similarity_score=0.34,
            risk_level=RiskLevel.LOW,
            cluster_sample_count=42,
            differentiators="Authentic clinical setting vs abstract renders.",
            data_provenance=DataProvenance.MOCK,
        )
    )
    counts["similarity_records"] = 1

    # -- Production queue: 8 items across states --
    queue_specs = [
        ("Radiologist AI overlay", image_idea_ids[0], None, ProductionQueueStatus.DISCOVERED, "P1"),
        ("Solar farm golden hour", image_idea_ids[1], None, ProductionQueueStatus.DISCOVERED, "P1"),
        ("Meditation corner", image_idea_ids[2], None, ProductionQueueStatus.IDEA_READY, "P2"),
        (
            "Ergonomic desk profile",
            image_idea_ids[3],
            None,
            ProductionQueueStatus.PROMPT_READY,
            "P2",
        ),
        ("Streetwear flat lay", image_idea_ids[4], None, ProductionQueueStatus.APPROVED, "P2"),
        (
            "Solar install timelapse",
            None,
            video_idea_ids[0],
            ProductionQueueStatus.IN_PRODUCTION,
            "P1",
        ),
        (
            "Meditation breath loop",
            None,
            video_idea_ids[1],
            ProductionQueueStatus.COMPLIANCE_REVIEW,
            "P2",
        ),
        ("Home office tour", None, video_idea_ids[2], ProductionQueueStatus.READY_TO_UPLOAD, "P3"),
    ]
    for i, (title, img_id, vid_id, status, band) in enumerate(queue_specs):
        session.add(
            ProductionQueue(
                opportunity_id=opp_ids[i % len(opp_ids)],
                image_idea_id=img_id,
                video_idea_id=vid_id,
                asset_type=AssetType.VIDEO if vid_id else AssetType.IMAGE,
                title=title,
                status=status,
                priority_band=band,
                target_date=date(2026, 10, 2),
                target_quantity=3,
                produced_count=1 if status in (ProductionQueueStatus.IN_PRODUCTION,) else 0,
                generation_tool="mock-generation-provider",
                notes=f"Demo queue item ({DEMO_BATCH}).",
            )
        )
    counts["production_queue"] = len(queue_specs)

    # -- Assets (2 demo) + metadata drafts (2, one current per asset) --

    asset_ids: list[str] = []
    for i, idea_id in enumerate(image_idea_ids[:2]):
        asset = Asset(
            image_idea_id=idea_id,
            prompt_id=prompt_ids[i] if i < len(prompt_ids) else None,
            asset_type=AssetType.IMAGE,
            title=f"Demo asset {i + 1} ({DEMO_BATCH})",
            storage_uri=f"https://mock.local/assets/demo-asset-{i + 1}.png",
            width_px=6000,
            height_px=3376,
        )
        session.add(asset)
        session.flush()
        asset_ids.append(asset.id)
        av = AssetVersion(
            asset_id=asset.id,
            version_number=1,
            storage_uri=asset.storage_uri,
            file_hash=hashlib.sha256(f"demo-asset-{i + 1}".encode()).hexdigest(),
            mime_type="image/png",
            file_size_bytes=4_200_000,
            width_px=6000,
            height_px=3376,
            change_summary="Demo seed version.",
            created_by="seed",
        )
        session.add(av)
        session.flush()
        asset.current_version_id = av.id
    counts["assets"] = 2
    counts["asset_versions"] = 2

    for i, asset_id in enumerate(asset_ids):
        session.add(
            MetadataRecord(
                asset_id=asset_id,
                version_number=1,
                title=f"Demo metadata title {i + 1} ({DEMO_BATCH})",
                description="A commercial stock photo concept rendered for demonstration. Clean composition, natural light, suitable for editorial and advertising use.",
                keywords=[
                    "commercial",
                    "concept",
                    "modern",
                    "professional",
                    "lifestyle",
                    "business",
                    "technology",
                    "people",
                    "workspace",
                    "creative",
                    "minimal",
                    "editorial",
                ],
                adobe_category="business",
                language="en",
                is_current=True,
                created_by="seed",
            )
        )
    counts["metadata"] = 2

    # -- Notifications: 5 --
    notif_specs = [
        (
            NotificationType.BRIEFING_READY,
            "Morning briefing ready",
            "Your demo daily briefing is ready to review.",
        ),
        (
            NotificationType.OPPORTUNITY_FOUND,
            "New opportunities",
            "6 new demo opportunities crossed the score threshold.",
        ),
        (
            NotificationType.TREND_ALERT,
            "Trend alert: solar imagery",
            "Demo alert: rising demand signal for solar installation imagery.",
        ),
        (
            NotificationType.COMPLIANCE_ALERT,
            "Compliance review needed",
            "1 demo queue item is waiting in COMPLIANCE_REVIEW.",
        ),
        (NotificationType.SYSTEM, "Seed complete", f"Demo data batch {DEMO_BATCH} loaded (MOCK)."),
    ]
    for ntype, title, body in notif_specs:
        session.add(Notification(type=ntype, title=title, body=body, sent_at=now))
    counts["notifications"] = len(notif_specs)

    session.add(Setting(project_id=None, key="seed.demo_batch", value={"value": DEMO_BATCH}))
    session.commit()
    return counts


def run_seed() -> dict:
    """Create tables (if needed) and run all seed steps. Idempotent."""
    import app.models  # noqa: F401 — register all tables on Base.metadata

    Base.metadata.create_all(bind=engine)
    session: Session = SessionLocal()
    try:
        report = {
            "taxonomy": seed_taxonomy(session),
            "trend_sources": seed_trend_sources(session),
            "compliance_rules": seed_compliance_rules(session),
            "settings": seed_settings(session),
            "demo": seed_demo(session),
        }
    finally:
        session.close()
    return report


if __name__ == "__main__":
    import pprint

    pprint.pprint(run_seed())
