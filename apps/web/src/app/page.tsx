import Link from "next/link";
import { SearchConsole } from "@/components/research/search-console";
import { Reveal } from "@/components/ui/reveal";
import { SectionHeading } from "@/components/ui/section-heading";
import { site, truthLayers } from "@/lib/site";

export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <>
      <section className="relative overflow-hidden bg-ink pt-28 text-white md:pt-36">
        <div className="home-hero-overlay absolute inset-0" aria-hidden />
        <div
          className="absolute inset-0 opacity-25"
          aria-hidden
          style={{
            background:
              "radial-gradient(circle at 78% 12%, rgba(246,184,23,.55) 0, transparent 42%), radial-gradient(circle at 12% 88%, rgba(22,93,255,.5) 0, transparent 45%)",
          }}
        />
        <div className="section-shell relative z-10 grid min-h-[62svh] items-end gap-12 pb-16 md:pb-24 lg:grid-cols-[1.25fr_.75fr]">
          <div>
            <p className="eyebrow hero-line text-white/70">Narrative arbitrage engine</p>
            <h1 className="h-display hero-line mt-6 max-w-5xl text-[clamp(3.4rem,8vw,7.5rem)] text-white">
              Did the crowd
              <br />
              find it first — or
              <br />
              <span className="text-[#bfd2ff]">arrive too late?</span>
            </h1>
          </div>
          <p className="hero-line max-w-xl border-t border-white/25 pt-6 text-base leading-7 text-white/70 lg:mb-3">
            Every story reaches Reddit, the newswires and the tape at different moments. The distance
            between those moments is the only edge worth measuring. Type a ticker and we will measure it
            against live sources.
          </p>
        </div>

        <div className="section-shell relative z-10 border-t border-white/15 py-6">
          <ul className="m-0 flex list-none flex-wrap items-center gap-x-10 gap-y-3 p-0">
            {truthLayers.map((layer) => (
              <li key={layer.source} className="flex items-baseline gap-3">
                <span className="eyebrow text-white">{layer.source}</span>
                <span className="text-sm text-white/55">{layer.claim}</span>
              </li>
            ))}
            <li className="eyebrow ml-auto text-[var(--solar)]">Who knew first?</li>
          </ul>
        </div>
      </section>

      <SearchConsole />

      <section className="section-rule">
        <div className="section-shell py-20 md:py-28">
          <SectionHeading
            eyebrow="Why a gap is the signal"
            title={<>Attention is easy to measure. Being early is not.</>}
            sub="Mention counts spike constantly, and almost all of it is noise that follows a move rather than leading one. Standardizing each layer separately makes the lead or lag visible."
          />

          <div className="mt-16 grid gap-px border border-line bg-line md:grid-cols-3">
            {[
              {
                title: "Whisper",
                body: "Social runs ahead of news and price. The most valuable and the most dangerous state, because unconfirmed is also where false positives live.",
              },
              {
                title: "Confirmed",
                body: "A filing or independent reporting catches up while price has not yet absorbed it. This is the only shape the engine will size a paper position into.",
              },
              {
                title: "Exit liquidity",
                body: "Attention arrives after the move, agreement is near-total and mention growth is decaying. The engine refuses the long side here.",
              },
            ].map((item, index) => (
              <Reveal key={item.title} delay={index * 0.06} className="bg-white p-8 md:p-10">
                <p className="eyebrow text-muted">0{index + 1}</p>
                <h3 className="h-display mt-5 text-[clamp(1.7rem,2.4vw,2.3rem)]">{item.title}</h3>
                <p className="mt-4 text-sm leading-6 text-muted">{item.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section-rule">
        <div className="section-shell grid gap-14 py-20 md:py-28 lg:grid-cols-[1fr_1fr] lg:gap-24">
          <Reveal>
            <p className="eyebrow text-muted">Honest by construction</p>
            <h2 className="h-display mt-5 text-[clamp(2.4rem,4.5vw,4.2rem)]">
              What this system
              <br />
              will not do.
            </h2>
          </Reveal>
          <Reveal delay={0.08}>
            <ul className="m-0 grid list-none gap-6 border-t border-line-strong p-0 pt-8">
              {[
                ["No live money", "There is no broker integration and no code path to one. Every position is paper, capped at 1% of NAV by a rule nothing downstream can raise."],
                ["No invented history", "The social leg has no licensed archive, so it accrues forward from the moment you run it. Backfilled rows say so explicitly instead of scoring a zero."],
                ["No look-ahead", "Entry is always the next bar's open. A signal can never fill on the bar that produced it."],
                ["No hidden model", "The stance comes from published rules. The language layer writes prose about the numbers; it never chooses the position."],
              ].map(([title, body]) => (
                <li key={title} className="border-b border-line pb-6">
                  <p className="text-[15px] font-bold text-ink">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
                </li>
              ))}
            </ul>
            <Link href={site.labHref} className="editorial-link mt-8 text-ink">
              See the validation lab <span aria-hidden>→</span>
            </Link>
          </Reveal>
        </div>
      </section>
    </>
  );
}
