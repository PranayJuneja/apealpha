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
    source: "WebCMD X",
    env: [],
    how: "Install the Twitter WebCMD plugin, then run `webcmd twitter login` once and complete login yourself. Each run searches current X posts without exposing the session to Ape Alpha.",
    without: "Reddit can keep the social leg live, but X sentiment and reach are absent and the partial coverage is disclosed.",
  },
  {
    source: "WebCMD Reddit",
    env: [],
    how: "Run `npm run webcmd -- reddit login` once and complete the login yourself. Each ticker query then searches that authorized session; APE Alpha receives normalized results, not your cookie or password.",
    without: "The social leg goes dark. Every gap metric becomes partial and no paper position can be sized.",
  },
  {
    source: "Reddit API fallback",
    env: ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
    how: "Optional only. Approved server-side OAuth is used when APE_SOCIAL_MODE=auto and the WebCMD Reddit session is unavailable.",
    without: "Nothing while WebCMD Reddit is healthy. No API approval is needed for the primary pathway.",
  },
  {
    source: "Alpaca",
    env: ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
    how: "Free IEX market data from alpaca.markets. Enables intraday bars and a real as-of window.",
    without: "Price falls back to Yahoo daily bars. Everything still works at end-of-day resolution.",
  },
  {
    source: "OpenAI GPT-5.6 Luna",
    env: ["OPENAI_API_KEY"],
    how: "One structured call writes the narrative and interprets measured sentiment, drivers and risks after deterministic scoring.",
    without: "The narrative and final understanding use transparent deterministic fallbacks. The stance and metrics are unaffected.",
  },
  {
    source: "WebCMD Google + Yahoo News",
    env: [],
    how: "Both current-news commands run for every resolved ticker. Google is locale-aware; Yahoo is independently filtered against the visible headline. No news login or API key is required.",
    without: "No setup is required. Either provider can keep the current-news leg live; GDELT supplies the historical baseline and every partial failure is disclosed.",
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
        sub="No social API approval is required. Authorized WebCMD X and Reddit sessions and every keyless provider are reported explicitly rather than silently zeroed."
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
