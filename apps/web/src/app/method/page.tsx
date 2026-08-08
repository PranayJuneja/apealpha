import type { Metadata } from "next";
import { PageHero } from "@/components/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { SectionHeading } from "@/components/ui/section-heading";

export const metadata: Metadata = {
  title: "Method",
  description: "How the narrative gap is computed and what it cannot see.",
};

const STEPS = [
  {
    number: "01",
    title: "Resolve",
    body: "The query is matched against the chosen market's listing universe — the SEC company-ticker file for the US, the NSE and BSE venue index for India. Symbols that collide with ordinary English — ALL, IT, ONE — require a cashtag. Historical symbol changes are applied so a 2021 observation is scored under the symbol it actually traded as.",
  },
  {
    number: "02",
    title: "Acquire",
    body: "Every query asks WebCMD to search the authorized X and Reddit sessions plus current Google News and Yahoo News. GDELT's historical baseline, the market's filing source and price bars are fetched concurrently under wall-clock budgets. A failure in one provider is isolated and recorded rather than converted to zero; duplicate headlines are counted once.",
  },
  {
    number: "03",
    title: "Standardize",
    body: "Each layer is converted to a robust z-score against its own recent history using median absolute deviation, so a normally quiet name and a permanently loud one are comparable. Only observations strictly before the evaluation point are used.",
  },
  {
    number: "04",
    title: "Compare",
    body: "The narrative gap is social minus news, and social minus price. A large positive gap means the crowd is ahead. A negative gap means it is following. That difference, not the raw volume, is the signal. Returns are always measured against the security's own market index — the S&P for US listings, the Nifty 50 for Indian ones.",
  },
  {
    number: "05",
    title: "Plan",
    body: "A phase and rules-based playbook follow deterministically. GPT-5.6 Luna then returns the short narrative and a structured final read of sentiment, drivers and risks in one call. The model cannot change the phase, stance, entry conditions, invalidation, time stop or position cap.",
  },
];

const LIMITS = [
  [
    "A dark source is not a quiet one",
    "If the social leg does not report, its z-score is an unmeasured zero — which would read as 'nobody is talking' and invert the finding. The engine refuses to assign a phase at all in that case, shows the layer as unmeasured rather than as zero, and computes no gap.",
  ],
  [
    "The social leg has no deep history",
    "The connected X and Reddit surfaces do not provide the licensed deep archive required for point-in-time reconstruction. Historical rows use news and price only and are marked as such. Social observations accrue forward from the moment you start running the engine.",
  ],
  [
    "Sentiment is a lexicon, not a model",
    "Bullish share is still counted from an explicit word list so the signal remains reproducible. GPT-5.6 Luna adds a final interpretation, but it does not rewrite that metric and may still misunderstand sarcasm or coordinated posting.",
  ],
  [
    "Price is end-of-day without Alpaca",
    "The keyless Yahoo fallback is daily. Intraday lead-lag, the timescale on which much of this actually happens, is not represented unless Alpaca intraday bars are configured.",
  ],
  [
    "Coverage is not evidence of absence",
    "Google News, Yahoo News and GDELT index large but incomplete slices of coverage. A quiet news z-score means the sources that answered were quiet; the coverage strip states which ones answered.",
  ],
  [
    "Nothing here is advice",
    "The engine produces research and paper plans. There is no broker integration and no code path to one.",
  ],
];

export default function MethodPage() {
  return (
    <>
      <PageHero
        eyebrow="Method"
        title={<>The distance between knowing and pricing.</>}
        sub="Five steps, all of them inspectable. Every number on a result page traces back to a timestamped source you can open."
      />

      <section className="section-shell py-16 md:py-24">
        <ol className="m-0 grid list-none gap-0 border-t border-line-strong p-0">
          {STEPS.map((step, index) => (
            <Reveal key={step.number} delay={index * 0.05}>
              <li className="grid gap-5 border-b border-line py-10 lg:grid-cols-[.5fr_1.5fr] lg:gap-16">
                <div className="flex items-baseline gap-5">
                  <span className="tabular text-sm text-muted">{step.number}</span>
                  <h2 className="h-display text-[clamp(1.7rem,2.6vw,2.4rem)]">{step.title}</h2>
                </div>
                <p className="max-w-3xl text-[15px] leading-7 text-muted">{step.body}</p>
              </li>
            </Reveal>
          ))}
        </ol>
      </section>

      <section className="section-rule" id="limits">
        <div className="section-shell py-20 md:py-28">
          <SectionHeading
            eyebrow="Known limits"
            title={<>What this will not tell you.</>}
            sub="Stated here rather than discovered later. A research tool that hides its blind spots is worse than no tool."
          />
          <ul className="mt-14 grid list-none gap-0 border-t border-line-strong p-0" id="coverage">
            {LIMITS.map(([title, body], index) => (
              <Reveal key={title} delay={index * 0.04}>
                <li className="grid gap-4 border-b border-line py-8 lg:grid-cols-[.7fr_1.3fr] lg:gap-16">
                  <p className="text-[17px] font-bold text-ink">{title}</p>
                  <p className="max-w-3xl text-sm leading-7 text-muted">{body}</p>
                </li>
              </Reveal>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}
