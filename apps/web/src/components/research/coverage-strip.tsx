import type { SourceStatus } from "@/types/research";

const TONE = {
  live: "var(--up)",
  degraded: "var(--solar)",
  unavailable: "var(--down)",
} as const;

const LABEL = {
  reddit: "Reddit",
  news: "News",
  price: "Price",
  filings: "Filings",
} as Record<string, string>;

/**
 * What the engine could actually see on this run. A signal computed with a dark
 * source is a different object from one computed with all four, so coverage is
 * shown next to the numbers rather than buried in a footnote.
 */
export function CoverageStrip({ coverage }: { coverage: SourceStatus[] }) {
  return (
    <ul className="m-0 grid list-none gap-px border border-line bg-line p-0 sm:grid-cols-2 lg:grid-cols-4">
      {coverage.map((status) => (
        <li key={status.source} className="bg-white p-5">
          <p className="flex items-center gap-2 text-[13px] font-bold text-ink">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: TONE[status.status] }}
            />
            {LABEL[status.source] ?? status.source}
          </p>
          <p className="eyebrow mt-3 text-muted">{status.status}</p>
          <p className="mt-2 text-xs leading-5 text-muted">
            {status.detail || `${status.events} observations via ${status.provider || "—"}`}
          </p>
        </li>
      ))}
    </ul>
  );
}
