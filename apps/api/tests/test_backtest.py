from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ape_alpha import backtest as backtest_module
from ape_alpha import backfill as backfill_module
from ape_alpha.backfill import backfill_ticker
from ape_alpha.backtest import forward_return, persist_backtest, run_backtest
from ape_alpha.contracts import BacktestConfig
from ape_alpha.markets import Market
from ape_alpha.research.resolve import Resolution
from ape_alpha.sources.market import Bar
from ape_alpha.store import COLUMNS, append_snapshots, read_snapshots

START = datetime(2026, 1, 5, 20, 0, tzinfo=UTC)


def synthetic_bars(count: int, *, drift: float = 0.01) -> list[Bar]:
    """Bars where each session opens at the prior close and drifts to its own.

    Open and close must differ, otherwise an open-to-close fill returns zero and
    the fixture cannot detect whether entry timing is being honoured at all.
    """
    bars = []
    price = 100.0
    for index in range(count):
        open_price = price
        price = open_price * (1 + drift)
        bars.append(
            Bar(
                at=START + timedelta(days=index),
                open=open_price,
                high=max(open_price, price) * 1.01,
                low=min(open_price, price) * 0.99,
                close=price,
                volume=1_000_000.0,
            )
        )
    return bars


def snapshot_row(index: int, **overrides: Any) -> dict[str, Any]:
    row = {column: 0 for column in COLUMNS}
    row.update(
        {
            "snapshot_id": f"test_{index}",
            "ticker": "TEST",
            "market": "US",
            "company": "Test Corp",
            "as_of": (START + timedelta(days=index)).isoformat(),
            "origin": "live",
            "phase": "CONFIRMED",
            "action": "PAPER_BUY",
            "conflict": False,
            "confidence": 0.7,
            "social_coverage": "live",
            "news_coverage": "live",
            "price_coverage": "live",
            "filing_coverage": "live",
            "price_provider": "test",
            "signal_version": "narrative-gap-v2",
            "dataset_version": "test",
            "social_z": 3.5,
            "unique_authors": 8,
            "bull_ratio": 0.8,
            "social_news_gap": 2.5,
            "social_price_gap": 2.0,
            "already_pumped_penalty": 0.1,
            "catalyst_quality": 0.7,
            "filing_confirmed": True,
            "market_z": 2.5,
            "relative_volume": 2.0,
            "price_resolution": "1Day",
        }
    )
    row.update(overrides)
    return row


@pytest.fixture
def priced(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(ticker: str, **_: Any) -> tuple[list[Bar], str]:
        # A flat benchmark isolates the strategy return from market drift.
        return (
            synthetic_bars(60, drift=0.0 if ticker in {"SPY", "^NSEI"} else 0.01),
            "test",
        )

    monkeypatch.setattr(backtest_module.market_source, "fetch_bars", fake_fetch)


def test_entry_is_the_next_bar_never_the_signal_bar() -> None:
    bars = synthetic_bars(10, drift=0.10)
    signal_at = bars[3].at
    # Entry must be bars[4].open, so the 1-bar return is bars[4].close/bars[4].open.
    assert forward_return(bars, signal_at, 1) == pytest.approx(bars[4].close / bars[4].open - 1)


def test_forward_return_is_none_past_the_end_of_the_tape() -> None:
    bars = synthetic_bars(5)
    assert forward_return(bars, bars[-1].at, 1) is None
    assert forward_return(bars, bars[0].at, 99) is None


def test_empty_store_reports_honestly_instead_of_inventing_results(tmp_path: Path) -> None:
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    assert run.strategies == []
    assert "empty" in run.dataset_label.lower()
    assert all(item.mode == "unavailable" for item in run.coverage)


def test_backtest_scores_real_forward_returns(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index) for index in range(5, 25)])
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    gap = next(item for item in run.strategies if item.strategy == "narrative_gap")
    assert gap.signals > 0
    # 1% daily drift against a flat benchmark, less 20bps of cost.
    assert gap.mean_excess_return == pytest.approx(0.01 - 0.002, abs=1e-3)


def test_social_dependent_strategies_are_skipped_when_the_leg_was_dark(tmp_path: Path, priced: None) -> None:
    rows = [snapshot_row(index, social_coverage="unavailable", origin="backfill") for index in range(5, 25)]
    append_snapshots(tmp_path, rows)
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    social = next(item for item in run.strategies if item.strategy == "narrative_gap")
    price = next(item for item in run.strategies if item.strategy == "price_volume")
    assert social.signals == 0
    assert price.signals > 0
    assert any("social leg" in caveat for caveat in run.caveats)


def test_conflicted_observations_never_reach_a_strategy(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index, conflict=True) for index in range(5, 25)])
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    assert all(item.signals == 0 for item in run.strategies)


def test_price_dependent_strategies_skip_rows_where_price_was_dark(
    tmp_path: Path, priced: None
) -> None:
    rows = [snapshot_row(index, price_coverage="unavailable") for index in range(5, 25)]
    append_snapshots(tmp_path, rows)
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    assert next(item for item in run.strategies if item.strategy == "price_volume").signals == 0
    assert next(item for item in run.strategies if item.strategy == "narrative_gap").signals == 0


def test_reentry_cooldown_suppresses_repeated_daily_signals(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index) for index in range(5, 25)])
    no_cooldown = asyncio.run(
        run_backtest(tmp_path, locked=True, config=BacktestConfig(reentry_cooldown_hours=0))
    )
    cooled = asyncio.run(
        run_backtest(tmp_path, locked=True, config=BacktestConfig(reentry_cooldown_hours=48))
    )
    raw_signals = next(item for item in no_cooldown.strategies if item.strategy == "price_volume").signals
    cooled_signals = next(item for item in cooled.strategies if item.strategy == "price_volume").signals
    assert 0 < cooled_signals < raw_signals


def test_costs_are_charged_on_both_sides(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index) for index in range(5, 25)])
    free = asyncio.run(run_backtest(tmp_path, locked=True))
    costly = asyncio.run(
        run_backtest(tmp_path, locked=True, config=BacktestConfig(transaction_cost_bps_per_side=50))
    )
    assert all(
        expensive.mean_excess_return <= cheap.mean_excess_return
        for cheap, expensive in zip(free.strategies, costly.strategies, strict=True)
    )


def test_holdout_is_excluded_unless_the_run_is_locked(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index) for index in range(5, 25)])
    development = asyncio.run(run_backtest(tmp_path, locked=False))
    locked = asyncio.run(run_backtest(tmp_path, locked=True))
    assert development.locked_holdout is False
    assert sum(item.signals for item in locked.strategies) > sum(item.signals for item in development.strategies)


def test_store_is_append_only_and_deduplicates(tmp_path: Path) -> None:
    rows = [snapshot_row(index) for index in range(5, 10)]
    assert append_snapshots(tmp_path, rows) == 5
    assert append_snapshots(tmp_path, rows) == 0
    assert len(read_snapshots(tmp_path)) == 5


def test_persisted_run_is_byte_stable(tmp_path: Path, priced: None) -> None:
    append_snapshots(tmp_path, [snapshot_row(index) for index in range(5, 25)])
    first = persist_backtest(tmp_path, asyncio.run(run_backtest(tmp_path, locked=True))).read_bytes()
    second = persist_backtest(tmp_path, asyncio.run(run_backtest(tmp_path, locked=True))).read_bytes()
    assert first == second


def test_mixed_market_run_names_both_benchmarks(tmp_path: Path, priced: None) -> None:
    rows = [snapshot_row(index) for index in range(5, 15)]
    rows.extend(
        snapshot_row(index + 20, ticker="TEST.NS", market="IN") for index in range(5, 15)
    )
    append_snapshots(tmp_path, rows)
    run = asyncio.run(run_backtest(tmp_path, locked=True))
    assert any("S&P 500 (SPY)" in caveat and "Nifty 50 (^NSEI)" in caveat for caveat in run.caveats)


def test_backfill_never_assigns_a_social_phase_without_social_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution = Resolution(
        ticker="TEST",
        display_symbol="TEST",
        company="Test Corp",
        cik=1,
        market=Market.US,
        confidence=1.0,
        matched_on="symbol",
    )

    async def fake_resolve(*_: Any, **__: Any) -> list[Resolution]:
        return [resolution]

    async def fake_fetch_bars(*_: Any, **__: Any) -> tuple[list[Bar], str]:
        return synthetic_bars(100), "test"

    async def fake_news(*_: Any, **__: Any) -> list[tuple[datetime, float]]:
        return []

    monkeypatch.setattr(backfill_module, "resolve", fake_resolve)
    monkeypatch.setattr(backfill_module.market_source, "fetch_bars", fake_fetch_bars)
    monkeypatch.setattr(backfill_module.news_source, "fetch_volume_timeline", fake_news)

    asyncio.run(backfill_ticker(tmp_path, "TEST", lookback_days=365))
    rows = read_snapshots(tmp_path)
    assert rows
    assert {row["phase"] for row in rows} == {"INDETERMINATE"}
    assert {row["social_coverage"] for row in rows} == {"unavailable"}
    assert {row["action"] for row in rows} == {"WATCH"}
    assert {row["confidence"] for row in rows} == {0.0}


def test_legacy_dark_social_rows_are_normalized_on_read(tmp_path: Path) -> None:
    append_snapshots(
        tmp_path,
        [
            snapshot_row(
                5,
                social_coverage="unavailable",
                phase="WHISPER",
                action="WATCH",
                conflict=True,
                confidence=0.88,
            )
        ],
    )
    row = read_snapshots(tmp_path)[0]
    assert row["phase"] == "INDETERMINATE"
    assert row["action"] == "WATCH"
    assert row["conflict"] is False
    assert row["confidence"] == 0.0
