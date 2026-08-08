from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Market(str, Enum):
    US = "US"
    IN = "IN"


@dataclass(frozen=True)
class MarketProfile:
    """Everything that differs between listing venues.

    Keeping this in one place is what stops market-specific assumptions — a US
    benchmark, a US regulator, English-language subreddits — from leaking into
    the scoring code.
    """

    market: Market
    label: str
    currency: str
    benchmark: str
    benchmark_label: str
    # Yahoo suffixes for the venue, primary first. Empty means bare US symbols.
    suffixes: tuple[str, ...]
    # Google News locale triple: hl (language), gl (country), ceid.
    news_locale: tuple[str, str, str]
    subreddits: tuple[str, ...]
    filing_source: str
    filing_label: str


US = MarketProfile(
    market=Market.US,
    label="United States",
    currency="USD",
    benchmark="SPY",
    benchmark_label="S&P 500 (SPY)",
    suffixes=(),
    news_locale=("en-US", "US", "US:en"),
    subreddits=(
        "wallstreetbets",
        "stocks",
        "investing",
        "StockMarket",
        "options",
        "pennystocks",
        "smallstreetbets",
        "SecurityAnalysis",
        "ValueInvesting",
    ),
    filing_source="sec",
    filing_label="SEC EDGAR",
)

INDIA = MarketProfile(
    market=Market.IN,
    label="India",
    currency="INR",
    benchmark="^NSEI",
    benchmark_label="Nifty 50",
    suffixes=(".NS", ".BO"),
    news_locale=("en-IN", "IN", "IN:en"),
    subreddits=(
        "IndianStreetBets",
        "IndiaInvestments",
        "DalalStreetTalks",
        "StockMarketIndia",
        "IndianStockMarket",
    ),
    filing_source="nse",
    filing_label="NSE announcements",
)

PROFILES: dict[Market, MarketProfile] = {Market.US: US, Market.IN: INDIA}


def profile(market: Market | str) -> MarketProfile:
    return PROFILES[Market(market)]


def base_symbol(symbol: str) -> str:
    """Strip a venue suffix so the bare ticker can be shown and searched."""
    for suffix in (".NS", ".BO"):
        if symbol.upper().endswith(suffix):
            return symbol[: -len(suffix)]
    return symbol
