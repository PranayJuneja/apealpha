import { percent } from "@/lib/format";
import type { AIUnderstanding } from "@/types/research";

const sentimentCopy: Record<AIUnderstanding["sentiment"], string> = {
  strongly_bearish: "Strongly bearish",
  bearish: "Bearish",
  mixed: "Mixed",
  bullish: "Bullish",
  strongly_bullish: "Strongly bullish",
};

export function UnderstandingCard({ understanding }: { understanding: AIUnderstanding }) {
  const isOpenAI = understanding.source === "openai";
  return (
    <div className="border border-line-strong bg-ink p-7 text-white md:p-9">
      <div className="flex flex-wrap items-start justify-between gap-5 border-b border-white/20 pb-6">
        <div>
          <p className="eyebrow text-white/60">Market sentiment</p>
          <h2 className="h-display mt-3 text-[clamp(2rem,4vw,3.5rem)]">
            {sentimentCopy[understanding.sentiment]}
          </h2>
        </div>
        <div className="text-right">
          <p className="tabular text-2xl font-semibold">{percent(understanding.confidence, 0)}</p>
          <p className="mt-1 text-xs text-white/60">confidence in this read</p>
        </div>
      </div>

      <p className="mt-7 max-w-4xl text-base leading-7 text-white/90">{understanding.summary}</p>
      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <div>
          <p className="eyebrow text-white/50">Why</p>
          <ul className="mt-4 grid gap-3 pl-5 text-sm leading-6 text-white/85">
            {understanding.drivers.map((driver) => <li key={driver}>{driver}</li>)}
          </ul>
        </div>
        <div>
          <p className="eyebrow text-white/50">What could change the call</p>
          <ul className="mt-4 grid gap-3 pl-5 text-sm leading-6 text-white/85">
            {understanding.risks.map((risk) => <li key={risk}>{risk}</li>)}
          </ul>
        </div>
      </div>
      <p className="mt-8 border-t border-white/20 pt-5 text-xs text-white/50">
        {isOpenAI ? `Summary written by ${understanding.model}` : "Rules-based summary"}. AI explains the
        evidence; fixed rules choose the action.
      </p>
    </div>
  );
}
