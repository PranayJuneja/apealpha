import { percent } from "@/lib/format";
import type { ResearchResult } from "@/types/research";

const sentimentLabel: Record<ResearchResult["understanding"]["sentiment"], string> = {
  strongly_bearish: "Strongly bearish",
  bearish: "Bearish",
  mixed: "Mixed",
  bullish: "Bullish",
  strongly_bullish: "Strongly bullish",
};

const actionCopy: Record<
  ResearchResult["snapshot"]["action"],
  { label: string; short: "Buy" | "Watch" | "Avoid"; className: string }
> = {
  PAPER_BUY: {
    label: "Paper buy setup",
    short: "Buy",
    className: "border-[var(--up)] bg-[var(--up-soft)] text-[var(--up)]",
  },
  WATCH: {
    label: "Watch for confirmation",
    short: "Watch",
    className: "border-[#df8b00] bg-[var(--solar-soft)] text-[#7a4d00]",
  },
  NO_TRADE: {
    label: "Stand aside",
    short: "Avoid",
    className: "border-[var(--down)] bg-[var(--down-soft)] text-[var(--down)]",
  },
};

export function SearchInsightCard({ result }: { result: ResearchResult }) {
  const action = actionCopy[result.snapshot.action];
  const liveSources = result.coverage.filter((source) => source.status === "live").length;
  const filingSeen = result.snapshot.features.filing_confirmed;
  const fallbackSentiment = result.snapshot.features.bull_ratio >= 0.6
    ? "bullish"
    : result.snapshot.features.bull_ratio <= 0.4
      ? "bearish"
      : "mixed";
  const sentiment = result.understanding?.sentiment ?? fallbackSentiment;
  const sentimentConfidence = result.understanding?.confidence ?? result.snapshot.confidence;
  const keyFindings = result.understanding?.drivers.slice(0, 2) ?? [
    `${result.snapshot.features.social_count} investor posts from ${result.snapshot.features.unique_authors} people`,
    `${result.snapshot.features.news_count} unique news stories in the latest window`,
  ];
  const mainRisk = result.understanding?.risks[0] ?? result.playbook.risks[0] ?? result.warnings[0];

  return (
    <aside
      aria-label={`Research summary for ${result.company}`}
      className="mt-10 overflow-hidden rounded-[1.5rem] border border-line-strong bg-ink text-white shadow-[0_24px_70px_rgba(17,24,20,.16)]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/15 px-6 py-4 md:px-8">
        <p className="eyebrow flex items-center gap-2 text-white/60">
          <span className="size-2 rounded-full bg-[var(--up)] shadow-[0_0_0_4px_rgba(13,107,70,.22)]" />
          Analysis complete
        </p>
        <p className="tabular text-xs text-white/55">
          {liveSources}/{result.coverage.length} sources live · {result.events.length} evidence items
        </p>
      </div>

      <div className="grid lg:grid-cols-[.78fr_1.22fr]">
        <div className="border-b border-white/15 p-6 md:p-8 lg:border-b-0 lg:border-r">
          <p className="eyebrow text-white/50">The plain-English read</p>
          <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
            <h2 className="h-display text-[clamp(2.3rem,5vw,4.4rem)]">
              {action.label}
            </h2>
            <span className="mb-1 text-sm font-semibold text-white/55">
              {percent(result.snapshot.confidence, 0)} signal confidence
            </span>
          </div>
          <p className="mt-5 max-w-xl text-sm leading-6 text-white/75">
            {result.playbook.rationale}
          </p>

          <div className="mt-7 grid grid-cols-3 gap-1 rounded-xl bg-white/8 p-1" aria-label="Rules-based action scale">
            {(["Buy", "Watch", "Avoid"] as const).map((item) => (
              <div
                key={item}
                className={`rounded-lg px-2 py-2.5 text-center text-xs font-bold ${
                  action.short === item ? action.className : "border border-transparent text-white/35"
                }`}
              >
                {item}
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-5 text-white/45">
            Research and paper trading only. This is not personal investment advice and does not place a trade.
          </p>
        </div>

        <div className="p-6 md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <p className="eyebrow text-white/50">Market sentiment</p>
              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
                {sentimentLabel[sentiment]}
              </p>
            </div>
            <div className="text-right">
              <p className="tabular text-xl font-semibold">
                {percent(sentimentConfidence, 0)}
              </p>
              <p className="mt-1 text-[11px] text-white/45">interpretation confidence</p>
            </div>
          </div>

          <div className="mt-7 grid gap-px overflow-hidden rounded-xl bg-white/15 sm:grid-cols-3">
            <div className="bg-[#18211c] p-4">
              <p className="eyebrow text-white/40">Social</p>
              <p className="mt-2 text-sm font-semibold">
                {result.snapshot.features.social_count} posts found
              </p>
            </div>
            <div className="bg-[#18211c] p-4">
              <p className="eyebrow text-white/40">News</p>
              <p className="mt-2 text-sm font-semibold">
                {result.snapshot.features.news_count} unique stories
              </p>
            </div>
            <div className="bg-[#18211c] p-4">
              <p className="eyebrow text-white/40">Filings</p>
              <p className="mt-2 text-sm font-semibold">
                {filingSeen ? "Recent filing found" : "No recent filing"}
              </p>
            </div>
          </div>

          {keyFindings.length > 0 ? (
            <div className="mt-7">
              <p className="eyebrow text-white/50">Why the engine says this</p>
              <ul className="mt-3 grid gap-2 pl-5 text-sm leading-6 text-white/75 marker:text-[var(--solar)]">
                {keyFindings.map((finding) => <li key={finding}>{finding}</li>)}
              </ul>
            </div>
          ) : null}

          {mainRisk ? (
            <p className="mt-6 border-l-2 border-[var(--solar)] pl-4 text-xs leading-5 text-white/60">
              <strong className="text-white/85">Watch out:</strong> {mainRisk}
            </p>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
