from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from ..config import settings
from .http import SourceError, request_json

ALPACA_BARS = "https://data.alpaca.markets/v2/stocks/bars"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass(frozen=True)
class Bar:
    at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _to_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _alpaca_bars(ticker: str, *, start: date, end: date, timeframe: str) -> list[Bar]:
    config = settings()
    payload = await request_json(
        "alpaca",
        ALPACA_BARS,
        params={
            "symbols": ticker,
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": "10000",
            "adjustment": "split",
            "feed": "iex",
            "sort": "asc",
        },
        headers={
            "APCA-API-KEY-ID": config.alpaca_key,
            "APCA-API-SECRET-KEY": config.alpaca_secret,
            "Accept": "application/json",
        },
    )
    series = (payload.get("bars") or {}).get(ticker) or []
    return [
        Bar(
            at=_to_utc(str(row["t"])),
            open=float(row["o"]),
            high=float(row["h"]),
            low=float(row["l"]),
            close=float(row["c"]),
            volume=float(row["v"]),
        )
        for row in series
    ]


def _yahoo_range(lookback_days: int) -> str:
    for days, label in ((30, "1mo"), (90, "3mo"), (180, "6mo"), (365, "1y"), (730, "2y"), (1825, "5y")):
        if lookback_days <= days:
            return label
    return "10y"


async def _yahoo_bars(ticker: str, *, start: date, end: date, lookback_days: int) -> list[Bar]:
    """Keyless daily fallback. End-of-day only, so intraday features degrade."""
    payload = await request_json(
        "yahoo",
        YAHOO_CHART.format(symbol=ticker),
        params={"range": _yahoo_range(lookback_days), "interval": "1d"},
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; ape-alpha/0.2)"},
    )
    results = ((payload or {}).get("chart") or {}).get("result") or []
    if not results:
        raise SourceError("yahoo", f"no chart series for {ticker}")

    series = results[0]
    stamps = series.get("timestamp") or []
    quote = ((series.get("indicators") or {}).get("quote") or [{}])[0]
    opens, highs = quote.get("open") or [], quote.get("high") or []
    lows, closes, volumes = quote.get("low") or [], quote.get("close") or [], quote.get("volume") or []

    bars: list[Bar] = []
    for index, stamp in enumerate(stamps):
        try:
            # Yahoo pads gaps with nulls; a bar missing any leg is unusable.
            values = (opens[index], highs[index], lows[index], closes[index], volumes[index])
            if any(value is None for value in values):
                continue
            at = datetime.fromtimestamp(float(stamp), tz=UTC)
            if not start <= at.date() <= end:
                continue
            bars.append(
                Bar(
                    at=at,
                    open=float(values[0]),
                    high=float(values[1]),
                    low=float(values[2]),
                    close=float(values[3]),
                    volume=float(values[4]),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    if not bars:
        raise SourceError("yahoo", f"no usable bars in range for {ticker}")
    return sorted(bars, key=lambda bar: bar.at)


async def fetch_bars(
    ticker: str,
    *,
    lookback_days: int = 180,
    end: date | None = None,
    timeframe: str = "1Day",
) -> tuple[list[Bar], str]:
    """Daily bars plus the provider that answered.

    Alpaca is preferred because it supports intraday timeframes and a real
    as-of window. Yahoo's chart endpoint covers the keyless case at daily
    resolution. The provider name is returned so source health can state which
    one actually answered.
    """
    config = settings()
    end_date = end or datetime.now(UTC).date()
    start_date = end_date - timedelta(days=lookback_days)

    if config.alpaca_enabled:
        try:
            # Alpaca treats a date-only end as midnight. Advancing one day on a
            # live query includes today's in-progress IEX bars; historical calls
            # with an explicit end retain their exact point-in-time boundary.
            alpaca_end = end_date if end is not None else end_date + timedelta(days=1)
            bars = await _alpaca_bars(ticker, start=start_date, end=alpaca_end, timeframe=timeframe)
            if bars:
                return bars, "alpaca"
        except SourceError:
            # Fall through to the keyless provider rather than failing the run.
            pass

    bars = await _yahoo_bars(ticker, start=start_date, end=end_date, lookback_days=lookback_days)
    return bars, "yahoo"
