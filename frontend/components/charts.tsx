"use client";
/**
 * Chart primitives — precision-instrument restyle (2026-09-19).
 * Dark stage styling enforced here so charts cannot drift: hairline grid,
 * warm-gray ticks, tooltip on elevated surface. Rule: monochrome muted by
 * default, one gold series max. No blue anywhere in the system.
 */
import {
  ResponsiveContainer,
  LineChart as RLine,
  Line,
  BarChart as RBar,
  Bar,
  AreaChart as RArea,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  Cell,
} from "recharts";
import {
  GOLD,
  GOLD_BRIGHT,
  GRID as PAL_GRID,
  MUTED_SERIES as PAL_MUTED,
  RACING_RED,
  STEEL,
  SUCCESS,
  SURFACE_ELEVATED,
  TICK as PAL_TICK,
  WARNING,
} from "./palette";

export const GRID = PAL_GRID;
export const TICK = PAL_TICK;
export const MUTED_SERIES = PAL_MUTED;
export const ACCENT_SERIES = GOLD;
export const INFO_SERIES = STEEL;
export const SUCCESS_SERIES = SUCCESS;
export const DANGER_SERIES = RACING_RED;
export const WARNING_SERIES = WARNING;

function ChartTooltip({ active, payload, label, formatter }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="depth-2 rounded-lg border border-border px-3 py-2 text-xs"
      style={{ background: SURFACE_ELEVATED }}
    >
      <p className="tnum mb-1 font-bold text-text-primary">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="flex items-center gap-2 text-text-secondary">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color ?? p.payload?.fill ?? MUTED_SERIES }} />
          {p.name}:{" "}
          <span className="tnum font-bold text-text-primary">
            {formatter ? formatter(p.value, p.name) : p.value}
          </span>
        </p>
      ))}
    </div>
  );
}

export interface SeriesDef {
  key: string;
  name: string;
  color?: string;
  accent?: boolean;
}

const baseAxis = {
  tick: { fill: TICK, fontSize: 11 },
  axisLine: { stroke: GRID },
  tickLine: false as const,
};

export function TrendLineChart({
  data,
  series,
  height = 220,
  yDomain,
  reference,
  formatter,
  ariaLabel,
}: {
  data: Record<string, unknown>[];
  series: SeriesDef[];
  height?: number;
  yDomain?: [number, number];
  reference?: { y: number; label: string };
  formatter?: (v: number, name: string) => string;
  ariaLabel: string;
}) {
  if (!data.length)
    return (
      <p className="py-8 text-center text-xs text-text-muted" role="img" aria-label={ariaLabel}>
        No data points yet.
      </p>
    );
  if (data.length === 1)
    return (
      <p className="py-8 text-center text-xs text-text-muted" role="img" aria-label={ariaLabel}>
        Single data point — a line needs more history.
      </p>
    );
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RLine data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...baseAxis} minTickGap={24} />
          <YAxis {...baseAxis} domain={yDomain ?? ["auto", "auto"]} width={44} tickFormatter={(v: number) => String(v)} />
          <Tooltip content={<ChartTooltip formatter={formatter} />} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: TICK }} />}
          {reference && (
            <ReferenceLine y={reference.y} stroke={TICK} strokeDasharray="4 4" label={{ value: reference.label, fill: TICK, fontSize: 10 }} />
          )}
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color ?? (s.accent ? GOLD : MUTED_SERIES)}
              strokeWidth={s.accent ? 2.5 : 1.75}
              dot={false}
              activeDot={{ r: 3, stroke: s.color ?? (s.accent ? GOLD : MUTED_SERIES) }}
              connectNulls={false}
            />
          ))}
        </RLine>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendBarChart({
  data,
  series,
  height = 220,
  formatter,
  ariaLabel,
  horizontal,
}: {
  data: Record<string, unknown>[];
  series: SeriesDef[];
  height?: number;
  formatter?: (v: number, name: string) => string;
  ariaLabel: string;
  horizontal?: boolean;
}) {
  if (!data.length)
    return (
      <p className="py-8 text-center text-xs text-text-muted" role="img" aria-label={ariaLabel}>
        No data points yet.
      </p>
    );
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RBar data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }} layout={horizontal ? "vertical" : "horizontal"}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          {horizontal ? (
            <>
              <XAxis type="number" {...baseAxis} />
              <YAxis type="category" dataKey="label" {...baseAxis} width={110} />
            </>
          ) : (
            <>
              <XAxis dataKey="label" {...baseAxis} minTickGap={16} />
              <YAxis {...baseAxis} width={44} />
            </>
          )}
          <Tooltip content={<ChartTooltip formatter={formatter} />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: TICK }} />}
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={s.color ?? (s.accent ? GOLD : MUTED_SERIES)}
              radius={[3, 3, 0, 0]}
              maxBarSize={28}
            />
          ))}
        </RBar>
      </ResponsiveContainer>
    </div>
  );
}

export function ConfidenceAreaChart({
  data,
  height = 220,
  ariaLabel,
}: {
  data: { label: string; value: number; low: number; high: number }[];
  height?: number;
  ariaLabel: string;
}) {
  if (!data.length)
    return (
      <p className="py-8 text-center text-xs text-text-muted" role="img" aria-label={ariaLabel}>
        No data points yet.
      </p>
    );
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RArea data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...baseAxis} minTickGap={24} />
          <YAxis {...baseAxis} width={44} />
          <Tooltip content={<ChartTooltip />} />
          <Area type="monotone" dataKey="high" name="Upper bound" stroke="none" fill={GOLD} fillOpacity={0.14} />
          <Area type="monotone" dataKey="low" name="Lower bound" stroke="none" fill={SURFACE_ELEVATED} fillOpacity={1} />
          <Area type="monotone" dataKey="value" name="Estimate" stroke={GOLD} strokeWidth={2} fill={GOLD} fillOpacity={0.08} dot={false} />
        </RArea>
      </ResponsiveContainer>
    </div>
  );
}

/** Compact horizontal bars for lists (e.g., category demand). */
export function MiniBars({
  rows,
  max,
}: {
  rows: { label: string; value: number; color?: string; suffix?: string }[];
  max?: number;
}) {
  const m = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2.5">
          <span className="w-32 shrink-0 truncate text-xs text-text-secondary" title={r.label}>
            {r.label}
          </span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: "#242428" }} aria-hidden>
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.min(100, (r.value / m) * 100)}%`, background: r.color ?? MUTED_SERIES }}
            />
          </span>
          <span className="tnum w-14 shrink-0 text-right text-xs font-bold text-text-primary">
            {Math.round(r.value)}{r.suffix ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Distribution bars (score histogram). */
export function Histogram({ bins, height = 160, ariaLabel }: { bins: { label: string; count: number; fill?: string }[]; height?: number; ariaLabel: string }) {
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RBar data={bins} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...baseAxis} />
          <YAxis {...baseAxis} allowDecimals={false} width={36} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Bar dataKey="count" name="Items" radius={[3, 3, 0, 0]} maxBarSize={36}>
            {bins.map((b, i) => (
              <Cell key={i} fill={b.fill ?? MUTED_SERIES} />
            ))}
          </Bar>
        </RBar>
      </ResponsiveContainer>
    </div>
  );
}

// Re-export palette tokens for any page-level canvas/SVG work.
export { GOLD as GOLD_C, GOLD_BRIGHT as GOLD_BRIGHT_C };
