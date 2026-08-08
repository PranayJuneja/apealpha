"use client";

import { useEffect, useState } from "react";
import { minutesBetween, offsetLabel, sourceLabel, utcTime } from "@/lib/format";
import type { SourceEvent } from "@/types/research";

/**
 * "Who knew first" — every observation on one timeline, in the order it became
 * knowable. Replaying it is the fastest way to see whether the crowd led the
 * tape or followed it.
 */
export function CausalTape({ events }: { events: SourceEvent[] }) {
  // The evidence ledger keeps every record. This tape answers a narrower
  // causal question, so it shows only the first knowable observation from each
  // independent layer; otherwise dozens of news articles overlap visually and
  // the "next source" can accidentally be another article from the same feed.
  const sourceFirsts = [...events]
    .sort((a, b) => Date.parse(a.source_created_at) - Date.parse(b.source_created_at))
    .filter(
      (event, index, sorted) =>
        sorted.findIndex((candidate) => candidate.source_type === event.source_type) === index,
    );
  const [step, setStep] = useState(sourceFirsts.length - 1);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setStep(sourceFirsts.length - 1);
    setPlaying(false);
  }, [events, sourceFirsts.length]);

  useEffect(() => {
    if (!playing) return;
    if (step >= sourceFirsts.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setStep((current) => current + 1), 700);
    return () => window.clearTimeout(timer);
  }, [playing, step, sourceFirsts.length]);

  if (sourceFirsts.length < 2) {
    return (
      <p className="text-sm leading-6 text-muted">
        A causal comparison needs at least two independent source layers. Only {sourceFirsts.length}
        reported for this security.
      </p>
    );
  }

  const first = sourceFirsts[0].source_created_at;
  const last = sourceFirsts[sourceFirsts.length - 1].source_created_at;
  const span = Math.max(1, new Date(last).getTime() - new Date(first).getTime());

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow text-muted">How the story unfolded — UTC</p>
          <h3 className="h-display mt-3 text-[clamp(1.8rem,3vw,2.6rem)]">What moved first?</h3>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            className="button-secondary"
            onClick={() => {
              if (step >= sourceFirsts.length - 1) {
                setStep(0);
                setPlaying(true);
              } else {
                setPlaying((value) => !value);
              }
            }}
          >
            {step >= sourceFirsts.length - 1 ? "Replay" : playing ? "Pause" : "Play"}
          </button>
          <input
            aria-label="Replay position"
            type="range"
            min={0}
            max={sourceFirsts.length - 1}
            value={step}
            onChange={(event) => {
              setStep(Number(event.target.value));
              setPlaying(false);
            }}
            className="w-40 accent-[var(--blue)]"
          />
        </div>
      </div>

      <div className="tape-track mt-10">
        <div className="tape-rule" />
        {sourceFirsts.map((event, index) => {
          const offset =
            ((new Date(event.source_created_at).getTime() - new Date(first).getTime()) / span) * 100;
          return (
            <div
              key={event.event_id}
              className={`tape-node source-${event.source_type} ${index <= step ? "is-visible" : ""}`}
              style={{ left: `${Math.min(96, offset)}%` }}
            >
              <span className="tape-dot" />
              <p className="eyebrow mt-3 text-ink">{sourceLabel(event.source_type)}</p>
              <p className="tabular mt-1 text-[11px] text-muted">{utcTime(event.source_created_at)}</p>
              {index === 0 ? <p className="eyebrow mt-1 text-[10px] text-volt">First</p> : null}
            </div>
          );
        })}
      </div>

      <p className="mt-6 border-t border-line pt-4 text-sm leading-6 text-muted">
        {sourceLabel(sourceFirsts[0].source_type)} moved first.{" "}
        {sourceFirsts.length > 1
          ? `The next independent source appeared ${offsetLabel(
              minutesBetween(sourceFirsts[0].source_created_at, sourceFirsts[1].source_created_at),
            ).toLowerCase()}.`
          : null}
      </p>
    </div>
  );
}
