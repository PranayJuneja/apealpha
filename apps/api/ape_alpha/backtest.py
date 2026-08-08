from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .contracts import BacktestConfig, BacktestRun, SourceCoverage, StrategyResult
from .markets import Market, profile as market_profile
from .sources import market as market_source
from .sources.http import SourceError
from .sources.market import Bar
from .store import derived_dir, read_snapshots

CODE_VERSION = "ape-alpha-0.2.0"


def benchmark_for(market: str | None) -> str:
    """Each market is measured against its own index.

    Scoring an Indian security's excess return against the S&P would attribute
    Nifty moves and the USD/INR basis to the strategy.
    """
    try:
        return market_profile(Market(market or "US")).benchmark
    except ValueError:
        return market_profile(Market.US).benchmark

HORIZON_BARS = {"1d": 1, "3d": 3, "5d": 5}

# Rules are fixed thresholds, never fitted to the data. A strategy that only
# fires on the social leg simply records zero signals on rows where that leg was
# dark, which is the honest outcome rather than a silent substitution.
STRATEGIES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "price_volume": lambda row: row["market_z"] >= 2.0 and row["relative_volume"] >= 1.8,
    "social_activity": lambda row: row["social_z"] >= 3.0 and row["unique_authors"] >= 5,
    "sentiment": lambda row: row["bull_ratio"] >= 0.75 and row["social_z"] >= 1.0,
    "narrative_gap": lambda row: (
        row["social_news_gap"] >= 2.0 and row["social_price_gap"] >= 1.5 and row["already_pumped_penalty"] < 0.4
    ),
    "narrative_gap_catalyst": lambda row: (
        row["social_news_gap"] >= 1.5
        and row["already_pumped_penalty"] < 0.35
        and (row["catalyst_quality"] >= 0.6 or row["filing_confirmed"])
    ),
}

SOCIAL_DEPENDENT = {"social_activity", "sentiment", "narrative_gap", "narrative_gap_catalyst"}
# Both gap rules read social_news_gap, so a dark news leg makes them unevaluable
# for the same reason a dark social leg does.
NEWS_DEPENDENT = {"narrative_gap", "narrative_gap_catalyst"}
PRICE_DEPENDENT = {"price_volume", "narrative_gap", "narrative_gap_catalyst"}


def _drawdown(returns: list[float]) -> float:
    if not returns:
        return 0.0
    equity = np.cumprod(1 + np.asarray(returns, dtype=float))
    peaks = np.maximum.accumulate(equity)
    return float(np.min(equity / peaks - 1.0))


def _bootstrap_ci(returns: list[float], samples: int, seed: int) -> tuple[float, float]:
    if len(returns) < 2:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    values = np.asarray(returns, dtype=float)
    means = [float(np.mean(rng.choice(values, len(values), replace=True))) for _ in range(samples)]
    return (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def forward_return(bars: list[Bar], signal_at: datetime, horizon_bars: int) -> float | None:
    """Return from the next tradeable open to the close `horizon_bars` later.

    Entry is deliberately the *next* bar's open. Filling at the close of the bar
    that produced the signal would be a look-ahead, and it is the single most
    common way a backtest like this lies.
    """
    entry_index = next((index for index, bar in enumerate(bars) if bar.at > signal_at), None)
    if entry_index is None:
        return None
    exit_index = entry_index + horizon_bars - 1
    if exit_index >= len(bars):
        return None
    entry = bars[entry_index].open
    if entry <= 0:
        return None
    return bars[exit_index].close / entry - 1.0


async def _load_price_history(tickers: set[str], lookback_days: int) -> dict[str, list[Bar]]:
    history: dict[str, list[Bar]] = {}
    for ticker in sorted(tickers):
        try:
            bars, _ = await market_source.fetch_bars(ticker, lookback_days=lookback_days)
            history[ticker] = bars
        except SourceError:
            history[ticker] = []
    return history


def _coverage(rows: list[dict[str, Any]]) -> list[SourceCoverage]:
    def summarize(source: str, column: str, mode: str, detail: str) -> SourceCoverage:
        observed = [row for row in rows if row.get(column) == "live"]
        return SourceCoverage(
            source=source,
            mode=mode if observed else "unavailable",  # type: ignore[arg-type]
            first_observation=_parse(observed[0]["as_of"]) if observed else None,
            last_observation=_parse(observed[-1]["as_of"]) if observed else None,
            observations=len(observed),
            detail=detail,
        )

    return [
        summarize(
            "reddit", "social_coverage", "forward_only",
            "No licensed deep history exists. Observations accrue from the moment live research runs.",
        ),
        summarize("news", "news_coverage", "historical", "GDELT absolute-window archive, real history."),
        summarize("price", "price_coverage", "historical", "Real daily bars from the configured provider."),
        summarize(
            "filings", "filing_coverage", "forward_only",
            "Official regulator or exchange timestamps captured by live research; no filing backfill yet.",
        ),
    ]


async def run_backtest(
    root: Path, *, locked: bool = False, config: BacktestConfig | None = None
) -> BacktestRun:
    """Evaluate the fixed rule set against the real point-in-time store.

    Outcomes are computed from real forward bars at run time rather than stored
    alongside the features, so an observation can never carry its own answer.
    """
    config = config or BacktestConfig()
    rows = read_snapshots(root)
    started = datetime.now(UTC)
    config_hash = hashlib.sha256(config.model_dump_json().encode()).hexdigest()

    coverage = _coverage(rows)
    if not rows:
        return BacktestRun(
            run_id=f"bt_{config_hash[:16]}",
            dataset_version="live-acquisition-v2",
            dataset_label="LIVE ACQUISITION — STORE EMPTY",
            configuration_hash=config_hash,
            code_version=CODE_VERSION,
            started_at=started,
            completed_at=datetime.now(UTC),
            locked_holdout=locked,
            status="completed",
            strategies=[],
            coverage=coverage,
            caveats=["The point-in-time store is empty. Run a backfill or some live research first."],
        )

    if not locked:
        split = int(len(rows) * (1 - config.holdout_fraction))
        rows = rows[: max(1, split)]

    span_days = max(90, (datetime.now(UTC) - _parse(rows[0]["as_of"])).days + 30)
    benchmarks = {benchmark_for(row.get("market")) for row in rows}
    history = await _load_price_history({row["ticker"] for row in rows} | benchmarks, span_days)
    horizon = HORIZON_BARS.get(config.primary_horizon, 1)
    cost = config.transaction_cost_bps_per_side * 2 / 10_000

    results: list[StrategyResult] = []
    social_rows = sum(1 for row in rows if row.get("social_coverage") == "live")

    for offset, (name, predicate) in enumerate(STRATEGIES.items()):
        returns: list[float] = []
        last_entry_by_ticker: dict[str, datetime] = {}
        for row in rows:
            if row.get("conflict"):
                continue
            if name in SOCIAL_DEPENDENT and row.get("social_coverage") != "live":
                continue
            if name in NEWS_DEPENDENT and row.get("news_coverage") != "live":
                continue
            if name in PRICE_DEPENDENT and row.get("price_coverage") != "live":
                continue
            try:
                if not predicate(row):
                    continue
            except (KeyError, TypeError):
                continue

            bars = history.get(row["ticker"], [])
            signal_at = _parse(row["as_of"])
            last_entry = last_entry_by_ticker.get(row["ticker"])
            if last_entry is not None and signal_at - last_entry < timedelta(
                hours=config.reentry_cooldown_hours
            ):
                continue
            raw = forward_return(bars, signal_at, horizon)
            if raw is None:
                continue
            benchmark = history.get(benchmark_for(row.get("market")), [])
            index_return = forward_return(benchmark, signal_at, horizon) if benchmark else 0.0
            returns.append(raw - (index_return or 0.0) - cost)
            last_entry_by_ticker[row["ticker"]] = signal_at

        wins = sum(value > 0 for value in returns)
        results.append(
            StrategyResult(
                strategy=name,
                signals=len(returns),
                win_rate=round(wins / len(returns), 4) if returns else 0.0,
                mean_excess_return=round(float(np.mean(returns)), 6) if returns else 0.0,
                confidence_interval=tuple(
                    round(value, 6) for value in _bootstrap_ci(returns, config.bootstrap_samples, config.seed + offset)
                ),
                total_return=round(float(np.prod(1 + np.asarray(returns)) - 1), 6) if returns else 0.0,
                max_drawdown=round(_drawdown(returns), 6),
                turnover=round(len(returns) / max(len(rows), 1), 6),
                false_positive_rate=round(sum(value <= 0 for value in returns) / len(returns), 4) if returns else 0.0,
            )
        )

    markets_present = {str(row.get("market") or "US") for row in rows}
    benchmark_labels = {
        "US": "S&P 500 (SPY)",
        "IN": "Nifty 50 (^NSEI)",
    }
    compared_to = " and ".join(
        benchmark_labels.get(market, benchmark_for(market)) for market in sorted(markets_present)
    )
    caveats = [
        f"Returns are excess of {compared_to} over the same window and net of round-trip costs.",
        "Entry is the next bar's open after the signal; no signal can fill on its own bar.",
        f"Repeated signals in the same security are suppressed for {config.reentry_cooldown_hours} hours.",
        f"The final {config.holdout_fraction:.0%} is held out unless the run is locked.",
    ]
    if social_rows == 0:
        caveats.append(
            "No observation in the store saw the social leg, so every social-dependent strategy "
            "reports zero signals. That is a coverage limit, not a result."
        )
    elif social_rows < 200:
        caveats.append(
            f"Only {social_rows} observations include the social leg. Treat social-dependent rows as "
            "indicative until the forward record is materially longer."
        )

    return BacktestRun(
        run_id=f"bt_{hashlib.sha256(f'{config_hash}{len(rows)}{locked}'.encode()).hexdigest()[:16]}",
        dataset_version="live-acquisition-v2",
        dataset_label="LIVE ACQUISITION — POINT-IN-TIME STORE",
        configuration_hash=config_hash,
        code_version=CODE_VERSION,
        started_at=started,
        completed_at=datetime.now(UTC),
        locked_holdout=locked,
        status="completed",
        strategies=results,
        coverage=coverage,
        caveats=caveats,
    )


def persist_backtest(root: Path, run: BacktestRun) -> Path:
    output = derived_dir(root) / "backtest.json"
    payload = json.loads(run.model_dump_json())
    payload["started_at"] = "reproducible-runtime-omitted"
    payload["completed_at"] = "reproducible-runtime-omitted"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output
