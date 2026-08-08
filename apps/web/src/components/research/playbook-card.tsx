import { percent } from "@/lib/format";
import type { Playbook } from "@/types/research";
import { StanceBadge } from "./phase-badge";

const ROWS = [
  { label: "Buy only if", key: "entry_trigger" },
  { label: "Walk away if", key: "invalidation" },
] as const;

export function PlaybookCard({ playbook }: { playbook: Playbook }) {
  const sized = playbook.max_nav_pct > 0;

  return (
    <div className={`p-8 md:p-10 ${sized ? "glass-sun" : "glass"}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="eyebrow text-muted">What to do next</p>
        <StanceBadge stance={playbook.stance} />
      </div>

      <p className="mt-6 text-[1.05rem] leading-7 text-ink">{playbook.rationale}</p>

      <dl className="mt-8 grid gap-6 border-t border-line-strong pt-6 sm:grid-cols-3">
        <div>
          <dt className="eyebrow text-muted">Position limit</dt>
          <dd className="stat-value mt-2">{sized ? percent(playbook.max_nav_pct, 2) : "—"}</dd>
          <p className="mt-2 text-xs leading-5 text-muted">of the simulated portfolio</p>
        </div>
        <div>
          <dt className="eyebrow text-muted">Review after</dt>
          <dd className="stat-value mt-2">{playbook.time_stop_hours > 0 ? `${playbook.time_stop_hours}h` : "—"}</dd>
          <p className="mt-2 text-xs leading-5 text-muted">{playbook.expected_holding_period}</p>
        </div>
        <div>
          <dt className="eyebrow text-muted">Trade type</dt>
          <dd className="stat-value mt-2">Simulation</dd>
          <p className="mt-2 text-xs leading-5 text-muted">no real trade is placed</p>
        </div>
      </dl>

      <dl className="mt-8 grid gap-5 border-t border-line pt-6">
        {ROWS.map((row) => (
          <div key={row.key} className="grid gap-2 sm:grid-cols-[9rem_1fr] sm:gap-6">
            <dt className="eyebrow text-muted">{row.label}</dt>
            <dd className="m-0 text-sm leading-6 text-ink">{playbook[row.key]}</dd>
          </div>
        ))}
      </dl>

      {playbook.risks.length > 0 ? (
        <div className="mt-8 border-t border-line pt-6">
          <p className="eyebrow text-muted">What would make this wrong</p>
          <ul className="mt-4 grid gap-3 pl-5">
            {playbook.risks.map((risk) => (
              <li key={risk} className="text-sm leading-6 text-ink marker:text-[var(--down)]">
                {risk}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
