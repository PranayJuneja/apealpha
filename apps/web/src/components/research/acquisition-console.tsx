"use client";

import { useEffect, useRef, useState } from "react";

export type SourcePhase = "idle" | "searching" | "live" | "dark";

export type TheaterSource = {
  phase: SourcePhase;
  count?: number;
  detail?: string;
};

export type TheaterState = {
  startedAt: number;
  query: string;
  resolved: { ticker: string; company: string; confidence: number } | null;
  classified: { phase: string; stance: string; gap: number } | null;
  sources: Record<string, TheaterSource>;
  log: { at: number; tag: string; line: string }[];
};

export function emptyTheater(query: string): TheaterState {
  return { startedAt: Date.now(), query, resolved: null, classified: null, sources: {}, log: [] };
}

/** Display order and copy for each acquisition leg the engine reports. */
const LEGS: {
  key: string;
  label: string;
  channel: string;
  searching: (q: string) => string[];
}[] = [
  {
    key: "resolve",
    label: "Listing resolution",
    channel: "SEC universe / venue index",
    searching: (q) => [`matching “${q}” against the listing universe…`],
  },
  {
    key: "social",
    label: "Investor posts",
    channel: "WebCMD · X + Reddit",
    searching: (q) => [
      `querying x.com for $${q}…`,
      `scanning r/stocks, r/wallstreetbets…`,
      "counting distinct authors…",
      "separating analysis from noise…",
    ],
  },
  {
    key: "news_current",
    label: "Current news",
    channel: "WebCMD · Google + Yahoo",
    searching: (q) => [
      `pulling Google News for ${q}…`,
      "reading Yahoo Finance coverage…",
      "dropping syndicated duplicates…",
    ],
  },
  {
    key: "news_archive",
    label: "News archive",
    channel: "GDELT global index",
    searching: () => ["sweeping the 7-day global archive…", "matching outlets and languages…"],
  },
  {
    key: "news_baseline",
    label: "Volume baseline",
    channel: "GDELT timeline",
    searching: () => ["building the coverage baseline…"],
  },
  {
    key: "filings",
    label: "Filings",
    channel: "SEC EDGAR / NSE",
    searching: () => ["checking the latest filings…", "reading acceptance timestamps…"],
  },
  {
    key: "price",
    label: "Price & volume",
    channel: "Market bars · 180d",
    searching: (q) => [`loading 180 days of ${q} bars…`, "computing relative volume…"],
  },
  {
    key: "analysis",
    label: "AI interpretation",
    channel: "GPT-5.6 Luna",
    searching: () => [
      "reading the evidence set…",
      "scoring sentiment from investor language…",
      "writing the plain-English read…",
    ],
  },
];

function useClock(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 120);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

function stamp(ms: number): string {
  const seconds = Math.max(0, ms) / 1000;
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(Math.floor(seconds % 60)).padStart(2, "0");
  return `${mm}:${ss}.${String(Math.floor((seconds % 1) * 10))}`;
}

function ActivityLine({ lines, tick }: { lines: string[]; tick: number }) {
  const line = lines[Math.floor(tick / 2600) % lines.length];
  return (
    <p className="theater-activity mt-2 truncate text-[11px] leading-4 text-white/55">{line}</p>
  );
}

function Dot({ phase }: { phase: SourcePhase }) {
  const color =
    phase === "live"
      ? "#39d98a"
      : phase === "dark"
        ? "#f0a48a"
        : phase === "searching"
          ? "var(--solar)"
          : "rgba(255,255,255,.25)";
  return (
    <span
      aria-hidden
      className={`inline-block size-2 shrink-0 rounded-full ${phase === "searching" ? "theater-pulse" : ""}`}
      style={{ background: color }}
    />
  );
}

/**
 * The live acquisition console: one tile per source leg, driven by real
 * progress events from the engine — nothing here is a canned animation.
 */
export function AcquisitionConsole({ state, done }: { state: TheaterState; done: boolean }) {
  const now = useClock(!done);
  const elapsed = (done ? state.log[state.log.length - 1]?.at ?? 0 : now - state.startedAt);
  const logRef = useRef<HTMLDivElement>(null);
  const ticker = state.resolved?.ticker ?? state.query.toUpperCase();

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [state.log.length]);

  const liveCount = Object.values(state.sources).filter((s) => s.phase === "live").length;

  return (
    <section
      aria-label="Live source acquisition"
      className="mt-10 overflow-hidden rounded-[1.5rem] border border-line-strong bg-ink text-white shadow-[0_24px_70px_rgba(17,24,20,.16)]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/15 px-6 py-4 md:px-8">
        <p className="eyebrow flex items-center gap-2 text-white/60">
          <span className={`size-2 rounded-full ${done ? "bg-[#39d98a]" : "theater-pulse bg-[var(--solar)]"}`} />
          {done ? "Acquisition complete" : "Live acquisition"} · {state.resolved
            ? `${state.resolved.ticker} — ${state.resolved.company}`
            : `resolving “${state.query}”`}
        </p>
        <p className="tabular text-xs text-white/55">
          T+{stamp(elapsed)} · {liveCount}/{LEGS.length} legs answered
        </p>
      </div>

      <div className="grid gap-px bg-white/12 sm:grid-cols-2 lg:grid-cols-4">
        {LEGS.map((leg) => {
          const source = state.sources[leg.key] ?? { phase: "idle" as const };
          return (
            <div key={leg.key} className="bg-[#161f1a] p-4 md:p-5">
              <p className="flex items-center gap-2">
                <Dot phase={source.phase} />
                <span className="text-[13px] font-bold leading-4">{leg.label}</span>
              </p>
              <p className="eyebrow mt-1.5 text-white/35">{leg.channel}</p>
              {source.phase === "searching" ? (
                <ActivityLine lines={leg.searching(ticker)} tick={now - state.startedAt} />
              ) : source.phase === "live" ? (
                <p className="theater-activity mt-2 text-[11px] leading-4 text-[#8fe6bc]">
                  {source.count !== undefined && source.count > 0
                    ? `${source.count} item${source.count === 1 ? "" : "s"} captured`
                    : source.detail || "answered"}
                </p>
              ) : source.phase === "dark" ? (
                <p className="mt-2 text-[11px] leading-4 text-[#f0a48a]">
                  no answer — continuing without it
                </p>
              ) : (
                <p className="mt-2 text-[11px] leading-4 text-white/30">queued</p>
              )}
            </div>
          );
        })}
      </div>

      <div
        ref={logRef}
        className="tabular max-h-40 overflow-y-auto border-t border-white/15 px-6 py-4 text-[11px] leading-5 text-white/60 md:px-8"
        aria-live="polite"
      >
        {state.log.length === 0 ? (
          <p className="text-white/40">Opening source channels…</p>
        ) : (
          state.log.map((entry, index) => (
            <p key={index} className="whitespace-nowrap">
              <span className="text-white/35">T+{stamp(entry.at)}</span>{" "}
              <span className="font-semibold text-white/80">{entry.tag.padEnd(9, " ")}</span>{" "}
              {entry.line}
            </p>
          ))
        )}
      </div>
    </section>
  );
}
