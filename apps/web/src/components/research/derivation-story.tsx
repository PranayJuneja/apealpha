import { sigma, signedPercent } from "@/lib/format";
import { phaseCopy } from "@/lib/site";
import type { ResearchResult } from "@/types/research";

const STANCE_LABEL: Record<ResearchResult["playbook"]["stance"], string> = {
  PAPER_LONG: "Buying potential",
  WATCH: "Setup forming",
  STAND_ASIDE: "Priced in — wait",
};

/**
 * The derivation chain: each step is the actual number the classifier used,
 * with the plain-English meaning underneath, ending at the rules verdict.
 */
export function DerivationStory({
  result,
  socialMeasured,
}: {
  result: ResearchResult;
  socialMeasured: boolean;
}) {
  const { features, phase } = { ...result.snapshot, features: result.snapshot.features };
  const steps = [
    {
      label: "Attention",
      value: socialMeasured ? sigma(features.social_z) : "—",
      jargon: "social z-score vs 30-day norm",
      plain: socialMeasured
        ? `${features.social_count} posts from ${features.unique_authors} people — how unusual today's chatter is against this stock's own history.`
        : "Investor conversation did not report on this run.",
    },
    {
      label: "Confirmation",
      value: sigma(features.news_z),
      jargon: "news z-score + filings",
      plain: `${features.news_count} unique stories${features.filing_confirmed ? " and a material filing inside 72h" : ", no fresh filing"} — is anyone credible backing the story?`,
    },
    {
      label: "Price",
      value: sigma(features.market_z),
      jargon: `market z · ${features.relative_volume.toFixed(2)}× volume`,
      plain: `The tape moved ${signedPercent(features.pre_signal_return)} over the prior five bars — how much of the story is already paid for.`,
    },
    {
      label: "Narrative gap",
      value: socialMeasured ? sigma(features.social_news_gap) : "—",
      jargon: "attention minus confirmation",
      plain: socialMeasured
        ? "The distance between what the crowd knows and what the record confirms. This gap is the whole edge."
        : "Cannot be measured without the social leg.",
    },
    {
      label: "Verdict",
      value: STANCE_LABEL[result.playbook.stance],
      jargon: `phase: ${phaseCopy[phase].label} · fixed rules`,
      plain: "Deterministic rules translate the gap into an action. The AI explains; it never decides.",
      verdict: true,
    },
  ];

  return (
    <div>
      <p className="eyebrow text-muted">How this verdict was derived</p>
      <ol className="mt-5 grid list-none gap-px border border-line bg-line p-0 md:grid-cols-5">
        {steps.map((step, index) => (
          <li
            key={step.label}
            className={`relative p-5 ${step.verdict ? "bg-ink text-white" : "bg-white"}`}
          >
            <p className={`eyebrow ${step.verdict ? "text-white/55" : "text-muted"}`}>
              {index + 1} · {step.label}
            </p>
            <p className="stat-value mt-3 text-[clamp(1.2rem,2vw,1.7rem)]">{step.value}</p>
            <p className={`tabular mt-1 text-[10px] uppercase tracking-[0.08em] ${step.verdict ? "text-white/45" : "text-muted"}`}>
              {step.jargon}
            </p>
            <p className={`mt-3 text-xs leading-5 ${step.verdict ? "text-white/75" : "text-muted"}`}>
              {step.plain}
            </p>
            {index < steps.length - 1 ? (
              <span
                aria-hidden
                className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-line-strong md:block"
                style={{ color: "var(--line-strong)" }}
              >
                →
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
