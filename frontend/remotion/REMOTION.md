# Remotion — programmatic video (StockPulse AI)

Real product capability, not decoration. Two compositions, both in the app's
design language (deep-black stage, champagne-gold accents, telemetry
typography, Didone serif for hero moments, tabular numerals).

## Compositions

| ID | Component | Use |
|----|-----------|-----|
| `ConceptPreview` | `remotion/compositions/ConceptPreview.tsx` | Storyboard-style motion preview for a video concept, built from the concept's own fields (title, concept, category, target duration, shot list with camera moves + durations). Each shot beat animates a previz suggestion of its camera move (push-in, pan, tilt, orbit…) behind kinetic typography. Labeled "PREVIZ — NOT FINAL FOOTAGE" throughout. |
| `DailyBriefing` | `remotion/compositions/DailyBriefing.tsx` | Short MP4 summarizing WHAT TO CREATE TODAY: top production recommendations with count-up scores, confidence bars, personal fit, quantities, plus the day's targets. Estimates stay labeled as estimates. |

Both are 1920×1080 @ 30fps. Durations are computed from input props
(`getConceptPreviewFrames` / `getDailyBriefingFrames`) and wired through
`calculateMetadata`, so the Player and the renderer always agree on length.

## Preview vs render

- **Preview** — `@remotion/player` plays the composition live in the browser.
  No render, no queue, no Chrome needed. Used inline on video idea cards,
  the idea drawer, and anywhere else a preview makes sense.
- **Render** — explicit user action only ("Render video" / "Render briefing"
  buttons). Jobs go through `POST /api/renders` → a small file-backed queue
  (`lib/renders/queue.ts`, state in `remotion/.queue/`):
  `queued → rendering → ready | failed`, polled from the UI, MP4 downloaded
  via `/api/renders/[id]/download`. One render runs at a time. **Nothing ever
  auto-renders in the background.**

## Headless Chrome requirement

Remotion renders video through a headless Chrome/Chromium binary. If it is
not installed, renders fail with a clear error telling you to run:

```bash
cd frontend
npm run remotion:browser   # = remotion browser ensure
```

This downloads a pinned headless-shell build into the Remotion cache
(`~/.cache/remotion`). It is a one-time setup step per machine; the Next.js
app itself never needs it (previews run in the user's own browser).

## API

- `POST /api/renders` — `{ kind: "concept" | "briefing", label: string, props: object }` → `201 { job }`
- `GET /api/renders` — `{ jobs: [...] }`, newest first
- `GET /api/renders/[id]` — `{ job }` (status polling)
- `GET /api/renders/[id]/download` — the finished MP4

Render implementation: the queue spawns the Remotion CLI —
`node node_modules/.bin/remotion render remotion/index.tsx <composition> <out.mp4> --props '{...}'` —
which bundles the composition and drives Chrome. Bundling takes ~30–60s on
first render; subsequent renders reuse the cache.

## Files

```
remotion/
  index.ts                    # Remotion entry (registerRoot) — CLI/studio only, never imported by Next
  REMOTION.md                 # this file
  compositions/
    shared.tsx                # design tokens + kinetic-text / camera-move / telemetry helpers
    ConceptPreview.tsx        # composition + input-props type + frame calculator
    DailyBriefing.tsx         # composition + input-props type + frame calculator
  .queue/                     # runtime state (git-ignored): jobs.json, props, rendered MP4s
components/remotion/
  players.tsx                 # <ConceptPlayer> / <BriefingPlayer> (@remotion/player, ssr:false)
  RenderControls.tsx          # <RenderVideoButton> — enqueue + poll + download
  props.ts                    # domain objects → composition input props
lib/renders/queue.ts          # server-only job queue + CLI spawner
app/api/renders/...           # REST surface above
```

## Notes

- The Remotion entry (`remotion/index.ts`) must never be imported by Next.js
  code — the app imports composition components directly for the Player.
- Composition code uses inline styles only (the Remotion bundle does not
  process the app's Tailwind); colors come from the same palette constants.
- Webfonts are not guaranteed inside headless Chrome, so compositions use
  system serif/sans stacks with the same visual intent.
