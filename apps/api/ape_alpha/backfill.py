from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .contracts import NarrativePhase, SignalFeatures
from .markets import Market
from .research.resolve import resolve
from .signals import SIGNAL_VERSION, already_pumped_penalty, robust_zscore
from .sources import market as market_source
from .sources import news as news_source
from .sources.http import SourceError
from .sources.market import Bar
from .store import append_snapshots, backfill_row

DATASET_VERSION = "live-acquisition-v2"

# Enough prior observations for a robust z-score to mean anything.
MIN_HISTORY = 40


def _bars_by_day(bars: list[Bar]) -> dict[Any, Bar]:
    return {bar.at.date(): bar for bar in bars}


def _historical_features(
    *,
    bars: list[Bar],
    index: int,
    news_values: list[float],
    news_index: int | None,
) -> SignalFeatures:
    """Reconstruct a feature vector as it would have looked on one past day.

    Only observations strictly before the evaluation point are used, so the row
    cannot see its own outcome. The social block is zeroed rather than guessed:
    there is no licensed Reddit history to reconstruct it from.
    """
    window = bars[: index + 1]
    returns = [
        window[step].close / window[step - 1].close - 1.0
        for step in range(1, len(window))
        if window[step - 1].close > 0
    ]
    latest_return = returns[-1] if returns else 0.0
    market_z = robust_zscore(latest_return, returns[-61:-1]) if len(returns) >= 6 else 0.0

    volumes = [bar.volume for bar in window[-21:-1] if bar.volume > 0]
    median_volume = sorted(volumes)[len(volumes) // 2] if volumes else 0.0
    relative_volume = window[-1].volume / median_volume if median_volume > 0 else 1.0

    trailing = window[-6:-1]
    pre_signal = (trailing[-1].close / trailing[0].close - 1.0) if len(trailing) >= 2 and trailing[0].close > 0 else 0.0

    news_z = 0.0
    if news_index is not None:
        news_history = news_values[max(0, news_index - 60) : news_index]
        if len(news_history) >= 5:
            news_z = robust_zscore(news_values[news_index], news_history)

    return SignalFeatures(
        social_count=0,
        unique_authors=0,
        social_acceleration=0.0,
        social_z=0.0,
        dd_density=0.0,
        bull_ratio=0.5,
        news_count=0,
        news_z=round(news_z, 4),
        catalyst_quality=0.0,
        novelty=0.0,
        filing_confirmed=False,
        market_z=round(market_z, 4),
        relative_volume=round(max(0.0, relative_volume), 4),
        abnormal_return_recent=round(latest_return, 6),
        price_resolution="1Day",
        pre_signal_return=round(pre_signal, 6),
        social_news_gap=round(0.0 - news_z, 4),
        social_price_gap=round(0.0 - market_z, 4),
        news_price_gap=round(news_z - market_z, 4),
        already_pumped_penalty=round(already_pumped_penalty(pre_signal, market_z), 4),
    )


async def backfill_ticker(
    root: Path, query: str, *, market: Market | str = Market.US, lookback_days: int = 365
) -> dict[str, Any]:
    """Reconstruct real historical observations for one security.

    News volume comes from GDELT's absolute-window archive and price from real
    bars. Both legs are genuine history. The social leg is left explicitly dark,
    which is the honest representation of what is obtainable.
    """
    candidates = await resolve(query, market=market)
    if not candidates:
        raise LookupError(f"Could not resolve {query!r}")
    best = candidates[0]

    end = datetime.now(UTC)
    start = end - timedelta(days=lookback_days)

    bars, provider = await market_source.fetch_bars(best.ticker, lookback_days=lookback_days + 90)
    if len(bars) < MIN_HISTORY + 10:
        raise SourceError("price", f"only {len(bars)} bars available for {best.ticker}")

    try:
        timeline = await news_source.fetch_volume_timeline(
            best.display_symbol, best.company, start=start, end=end
        )
    except SourceError:
        timeline = []

    news_by_day = {stamp.date(): value for stamp, value in timeline}
    news_days = sorted(news_by_day)
    news_values = [news_by_day[day] for day in news_days]
    news_position = {day: index for index, day in enumerate(news_days)}

    rows: list[dict[str, Any]] = []
    for index in range(MIN_HISTORY, len(bars)):
        bar = bars[index]
        day = bar.at.date()
        if day < start.date():
            continue
        news_index = news_position.get(day)
        # A day with no news baseline still yields a valid price observation.
        # It is recorded with the news leg flagged unavailable so news-dependent
        # rules skip it, instead of a zeroed news_z masquerading as "no coverage".
        news_measured = news_index is not None and news_index >= 5
        features = _historical_features(
            bars=bars,
            index=index,
            news_values=news_values,
            news_index=news_index if news_measured else None,
        )
        rows.append(
            backfill_row(
                ticker=best.ticker,
                market=best.market.value,
                company=best.company,
                as_of=bar.at,
                features=features,
                # A backfill cannot see licensed historical Reddit data. Any
                # social lead/lag phase would therefore be a claim about an
                # unmeasured zero rather than a measured crowd.
                phase=NarrativePhase.INDETERMINATE.value,
                price_provider=provider,
                signal_version=SIGNAL_VERSION,
                dataset_version=DATASET_VERSION,
                news_measured=news_measured,
            )
        )

    added = append_snapshots(root, rows)
    return {
        "ticker": best.ticker,
        "market": best.market.value,
        "company": best.company,
        "candidate_rows": len(rows),
        "added": added,
        "price_provider": provider,
        "news_days": len(news_days),
        "social": "unavailable — no licensed Reddit history",
    }
