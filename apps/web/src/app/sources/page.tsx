import type { Metadata } from "next";
import { PageHero } from "@/components/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { loadSourceHealth } from "@/lib/api";
import type { SourceHealth } from "@/types/research";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Source health",
  description: "What each acquisition leg can currently do.",
};

const SETUP = [
  {
    source: "Reddit",
    env: ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
    how: "Create a script or web app at reddit.com/prefs/apps. App-only OAuth, free tier, 100 requests per minute.",
    without: "The social leg goes dark. Every gap metric becomes partial and no paper position can be sized.",
  },
  {
    source: "Alpaca",
    env: ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
    how: "Free IEX market data from alpaca.markets. Enables intraday bars and a real as-of window.",
    without: "Price falls back to Yahoo daily bars. Everything still works at end-of-day resolution.",
  },
  {
    source: "Groq",
    env: ["GROQ_API_KEY"],
    how: "Optional narrative layer that writes prose about the computed metrics.",
    without: "Deterministic rule-written narrative is used instead. The stance is unaffected either way.",
  },
  {
    source: "Google News",
    env: [],
    how: "Keyless and locale-aware. Supplies the current news window in the market's own language and region, so Indian listings return Indian press.",
    without: "No setup is required. It has no archive, so GDELT still supplies the historical baseline; transient source failures are reported as degraded coverage.",
  },
  {
    source: "GDELT, SEC EDGAR and NSE",
    env: [],
    how: "All keyless. GDELT supplies the historical news archive back to 2017; EDGAR covers US filings and wants a descriptive SEC_USER_AGENT; NSE covers Indian corporate announcements.",
    without: "No setup is required. Network, rate-limit or upstream failures are still reported per run rather than hidden.",
  },
];

export default async function SourcesPage() {
  let sources: SourceHealth[] = [];
  let error = "";
  try {
    sources = (await loadSourceHealth()).sources;
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "Source health is unavailable.";
  }

  return (
    <>
      <PageHero
        eyebrow="Source health"
        title={<>Every leg, and what happens when one goes dark.</>}
        sub="No credential is required to run the engine. Each missing key disables exactly one source and is reported rather than silently zeroed."
      />

      <section className="section-shell py-16 md:py-24">
        <Reveal>
          <p className="eyebrow text-muted">Configuration readiness</p>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
            Ready means no local setup is missing. Upstream availability is measured again on every
            research run, and that run&apos;s coverage strip is the authoritative status.
          </p>
          {error ? (
            <p className="mt-5 max-w-2xl border-l-2 border-[var(--solar)] bg-[var(--solar-soft)] px-5 py-4 text-sm leading-6 text-ink">
              {error}
            </p>
          ) : (
            <ul className="mt-5 grid list-none gap-px border border-line bg-line p-0 md:grid-cols-2 lg:grid-cols-3">
              {sources.map((item) => (
                <li key={item.source} className="bg-white p-7">
                  <p className="flex items-center gap-2 text-[15px] font-bold text-ink">
                    <span
                      aria-hidden
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ background: item.status === "ready" ? "var(--up)" : "var(--down)" }}
                    />
                    {item.source}
                  </p>
                  <p className="eyebrow mt-3 text-muted">{item.status}</p>
                  <p className="mt-3 text-xs leading-5 text-muted">{item.detail}</p>
                </li>
              ))}
            </ul>
          )}
        </Reveal>

        <Reveal delay={0.08}>
          <div className="mt-20">
            <p className="eyebrow text-muted">Setup</p>
            <h2 className="h-display mt-5 max-w-3xl text-[clamp(2rem,3.5vw,3.2rem)]">
              What each key buys you.
            </h2>
            <ul className="mt-10 grid list-none gap-0 border-t border-line-strong p-0">
              {SETUP.map((item) => (
                <li key={item.source} className="grid gap-4 border-b border-line py-8 lg:grid-cols-[.8fr_1.2fr] lg:gap-12">
                  <div>
                    <p className="text-[17px] font-bold text-ink">{item.source}</p>
                    {item.env.length > 0 ? (
                      <p className="tabular mt-3 text-xs leading-6 text-muted">{item.env.join("\n")}</p>
                    ) : (
                      <p className="mt-3 text-xs text-muted">No credential required</p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm leading-6 text-ink">{item.how}</p>
                    <p className="mt-3 text-sm leading-6 text-muted">
                      <span className="font-semibold text-ink">Without it: </span>
                      {item.without}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </section>
    </>
  );
}
