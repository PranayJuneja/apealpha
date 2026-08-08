"use client";

import { useRef, useState } from "react";
import { markets } from "@/lib/site";
import type { MarketCode, ResearchResult } from "@/types/research";
import {
  AcquisitionConsole,
  emptyTheater,
  type TheaterState,
} from "./acquisition-console";
import { ResultView } from "./result-view";
import { SearchInsightCard } from "./search-insight-card";

/** Human log copy for each engine progress event. */
const LEG_TAGS: Record<string, string> = {
  resolve: "RESOLVE",
  social: "SOCIAL",
  news_current: "NEWS",
  news_archive: "ARCHIVE",
  news_baseline: "BASELINE",
  filings: "FILINGS",
  price: "PRICE",
  analysis: "AI",
};

type StreamEvent = {
  type: string;
  key?: string;
  ok?: boolean;
  count?: number;
  detail?: string;
  ticker?: string;
  company?: string;
  confidence?: number;
  phase?: string;
  stance?: string;
  gap?: number;
  sentiment?: string;
  evidence?: number;
  message?: string;
  result?: ResearchResult;
};

function applyEvent(state: TheaterState, event: StreamEvent): TheaterState {
  const at = Date.now() - state.startedAt;
  const next: TheaterState = {
    ...state,
    sources: { ...state.sources },
    log: [...state.log],
  };
  const push = (tag: string, line: string) => next.log.push({ at, tag, line });

  switch (event.type) {
    case "resolve_start":
      next.sources.resolve = { phase: "searching" };
      push("RESOLVE", `matching “${state.query}” against the listing universe`);
      break;
    case "resolved":
      next.resolved = {
        ticker: event.ticker ?? "",
        company: event.company ?? "",
        confidence: event.confidence ?? 0,
      };
      next.sources.resolve = { phase: "live", detail: event.ticker };
      push(
        "RESOLVE",
        `matched ${event.ticker} — ${event.company} (${Math.round((event.confidence ?? 0) * 100)}%)`,
      );
      break;
    case "source_start":
      if (event.key) {
        next.sources[event.key] = { phase: "searching" };
        push(LEG_TAGS[event.key] ?? event.key.toUpperCase(), "channel open, searching…");
      }
      break;
    case "source_done":
      if (event.key) {
        next.sources[event.key] = event.ok
          ? { phase: "live", count: event.count }
          : { phase: "dark", detail: event.detail };
        push(
          LEG_TAGS[event.key] ?? event.key.toUpperCase(),
          event.ok
            ? `${event.count ?? 0} items captured`
            : `no answer (${event.detail ?? "unavailable"}) — continuing`,
        );
      }
      break;
    case "classified":
      next.classified = {
        phase: event.phase ?? "",
        stance: event.stance ?? "",
        gap: event.gap ?? 0,
      };
      push(
        "SIGNAL",
        `phase ${event.phase} · attention-vs-news gap ${(event.gap ?? 0) >= 0 ? "+" : ""}${(event.gap ?? 0).toFixed(1)}σ`,
      );
      break;
    case "analysis_start":
      next.sources.analysis = { phase: "searching" };
      push("AI", `GPT-5.6 Luna reading ${event.evidence ?? 0} evidence items`);
      break;
    case "analysis_done":
      next.sources.analysis = event.ok
        ? { phase: "live", detail: `sentiment: ${(event.sentiment ?? "").replace("_", " ")}` }
        : { phase: "dark", detail: "deterministic fallback" };
      push("AI", event.ok ? `sentiment read: ${(event.sentiment ?? "").replace("_", " ")}` : "fallback to fixed rules");
      break;
  }
  return next;
}

export function SearchConsole() {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState<MarketCode>("US");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [theater, setTheater] = useState<TheaterState | null>(null);
  const theaterRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const active = markets.find((item) => item.code === market) ?? markets[0];

  async function runPlain(trimmed: string): Promise<ResearchResult> {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: trimmed, market }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body?.error ?? "Research failed.");
    return body as ResearchResult;
  }

  async function runStreamed(trimmed: string): Promise<ResearchResult> {
    const response = await fetch("/api/research/stream", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: trimmed, market }),
    });
    if (!response.ok || !response.body) {
      // The stream endpoint answers with JSON on validation/offline errors.
      let message = "Research failed.";
      try {
        message = (await response.json())?.error ?? message;
      } catch {
        /* keep default */
      }
      throw new Error(message);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult: ResearchResult | null = null;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let event: StreamEvent;
        try {
          event = JSON.parse(line) as StreamEvent;
        } catch {
          continue;
        }
        if (event.type === "result" && event.result) {
          finalResult = event.result;
        } else if (event.type === "error") {
          throw new Error(event.message ?? "Research failed.");
        } else {
          setTheater((current) => (current ? applyEvent(current, event) : current));
        }
      }
    }
    if (!finalResult) throw new Error("The research stream ended without a result.");
    return finalResult;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a ticker, cashtag or company name.");
      return;
    }

    setError("");
    setResult(null);
    setBusy(true);
    setTheater(emptyTheater(trimmed));
    window.setTimeout(
      () => theaterRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }),
      120,
    );
    try {
      let body: ResearchResult;
      try {
        body = await runStreamed(trimmed);
      } catch (streamError) {
        // A missing stream route or a proxy that buffers should not kill the
        // demo — the classic endpoint returns the same result without theater.
        if (streamError instanceof TypeError) body = await runPlain(trimmed);
        else throw streamError;
      }
      setResult(body);
      window.setTimeout(
        () => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
        160,
      );
    } catch (caught) {
      setTheater(null);
      setError(caught instanceof Error ? caught.message : "Research failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="section-shell py-16 md:py-24" id="run">
        <div className="grid gap-14 lg:grid-cols-[.7fr_1.3fr] lg:gap-24">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <p className="eyebrow text-muted">Live market check</p>
            <h2 className="h-display mt-5 text-[clamp(2.6rem,5vw,4.6rem)]">
              Search a stock.
              <br />
              See what
              <br />changed.
            </h2>
            <div className="mt-9 border-t border-line pt-6 text-sm leading-6 text-muted">
              <p>
                Enter a ticker or company. We check what investors are saying, what trusted sources
                confirm, and what the price already reflects—then show the next sensible move.
              </p>
              <p className="mt-3">
                Every result is built from a fresh search and links back to the evidence behind it.
              </p>
            </div>
          </div>

          <form onSubmit={submit} noValidate className="border-t border-line-strong pt-10">
            <fieldset className="mb-9 border-0 p-0">
              <legend className="eyebrow mb-3 text-muted">Market</legend>
              <div className="inline-flex flex-wrap border border-line-strong bg-white p-1">
                {markets.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    onClick={() => {
                      setMarket(item.code);
                      setQuery("");
                      setError("");
                      setResult(null);
                      setTheater(null);
                    }}
                    aria-pressed={market === item.code}
                    className={`min-h-10 px-5 text-sm font-semibold transition-colors ${
                      market === item.code ? "bg-ink text-white" : "text-muted hover:bg-paper"
                    }`}
                  >
                    {item.short}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-xs leading-5 text-muted">
                Results compared with {active.benchmark} · company updates from {active.filings}
              </p>
            </fieldset>

            <label htmlFor="ticker-query" className="eyebrow text-muted">
              Ticker or company
            </label>
            <div className="relative mt-3">
              <input
                id="ticker-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={active.examples[0]}
                autoComplete="off"
                spellCheck={false}
                className="ticker-field"
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "query-error" : "query-hint"}
              />
              <span className="absolute right-0 top-1/2 -translate-y-1/2 text-sm font-semibold text-muted">
                {active.label}
              </span>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted">Try</span>
              {active.examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuery(example)}
                  className="rounded-full border border-line-strong bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ink"
                >
                  {example}
                </button>
              ))}
            </div>

            {error ? (
              <p
                id="query-error"
                role="alert"
                className="mt-8 border border-[#e8b8a8] bg-[#fff2ed] p-4 text-sm font-semibold leading-6 text-[#8f3219]"
              >
                {error}
              </p>
            ) : null}

            <div className="mt-9 flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:justify-between">
              <button type="submit" disabled={busy} className="button-primary w-full sm:w-auto">
                {busy ? "Checking live sources…" : "Analyze this stock"}
                <span aria-hidden>{busy ? "◴" : "→"}</span>
              </button>
              <p id="query-hint" role="status" aria-live="polite" className="max-w-sm text-xs leading-5 text-muted">
                {busy
                  ? "Watch each source answer in real time below."
                  : `Live posts, news, ${active.filings}, and price data are checked for every search.`}
              </p>
            </div>

            {theater ? (
              <div ref={theaterRef}>
                <AcquisitionConsole state={theater} done={!busy} />
              </div>
            ) : null}

            {result ? (
              <div ref={resultRef}>
                <SearchInsightCard result={result} />
              </div>
            ) : null}
          </form>
        </div>
      </section>

      <div>
        {result ? (
          <div className="border-t border-line bg-white/60">
            <ResultView result={result} />
          </div>
        ) : null}
      </div>
    </>
  );
}
