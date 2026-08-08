import { minutesBetween, offsetLabel, sourceLabel, utcDate, utcTime } from "@/lib/format";
import type { SourceEvent } from "@/types/research";

const INITIAL_ROWS = 24;

function eventSourceLabel(event: SourceEvent): string {
  if (event.source_type === "social") return "REDDIT";
  if (event.source_type === "news") {
    const provider = String(event.metadata.provider ?? "").toLowerCase();
    if (provider.includes("google")) return "GOOGLE";
    if (provider.includes("yahoo")) return "YAHOO";
    if (provider.includes("gdelt")) return "GDELT";
  }
  return sourceLabel(event.source_type);
}

function EventRows({ events, first }: { events: SourceEvent[]; first: string }) {
  return events.map((event) => (
    <li key={event.event_id} className="border-b border-line">
      <a
        href={event.source_url}
        target="_blank"
        rel="noreferrer noopener"
        className="grid gap-2 py-5 transition-colors hover:bg-white/70 sm:grid-cols-[7rem_1fr_auto] sm:items-baseline sm:gap-6 sm:px-2"
      >
        <span className={`source-chip source-${event.source_type}`}>
          {eventSourceLabel(event)}
        </span>
        <span className="text-[15px] leading-6 text-ink">{event.title}</span>
        <span className="tabular text-right text-xs text-muted">
          {utcDate(event.source_created_at)} {utcTime(event.source_created_at)}
          <span className="mt-1 block text-[10px] tracking-[0.1em] text-muted">
            {offsetLabel(minutesBetween(first, event.source_created_at))}
          </span>
        </span>
      </a>
    </li>
  ));
}

export function EvidenceLedger({ events }: { events: SourceEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm leading-6 text-muted">
        No observations were retrieved for this security in the current window.
      </p>
    );
  }

  const first = events[0].source_created_at;
  const splitAt = Math.max(0, events.length - INITIAL_ROWS);
  const earlier = events.slice(0, splitAt);
  const recent = events.slice(splitAt);

  return (
    <div className="border-t border-line">
      {earlier.length > 0 ? (
        <details className="border-b border-line bg-white/55">
          <summary className="cursor-pointer px-2 py-5 text-sm font-bold text-ink marker:text-[var(--blue)]">
            Show {earlier.length} earlier observations
          </summary>
          <ol className="m-0 list-none border-t border-line p-0">
            <EventRows events={earlier} first={first} />
          </ol>
        </details>
      ) : null}
      <ol className="m-0 list-none p-0">
        <EventRows events={recent} first={first} />
      </ol>
    </div>
  );
}
