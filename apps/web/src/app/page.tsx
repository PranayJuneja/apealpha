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
            <p className="eyebrow hero-line text-white/70">Market intelligence, in plain English</p>
            <h1 className="h-display hero-line mt-6 max-w-5xl text-[clamp(3.4rem,8vw,7.5rem)] text-white">
              Is this stock story
              <br />
              still early — or
              <br />
              <span className="text-[#bfd2ff]">already priced in?</span>
            </h1>
          </div>
          <p className="hero-line max-w-xl border-t border-white/25 pt-6 text-base leading-7 text-white/70 lg:mb-3">
            Search a company. APE Alpha checks what investors are saying, what reliable sources have
            confirmed, and how the price has moved. Then it gives you a clear next step: watch, paper buy,
            or stay away.
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
            <li className="eyebrow ml-auto text-[var(--solar)]">One search. One clear read.</li>
          </ul>
        </div>
      </section>

      <SearchConsole />

      <section className="section-rule">
        <div className="section-shell py-20 md:py-28">
          <SectionHeading
            eyebrow="Why timing matters"
            title={<>A popular story is not always an early one.</>}
            sub="We compare investor conversation, confirmed news, and price action to show whether attention is leading the move or simply chasing it."
          />

          <div className="mt-16 grid gap-px border border-line bg-line md:grid-cols-3">
            {[
              {
                title: "Early signal",
                body: "Investors are talking before news and price react. Interesting, but still unconfirmed.",
              },
              {
                title: "Evidence building",
                body: "A filing or independent report supports the story before price fully reacts. This can become a paper-buy setup.",
              },
              {
                title: "Too late",
                body: "Price has already moved and attention is arriving afterward. APE Alpha flags the chase and tells you to stay out.",
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
            <p className="eyebrow text-muted">Built for honest decisions</p>
            <h2 className="h-display mt-5 text-[clamp(2.4rem,4.5vw,4.2rem)]">
              What APE Alpha
              <br />
              will never pretend.
            </h2>
          </Reveal>
          <Reveal delay={0.08}>
            <ul className="m-0 grid list-none gap-6 border-t border-line-strong p-0 pt-8">
              {[
                ["Simulation only", "There is no broker connection. Every suggested position is a paper plan and can never exceed 1% of the test portfolio."],
                ["No made-up history", "If past conversation data is unavailable, APE Alpha says so. Missing information is never presented as silence."],
                ["No hindsight", "A test entry begins at the next market open, so a result never benefits from a price that was not known yet."],
                ["Rules choose the action", "Published rules decide watch, paper buy, or stay away. AI only makes the measured evidence easier to read."],
              ].map(([title, body]) => (
                <li key={title} className="border-b border-line pb-6">
                  <p className="text-[15px] font-bold text-ink">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
                </li>
              ))}
            </ul>
            <Link href={site.labHref} className="editorial-link mt-8 text-ink">
              See how the rules performed <span aria-hidden>→</span>
            </Link>
          </Reveal>
        </div>
      </section>
    </>
  );
}
