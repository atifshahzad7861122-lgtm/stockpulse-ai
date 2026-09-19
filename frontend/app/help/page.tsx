"use client";
/**
 * Help — how StockPulse AI works: pipeline, provenance, scoring, queue
 * states/transitions, gates, keyboard shortcuts, FAQ.
 */
import { useState } from "react";
import { BookOpen, ChevronDown, Keyboard } from "lucide-react";
import { PageHeader, Panel, WhyThis, cx } from "../../components/ui";
import { ProvenanceBadge } from "../../components/scores";
import { ALL_STATES, stateLabel } from "../../lib/transitions";

export default function HelpPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Help"
        description="How StockPulse AI works — the pipeline, the scores, the labels, and the rules it will not break."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="The pipeline">
          <ol className="space-y-2.5 text-[13px]">
            {[
              ["1 · Trend engine", "Aggregates signals across sources into 7-day trend scores per category and micro-niche."],
              ["2 · Opportunity analysis", "Ranks where the best opportunity is right now — opportunity, commercial, and saturation scores with confidence."],
              ["3 · Your ideas", "You write the concepts. The pipeline refines wording, checks originality, and drafts shot lists."],
              ["4 · Prompt Studio", "Firefly-ready prompts with keyword and SEO support, scored and compliance-screened."],
              ["5 · Gates", "Compliance, similarity, and human approval gates decide what may enter the production queue."],
              ["6 · Production queue", "Ideas move through 13 gated states toward manual submission to Adobe Stock."],
              ["7 · Planner & analytics", "Capacity planning, submission calendar, and honest performance numbers."],
            ].map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="shrink-0 font-display font-semibold text-accent-primary">{t.split(" · ")[0]}</span>
                <div><p className="font-semibold text-text-primary">{t.split(" · ")[1]}</p><p className="text-text-secondary">{d}</p></div>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel title="Provenance labels">
          <div className="space-y-3 text-[13px] text-text-secondary">
            <p>Every number carries its source. Two labels matter:</p>
            <div className="flex items-center gap-2"><ProvenanceBadge provenance="VERIFIED" /><span><strong className="text-text-primary">Live</strong> — computed from connected sources.</span></div>
            <div className="flex items-center gap-2"><ProvenanceBadge mock /><span><strong className="text-text-primary">Demo data</strong> — an illustrative placeholder. Never treat it as real Adobe Stock data.</span></div>
            <p>Demo records are also marked <code className="rounded bg-bg-secondary px-1 font-mono text-[11px]">provenance: “MOCK”</code> in API payloads. We never invent sales figures or imply guaranteed Adobe acceptance.</p>
          </div>
        </Panel>
      </div>

      <Panel title="How scores are computed">
        <div className="grid gap-4 md:grid-cols-2 text-[13px]">
          <Formula name="Trend score (TS)" formula="0.30·TV + 0.25·SG + 0.20·KM + 0.15·EG + 0.10·SE" note="How hot a trend is: trend velocity, signal growth, keyword momentum, engagement, source breadth." />
          <Formula name="Opportunity score (OS)" formula="0.35·TS + 0.25·CR + 0.20·CD + 0.20·(100 − saturation)" note="Should we act. Actionable at ≥ 55 with confidence ≥ 50%." />
          <Formula name="Commercial score (CPS)" formula="0.35·CR + 0.25·CD + 0.15·SE + 0.15·(100 − CO) + 0.10·format fit" note="How sellable a concept is." />
          <Formula name="Saturation (CSS)" formula="100 × (0.55·CS + 0.45·CO)" note="0–30 Open (≤ 8 assets) · 31–55 Moderate (≤ 5) · 56–75 Competitive (≤ 3) · 76–100 Saturated (≤ 2)." />
          <Formula name="Prediction confidence (PC)" formula="0.30·coverage + 0.25·freshness + 0.20·sources + 0.15·stability + 0.10·your agreement" note="Below 50%, outputs are marked degraded. All predictions are estimates, never guarantees." />
          <Formula name="Priority" formula="0.70·OS + 0.30·PC" note="Queue ordering: opportunity score weighted by confidence." />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Queue states & transitions">
          <p className="mb-3 text-[13px] text-text-secondary">13 states, only the documented transitions T01–T29 are legal. Illegal jumps are rejected by the backend.</p>
          <div className="flex flex-wrap gap-1.5">
            {ALL_STATES.map((s) => (
              <span key={s} className="rounded bg-surface-elevated px-2 py-1 text-[11px] text-text-secondary">{stateLabel(s)}</span>
            ))}
          </div>
          <WhyThis label="Why so strict">
            <p>Strict transitions keep the pipeline auditable: nothing can skip screening, approval, or submission recording. The Move dialog only offers legal targets.</p>
          </WhyThis>
        </Panel>

        <Panel title="The gates">
          <ul className="space-y-2.5 text-[13px] text-text-secondary">
            <Gate id="GATE-02" text="Ideas are human-created. The pipeline refines — it never invents concepts on its own." />
            <Gate id="GATE-04" text="Compliance PASS (or reviewed approval) is required before queueing. HIGH RISK blocks submission." />
            <Gate id="GATE-05" text="Similarity ≥ 80% blocks queueing until the concept is differentiated or risk is accepted with a reason." />
            <Gate id="GATE-06" text="Prompts need compliance screening before entering the queue." />
            <Gate id="GATE-07" text="Submission records your manual upload. StockPulse never uploads to Adobe on your behalf." />
          </ul>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={<span className="flex items-center gap-2"><Keyboard size={14} aria-hidden /> Keyboard shortcuts</span>}>
          <ul className="space-y-2 text-[13px] text-text-secondary">
            <Shortcut keys={["⌘/Ctrl", "K"]} text="Command palette — jump anywhere, run actions" />
            <Shortcut keys={["/"]} text="Focus search (on pages with a search field)" />
            <Shortcut keys={["Esc"]} text="Close drawer / dialog" />
          </ul>
        </Panel>

        <Panel title={<span className="flex items-center gap-2"><BookOpen size={14} aria-hidden /> FAQ</span>}>
          <div className="space-y-1">
            <Faq q="Does StockPulse upload to Adobe for me?" a="No. Submission actions record your manual upload — the ID Adobe gives you, your notes. Nothing leaves this app toward Adobe automatically." />
            <Faq q="Why is an opportunity 'not actionable'?" a="It sits below the action bar: opportunity score ≥ 55 and confidence ≥ 50%. Approving below the bar would be acting on insufficient evidence, so approval is disabled with the reason shown." />
            <Faq q="What does 'Demo data' mean?" a="The record is an illustrative placeholder from the demo provider, not a live source. Figures may look realistic but must not drive real decisions." />
            <Faq q="Can I change the thresholds?" a="Yes — Settings → Scoring & screening thresholds. The gates re-evaluate against the new values." />
            <Faq q="A panel shows an error. What now?" a="Panels fail independently. Use the retry button; the error card carries a trace ID for support. Other panels keep working." />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Formula({ name, formula, note }: { name: string; formula: string; note: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="font-semibold text-text-primary">{name}</p>
      <p className="mt-1 font-mono text-[11.5px] text-accent-secondary">{formula}</p>
      <p className="mt-1.5 text-text-secondary">{note}</p>
    </div>
  );
}

function Gate({ id, text }: { id: string; text: string }) {
  return (
    <li className="flex gap-2.5">
      <span className="shrink-0 rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[11px] text-accent-primary">{id}</span>
      <span>{text}</span>
    </li>
  );
}

function Shortcut({ keys, text }: { keys: string[]; text: string }) {
  return (
    <li className="flex items-center gap-2.5">
      <span className="flex gap-1">
        {keys.map((k) => <kbd key={k} className="rounded border border-border bg-bg-secondary px-1.5 py-0.5 font-mono text-[11px] text-text-primary">{k}</kbd>)}
      </span>
      <span>{text}</span>
    </li>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-border">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-[13px] font-medium text-text-primary">
        {q}
        <ChevronDown size={14} className={cx("ml-auto shrink-0 text-text-muted transition-transform", !open && "-rotate-90")} aria-hidden />
      </button>
      {open && <p className="px-3 pb-3 text-[13px] text-text-secondary">{a}</p>}
    </div>
  );
}
