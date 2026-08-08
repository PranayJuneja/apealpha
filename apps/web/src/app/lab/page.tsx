import type { Metadata } from "next";
import { PageHero } from "@/components/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { loadBacktest } from "@/lib/api";
import { percent, signedPercent, strategyLabel, utcDateFull } from "@/lib/format";
import type { Backtest } from "@/types/research";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Validation lab",
  description: "Fixed rules evaluated against the real point-in-time store.",
};

const MODE_COPY = {
  historical: "Real history",
  forward_only: "Forward only",
  unavailable: "No coverage",
} as const;

function EmptyState({ reason }: { reason: string }) {
  return (
    <div className="glass p-10">
      <p className="eyebrow text-muted">Nothing to show yet</p>
      <h2 className="h-display mt-5 text-[clamp(1.8rem,3vw,2.6rem)]">The store has not been built.</h2>
      <p className="mt-5 max-w-xl text-sm leading-6 text-muted">{reason}</p>
      <pre className="mt-8 overflow-x-auto border border-line bg-white p-5 text-xs leading-6 text-ink">
        <code>
          npm run api{"\n"}
          npm run backfill -- AAPL MSFT NVDA{"\n"}
          npm run backtest
        </code>
      </pre>
    </div>
  );
}

function StrategyTable({ backtest }: { backtest: Backtest }) {
  if (backtest.strategies.length === 0) {
    return (
      <p className="border-t border-line pt-6 text-sm leading-6 text-muted">
        No strategy produced an evaluable signal against the current store.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse text-left">
        <thead>
          <tr className="border-b border-line-strong">
            {["Strategy", "Signals", "Win rate", "Mean excess", "95% interval", "Max drawdown"].map((head) => (
              <th key={head} className="eyebrow py-4 pr-6 font-semibold text-muted">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {backtest.strategies.map((strategy) => (
            <tr key={strategy.strategy} className="border-b border-line">
              <td className="py-5 pr-6 text-[15px] font-bold text-ink">{strategyLabel(strategy.strategy)}</td>
              <td className="tabular py-5 pr-6 text-sm">{strategy.signals}</td>
              <td className="tabular py-5 pr-6 text-sm">
                {strategy.signals > 0 ? percent(strategy.win_rate, 0) : "—"}
              </td>
              <td
                className={`tabular py-5 pr-6 text-sm font-semibold ${
                  strategy.mean_excess_return >= 0 ? "text-up" : "text-down"
                }`}
              >
                {strategy.signals > 0 ? signedPercent(strategy.mean_excess_return, 2) : "—"}
              </td>
              <td className="tabular py-5 pr-6 text-sm text-muted">
                {strategy.signals > 1
                  ? `${signedPercent(strategy.confidence_interval[0], 2)} → ${signedPercent(
                      strategy.confidence_interval[1],
                      2,
                    )}`
                  : "—"}
              </td>
              <td className="tabular py-5 pr-6 text-sm text-muted">
                {strategy.signals > 0 ? percent(strategy.max_drawdown, 1) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function LabPage() {
  let backtest: Backtest | null = null;
  let reason = "";
  try {
    backtest = await loadBacktest();
  } catch (caught) {
    reason =
      caught instanceof Error
        ? caught.message
        : "The research API did not return a completed run.";
  }

  return (
    <>
      <PageHero
        eyebrow="Validation lab"
        title={<>Does the rule survive contact with real data?</>}
        sub="Fixed thresholds, never fitted. Entry is the next bar's open, returns are excess of each listing's own market benchmark, and costs are charged on both sides."
      />

      <section className="section-shell py-16 md:py-24">
        {backtest === null ? (
          <Reveal>
            <EmptyState reason={reason} />
          </Reveal>
        ) : (
          <>
            <Reveal>
              <div className="flex flex-wrap items-baseline justify-between gap-6 border-b border-line-strong pb-6">
                <div>
                  <p className="eyebrow text-muted">{backtest.dataset_label}</p>
                  <h2 className="h-display mt-4 text-[clamp(2rem,3.5vw,3.2rem)]">Strategy comparison</h2>
                </div>
                <p className="tabular text-[11px] leading-5 text-muted">
                  RUN {backtest.run_id}
                  <br />
                  CFG {backtest.configuration_hash.slice(0, 16)}
                  <br />
                  HOLDOUT {backtest.locked_holdout ? "INCLUDED" : "SEALED"}
                </p>
              </div>
            </Reveal>

            <Reveal delay={0.06}>
              <div className="mt-10">
                <StrategyTable backtest={backtest} />
              </div>
            </Reveal>

            <Reveal delay={0.1}>
              <div className="mt-16">
                <p className="eyebrow text-muted">Source coverage</p>
                <ul className="mt-5 grid list-none gap-px border border-line bg-line p-0 sm:grid-cols-2 lg:grid-cols-4">
                  {backtest.coverage.map((item) => (
                    <li key={item.source} className="bg-white p-6">
                      <p className="text-[15px] font-bold capitalize text-ink">{item.source}</p>
                      <p className="eyebrow mt-3 text-muted">{MODE_COPY[item.mode]}</p>
                      <p className="tabular mt-3 text-sm">{item.observations.toLocaleString()} obs</p>
                      {item.first_observation ? (
                        <p className="tabular mt-1 text-[11px] text-muted">
                          {utcDateFull(item.first_observation)} → {utcDateFull(item.last_observation!)}
                        </p>
                      ) : null}
                      <p className="mt-3 text-xs leading-5 text-muted">{item.detail}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>

            <Reveal delay={0.14}>
              <div className="mt-14 border-t border-line pt-8">
                <p className="eyebrow text-muted">Caveats</p>
                <ul className="mt-5 grid gap-3 pl-5">
                  {backtest.caveats.map((caveat) => (
                    <li key={caveat} className="max-w-3xl text-sm leading-6 text-muted">
                      {caveat}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          </>
        )}
      </section>
    </>
  );
}
