"use client";
/**
 * Settings (docs/05 screen 19) — single-user: capacity, scoring thresholds,
 * notifications, data & privacy, API connection.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Database, Gauge, SlidersHorizontal } from "lucide-react";
import {
  Button,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  WhyThis,
} from "../../components/ui";
import { useToast } from "../../components/toast";
import { useSettings, useSettingsMutations } from "../../hooks/useApi";

type SettingsMap = Record<string, unknown>;

const num = (v: unknown, fallback: number) => (typeof v === "number" && Number.isFinite(v) ? v : fallback);
const bool = (v: unknown, fallback: boolean) => (typeof v === "boolean" ? v : fallback);

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Settings"
        description="Single-user workspace. Changes apply immediately and are recorded."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <CapacitySection />
        <ThresholdsSection />
        <NotificationsSection />
        <DataSection />
      </div>
    </div>
  );
}

function useSettingFields() {
  const settings = useSettings();
  const muts = useSettingsMutations();
  const { toast } = useToast();
  const [draft, setDraft] = useState<SettingsMap>({});
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (settings.data && !initialized) {
      setDraft({ ...settings.data });
      setInitialized(true);
    }
  }, [settings.data, initialized]);

  const get = <T,>(key: string, fallback: T): T => (draft[key] === undefined ? fallback : (draft[key] as T));
  const set = (key: string, value: unknown) => setDraft((d) => ({ ...d, [key]: value }));

  const save = (keys: string[]) => {
    const patch: SettingsMap = {};
    for (const k of keys) patch[k] = draft[k];
    muts.mutate(patch, {
      onSuccess: () => toast({ title: "Settings saved", tone: "success" }),
      onError: (e) => toast({ title: "Save failed", description: e.message, tone: "danger" }),
    });
  };

  return { settings, muts, get, set, save };
}

function CapacitySection() {
  const { settings, muts, get, set, save } = useSettingFields();
  const weekly = num(get("planner.weekly_capacity", 0), 0);
  return (
    <Panel title={<span className="flex items-center gap-2"><Gauge size={14} className="text-accent-primary" aria-hidden /> Capacity</span>}
      action={<Button size="sm" variant="primary" loading={muts.isPending} onClick={() => save(["planner.weekly_capacity"])}>Save</Button>}>
      <QueryView query={settings} loading={<Skeleton className="h-24" />} empty={<EmptyState compact title="No settings" />} errorTitle="Settings unavailable">
        {() => (
          <div className="space-y-3">
            <Field label="Weekly submission capacity" hint="Assets you can realistically produce and upload per week. Used by the briefing and queue planning.">
              <Input type="number" min={0} value={weekly} onChange={(e) => set("planner.weekly_capacity", Number(e.target.value))} data-testid="settings-weekly-capacity" />
            </Field>
            <p className="text-xs text-text-muted">Also editable in the <Link href="/planner" className="text-accent-secondary hover:underline">Planner</Link>.</p>
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

function ThresholdsSection() {
  const { settings, muts, get, set, save } = useSettingFields();
  const score = num(get("scoring.min_opportunity_score", 55), 55);
  const conf = num(get("scoring.min_confidence", 0.5), 0.5);
  const simReview = num(get("similarity.review_threshold", 0.6), 0.6);
  const simHigh = num(get("similarity.high_risk_threshold", 0.8), 0.8);

  return (
    <Panel title={<span className="flex items-center gap-2"><SlidersHorizontal size={14} className="text-accent-primary" aria-hidden /> Scoring & screening thresholds</span>}
      action={<Button size="sm" variant="primary" loading={muts.isPending} onClick={() => save(["scoring.min_opportunity_score", "scoring.min_confidence", "similarity.review_threshold", "similarity.high_risk_threshold"])}>Save</Button>}>
      <QueryView query={settings} loading={<Skeleton className="h-32" />} empty={<EmptyState compact title="No settings" />} errorTitle="Settings unavailable">
        {() => (
          <div className="space-y-4">
            <Field label={`Minimum opportunity score · ${score}`} hint="Below this, items are not actionable and cannot be approved.">
              <input type="range" min={0} max={100} step={5} value={score} onChange={(e) => set("scoring.min_opportunity_score", Number(e.target.value))} className="w-full" aria-label="Minimum opportunity score" />
            </Field>
            <Field label={`Minimum confidence · ${Math.round(conf * 100)}%`} hint="Below this, outputs are marked degraded.">
              <input type="range" min={0} max={1} step={0.05} value={conf} onChange={(e) => set("scoring.min_confidence", Number(e.target.value))} className="w-full" aria-label="Minimum confidence" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Similarity review ≥">
                <Input type="number" min={0} max={1} step={0.05} value={simReview} onChange={(e) => set("similarity.review_threshold", Number(e.target.value))} />
              </Field>
              <Field label="Similarity high-risk ≥">
                <Input type="number" min={0} max={1} step={0.05} value={simHigh} onChange={(e) => set("similarity.high_risk_threshold", Number(e.target.value))} />
              </Field>
            </div>
            <WhyThis label="What these gates do">
              <p>The actionability bar (score + confidence) and similarity thresholds are enforced at GATE-02/05/07. Lowering them widens the funnel but admits weaker evidence — the UI always shows what cleared and what didn’t.</p>
            </WhyThis>
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

function NotificationsSection() {
  const { settings, muts, get, set, save } = useSettingFields();
  const briefReady = bool(get("notifications.daily_briefing_ready", true), true);
  const complianceBlocked = bool(get("notifications.compliance_blocked", true), true);
  const runFailed = bool(get("notifications.agent_run_failed", true), true);
  const capacityWarn = bool(get("notifications.capacity_warning", true), true);

  const rows = [
    { key: "notifications.daily_briefing_ready", label: "Daily briefing ready", value: briefReady, hint: "When the morning pipeline run completes." },
    { key: "notifications.compliance_blocked", label: "Compliance blocked an item", value: complianceBlocked, hint: "HIGH RISK or REVIEW verdicts." },
    { key: "notifications.agent_run_failed", label: "Agent run failed", value: runFailed, hint: "Any supervised run that ends in error." },
    { key: "notifications.capacity_warning", label: "Capacity warnings", value: capacityWarn, hint: "When planned work exceeds weekly capacity." },
  ];

  return (
    <Panel title={<span className="flex items-center gap-2"><Bell size={14} className="text-accent-primary" aria-hidden /> Notifications</span>}
      action={<Button size="sm" variant="primary" loading={muts.isPending} onClick={() => save(rows.map((r) => r.key))}>Save</Button>}>
      <QueryView query={settings} loading={<Skeleton className="h-32" />} empty={<EmptyState compact title="No settings" />} errorTitle="Settings unavailable">
        {() => (
          <ul className="space-y-2.5">
            {rows.map((r) => (
              <li key={r.key} className="flex items-center gap-3">
                <input type="checkbox" id={r.key} checked={r.value} onChange={(e) => set(r.key, e.target.checked)} className="h-4 w-4 accent-[#FF5C35]" />
                <div>
                  <label htmlFor={r.key} className="cursor-pointer text-[13px] font-medium text-text-primary">{r.label}</label>
                  <p className="text-[11px] text-text-muted">{r.hint}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function DataSection() {
  const { toast } = useToast();
  return (
    <Panel title={<span className="flex items-center gap-2"><Database size={14} className="text-accent-primary" aria-hidden /> Data & API</span>}>
      <div className="space-y-3 text-[13px]">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-medium text-text-primary">API connection</p>
            <p className="text-xs text-text-muted">Base URL is configured via the NEXT_PUBLIC_API_URL environment variable.</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => toast({ title: "Connection check", description: "Open any page — failed requests surface as retryable error cards with the trace ID.", tone: "info" })}>
            How to verify
          </Button>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-medium text-text-primary">Export workspace</p>
            <p className="text-xs text-text-muted">Download your records as CSV from Analytics.</p>
          </div>
          <Link href="/analytics"><Button size="sm" variant="outline">Go to export</Button></Link>
        </div>
        <div className="rounded-md border border-border bg-bg-secondary p-3 text-xs text-text-muted">
          Demo data is always labeled <strong className="text-text-primary">“Demo data”</strong>. Records with
          provenance MOCK are placeholders — they are never presented as real Adobe Stock figures.
        </div>
      </div>
    </Panel>
  );
}
