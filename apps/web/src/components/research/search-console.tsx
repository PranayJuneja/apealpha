"use client";

import { useEffect, useRef, useState } from "react";
import { markets } from "@/lib/site";
import type { MarketCode, ResearchResult } from "@/types/research";
import { ResultView } from "./result-view";
import { SearchInsightCard } from "./search-insight-card";

// The pipeline runs in this order, so the labels describe what is genuinely
// happening rather than animating a meaningless bar.
function stagesFor(market: MarketCode) {
  const filings = market === "US" ? "EDGAR" : "NSE announcements";
  return [
    { at: 0, label: "Finding the right company…" },
    { at: 1800, label: `Checking investor posts, news, and ${filings}…` },
    { at: 6000, label: "Comparing attention with the price move…" },
    { at: 11000, label: "Turning the evidence into a next step…" },
    { at: 14000, label: "Writing your plain-English summary…" },
  ];
}

export function SearchConsole() {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState<MarketCode>("US");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ResearchResult | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const active = markets.find((item) => item.code === market) ?? markets[0];
  const stages = stagesFor(market);

  useEffect(() => {
    if (!busy) {
      setStage(0);
      return;
    }
    const timers = stages.map((item, index) =>
      window.setTimeout(() => setStage(index), item.at),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [busy, market]);

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
    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query: trimmed, market }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error ?? "Research failed.");
      setResult(body as ResearchResult);
      window.setTimeout(
        () => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
        80,
      );
    } catch (caught) {
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
                  ? stages[stage].label
                    : `Live posts, news, ${active.filings}, and price data are checked for every search.`}
              </p>
            </div>

            {busy ? (
              <div className="progress-rail mt-6" role="presentation">
                <span style={{ width: `${((stage + 1) / stages.length) * 100}%` }} />
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
