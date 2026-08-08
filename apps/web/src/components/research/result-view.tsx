import { percent, signedPercent, sigma } from "@/lib/format";
import { phaseCopy } from "@/lib/site";
import type { ResearchResult } from "@/types/research";
import { Reveal } from "@/components/ui/reveal";
import { CausalTape } from "./causal-tape";
import { CoverageStrip } from "./coverage-strip";
import { EvidenceLedger } from "./evidence-ledger";
import { NarrativeGap } from "./narrative-gap";
import { PhaseBadge } from "./phase-badge";
import { PlaybookCard } from "./playbook-card";

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="bg-white p-6">
      <p className="eyebrow text-muted">{label}</p>
      <p className="stat-value mt-3">{value}</p>
      <p className="mt-2 text-xs leading-5 text-muted">{note}</p>
    </div>
  );
}

export function ResultView({ result }: { result: ResearchResult }) {
  const { snapshot, playbook, features } = { ...result, features: result.snapshot.features };
  const copy = phaseCopy[snapshot.phase];
  // A dark social leg leaves social_z at an unmeasured zero. Rendering that as
  // a value would invert the reading, so those tiles show "—" instead.
  const socialMeasured = result.coverage.some(
    (status) => ["social", "reddit"].includes(status.source) && status.status === "live",
  );

  return (
    <div className="pb-24">
      <section className="section-shell pt-16 md:pt-20">
        <Reveal>
          <div className="flex flex-wrap items-start justify-between gap-6 border-b border-line-strong pb-8">
            <div>
              <p className="eyebrow text-muted">
                {result.display_symbol} · {result.market_label} · {result.currency}
                {result.cik ? ` · CIK ${result.cik}` : ""} · resolved from “{result.query}”
              </p>
              <h1 className="h-display mt-4 text-[clamp(3rem,7vw,6.5rem)]">{result.company}</h1>
            </div>
            <div className="flex flex-col items-start gap-3 md:items-end">
              <PhaseBadge phase={snapshot.phase} />
              {snapshot.phase === "INDETERMINATE" ? null : (
                <p className="tabular text-sm text-muted">{percent(snapshot.confidence, 0)} confidence</p>
              )}
              {snapshot.conflict ? (
                <p className="text-sm font-bold text-down">Sources disagree</p>
              ) : null}
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.06}>
          <p className="mt-8 max-w-4xl text-[1.15rem] leading-8 text-ink">{result.narrative}</p>
          <p className="mt-4 text-xs text-muted">
            {copy.summary} Narrative written by {result.narrative_source === "groq" ? "the language layer" : "deterministic rules"};
            the stance below always comes from rules.
          </p>
        </Reveal>
      </section>

      {result.warnings.length > 0 ? (
        <section className="section-shell mt-10">
          <Reveal>
            <div className="border-l-2 border-[var(--solar)] bg-[var(--solar-soft)] px-6 py-5">
              <p className="eyebrow text-ink">Read this first</p>
              <ul className="mt-3 grid gap-2 pl-5">
                {result.warnings.map((warning) => (
                  <li key={warning} className="text-sm leading-6 text-ink">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </section>
      ) : null}

      <section className="section-shell mt-16 grid gap-14 lg:grid-cols-[1.15fr_.85fr] lg:gap-20">
        <Reveal>
          <NarrativeGap features={features} socialMeasured={socialMeasured} />
        </Reveal>
        <Reveal delay={0.08}>
          <PlaybookCard playbook={playbook} />
        </Reveal>
      </section>

      <section className="section-shell mt-16">
        <Reveal>
          <p className="eyebrow text-muted">Signal detail</p>
          <div className="mt-5 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Social acceleration"
              value={socialMeasured ? `${features.social_acceleration.toFixed(2)}×` : "—"}
              note={socialMeasured ? "vs the prior six-day mean" : "social leg did not report"}
            />
            <Metric
              label="Distinct authors"
              value={socialMeasured ? String(features.unique_authors) : "—"}
              note={socialMeasured ? `across ${features.social_count} posts in 24h` : "social leg did not report"}
            />
            <Metric
              label="Analysis density"
              value={socialMeasured ? percent(features.dd_density, 0) : "—"}
              note={socialMeasured ? "share of posts carrying argument" : "social leg did not report"}
            />
            <Metric
              label="Bullish share"
              value={socialMeasured ? percent(features.bull_ratio, 0) : "—"}
              note={socialMeasured ? "directional language only" : "social leg did not report"}
            />
            <Metric
              label="Catalyst quality"
              value={percent(features.catalyst_quality, 0)}
              note={features.filing_confirmed ? "material filing inside 72h" : "no recent filing"}
            />
            <Metric
              label="Coverage novelty"
              value={percent(features.novelty, 0)}
              note={`${features.news_count} articles, duplicates removed`}
            />
            <Metric
              label="Relative volume"
              value={`${features.relative_volume.toFixed(2)}×`}
              note={`${features.price_resolution} bars`}
            />
            <Metric
              label="Already priced"
              value={features.already_pumped_penalty.toFixed(2)}
              note={`${signedPercent(features.pre_signal_return)} over the prior five bars`}
            />
          </div>
        </Reveal>
      </section>

      <section className="section-shell mt-16">
        <Reveal>
          <p className="eyebrow text-muted">What this run could see</p>
          <div className="mt-5">
            <CoverageStrip coverage={result.coverage} />
          </div>
        </Reveal>
      </section>

      <section className="section-shell mt-20 border-t border-line pt-14">
        <Reveal>
          <CausalTape events={result.events} />
        </Reveal>
      </section>

      <section className="section-shell mt-20 grid gap-12 lg:grid-cols-[.5fr_1.5fr] lg:gap-20">
        <Reveal>
          <p className="eyebrow text-muted">Evidence ledger</p>
          <h3 className="h-display mt-4 text-[clamp(1.8rem,3vw,2.6rem)]">Every observation, timestamped.</h3>
          <p className="mt-5 text-sm leading-6 text-muted">
            {result.events.length} records. Each links to its source so any number above can be traced back
            to the thing that produced it.
          </p>
          <p className="tabular mt-6 text-[11px] leading-5 text-muted">
            SNAPSHOT {snapshot.snapshot_id}
            <br />
            SIGNAL {snapshot.signal_version} · CLASSIFIER {snapshot.classifier_version}
            <br />
            GAP vs NEWS {socialMeasured ? sigma(features.social_news_gap) : "—"} · vs PRICE{" "}
            {socialMeasured ? sigma(features.social_price_gap) : "—"}
          </p>
        </Reveal>
        <Reveal delay={0.08}>
          <EvidenceLedger events={result.events} />
        </Reveal>
      </section>
    </div>
  );
}
