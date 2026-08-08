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
    title: "Find the company",
    body: "We match the name or ticker to the correct US or Indian listing. This prevents similar company names and common words from sending the search to the wrong stock.",
  },
  {
    number: "02",
    title: "Gather live evidence",
    body: "We check investor conversations, current news, company filings, and price data at the same time. Duplicate stories count once, and a missing source is clearly marked instead of treated as zero activity.",
  },
  {
    number: "03",
    title: "Compare with normal",
    body: "Every stock has a different baseline. We compare today's activity with what is normal for that company, so a quiet stock and a famous stock can be judged fairly.",
  },
  {
    number: "04",
    title: "See what moved first",
    body: "We compare conversation, confirmed news, and price. If conversation leads, the story may be early. If price moved first, people may simply be chasing it. US results are compared with the S&P 500 and Indian results with the Nifty 50.",
  },
  {
    number: "05",
    title: "Give the next step",
    body: "Fixed rules choose watch, paper buy, or stay away. AI explains the evidence, sentiment, reasons, and risks in plain English, but it cannot change the action.",
  },
];

const LIMITS = [
  [
    "Missing data does not mean silence",
    "If investor conversation data is unavailable, APE Alpha will not assume nobody is talking. It marks the source as missing and does not make an early-or-late call.",
  ],
  [
    "Past conversations are limited",
    "The connected social sources do not provide a licensed long-term archive. Historical tests use news and price where conversation data is unavailable, and mark those rows clearly.",
  ],
  [
    "Sentiment can miss tone",
    "Positive and negative language is counted with a fixed word list so results are repeatable. Sarcasm and coordinated posting can still fool it, so sentiment is evidence—not proof.",
  ],
  [
    "Some price data is daily",
    "Without Alpaca, price checks use daily Yahoo data. Fast moves within a trading day will not be visible in that mode.",
  ],
  [
    "No source sees everything",
    "Google News, Yahoo News, and GDELT cover a large but incomplete share of the news. Every result shows which sources actually answered.",
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
        eyebrow="How it works"
        title={<>From a ticker to a clear next step.</>}
        sub="Five transparent steps. Every conclusion links back to evidence you can open yourself."
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
            eyebrow="What to keep in mind"
            title={<>Where the signal can be wrong.</>}
            sub="Every research tool has blind spots. APE Alpha shows its limits so you can judge each result with the right context."
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
