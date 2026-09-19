import Shell from "../components/Shell";

type Props = {
  title: string;
  moduleRef: string;
  description: string;
  /** Set true when the page currently shows placeholder/mock data (CONTRACT.md mock convention). */
  demoData?: boolean;
  children?: React.ReactNode;
};

/**
 * "Coming online" shell for Phase-1 placeholder pages.
 * Uses design tokens only (docs/07). Full pages land in later phases.
 */
export default function PageShell({ title, moduleRef, description, demoData, children }: Props) {
  return (
    <Shell>
      <header className="mb-6">
        <div className="mb-1 flex items-center gap-3">
          <h1 className="font-display text-3xl font-semibold text-text-primary">{title}</h1>
          {demoData && (
            <span className="chip-warning rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider">
              Demo data
            </span>
          )}
        </div>
        <p className="text-sm text-text-muted">
          {moduleRef} · Provenance labels appear next to every metric in the full build.
        </p>
      </header>
      <section className="rounded-lg border border-border bg-surface-base p-6">
        <p className="text-sm text-text-secondary">{description}</p>
        <p className="mt-3 text-sm text-text-muted">
          This screen is coming online in a later implementation phase. See CONTRACT.md for the
          backend contract it will consume.
        </p>
        {children}
      </section>
    </Shell>
  );
}
